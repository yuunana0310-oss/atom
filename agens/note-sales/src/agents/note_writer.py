"""
note_writer エージェント

承認済み TopicCandidate から NoteDraft（Markdown）を生成する。

生成フロー:
  1. 承認済み TopicCandidate を取得
  2. 関連 PainPoint を取得
  3. テンプレートベースで free_part + paid_part を生成
  4. NoteDraft として SQLite + JSON に保存
  5. Markdown ファイルを data/processed/drafts/ に出力

設計方針:
- テンプレートベース実装（[FUTURE_LLM] マークで Claude API 置き換え可能）
- free_part と paid_part を明確に分離
- price は TopicCandidate.recommended_price_range の下限値を使用
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.adapters.storage_json import (
    load_note_drafts,
    load_topic_candidates,
    read_json,
    save_note_drafts_append,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import ArticleStatus, NoteDraft, PainPoint, TopicCandidate
from src.core.settings import AppSettings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# テンプレート定数（アングル別）
# ---------------------------------------------------------------------------

# アングル別：なぜ解決できないのか
_WHY_NOT_SOLVED: dict[str, str] = {
    "体験談＋本音レポート": (
        "多くの解説記事は「使い方」を教えてくれますが、"
        "「実際に使ってみてどうだったか」という本音の情報が少ないのが現実です。\n"
        "成功体験だけでなく、失敗した場面や「ここで詰まった」という情報こそが、"
        "同じ立場の人には一番参考になります。"
    ),
    "ステップバイステップガイド": (
        "多くの解説は途中から前提知識が必要になり、初心者が置いていかれます。\n"
        "実際には、最初のセットアップさえ乗り越えれば、"
        "あとは思ったよりシンプルに進めることができます。"
    ),
    "失敗談＋解決策": (
        "失敗した経験を公開している情報は少なく、成功事例ばかりが目に入ります。\n"
        "しかし実際には、最初から上手くいく人はほとんどいません。"
        "失敗のパターンを知ることが、最短で成果を出す近道になります。"
    ),
    "比較レポート": (
        "ツールの比較記事はあっても、実際に両方を使い込んだ上での比較は少ないです。\n"
        "スペック比較ではなく、実際の使用感と自分のユースケースへの適合度が"
        "判断に必要な情報です。"
    ),
    "収益公開＋実践法": (
        "収益を公開している人の情報は断片的で、再現性がわかりにくいことが多いです。\n"
        "「いくら稼いだか」だけでなく「どうやって稼いだか」という手順が、"
        "同じ成果を出すために本当に必要な情報です。"
    ),
}

# アングル別：無料パートの本文（価値提供セクション）
_FREE_BODY: dict[str, str] = {
    "体験談＋本音レポート": (
        "最初の{period}を振り返ると、大きく3つのフェーズがありました。\n\n"
        "**第1フェーズ（最初の数日）**: 何もわからず試行錯誤\n"
        "**第2フェーズ（1週間後）**: 少しずつコツを掴む\n"
        "**第3フェーズ（{period}後）**: 自分なりの使い方が確立\n\n"
        "有料パートでは、この3フェーズの具体的な内容と、"
        "実際に使ったプロンプトや手順を公開します。"
    ),
    "ステップバイステップガイド": (
        "この記事の手順は全部で5ステップです。順番通りに進めれば必ずできます。\n\n"
        "ステップ1〜3の概要をここで紹介します。\n\n"
        "**ステップ1**: 環境の確認（5分）\n"
        "**ステップ2**: 初期設定（15〜30分）\n"
        "**ステップ3**: 最初のタスクを実行（10分）\n\n"
        "有料パートでは、ステップ4・5と、"
        "各ステップの詰まりやすいポイントの解決策を解説します。"
    ),
    "失敗談＋解決策": (
        "私が実際に犯した失敗は3つあります。\n\n"
        "**失敗1**: 最初から難しいことをやろうとした\n"
        "**失敗2**: 指示が曖昧すぎた\n"
        "**失敗3**: エラーが出たときに諦めてしまった\n\n"
        "有料パートでは、各失敗からの具体的な立て直し方と、"
        "同じ失敗を避けるための事前チェックリストを公開します。"
    ),
    "比較レポート": (
        "今回比較したのは、実際に1ヶ月間使い込んだ結果です。\n\n"
        "無料パートでは、比較の結論だけお伝えします。\n\n"
        "**速度**: 互角\n"
        "**使いやすさ**: 用途による\n"
        "**コスト**: 月額プランで3倍の差\n\n"
        "有料パートでは、実際のスクリーンショットと"
        "ユースケース別のおすすめを詳しく解説します。"
    ),
    "収益公開＋実践法": (
        "結論から言うと、最初の{period}で月{revenue}円の収益を出しました。\n\n"
        "「どうせ特別なスキルがあるから」と思うかもしれませんが、"
        "私は{audience_type}です。\n\n"
        "有料パートでは、月{revenue}円を達成した具体的な手順と、"
        "実際に使ったプロンプト・ツールを全て公開します。"
    ),
}

# アングル別：有料パートのステップタイトルと内容ひな型
_STEPS: dict[str, list[tuple[str, str]]] = {
    "体験談＋本音レポート": [
        (
            "実際に使ったプロンプト集（所要時間: 読むだけ）",
            "最初の1週間で一番効果があったプロンプトを5つ公開します。\n"
            "コピーして使えるように、そのまま貼り付け可能な形式で記載しています。\n\n"
            "1. タスク整理プロンプト: 「以下のタスクを優先度順に整理してください。[タスク内容]」\n"
            "2. 文章改善プロンプト: 「以下の文章をもっと自然な日本語に修正してください。[文章]」\n"
            "3. 要約プロンプト: 「以下の内容を3行で要約してください。[内容]」",
        ),
        (
            "詰まった場面と抜け出し方（所要時間: 10分）",
            "一番多い詰まりパターンは「指示が漠然としすぎる」ことです。\n\n"
            "**NG例**: 「記事を書いて」\n"
            "**OK例**: 「AIを使って副業収入を増やしたい30代会社員向けに、"
            "500字程度の記事を書いてください。専門用語は使わずに」\n\n"
            "具体的な条件（対象者・文字数・トーン）を指定するだけで、"
            "出力の質が大きく変わります。",
        ),
        (
            "継続のコツと次のステップ（所要時間: 5分）",
            "2週間続けた結果、一番効果があったのは「毎日1つだけ試す」という習慣でした。\n\n"
            "次のステップとして、以下の順番で試してみてください。\n\n"
            "1. 日常業務の小さなタスクに使う（1日目〜7日目）\n"
            "2. 複数の指示をつなげる（8日目〜14日目）\n"
            "3. 自分専用のプロンプトをカスタマイズする（15日目以降）",
        ),
    ],
    "ステップバイステップガイド": [
        (
            "ステップ4: 自分のユースケースに合わせる（所要時間: 20分）",
            "最初の3ステップをクリアしたら、次は自分の仕事や用途に合わせて設定をカスタマイズします。\n\n"
            "具体的には以下の設定を調整してください：\n\n"
            "1. 使用言語を日本語に設定: 最初のプロンプトに「日本語で回答してください」を追加\n"
            "2. 回答の詳細度を指定: 「詳しく」「簡潔に」などを明示\n"
            "3. 出力形式を指定: 「箇条書きで」「表形式で」など",
        ),
        (
            "ステップ5: つまずきポイントQ&A（所要時間: 読むだけ）",
            "実際に使い始めた人からよくある質問をまとめました。\n\n"
            "**Q: 回答が英語になってしまう**\n"
            "A: プロンプトの先頭に「日本語で」と追加してください。\n\n"
            "**Q: 指示通りの結果にならない**\n"
            "A: 指示をより具体的にしてください。対象者・文字数・目的を明示するのが効果的です。\n\n"
            "**Q: 同じ質問を繰り返している気がする**\n"
            "A: よく使うプロンプトをメモ帳に保存して再利用すると効率的です。",
        ),
        (
            "完全ロードマップ（1ヶ月間の使い方計画）",
            "1ヶ月でものにするための週次スケジュールです。\n\n"
            "**1週目**: 基本操作に慣れる（1日1タスク）\n"
            "**2週目**: 仕事の小さなタスクに活用する\n"
            "**3週目**: 複雑なタスクに挑戦する\n"
            "**4週目**: 自分専用のプロンプトテンプレートを作る\n\n"
            "毎日30分続けることで、1ヶ月後には仕事の効率が変わります。",
        ),
    ],
    "失敗談＋解決策": [
        (
            "失敗1の詳細と解決策（所要時間: 5分）",
            "最初の失敗は「難しいことからやろうとした」ことです。\n\n"
            "最初から完璧な成果物を求めると、必ず壁にぶつかります。\n\n"
            "**解決策**: 最初の1週間は「こなせるかどうか」ではなく「慣れること」を目標にする。\n"
            "具体的には、失敗してもいい小さなタスクから始めることです。\n\n"
            "実際に私が最初にやったタスク：メールの返信文を作成させる（5分のタスク）",
        ),
        (
            "失敗2の詳細と解決策（所要時間: 5分）",
            "2番目の失敗は「指示が曖昧だった」ことです。\n\n"
            "「もっと良くして」という指示では、何を改善すればいいかAIには分かりません。\n\n"
            "**解決策**: 5W1Hを意識した指示を出す。\n\n"
            "NGパターン: 「この文章を改善して」\n"
            "OKパターン: 「この文章を、30代会社員向けに、"
            "親しみやすい口調で、200字以内に改善してください」",
        ),
        (
            "失敗3の詳細と「諦めない」ための事前チェックリスト（所要時間: 3分）",
            "3番目の失敗は「エラーが出たときに諦めた」ことです。\n\n"
            "エラーが出たとき、まず確認すべきことリスト：\n\n"
            "□ インターネット接続は正常か\n"
            "□ 指示に禁止されているワードが含まれていないか\n"
            "□ 一度に多くのことを頼みすぎていないか（1回の指示は1タスクが基本）\n"
            "□ 前の会話の流れが複雑になっていないか（新しいチャットを開く）\n\n"
            "このチェックリストで9割のエラーは解決します。",
        ),
    ],
    "比較レポート": [
        (
            "比較項目1: 基本性能と速度（所要時間: 読むだけ）",
            "実際に同じタスクを両方に依頼して計測しました。\n\n"
            "| 項目 | ツールA | ツールB |\n"
            "|------|---------|----------|\n"
            "| 回答速度 | 約3秒 | 約5秒 |\n"
            "| 日本語精度 | ★★★★☆ | ★★★☆☆ |\n"
            "| 長文対応 | ○ | △ |\n\n"
            "速度ではツールA、日本語の自然さもツールAが優れていました。",
        ),
        (
            "比較項目2: コストと継続性（所要時間: 読むだけ）",
            "月額料金の比較です。\n\n"
            "| プラン | ツールA | ツールB |\n"
            "|--------|---------|----------|\n"
            "| 無料プラン | 月20回 | 月50回 |\n"
            "| 有料プラン | 月2,000円 | 月6,000円 |\n\n"
            "コストパフォーマンスはツールAが大幅に優れています。\n"
            "月50回以下の利用なら、ツールBの無料プランで十分です。",
        ),
        (
            "ユースケース別おすすめと最終結論（所要時間: 読むだけ）",
            "どちらを選ぶべきかは、用途によって異なります。\n\n"
            "**文章作成メインの副業**: ツールA推奨\n"
            "→ 日本語精度が高く、長文も得意\n\n"
            "**データ分析や表計算**: ツールB推奨\n"
            "→ 表形式の出力が得意で精度が高い\n\n"
            "**最初の1本**: ツールA推奨\n"
            "→ 日本語サポートが充実しており、初心者でも使いやすい",
        ),
    ],
    "収益公開＋実践法": [
        (
            "収益の内訳公開（所要時間: 読むだけ）",
            "最初の3ヶ月の月別収益と収益源の内訳です。\n\n"
            "| 月 | noteの収益 | その他 | 合計 |\n"
            "|----|-----------|--------|------|\n"
            "| 1ヶ月目 | 3,000円 | 0円 | 3,000円 |\n"
            "| 2ヶ月目 | 12,000円 | 5,000円 | 17,000円 |\n"
            "| 3ヶ月目 | 28,000円 | 15,000円 | 43,000円 |\n\n"
            "1ヶ月目はほぼゼロですが、コンテンツが増えるにつれ複利的に伸びます。",
        ),
        (
            "収益を作った具体的な手順（所要時間: 15分）",
            "月3万円を達成するまでの具体的なステップです。\n\n"
            "**ステップ1**: 自分の得意領域を1つ決める（1日）\n"
            "**ステップ2**: 無料記事を3本投稿してフォロワーを集める（2週間）\n"
            "**ステップ3**: 最も読まれた無料記事をベースに有料記事を書く（3日）\n"
            "**ステップ4**: ThreadsとnoteのURL連携で流入を増やす（1週間）\n"
            "**ステップ5**: データを見て改善を繰り返す（継続）",
        ),
        (
            "実際に使ったプロンプトと設定（所要時間: 読むだけ）",
            "記事生成に使ったプロンプトをそのまま公開します。\n\n"
            "**記事構成生成プロンプト:**\n"
            "```\n"
            "あなたはnoteで有料記事を販売するプロです。\n"
            "[ターゲット読者]向けに、[テーマ]についての記事構成を作ってください。\n"
            "有料部分には具体的な手順や実践ノウハウを含めてください。\n"
            "```\n\n"
            "このプロンプトで記事の骨格が5分で完成します。",
        ),
    ],
}

# アングル別：購入対象者
_FOR_WHO: dict[str, list[str]] = {
    "体験談＋本音レポート": [
        "同じ状況の人の実体験が知りたい方",
        "失敗パターンを事前に知って無駄を省きたい方",
        "成功事例だけでなく「本音」の情報を求めている方",
    ],
    "ステップバイステップガイド": [
        "手順通りに進めれば確実にできると確信したい方",
        "詰まったときの解決策が知りたい方",
        "1ヶ月以内に使えるようになりたい方",
    ],
    "失敗談＋解決策": [
        "同じ失敗を繰り返したくない方",
        "なぜうまくいかないのかを理解したい方",
        "効率よく成果を出したい方",
    ],
    "比較レポート": [
        "複数のツールを試す時間を節約したい方",
        "自分のユースケースに合ったツールを選びたい方",
        "実際の使用感ベースの情報がほしい方",
    ],
    "収益公開＋実践法": [
        "AIを使って副業収入を作りたい方",
        "具体的な数字と再現できる手順がほしい方",
        "3ヶ月以内に成果を出したい方",
    ],
}

# アングル別：非購入対象者
_NOT_FOR_WHO: dict[str, list[str]] = {
    "体験談＋本音レポート": [
        "すでに使いこなしている上級者の方（新しい情報は少ないです）",
        "理論的な解説を求めている方（実体験ベースの内容です）",
    ],
    "ステップバイステップガイド": [
        "すでに基本的な操作ができる方",
        "自分でドキュメントを読んで学ぶのが得意な方",
    ],
    "失敗談＋解決策": [
        "すでに成果が出ている方（失敗からの回復が中心です）",
        "最初から完璧な手順を求めている方",
    ],
    "比較レポート": [
        "すでにどちらかのツールを深く使い込んでいる方",
        "スペック比較表だけが目的の方（主観的な使用感が中心です）",
    ],
    "収益公開＋実践法": [
        "すでに月10万円以上の副業収入がある方（初〜中級者向けの内容です）",
        "AIツールを使わずに稼ぐ方法を探している方",
    ],
}

# アングル別：まとめ文
_CONCLUSION: dict[str, str] = {
    "体験談＋本音レポート": (
        "{tool}は、使い方さえ分かれば誰でも実践できるツールです。\n"
        "大切なのは、最初から完璧を目指さず、"
        "小さな成功を積み重ねていくことです。\n\n"
        "この記事が、{audience_type}の方の最初の一歩を後押しできれば嬉しいです。"
    ),
    "ステップバイステップガイド": (
        "5つのステップを順番に進めれば、必ず使えるようになります。\n"
        "焦らず、1日1ステップのペースで進めてみてください。\n\n"
        "1ヶ月後には、{audience_type}でも{tool}を自分の仕事に活用できるはずです。"
    ),
    "失敗談＋解決策": (
        "失敗は誰でもします。大切なのは同じ失敗を繰り返さないことです。\n"
        "この記事の失敗パターンと解決策が、"
        "あなたの時間と労力を節約する参考になれば幸いです。\n\n"
        "まず1つだけ、今日から実践してみてください。"
    ),
    "比較レポート": (
        "ツール選びに正解はありません。大切なのは自分のユースケースに合ったものを選ぶことです。\n"
        "この記事の比較データが、あなたに合ったツール選びの参考になれば幸いです。\n\n"
        "迷ったときは、まず無料プランで試してみることをおすすめします。"
    ),
    "収益公開＋実践法": (
        "最初の3ヶ月は誰でも苦しいですが、コンテンツが積み重なると複利的に伸びます。\n"
        "大切なのは継続することと、データを見て改善し続けることです。\n\n"
        "この記事の手順通りに進めれば、{audience_type}でも再現できます。"
    ),
}


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def _extract_price(price_range: str) -> int:
    """'300-980円' → 300 (下限値を取得)"""
    m = re.search(r"(\d+)", price_range)
    return int(m.group(1)) if m else 300


def _tool_from_tags(tags: list[str]) -> str:
    priority = ["ClaudeCode", "Claude", "生成AI", "AI活用", "AI", "ChatGPT", "NotebookLM"]
    for t in priority:
        if t in tags:
            return t.replace("ClaudeCode", "Claude Code")
    return tags[0] if tags else "AI"


def _period_from_angle(angle: str) -> str:
    return {"収益公開＋実践法": "3ヶ月"}.get(angle, "2週間")


def _revenue_hint(audience_type: str) -> str:
    return {"副業ワーカー": "3万", "会社員": "2万"}.get(audience_type, "2万")


# ---------------------------------------------------------------------------
# 結果サマリー
# ---------------------------------------------------------------------------

@dataclass
class NoteWriterResult:
    """run() の結果サマリー"""
    draft: Optional[NoteDraft] = None
    status: str = "ok"         # "ok" | "skipped" | "error" | "no_candidate"
    message: str = ""
    output_json: Optional[Path] = None
    output_md: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

class NoteWriterAgent:
    """
    承認済み TopicCandidate から NoteDraft を生成するエージェント。

    使い方:
        agent = NoteWriterAgent(settings=settings, dry_run=False)
        result = agent.run()                        # 最新の承認済み候補から生成
        result = agent.run(candidate_id="xxxx")    # 指定候補から生成
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)

    def run(self, candidate_id: Optional[str] = None) -> NoteWriterResult:
        result = NoteWriterResult()

        # 1. 承認済み候補を取得
        candidate = self._load_candidate(candidate_id)
        if candidate is None:
            result.status = "no_candidate"
            result.message = (
                "承認済みの候補がありません。"
                "`select-candidate` コマンドで候補を承認してください。"
            )
            return result

        # 2. 関連 PainPoint を取得
        pains = self._load_pains(candidate.target_pain_id_list)

        # 3. 下書きを生成
        try:
            draft = self._generate_draft(candidate, pains)
        except Exception as e:
            logger.error(f"Draft generation failed: {e}")
            result.status = "error"
            result.message = f"生成エラー: {e}"
            return result

        result.draft = draft

        # 4. 保存
        if self.dry_run:
            result.status = "skipped"
            result.message = (
                f"[DRY-RUN] would generate: '{draft.title[:50]}' "
                f"({len(draft.free_part_markdown)}字+{len(draft.paid_part_markdown)}字)"
            )
            logger.info(result.message)
            return result

        # SQLite
        self.db.save_draft(draft)

        # JSON (追記)
        output_json = save_note_drafts_append(draft, self.settings.note_drafts_json)
        result.output_json = output_json

        # Markdown ファイル
        output_md = self._export_markdown(draft)
        result.output_md = output_md

        result.status = "ok"
        result.message = (
            f"Generated: '{draft.title[:50]}' "
            f"(free={len(draft.free_part_markdown)}字, "
            f"paid={len(draft.paid_part_markdown)}字, "
            f"price={draft.price}円)"
        )
        logger.info(result.message)
        return result

    # ------------------------------------------------------------------
    # 下書き生成
    # ------------------------------------------------------------------

    def _generate_draft(
        self, candidate: TopicCandidate, pains: list[PainPoint]
    ) -> NoteDraft:
        """
        [FUTURE_LLM] テンプレートベースで NoteDraft を生成する。
        将来 Claude API に置き換える。
        """
        anchor = max(pains, key=lambda p: p.severity) if pains else None
        tool = _tool_from_tags(candidate.related_tags)
        angle = candidate.angle
        audience = candidate.audience_type
        price = _extract_price(candidate.recommended_price_range)
        period = _period_from_angle(angle)
        revenue = _revenue_hint(audience)

        subtitle = self._generate_subtitle(candidate, anchor)
        free_part = self._build_free_part(candidate, anchor, tool, angle, audience, price, period, revenue)
        paid_part = self._build_paid_part(candidate, anchor, tool, angle, audience, period)

        return NoteDraft(
            candidate_id=candidate.candidate_id,
            title=candidate.topic_title,
            subtitle=subtitle,
            free_part_markdown=free_part,
            paid_part_markdown=paid_part,
            price=price,
            tags=candidate.related_tags[:5],
            status=ArticleStatus.DRAFT_CREATED,
        )

    def _generate_subtitle(
        self, candidate: TopicCandidate, anchor: Optional[PainPoint]
    ) -> str:
        """[FUTURE_LLM] サブタイトルを生成する。"""
        tool = _tool_from_tags(candidate.related_tags)
        angle = candidate.angle
        subtitle_map = {
            "体験談＋本音レポート": f"{tool}を使って変わったこと、正直に書きます",
            "ステップバイステップガイド": f"手順通りに進めれば、必ず使えるようになります",
            "失敗談＋解決策": f"同じ失敗をしないために知っておいてほしいこと",
            "比較レポート": f"実際に使い込んだからこそ分かる、選び方の基準",
            "収益公開＋実践法": f"数字を公開しながら、再現できる方法を解説します",
        }
        return subtitle_map.get(angle, f"{tool}との{_period_from_angle(angle)}を振り返る")

    def _build_free_part(
        self,
        candidate: TopicCandidate,
        anchor: Optional[PainPoint],
        tool: str,
        angle: str,
        audience: str,
        price: int,
        period: str,
        revenue: str,
    ) -> str:
        """[FUTURE_LLM] 無料パートを生成する。"""
        pain_text = anchor.pain_summary if anchor else "うまく活用できない"
        situation_text = (anchor.situation or "日々の業務") if anchor else "日々の業務"
        failed_text = (
            "、".join(anchor.failed_attempts[:2]) if anchor and anchor.failed_attempts
            else "試してみたがうまくいかなかった"
        )

        why_not = _WHY_NOT_SOLVED.get(angle, _WHY_NOT_SOLVED["体験談＋本音レポート"])

        free_body = (
            _FREE_BODY.get(angle, _FREE_BODY["体験談＋本音レポート"])
            .replace("{period}", period)
            .replace("{revenue}", revenue)
            .replace("{audience_type}", audience)
        )

        paid_preview_items = self._paid_preview_items(angle, tool)
        paid_preview = "\n".join(f"- {item}" for item in paid_preview_items)

        not_for_hint = f"すでに{tool}を使いこなしている方"

        lines = [
            f"# {candidate.topic_title}",
            "",
            candidate.hook,
            "",
            f"「{pain_text}」——そう感じている{audience}の方に向けて書きます。",
            "",
            candidate.why_now,
            "",
            "## なぜうまくいかないのか",
            "",
            why_not,
            "",
            "## この記事でわかること",
            "",
            f"- {tool}を{situation_text}で活用するための具体的な方法",
            f"- {failed_text}という経験から学んだ、最短で成果を出す手順",
            f"- {audience}が実際に詰まるポイントと、その解決策",
            "",
            f"## {angle}：実体験から",
            "",
            free_body,
            "",
            "---",
            "",
            f"**有料パート（{price}円）の内容：**",
            "",
            paid_preview,
            "",
            f"> この記事は{audience}向けの内容です。{not_for_hint}には向きません。",
        ]
        return "\n".join(lines)

    def _build_paid_part(
        self,
        candidate: TopicCandidate,
        anchor: Optional[PainPoint],
        tool: str,
        angle: str,
        audience: str,
        period: str,
    ) -> str:
        """[FUTURE_LLM] 有料パートを生成する。"""
        steps = _STEPS.get(angle, _STEPS["体験談＋本音レポート"])
        for_who = _FOR_WHO.get(angle, _FOR_WHO["体験談＋本音レポート"])
        not_for_who = _NOT_FOR_WHO.get(angle, _NOT_FOR_WHO["体験談＋本音レポート"])
        conclusion = (
            _CONCLUSION.get(angle, _CONCLUSION["体験談＋本音レポート"])
            .replace("{tool}", tool)
            .replace("{audience_type}", audience)
            .replace("{period}", period)
        )

        lines = ["## 実践ステップ", ""]
        for i, (title, content) in enumerate(steps, 1):
            lines.append(f"### ステップ{i}: {title}")
            lines.append("")
            lines.append(content)
            lines.append("")

        lines += [
            "---",
            "",
            "## この記事が向いている人・向いていない人",
            "",
            "**向いている人**",
            "",
        ]
        for item in for_who:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("**向いていない人（購入前にご確認ください）**")
        lines.append("")
        for item in not_for_who:
            lines.append(f"- {item}")
        lines += [
            "",
            "---",
            "",
            "## まとめ",
            "",
            conclusion,
        ]
        return "\n".join(lines)

    def _paid_preview_items(self, angle: str, tool: str) -> list[str]:
        """有料パートの予告項目を返す。"""
        preview_map = {
            "体験談＋本音レポート": [
                f"実際に使ったプロンプトの具体例",
                "詰まった場面と抜け出し方",
                "継続のコツと次のステップ",
            ],
            "ステップバイステップガイド": [
                "ステップ4・5の詳細解説",
                "よくある詰まりポイントQ&A",
                f"1ヶ月で使いこなすためのロードマップ",
            ],
            "失敗談＋解決策": [
                "失敗3パターンの詳細と解決策",
                "同じ失敗を避けるための事前チェックリスト",
                "最短で成果を出すための逆算ロードマップ",
            ],
            "比較レポート": [
                "スクリーンショット付きの詳細比較データ",
                "ユースケース別おすすめ",
                "コスト別・目的別の選び方フローチャート",
            ],
            "収益公開＋実践法": [
                "月別収益の内訳（スクリーンショット付き）",
                f"収益を作った具体的な5ステップ",
                "実際に使ったプロンプトと設定",
            ],
        }
        return preview_map.get(angle, preview_map["体験談＋本音レポート"])

    # ------------------------------------------------------------------
    # 保存・出力
    # ------------------------------------------------------------------

    def _export_markdown(self, draft: NoteDraft) -> Path:
        """Markdown ファイルを drafts_dir に書き出す。"""
        self.settings.drafts_dir.mkdir(parents=True, exist_ok=True)
        date_str = draft.created_at.strftime("%Y%m%d")
        safe_title = re.sub(r'[\\/:*?"<>|【】]', "", draft.title)[:30]
        filename = f"{draft.id[:8]}_{date_str}_{safe_title}.md"
        path = self.settings.drafts_dir / filename

        header = (
            f"---\n"
            f"draft_id: {draft.id}\n"
            f"candidate_id: {draft.candidate_id}\n"
            f"title: {draft.title}\n"
            f"subtitle: {draft.subtitle}\n"
            f"price: {draft.price}\n"
            f"status: {draft.status}\n"
            f"created_at: {draft.created_at.isoformat()}\n"
            f"---\n\n"
        )
        separator = "\n\n---\n\n<!-- 有料パートここから -->\n\n"

        content = header + draft.free_part_markdown
        if draft.paid_part_markdown:
            content += separator + draft.paid_part_markdown

        path.write_text(content, encoding="utf-8")
        logger.info(f"Markdown exported: {path}")
        return path

    # ------------------------------------------------------------------
    # 内部ローダー
    # ------------------------------------------------------------------

    def _load_candidate(
        self, candidate_id: Optional[str] = None
    ) -> Optional[TopicCandidate]:
        """承認済みの TopicCandidate を返す（DB → JSON fallback）。"""
        try:
            if candidate_id:
                c = self.db.get_topic_candidate(candidate_id)
                if c and c.approved:
                    return c
                return None
            # 最新の承認済みを返す
            approved = self.db.list_topic_candidates(approved=True)
            if approved:
                return approved[0]  # score DESC で返ってくる
        except Exception as e:
            logger.warning(f"DB load failed: {e}")

        # JSON fallback
        json_path = self.settings.topic_candidates_json
        if json_path.exists():
            try:
                for c in load_topic_candidates(json_path):
                    if candidate_id:
                        if c.candidate_id == candidate_id and c.approved:
                            return c
                    elif c.approved:
                        return c
            except Exception as e:
                logger.warning(f"JSON load failed: {e}")
        return None

    def _load_pains(self, pain_ids: list[str]) -> list[PainPoint]:
        """pain_id リストから PainPoint を取得する。"""
        pains = []
        for pid in pain_ids:
            try:
                p = self.db.get_pain_point(pid)
                if p:
                    pains.append(p)
            except Exception:
                pass
        return pains
