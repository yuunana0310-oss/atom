"""
researcher エージェント

pain_points から「売れるnote記事」の候補を3〜5件生成し、
スコアリングしてtopic_candidates.jsonとSQLiteに保存する。

設計方針:
- ルールベース実装（将来LLM化しやすいよう関数境界を分けている）
- [FUTURE_LLM] マークの関数がLLM置き換え候補
- winning_patterns.json を参照してスコアリングを補正（[FUTURE_HOOK]）
- 候補の類似除外は pain_id の Jaccard 類似度で判定

候補生成フロー:
  1. pain_points をロード
  2. (audience_type × primary_tag) でグルーピング
  3. グループごとに候補を生成
  4. 各候補をスコアリング
  5. 類似候補を除外（Jaccard > threshold）
  6. スコア降順で top 3〜5 件に絞る
  7. SQLite + JSON に保存
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.adapters.storage_json import (
    load_topic_candidates,
    read_json,
    save_topic_candidates,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import ArticleStatus, PainPoint, TopicCandidate
from src.core.settings import AppSettings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# タイトル・フック テンプレート
# ---------------------------------------------------------------------------

# (audience_type, primary_tag) → タイトルテンプレートリスト
_TITLE_TEMPLATES: dict[str, list[str]] = {
    "非エンジニア": [
        "【非エンジニアが2週間試した】{tool}、正直に書く",
        "コードが書けない私が{tool}を使って変わったこと",
        "「{tool}は無理」と諦めかけた非エンジニアの話",
    ],
    "副業ワーカー": [
        "副業で{tool}を使い始めて3ヶ月、正直な収益レポート",
        "{tool}で副業収入を作るための全手順【実体験】",
        "月収+{revenue}円達成した{tool}副業の始め方",
    ],
    "会社員": [
        "会社員が{tool}を使って{goal}できるようになった話",
        "平日2時間で実践できる{tool}活用術",
    ],
    "初心者": [
        "【完全初心者向け】{tool}で{goal}する全手順",
        "初めて{tool}を使う人に伝えたいこと",
    ],
    "エンジニア": [
        "実務で{tool}を使い倒した記録：できること・できないこと",
        "{tool}で実際に作った{outcome}の全手順",
    ],
    "不明": [
        "{tool}を使って{goal}した話",
        "{pain_keyword}を解決した{tool}の具体的な使い方",
    ],
}

_HOOK_TEMPLATES: dict[str, list[str]] = {
    "非エンジニア": [
        "「自分には無理かも」と思ったことありませんか？",
        "エンジニアじゃないと使えない？そんなことはありません。",
    ],
    "副業ワーカー": [
        "副業でAIを使いたいけど、何から始めればいいか迷っていませんか？",
        "月数万円の副業収入、AIを使えば本当に実現できます。",
    ],
    "会社員": [
        "忙しい毎日の中で、AIを使いこなせていないと感じていませんか？",
    ],
    "初心者": [
        "初めてでも大丈夫です。手順通りやれば必ずできます。",
    ],
    "エンジニア": [
        "実際に使ってみないと分からないことがあります。",
    ],
    "不明": [
        "同じ悩みを抱えている人に向けて書きます。",
    ],
}

# アングル定義（angle → paid_reason テンプレート）
_ANGLE_PAID_REASON: dict[str, str] = {
    "体験談＋本音レポート": "実際に試した結果と失敗パターンの具体的な記録",
    "ステップバイステップガイド": "再現性のある手順と、詰まりやすいポイントの解説",
    "失敗談＋解決策": "失敗したからこそ分かる注意点と、実際に機能した解決策",
    "比較レポート": "複数ツールを実際に使い比べた客観的なデータ",
    "収益公開＋実践法": "実際の収益データと、再現できる具体的な行動手順",
}

# アングル定義（audience_type → 推奨アングル）
_AUDIENCE_ANGLE: dict[str, str] = {
    "非エンジニア": "体験談＋本音レポート",
    "副業ワーカー": "収益公開＋実践法",
    "会社員": "失敗談＋解決策",
    "初心者": "ステップバイステップガイド",
    "エンジニア": "比較レポート",
    "不明": "体験談＋本音レポート",
}

# 価格帯ルール（angle → 推奨価格帯）
_PRICE_RULES: dict[str, str] = {
    "収益公開＋実践法": "980-1980円",
    "ステップバイステップガイド": "500-980円",
    "体験談＋本音レポート": "0-300円",
    "失敗談＋解決策": "300-500円",
    "比較レポート": "300-980円",
}

# タグ優先順（primary_tag 選択に使用）
_TAG_PRIORITY = [
    "ClaudeCode", "Claude", "生成AI", "AI活用", "AI",
    "副業", "note", "noteで稼ぐ", "プロンプト", "初心者",
]


# ---------------------------------------------------------------------------
# PainPoint グルーピング
# ---------------------------------------------------------------------------

def _primary_tag(tags: list[str]) -> str:
    """タグリストから最も優先度の高いタグを返す。"""
    for t in _TAG_PRIORITY:
        if t in tags:
            return t
    return tags[0] if tags else "AI"


def _tool_name(tags: list[str]) -> str:
    """タグからツール名を推定する。"""
    tool_tags = {"ClaudeCode": "Claude Code", "Claude": "Claude",
                 "生成AI": "生成AI", "AI活用": "AI", "AI": "AI"}
    for t in _TAG_PRIORITY:
        if t in tags and t in tool_tags:
            return tool_tags[t]
    return "AI"


def group_pain_points(
    pains: list[PainPoint],
) -> dict[tuple[str, str], list[PainPoint]]:
    """
    PainPointを (audience_type, primary_tag) でグルーピングする。

    [FUTURE_LLM] より高度なセマンティッククラスタリングに置き換え可能。
    """
    groups: dict[tuple[str, str], list[PainPoint]] = {}
    for p in pains:
        key = (p.audience_type, _primary_tag(p.related_tags))
        groups.setdefault(key, []).append(p)
    return groups


# ---------------------------------------------------------------------------
# スコアリング
# ---------------------------------------------------------------------------

class CandidateScorer:
    """
    TopicCandidate のスコアリングを担当する。

    [FUTURE_LLM] score() をClaude APIに置き換えると精度が向上する。
    スコア重みは settings から注入するため、コードを変えずに調整できる。
    """

    def __init__(
        self,
        weights: dict[str, float],
        expertise_tags: list[str],
        trend_tags: list[str],
        winning_patterns: Optional[dict] = None,
    ):
        self.weights = weights
        self.expertise_tags = set(expertise_tags)
        self.trend_tags = set(trend_tags)
        self.winning_patterns = winning_patterns or {}

    def score(
        self, candidate: TopicCandidate, source_pains: list[PainPoint]
    ) -> TopicCandidate:
        """
        候補にスコアを付けて返す。
        score_breakdown にスコア内訳（重み・各点数）を記録する。
        """
        demand = self._score_demand(candidate, source_pains)
        monetization = self._score_monetization(candidate)
        threads_fit = self._score_threads_fit(candidate)
        expertise_fit = self._score_expertise_fit(candidate)
        trend = self._score_trend(candidate)

        w = self.weights
        total = (
            demand * w.get("demand", 0.30)
            + monetization * w.get("monetization", 0.25)
            + threads_fit * w.get("threads_fit", 0.20)
            + expertise_fit * w.get("expertise_fit", 0.15)
            + trend * w.get("trend", 0.10)
        )

        # [FUTURE_HOOK] winning_patterns による補正
        total = self._apply_pattern_boost(candidate, total)

        candidate.demand_score = round(demand, 2)
        candidate.monetization_score = round(monetization, 2)
        candidate.threads_fit_score = round(threads_fit, 2)
        candidate.expertise_fit_score = round(expertise_fit, 2)
        candidate.trend_score = round(trend, 2)
        candidate.total_score = round(min(10.0, total), 2)
        candidate.score_breakdown = {
            "weights": w,
            "demand": round(demand, 2),
            "monetization": round(monetization, 2),
            "threads_fit": round(threads_fit, 2),
            "expertise_fit": round(expertise_fit, 2),
            "trend": round(trend, 2),
            "total_raw": round(total, 2),
        }
        return candidate

    def _score_demand(
        self, candidate: TopicCandidate, source_pains: list[PainPoint]
    ) -> float:
        """[FUTURE_LLM] 需要スコア: 関連painの深刻度・頻度から計算"""
        pain_map = {p.pain_id: p for p in source_pains}
        relevant = [pain_map[pid] for pid in candidate.target_pain_id_list
                    if pid in pain_map]
        if not relevant:
            return 3.0

        avg_severity = sum(p.severity for p in relevant) / len(relevant)
        avg_frequency = sum(p.frequency for p in relevant) / len(relevant)
        avg_engagement = sum(p.engagement_count or 0 for p in relevant) / len(relevant)

        # 深刻度 (1-5) → 0-10 換算
        base = avg_severity * 2.0
        # 頻度補正
        base += (avg_frequency - 1) * 0.5
        # エンゲージメント補正
        if avg_engagement >= 50:
            base += 1.5
        elif avg_engagement >= 20:
            base += 0.8
        # pain件数補正（1件より複数の方が需要が広い）
        if len(relevant) >= 3:
            base += 1.0
        elif len(relevant) >= 2:
            base += 0.5

        return min(10.0, base)

    def _score_monetization(self, candidate: TopicCandidate) -> float:
        """[FUTURE_LLM] 有料化スコア: アングル・価格帯・paid_reason の強さ"""
        base = 5.0
        # アングルによるブース
        angle_boost = {
            "収益公開＋実践法": 3.0,
            "ステップバイステップガイド": 2.0,
            "失敗談＋解決策": 1.0,
            "比較レポート": 1.0,
            "体験談＋本音レポート": 0.0,
        }
        base += angle_boost.get(candidate.angle, 0.0)
        # paid_reason が充実しているか（文字数で簡易判定）
        if len(candidate.paid_reason) >= 30:
            base += 0.5
        # 高価格帯は有料化しやすさの証
        if "980" in candidate.recommended_price_range or "1980" in candidate.recommended_price_range:
            base += 1.0
        return min(10.0, base)

    def _score_threads_fit(self, candidate: TopicCandidate) -> float:
        """[FUTURE_LLM] Threads適合度: フックの質・タグ・訴求力"""
        base = 4.0
        hook = candidate.hook
        # 疑問形フックは Threads で反応が取りやすい
        if "？" in hook or "ませんか" in hook or "ですか" in hook:
            base += 2.0
        elif "ます" in hook or "ました" in hook:
            base += 1.0
        # 共感ワード
        empathy_words = ["悩み", "困", "分から", "できない", "諦め", "不安"]
        if any(w in hook for w in empathy_words):
            base += 1.5
        # タグが Threads で人気かどうか（trend_tagsと重複するので軽め）
        if any(t in self.trend_tags for t in candidate.related_tags):
            base += 0.5
        return min(10.0, base)

    def _score_expertise_fit(self, candidate: TopicCandidate) -> float:
        """[FUTURE_LLM] 専門性適合度: タグと expertise_tags の重複"""
        overlap = len(set(candidate.related_tags) & self.expertise_tags)
        total_tags = max(1, len(candidate.related_tags))
        ratio = overlap / total_tags
        return min(10.0, ratio * 10.0 + 2.0)  # 最低2点は保証

    def _score_trend(self, candidate: TopicCandidate) -> float:
        """[FUTURE_LLM] トレンドスコア: trend_tags との重複"""
        overlap = len(set(candidate.related_tags) & self.trend_tags)
        base = min(10.0, overlap * 2.5)
        # why_nowに時事ワードがあればボーナス
        timely_words = ["2026", "最新", "今", "注目", "急増", "人気"]
        if any(w in candidate.why_now for w in timely_words):
            base = min(10.0, base + 1.5)
        return base

    def _apply_pattern_boost(self, candidate: TopicCandidate, total: float) -> float:
        """
        [FUTURE_HOOK] winning_patterns.json に基づいてスコアを補正する。
        現状: 既知の高パフォーマンスアングルに微小ブーストを付与。
        """
        if not self.winning_patterns:
            return total
        for pattern in self.winning_patterns.get("angle_patterns", []):
            if pattern.get("angle") == candidate.angle:
                m_boost = pattern.get("monetization_boost", 0.0)
                t_boost = pattern.get("threads_fit_boost", 0.0)
                # 全体スコアへの影響は小さく抑える
                total += (m_boost * self.weights.get("monetization", 0.25) * 0.1
                          + t_boost * self.weights.get("threads_fit", 0.20) * 0.1)
        return total


# ---------------------------------------------------------------------------
# 候補生成ロジック
# ---------------------------------------------------------------------------

class CandidateGenerator:
    """
    PainPointのグループからTopicCandidateを生成するルールベースエンジン。

    [FUTURE_LLM] generate() をClaude APIに置き換える。
    その場合も外部インターフェース generate(pains) → list[TopicCandidate] は維持する。
    """

    def generate(self, pains: list[PainPoint]) -> list[TopicCandidate]:
        """
        [FUTURE_LLM] pain_points から候補を生成する。
        現状: グルーピング + テンプレートタイトル生成（バリエーション付き）。
        """
        groups = group_pain_points(pains)
        candidates: list[TopicCandidate] = []

        for (audience_type, primary_tag), group_pains in groups.items():
            title_templates = _TITLE_TEMPLATES.get(audience_type, _TITLE_TEMPLATES["不明"])
            hook_templates = _HOOK_TEMPLATES.get(audience_type, _HOOK_TEMPLATES["不明"])
            # グループあたり最大 min(テンプレート数, 痛み点数, 3) 件を生成
            n_variants = min(len(title_templates), len(hook_templates), len(group_pains), 3)
            # テンプレートの開始インデックスをランダムにずらして毎回違う組み合わせにする
            start_idx = random.randint(0, len(title_templates) - 1)
            for i in range(n_variants):
                template_idx = (start_idx + i) % len(title_templates)
                candidate = self._generate_one(audience_type, primary_tag, group_pains, template_idx=template_idx)
                if candidate:
                    candidates.append(candidate)

        return candidates

    def _generate_one(
        self,
        audience_type: str,
        primary_tag: str,
        pains: list[PainPoint],
        template_idx: int = 0,
    ) -> Optional[TopicCandidate]:
        """グループ内のpain群から1つのTopicCandidateを生成する。"""
        # ランダムにシャッフルしたpainリストからtemplate_idxで異なるanchorを選ぶ
        shuffled_pains = sorted(pains, key=lambda p: p.severity, reverse=True)
        # 上位pains内でランダムに選択（深刻度順の上位50%から）
        top_half = shuffled_pains[:max(1, len(shuffled_pains) // 2 + 1)]
        anchor = random.choice(top_half)

        tool = _tool_name([primary_tag] + anchor.related_tags)
        templates = _TITLE_TEMPLATES.get(audience_type, _TITLE_TEMPLATES["不明"])
        title = self._fill_template(templates[template_idx % len(templates)], tool=tool, anchor=anchor)

        hook_templates = _HOOK_TEMPLATES.get(audience_type, _HOOK_TEMPLATES["不明"])
        hook = hook_templates[template_idx % len(hook_templates)]

        angle = _AUDIENCE_ANGLE.get(audience_type, "体験談＋本音レポート")
        paid_reason = _ANGLE_PAID_REASON.get(angle, "実体験に基づく具体的な情報")
        recommended_price = _PRICE_RULES.get(angle, "300-980円")

        # タグを全pain点から収集
        all_tags: set[str] = set()
        for p in pains:
            all_tags.update(p.related_tags)

        why_now = self._generate_why_now(primary_tag, audience_type)
        buyer_intent = self._generate_buyer_intent(audience_type, angle)

        return TopicCandidate(
            target_pain_id_list=[p.pain_id for p in pains],
            topic_title=title,
            hook=hook,
            angle=angle,
            why_now=why_now,
            expected_buyer_intent=buyer_intent,
            paid_reason=paid_reason,
            recommended_price_range=recommended_price,
            audience_type=audience_type,
            related_tags=sorted(all_tags),
        )

    def _fill_template(self, template: str, tool: str, anchor: PainPoint) -> str:
        """[FUTURE_LLM] テンプレートを埋める。"""
        pain_kw = anchor.pain_summary[:20] if anchor.pain_summary else "AI活用"
        return (
            template
            .replace("{tool}", tool)
            .replace("{pain_keyword}", pain_kw)
            .replace("{goal}", "生産性を上げる")
            .replace("{outcome}", "副業収入を作る")
            .replace("{revenue}", "3万")
            .replace("{period}", "2週間")
            .replace("{count}", "5")
            .replace("{audience}", _audience_short(anchor.audience_type))
        )

    def _generate_why_now(self, primary_tag: str, audience_type: str) -> str:
        """[FUTURE_LLM] 時事性コメントを生成する。"""
        tag_why = {
            "ClaudeCode": "Claude Code が 2026年に急速に普及しており、非エンジニアの参入が増えている",
            "生成AI": "生成AI活用が2026年の副業トレンドとして注目されている",
            "AI活用": "AIツールの活用が副業・業務効率化の主流になりつつある",
            "副業": "副業解禁・物価高の影響で、AIを活用した副業への関心が急増している",
            "note": "note の有料記事市場が拡大し、AI活用記事の需要が高まっている",
        }
        return tag_why.get(primary_tag, f"{primary_tag}への関心が高まっている時期のため")

    def _generate_buyer_intent(self, audience_type: str, angle: str) -> str:
        """[FUTURE_LLM] 購読者の購買動機を記述する。"""
        intent_map = {
            ("非エンジニア", "体験談＋本音レポート"):
                "同じ立場の人の体験談で安心したい、失敗パターンを知っておきたい",
            ("副業ワーカー", "収益公開＋実践法"):
                "実際の収益データと再現できる手順を知りたい",
            ("初心者", "ステップバイステップガイド"):
                "手順通りに進めれば自分でもできると確信したい",
            ("会社員", "失敗談＋解決策"):
                "同じ失敗を避けて、効率よく成果を出したい",
            ("エンジニア", "比較レポート"):
                "自分のユースケースに合ったツール選定の判断材料がほしい",
        }
        key = (audience_type, angle)
        return intent_map.get(key, "具体的な手順と実体験に基づいた情報がほしい")


def _audience_short(audience_type: str) -> str:
    short = {
        "非エンジニア": "非エンジニア",
        "副業ワーカー": "副業ワーカー",
        "会社員": "会社員",
        "初心者": "初心者",
        "エンジニア": "エンジニア",
    }
    return short.get(audience_type, "私")


# ---------------------------------------------------------------------------
# 類似除外
# ---------------------------------------------------------------------------

def _title_bigrams(title: str) -> set[str]:
    """タイトルを2文字bigram集合に変換する。"""
    return {title[i:i+2] for i in range(len(title) - 1)} if len(title) >= 2 else {title}


def deduplicate_candidates(
    candidates: list[TopicCandidate],
    threshold: float = 0.6,
) -> list[TopicCandidate]:
    """
    タイトルのbigram Jaccard 類似度が threshold 以上の候補を除外（高スコアを残す）。

    [FUTURE_LLM] より精度の高い類似判定に置き換え可能。
    """
    if len(candidates) <= 1:
        return candidates

    # スコア降順にソート（高いものを優先的に残す）
    sorted_c = sorted(candidates, key=lambda c: c.total_score, reverse=True)
    kept: list[TopicCandidate] = []

    for cand in sorted_c:
        cand_bigrams = _title_bigrams(cand.topic_title)
        is_duplicate = False
        for kept_c in kept:
            kept_bigrams = _title_bigrams(kept_c.topic_title)
            sim = _jaccard(cand_bigrams, kept_bigrams)
            if sim >= threshold:
                logger.debug(
                    f"Dedup: {cand.candidate_id[:8]} '{cand.topic_title[:30]}' (score={cand.total_score:.1f}) "
                    f"similar to '{kept_c.topic_title[:30]}' (Jaccard={sim:.2f})"
                )
                is_duplicate = True
                break
        if not is_duplicate:
            kept.append(cand)

    return kept


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

@dataclass
class ResearcherResult:
    """run() の結果サマリー"""
    candidates: list[TopicCandidate] = field(default_factory=list)
    generated: int = 0
    after_dedup: int = 0
    final_count: int = 0
    output_json: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


class ResearcherAgent:
    """
    researcher のメインエージェント。

    使い方:
        agent = ResearcherAgent(settings=settings, dry_run=False)
        result = agent.run()                    # pain_points.json から自動読み込み
        result = agent.run(pains=pain_list)     # PainPoint リストを直接渡す
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)
        self.generator = CandidateGenerator()
        self.scorer = CandidateScorer(
            weights=settings.score_weights,
            expertise_tags=settings.expertise_tags,
            trend_tags=settings.trend_tags,
            winning_patterns=self._load_winning_patterns(),
        )

    def run(self, pains: Optional[list[PainPoint]] = None) -> ResearcherResult:
        """メインエントリ。"""
        result = ResearcherResult()

        # 1. PainPoint 読み込み
        if pains is None:
            pains = self._load_pain_points()
        if not pains:
            result.warnings.append("No pain points found. Run collect-pain first.")
            return result

        # 2. 候補生成
        candidates = self.generator.generate(pains)
        result.generated = len(candidates)
        logger.info(f"Generated {len(candidates)} raw candidates")

        if not candidates:
            result.warnings.append("No candidates generated. Check pain points data.")
            return result

        # 3. スコアリング
        scored = [self.scorer.score(c, pains) for c in candidates]

        # 4. 類似除外
        deduped = deduplicate_candidates(
            scored, threshold=self.settings.researcher_similarity_threshold
        )
        result.after_dedup = len(deduped)

        # 5. 上位 3〜5 件に絞る
        top = sorted(deduped, key=lambda c: c.total_score, reverse=True)
        top = top[:self.settings.candidates_max]
        if len(top) < self.settings.candidates_min:
            result.warnings.append(
                f"Only {len(top)} candidates generated (min={self.settings.candidates_min}). "
                "Consider adding more pain points."
            )

        result.candidates = top
        result.final_count = len(top)

        # 6. 保存（既存の未レビュー候補を削除してから新規保存）
        if not self.dry_run:
            cleared = self.db.clear_unreviewed_candidates()
            if cleared:
                logger.info(f"Cleared {cleared} old unreviewed candidates before saving new ones")
            for c in top:
                self.db.save_topic_candidate(c)
            output_path = save_topic_candidates(top, self.settings.topic_candidates_json)
            result.output_json = output_path
            logger.info(f"Saved {len(top)} topic candidates to {output_path}")
        else:
            logger.info(f"[DRY-RUN] Would save {len(top)} topic candidates")
            for c in top[:3]:
                logger.info(
                    f"  [DRY-RUN] {c.candidate_id[:8]}: {c.topic_title[:50]} "
                    f"(score={c.total_score:.1f})"
                )

        return result

    # ------------------------------------------------------------------
    # 内部メソッド
    # ------------------------------------------------------------------

    def _load_pain_points(self) -> list[PainPoint]:
        """SQLite → JSON の順で既存 PainPoint を読み込む。"""
        try:
            pains = self.db.list_pain_points()
            if pains:
                return pains
        except Exception as e:
            logger.warning(f"Could not load from DB: {e}")

        # fallback: JSON ファイル
        json_path = self.settings.pain_points_json
        if json_path.exists():
            try:
                raw = read_json(json_path)
                if isinstance(raw, dict) and "pain_points" in raw:
                    return [PainPoint.model_validate(p) for p in raw["pain_points"]]
            except Exception as e:
                logger.warning(f"Could not load from JSON: {e}")
        return []

    def _load_winning_patterns(self) -> dict:
        """
        [FUTURE_HOOK] winning_patterns.json を読み込む。
        存在しない場合は空dict（スコア補正なし）。
        """
        path = self.settings.winning_patterns_json
        if path.exists():
            try:
                data = read_json(path)
                return data or {}
            except Exception as e:
                logger.warning(f"Could not load winning_patterns: {e}")
        return {}
