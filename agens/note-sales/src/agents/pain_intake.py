"""
pain_intake エージェント

各種入力ソース（投稿履歴・コメント要約・反応ログ・現場メモ・手動メモ）から
読者の悩みポイントを抽出・構造化してSQLite + JSONに保存する。

設計方針:
- ルールベース実装（将来LLM化しやすいよう関数境界を分けている）
- [FUTURE_LLM] マークの関数がLLM置き換えの候補
- スキーマ揺れに耐えるため、フィールド名を複数パターンで試みる
- 既存データは上書きせず追記・pain_idで管理
- 不完全な入力でも落ちずに処理継続

入力フォーマット例:
  - data/raw/sample_post_history.json
  - data/raw/sample_comments.json
  - data/raw/sample_manual_memo.json
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from src.adapters.storage_json import read_json, write_json
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import PainPoint, RawSource, SourceType
from src.core.settings import AppSettings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# ルールベース定義
# ---------------------------------------------------------------------------

# 悩み指標キーワード（これが1つ以上あればpain候補）
# 活用形のブレをカバーするためステム形で登録している
_PAIN_INDICATORS: list[str] = [
    "困", "できない", "できず", "できません", "できなかった", "できなくて",
    "続かない", "わからない", "わからなくて", "わからなかった",
    "分からない", "分からず", "分からなくて", "分からなかった",
    "怖い", "失敗", "うまくいかない", "うまくいかな", "うまく行かない",
    "難しい", "難しく", "エラー", "詰まった", "詰まる", "諦め", "挫折",
    "無理", "どうすれば", "どうしたら", "教えて", "助けて", "困惑",
    "不安", "心配", "迷", "迷ってい", "できるか", "できるかな", "わかりません",
]

# 純粋な感想（これだけの場合は除外）
_IMPRESSION_ONLY: list[str] = [
    "すごい", "素晴らしい", "最高", "感動", "楽しい", "面白い",
    "ありがとう", "感謝", "サンキュー", "よかった", "嬉しい",
]

# 深刻度スコア (severity: 1-5)
_SEVERITY_HIGH: list[str] = ["失敗", "詰まった", "壊れた", "無理", "挫折", "諦め", "できない", "エラー"]
_SEVERITY_MED: list[str] = ["困った", "うまくいかない", "難しい", "分からない", "わからない"]
_SEVERITY_LOW: list[str] = ["不安", "心配", "迷", "どうすれば"]

# 緊急度スコア (urgency: 1-5)
_URGENCY_HIGH: list[str] = ["今すぐ", "今日中", "急いで", "緊急", "明日まで", "今週中", "すぐに"]
_URGENCY_MED: list[str] = ["なるべく早く", "できれば早め", "早急"]

# 頻度スコア (frequency: 1-5)
_FREQ_HIGH: list[str] = ["毎回", "いつも", "何度も", "繰り返し", "また", "再び", "相変わらず"]
_FREQ_MED: list[str] = ["たまに", "ときどき", "時々"]

# 読者属性マーカー
_AUDIENCE_MARKERS: dict[str, list[str]] = {
    "非エンジニア": ["非エンジニア", "コード書けない", "プログラミング未経験", "文系", "ITが苦手"],
    "エンジニア": ["エンジニア", "開発者", "プログラマー", "SE", "dev"],
    "副業ワーカー": ["副業", "サイドビジネス", "フリーランス", "複業"],
    "会社員": ["会社員", "サラリーマン", "OL", "会社"],
    "初心者": ["初心者", "はじめて", "始めたばかり", "初めて"],
}

# 自動タグ付け
_AUTO_TAGS: dict[str, list[str]] = {
    "AI": ["AI", "人工知能", "ChatGPT", "Gemini", "Copilot"],
    "Claude": ["Claude", "クロード"],
    "ClaudeCode": ["Claude Code", "ClaudeCode", "クロードコード"],
    "生成AI": ["生成AI", "生成系AI"],
    "副業": ["副業", "副業収入", "サイドビジネス"],
    "プログラミング": ["プログラミング", "コーディング", "コード"],
    "初心者": ["初心者", "入門", "はじめて"],
    "効率化": ["効率化", "自動化", "時短"],
    "noteで稼ぐ": ["note", "記事販売", "有料記事"],
}

# 失敗試行を示すパターン（前後の文脈を取る）
_FAILED_ATTEMPT_PATTERNS: list[str] = [
    r"(.{5,30})(?:を試したが|を試したけど|したが|したけど|したのに|してみたが|してみたけど)(?:うまくいかなかった|ダメだった|無理だった|失敗した)",
    r"(.{5,30})(?:しても|を使っても)(?:うまくいかない|できない|ダメ)",
    r"(?:試した|やってみた|使ってみた)が(.{5,30})(?:上手くいかなかった|ダメだった|無理だった)",
]

# 状況を示すパターン
_SITUATION_PATTERNS: list[str] = [
    r"(.{5,40})(?:しようとしたら|しようとしたとき|するときに|する際に|するとき)",
    r"(.{5,40})(?:を使って|を使おうとして|を試して)",
    r"(?:最近|先日|今日)(.{5,40})(?:をやってみた|をやった|をしていた)",
]


# ---------------------------------------------------------------------------
# 入力スキーマ正規化
# ---------------------------------------------------------------------------

class SourceNormalizer:
    """
    各種入力JSONのスキーマ揺れを吸収してRawSourceに変換する。

    対応パターン:
      post_history   : {body/text/content, post_id/id, likes, replies, tags}
      comment_summary: {comment_summary/text, post_id, reaction_type, count}
      field_note     : {memo/text/note, tags, type}
      manual_memo    : {text/memo/description, tags}
    """

    @classmethod
    def normalize_item(
        cls,
        raw: dict[str, Any],
        hint_type: Optional[SourceType] = None,
    ) -> Optional[RawSource]:
        """
        1件のdictをRawSourceに変換する。
        変換できない場合はNoneを返す（落とさない）。
        """
        if not isinstance(raw, dict):
            logger.warning(f"Skipping non-dict item: {type(raw)}")
            return None

        # テキスト取得（複数フィールド名に対応）
        text = cls._pick(raw, ["text", "body", "content", "message", "memo", "note",
                                "comment_summary", "description", "comment", "post_text"])
        if not text:
            logger.debug(f"No text field found in item: {list(raw.keys())}")
            return None

        # 投稿ID取得
        post_id = cls._pick(raw, ["post_id", "id", "thread_id", "article_id"])
        if isinstance(post_id, (int, float)):
            post_id = str(post_id)

        # タグ取得
        tags_raw = raw.get("tags", raw.get("hashtags", raw.get("categories", [])))
        if isinstance(tags_raw, str):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        elif isinstance(tags_raw, list):
            tags = [str(t) for t in tags_raw if t]
        else:
            tags = []

        # エンゲージメント合計
        likes   = cls._int(raw, ["likes", "like_count", "favorites"])
        replies = cls._int(raw, ["replies", "reply_count", "comments"])
        reposts = cls._int(raw, ["reposts", "repost_count", "retweets", "shares"])
        views   = cls._int(raw, ["views", "view_count", "impressions"])
        engagement = likes + replies + reposts
        if engagement == 0 and views > 0:
            engagement = max(1, views // 100)  # views から推定（参考値）

        # 日時取得
        created_at = cls._parse_datetime(
            cls._pick(raw, ["created_at", "timestamp", "date", "posted_at"])
        )

        # ソースタイプ判定
        source_type = hint_type or cls._detect_type(raw)

        return RawSource(
            source_type=source_type,
            text=str(text).strip(),
            post_id=str(post_id) if post_id else None,
            tags=tags,
            engagement_total=engagement,
            created_at=created_at,
            raw=raw,
        )

    @classmethod
    def normalize_file(
        cls, path: Path, hint_type: Optional[SourceType] = None
    ) -> list[RawSource]:
        """JSONファイルを読んでRawSourceのリストを返す。単一オブジェクトもリストも受け付ける。"""
        raw_data = read_json(path)
        if raw_data is None:
            logger.warning(f"Could not read file: {path}")
            return []

        items = raw_data if isinstance(raw_data, list) else [raw_data]
        results: list[RawSource] = []
        for item in items:
            source = cls.normalize_item(item, hint_type)
            if source is not None:
                results.append(source)
        logger.debug(f"Normalized {len(results)}/{len(items)} items from {path.name}")
        return results

    @staticmethod
    def _pick(d: dict, keys: list[str]) -> Any:
        for k in keys:
            v = d.get(k)
            if v is not None and v != "":
                return v
        return None

    @staticmethod
    def _int(d: dict, keys: list[str]) -> int:
        for k in keys:
            v = d.get(k)
            if v is not None:
                try:
                    return int(v)
                except (ValueError, TypeError):
                    pass
        return 0

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(value)[:19], fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _detect_type(raw: dict) -> SourceType:
        """内容からソースタイプを推定する"""
        keys = set(raw.keys())
        if "body" in keys or ("likes" in keys and "replies" in keys):
            return SourceType.POST_HISTORY
        if "comment_summary" in keys or "reaction_type" in keys:
            return SourceType.COMMENT_SUMMARY
        if raw.get("type") in ("field_note", "フィールドノート", "現場メモ"):
            return SourceType.FIELD_NOTE
        if raw.get("type") in ("reaction_log", "反応ログ"):
            return SourceType.REACTION_LOG
        return SourceType.MANUAL_MEMO


# ---------------------------------------------------------------------------
# ルールベース抽出ロジック
# ---------------------------------------------------------------------------

class PainExtractor:
    """
    RawSource から PainPoint を抽出するルールベースエンジン。

    [FUTURE_LLM] このクラス全体をClaude APIに置き換える。
    その場合も外部インターフェース extract(source) → list[PainPoint] は維持する。
    """

    def __init__(self, min_text_length: int = 15, require_pain_keyword: bool = True):
        self.min_text_length = min_text_length
        self.require_pain_keyword = require_pain_keyword

    def extract(self, source: RawSource) -> list[PainPoint]:
        """1つのRawSourceからPainPointのリストを返す。"""
        text = source.text.strip()

        # 最小文字数チェック
        if len(text) < self.min_text_length:
            logger.debug(f"Skipping short text ({len(text)} chars): {text[:30]}")
            return []

        # 純粋な感想のみかチェック
        if self._is_impression_only(text):
            logger.debug(f"Skipping impression-only text: {text[:40]}")
            return []

        # 悩みキーワードチェック
        if self.require_pain_keyword and not self._has_pain_indicator(text):
            logger.debug(f"No pain indicator found: {text[:40]}")
            return []

        # PainPointを生成
        pain = PainPoint(
            source_post_id=source.post_id,
            source_type=source.source_type if isinstance(source.source_type, str)
                         else source.source_type.value,
            original_text=text[:500],  # 長すぎる場合は切り詰め
            pain_summary=self._summarize_pain(text),   # [FUTURE_LLM]
            severity=self._score_severity(text),        # [FUTURE_LLM]
            urgency=self._score_urgency(text),          # [FUTURE_LLM]
            frequency=self._score_frequency(text, source.engagement_total),  # [FUTURE_LLM]
            audience_type=self._detect_audience(text),  # [FUTURE_LLM]
            situation=self._extract_situation(text),    # [FUTURE_LLM]
            failed_attempts=self._extract_failed_attempts(text),  # [FUTURE_LLM]
            related_tags=self._extract_tags(text, source.tags),
            engagement_count=source.engagement_total or None,
            created_at=source.created_at or datetime.now(),
        )
        return [pain]

    # --- [FUTURE_LLM] 以下の各関数がLLM置き換え候補 ---

    def _summarize_pain(self, text: str) -> str:
        """
        [FUTURE_LLM] 悩みの要約を生成する。
        現状: 悩みキーワードを含む文を優先的に抽出して截断。
        """
        # 文に分割（句点・感嘆符・改行で分割）
        sentences = re.split(r"[。！\n]", text)

        # 悩みキーワードを含む文を優先
        for sentence in sentences:
            s = sentence.strip()
            if len(s) >= 10 and self._has_pain_indicator(s):
                summary = s[:100]
                return summary

        # 見つからなければ先頭を使う
        return text[:100].replace("\n", " ").strip()

    def _score_severity(self, text: str) -> int:
        """[FUTURE_LLM] 深刻度スコア（1-5）"""
        if any(kw in text for kw in _SEVERITY_HIGH):
            return 4
        if any(kw in text for kw in _SEVERITY_MED):
            return 3
        if any(kw in text for kw in _SEVERITY_LOW):
            return 2
        return 1

    def _score_urgency(self, text: str) -> int:
        """[FUTURE_LLM] 緊急度スコア（1-5）"""
        if any(kw in text for kw in _URGENCY_HIGH):
            return 5
        if any(kw in text for kw in _URGENCY_MED):
            return 3
        return 1

    def _score_frequency(self, text: str, engagement: int) -> int:
        """[FUTURE_LLM] 頻度スコア（1-5）"""
        score = 1
        if any(kw in text for kw in _FREQ_HIGH):
            score = 4
        elif any(kw in text for kw in _FREQ_MED):
            score = 2
        # エンゲージメントが高い = 多くの人が共感 = 頻度高い
        if engagement >= 50:
            score = min(5, score + 2)
        elif engagement >= 20:
            score = min(5, score + 1)
        return score

    def _detect_audience(self, text: str) -> str:
        """[FUTURE_LLM] 読者属性を検出する"""
        for audience, markers in _AUDIENCE_MARKERS.items():
            if any(m in text for m in markers):
                return audience
        return "不明"

    def _extract_situation(self, text: str) -> str:
        """[FUTURE_LLM] 悩みが発生した状況を抽出する"""
        for pattern in _SITUATION_PATTERNS:
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()[:80]
        # パターンにマッチしなければ先頭の短縮版
        return text[:40].replace("\n", " ").strip()

    def _extract_failed_attempts(self, text: str) -> list[str]:
        """[FUTURE_LLM] 試みて失敗したことを抽出する"""
        attempts: list[str] = []
        for pattern in _FAILED_ATTEMPT_PATTERNS:
            for m in re.finditer(pattern, text):
                attempt = m.group(1).strip()
                if attempt and len(attempt) >= 3:
                    attempts.append(attempt[:60])
        return attempts[:5]  # 最大5件

    def _extract_tags(self, text: str, source_tags: list[str]) -> list[str]:
        """テキストと既存タグからタグセットを生成する"""
        tags = set(source_tags)
        for tag, keywords in _AUTO_TAGS.items():
            if any(kw in text for kw in keywords):
                tags.add(tag)
        # 読者属性もタグに加える
        audience = self._detect_audience(text)
        if audience != "不明":
            tags.add(audience)
        return sorted(tags)

    @staticmethod
    def _has_pain_indicator(text: str) -> bool:
        return any(kw in text for kw in _PAIN_INDICATORS)

    @staticmethod
    def _is_impression_only(text: str) -> bool:
        """痛みキーワードなしで感想キーワードだけなら True"""
        has_pain = any(kw in text for kw in _PAIN_INDICATORS)
        has_impression = any(kw in text for kw in _IMPRESSION_ONLY)
        return has_impression and not has_pain


# ---------------------------------------------------------------------------
# 類似クラスタリング
# ---------------------------------------------------------------------------

class PainClusterer:
    """
    抽出されたPainPointの類似グループを検出する。
    統合はせず、similar_pain_ids と cluster_id でリンクするだけ。

    [FUTURE_LLM] _compute_similarity をClaude APIに置き換えると精度が上がる。
    """

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def cluster(self, pains: list[PainPoint]) -> list[PainPoint]:
        """
        pains リスト内で類似ペアを検出し、
        similar_pain_ids と cluster_id を付与して返す。
        """
        if len(pains) <= 1:
            return pains

        # Union-Find で同一クラスタを管理
        parent: dict[str, str] = {p.pain_id: p.pain_id for p in pains}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra  # 古いIDをルートにする

        # 全ペア比較
        for i in range(len(pains)):
            for j in range(i + 1, len(pains)):
                sim = self._compute_similarity(pains[i], pains[j])
                if sim >= self.threshold:
                    union(pains[i].pain_id, pains[j].pain_id)
                    logger.debug(
                        f"Similar pains: {pains[i].pain_id[:8]} ↔ {pains[j].pain_id[:8]} "
                        f"(sim={sim:.2f})"
                    )

        # cluster_id と similar_pain_ids を付与
        cluster_members: dict[str, list[str]] = {}
        for p in pains:
            root = find(p.pain_id)
            cluster_members.setdefault(root, []).append(p.pain_id)

        for p in pains:
            root = find(p.pain_id)
            members = cluster_members[root]
            if len(members) > 1:
                p.cluster_id = root
                p.similar_pain_ids = [m for m in members if m != p.pain_id]

        return pains

    def _compute_similarity(self, a: PainPoint, b: PainPoint) -> float:
        """
        [FUTURE_LLM] 2つのPainPointの類似度を計算する（0.0〜1.0）。
        現状: タグのJaccard + キーワードオーバーラップの加重平均。
        """
        # タグJaccard
        tag_sim = _jaccard(set(a.related_tags), set(b.related_tags))

        # audience_type一致ボーナス
        audience_bonus = 0.15 if a.audience_type == b.audience_type != "不明" else 0.0

        # pain_summaryのキーワードオーバーラップ
        text_sim = _keyword_overlap(a.pain_summary, b.pain_summary)

        # 加重平均
        total = tag_sim * 0.5 + text_sim * 0.35 + audience_bonus * 0.15
        return min(1.0, total)


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def _keyword_overlap(text_a: str, text_b: str) -> float:
    """形態素解析なしの簡易キーワードオーバーラップ"""
    # 3文字以上の単語（ASCII/数字以外）を抽出
    def tokenize(t: str) -> set[str]:
        tokens = re.findall(r"[^\s\u3000-\u303f\uff01-\uff60]{2,}", t)
        return {tok for tok in tokens if len(tok) >= 2}

    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    return _jaccard(tokens_a, tokens_b)


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

@dataclass
class PainIntakeResult:
    """run() の結果サマリー"""
    extracted: int = 0
    skipped: int = 0
    error_count: int = 0
    similar_linked: int = 0
    output_json: Optional[Path] = None
    pain_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PainIntakeAgent:
    """
    pain_intake のメインエージェント。

    使い方:
        agent = PainIntakeAgent(settings=settings, dry_run=False)
        result = agent.run(input_path)
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)
        self.normalizer = SourceNormalizer()
        self.extractor = PainExtractor(
            min_text_length=settings.pain_min_text_length,
            require_pain_keyword=settings.pain_require_keyword,
        )
        self.clusterer = PainClusterer(threshold=settings.pain_similarity_threshold)

    def run(self, input_path: Path) -> PainIntakeResult:
        """
        input_pathのJSONファイル（またはディレクトリ）を処理して
        PainPointを抽出・保存する。
        """
        result = PainIntakeResult()

        # 1. ファイル収集
        files = self._collect_files(input_path)
        if not files:
            result.warnings.append(f"No JSON files found in: {input_path}")
            logger.warning(f"No JSON files found: {input_path}")
            return result

        # 2. ソース正規化
        sources: list[RawSource] = []
        for f in files:
            try:
                normalized = SourceNormalizer.normalize_file(f)
                sources.extend(normalized)
            except Exception as e:
                result.error_count += 1
                result.warnings.append(f"Error loading {f.name}: {e}")
                logger.error(f"Error loading {f}: {e}")

        logger.info(f"Loaded {len(sources)} sources from {len(files)} files")

        # 3. 悩み抽出
        new_pains: list[PainPoint] = []
        for source in sources:
            try:
                extracted = self.extractor.extract(source)
                new_pains.extend(extracted)
                result.skipped += (1 - len(extracted)) if not extracted else 0
            except Exception as e:
                result.error_count += 1
                result.warnings.append(f"Extraction error: {e}")
                logger.error(f"Extraction error for source {source.source_id}: {e}")

        result.skipped = len(sources) - len(new_pains) - result.error_count
        logger.info(f"Extracted {len(new_pains)} pain points from {len(sources)} sources")

        if not new_pains:
            result.warnings.append("No pain points extracted. Check input files and pain keywords.")
            return result

        # 4. 類似クラスタリング（新規同士 + 既存との照合）
        existing = self._load_existing_pains()
        all_pains = existing + new_pains
        clustered = self.clusterer.cluster(all_pains)

        # 既存以外の新規のみを保存対象に
        existing_ids = {p.pain_id for p in existing}
        pains_to_save = [p for p in clustered if p.pain_id not in existing_ids]

        # 既存の similar_pain_ids が更新されていればそれも更新
        updated_existing = [p for p in clustered if p.pain_id in existing_ids
                            and p.similar_pain_ids]

        result.similar_linked = sum(1 for p in pains_to_save if p.similar_pain_ids)
        result.extracted = len(pains_to_save)
        result.pain_ids = [p.pain_id for p in pains_to_save]

        # 5. 保存
        if not self.dry_run:
            for pain in pains_to_save:
                self.db.save_pain_point(pain)
            for pain in updated_existing:
                self.db.save_pain_point(pain)  # 既存の類似リンクを更新

            output_path = self._save_json(clustered)
            result.output_json = output_path
            logger.info(f"Saved {len(pains_to_save)} new pain points to {output_path}")
        else:
            logger.info(f"[DRY-RUN] Would save {len(pains_to_save)} pain points")
            for p in pains_to_save[:3]:  # 先頭3件をログ出力
                logger.info(f"  [DRY-RUN] {p.pain_id[:8]}: {p.pain_summary[:60]}")

        return result

    # ------------------------------------------------------------------
    # 内部メソッド
    # ------------------------------------------------------------------

    def _collect_files(self, path: Path) -> list[Path]:
        """パス指定がファイルならそのまま、ディレクトリなら配下のJSONを収集"""
        if path.is_file():
            return [path] if path.suffix == ".json" else []
        if path.is_dir():
            # .gitkeepやサブディレクトリのファイルは除く（直下のみ）
            return sorted(f for f in path.iterdir()
                          if f.is_file() and f.suffix == ".json" and not f.name.startswith("."))
        logger.warning(f"Path does not exist: {path}")
        return []

    def _load_existing_pains(self) -> list[PainPoint]:
        """既存のpain_points.jsonとSQLiteから既存データを読む（どちらか片方でも可）"""
        # SQLiteから読む（最速）
        try:
            return self.db.list_pain_points()
        except Exception as e:
            logger.warning(f"Could not load existing pains from DB: {e}")

        # fallback: JSONファイルから読む
        json_path = self.settings.pain_points_json
        if json_path.exists():
            try:
                data = read_json(json_path)
                if isinstance(data, dict) and "pain_points" in data:
                    return [PainPoint.model_validate(p) for p in data["pain_points"]]
                if isinstance(data, list):
                    return [PainPoint.model_validate(p) for p in data]
            except Exception as e:
                logger.warning(f"Could not load existing pains from JSON: {e}")
        return []

    def _save_json(self, pains: list[PainPoint]) -> Path:
        """pain_points.json として保存する"""
        output = {
            "version": "2.0",
            "generated_at": datetime.now().isoformat(),
            "count": len(pains),
            "pain_points": [p.model_dump(mode="json") for p in pains],
        }
        path = self.settings.pain_points_json
        write_json(path, output)
        return path
