"""
共通Pydanticモデル定義

状態遷移:
  pain_collected
    → candidate_generated
    → human_approved
    → draft_created
    → editor_review
    → publish_ready
    → published
    → promo_brief_ready
    → analyzed
    → pattern_updated
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 状態定義
# ---------------------------------------------------------------------------

class ArticleStatus(str, Enum):
    """noteアーティクルのライフサイクル全状態"""
    PAIN_COLLECTED       = "pain_collected"
    CANDIDATE_GENERATED  = "candidate_generated"
    HUMAN_APPROVED       = "human_approved"
    DRAFT_CREATED        = "draft_created"
    EDITOR_REVIEW        = "editor_review"
    PUBLISH_READY        = "publish_ready"
    PUBLISHED            = "published"
    PROMO_BRIEF_READY    = "promo_brief_ready"
    ANALYZED             = "analyzed"
    PATTERN_UPDATED      = "pattern_updated"


VALID_TRANSITIONS: dict[ArticleStatus, list[ArticleStatus]] = {
    ArticleStatus.PAIN_COLLECTED:      [ArticleStatus.CANDIDATE_GENERATED],
    ArticleStatus.CANDIDATE_GENERATED: [ArticleStatus.HUMAN_APPROVED],
    ArticleStatus.HUMAN_APPROVED:      [ArticleStatus.DRAFT_CREATED],
    ArticleStatus.DRAFT_CREATED:       [ArticleStatus.EDITOR_REVIEW],
    ArticleStatus.EDITOR_REVIEW:       [ArticleStatus.PUBLISH_READY],
    ArticleStatus.PUBLISH_READY:       [ArticleStatus.PUBLISHED],
    ArticleStatus.PUBLISHED:           [ArticleStatus.PROMO_BRIEF_READY],
    ArticleStatus.PROMO_BRIEF_READY:   [ArticleStatus.ANALYZED],
    ArticleStatus.ANALYZED:            [ArticleStatus.PATTERN_UPDATED],
    ArticleStatus.PATTERN_UPDATED:     [],
}


# ---------------------------------------------------------------------------
# 入力ソースの種別
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    """pain_intakeが受け付ける入力ソースの種別"""
    POST_HISTORY    = "post_history"     # Threads運用部の投稿履歴
    COMMENT_SUMMARY = "comment_summary"  # コメント要約
    REACTION_LOG    = "reaction_log"     # 反応ログ
    FIELD_NOTE      = "field_note"       # 現場メモ
    MANUAL_MEMO     = "manual_memo"      # 手動メモ
    UNKNOWN         = "unknown"          # 判別不能


# ---------------------------------------------------------------------------
# 入力ソースの統一スキーマ（スキーマ揺れ吸収後の正規化形）
# ---------------------------------------------------------------------------

class RawSource(BaseModel):
    """
    各種入力JSONを正規化した統一スキーマ。
    SourceNormalizerが変換する。
    """
    source_id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: SourceType
    text: str = Field(..., description="抽出対象となるテキスト本文")
    post_id: Optional[str] = Field(None, description="元投稿のID（あれば）")
    tags: list[str] = Field(default_factory=list)
    engagement_total: int = Field(default=0, description="いいね+返信+リポストの合計")
    created_at: Optional[datetime] = None
    raw: dict[str, Any] = Field(default_factory=dict, description="元データ全体（デバッグ用）")

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# 読者の悩みポイント（Task 2拡張版）
# ---------------------------------------------------------------------------

class PainPoint(BaseModel):
    """
    読者の悩みを構造化したモデル。pain_intakeモジュールが生成する。

    Task 1→2 breaking changes:
        id          → pain_id
        description → original_text
        category    → related_tags (str→list[str])
        source      → source_type
        threads_post_id → source_post_id
    """
    pain_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)

    # ソース情報
    source_post_id: Optional[str] = Field(None, description="元のThreads投稿ID")
    source_type: str = Field(default="manual_memo", description="収集元の種別")

    # 悩みの内容
    original_text: str = Field(..., min_length=1, description="元テキスト（抜粋）")
    pain_summary: str = Field(..., description="悩みの要約（100字以内）")

    # スコアリング（いずれも 1〜5）
    severity: int = Field(default=1, ge=1, le=5, description="深刻度")
    urgency: int = Field(default=1, ge=1, le=5, description="緊急度")
    frequency: int = Field(default=1, ge=1, le=5, description="頻度・再現性")

    # 文脈情報
    audience_type: str = Field(default="不明", description="想定読者属性")
    situation: str = Field(default="", description="悩みが発生した状況")
    failed_attempts: list[str] = Field(default_factory=list, description="試みて失敗したこと")
    related_tags: list[str] = Field(default_factory=list, description="関連タグ")

    # クラスタリング情報
    cluster_id: Optional[str] = Field(None, description="類似グループID")
    similar_pain_ids: list[str] = Field(default_factory=list, description="類似するpain_idのリスト")

    # 元エンゲージメント（参考値）
    engagement_count: Optional[int] = Field(None, description="いいね・返信数合計")

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# トピック候補（Task 3: researcherが生成、selectorが承認）
# ---------------------------------------------------------------------------

class TopicCandidate(BaseModel):
    """
    researcher エージェントが pain_points から生成するnote記事の候補。
    NoteCandidate は将来このモデルを参照して下書き工程に進む。
    """
    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    status: ArticleStatus = Field(default=ArticleStatus.CANDIDATE_GENERATED)

    # 関連 pain
    target_pain_id_list: list[str] = Field(..., description="根拠となるPainPointのID群")

    # コンテンツ設計
    topic_title: str = Field(..., description="記事タイトル案")
    hook: str = Field(..., description="冒頭フック文（読者への問いかけ）")
    angle: str = Field(..., description="切り口・アングル")
    why_now: str = Field(..., description="今このテーマを書く理由（時事性・トレンド）")
    expected_buyer_intent: str = Field(..., description="想定購読者が買う動機")
    paid_reason: str = Field(..., description="有料にする根拠（再現性・希少性など）")
    recommended_price_range: str = Field(default="300-980円", description="推奨価格帯")
    audience_type: str = Field(default="不明", description="ターゲット読者属性")
    related_tags: list[str] = Field(default_factory=list)

    # スコア内訳（各 0〜10）
    demand_score: float = Field(default=0.0, ge=0, le=10, description="需要スコア")
    monetization_score: float = Field(default=0.0, ge=0, le=10, description="有料化しやすさ")
    threads_fit_score: float = Field(default=0.0, ge=0, le=10, description="Threads訴求適合度")
    expertise_fit_score: float = Field(default=0.0, ge=0, le=10, description="執筆者専門性適合度")
    trend_score: float = Field(default=0.0, ge=0, le=10, description="トレンド性")
    total_score: float = Field(default=0.0, ge=0, le=10, description="加重合計スコア")
    score_breakdown: dict[str, Any] = Field(
        default_factory=dict,
        description="スコア内訳（重み・各点数を保持）",
    )

    # 承認情報
    approved: bool = Field(default=False)
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class Approval(BaseModel):
    """
    人間によるトピック候補の承認記録。
    自動承認は行わず、必ずこのモデル経由で記録する。
    """
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    approved_at: datetime = Field(default_factory=datetime.now)

    selected_candidate_id: str = Field(..., description="承認したTopicCandidateのID")
    selected_by: str = Field(default="human", description="承認者識別子")
    selected_reason: Optional[str] = Field(None, description="選んだ理由（任意）")

    # 承認時スナップショット
    snapshot_score: float = Field(default=0.0, description="承認時のtotal_score")
    snapshot_title: str = Field(default="", description="承認時のtopic_title")

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# noteの候補テーマ（Task 1 後方互換維持。Task 4以降はTopicCandidateを参照）
# ---------------------------------------------------------------------------

class NoteCandidate(BaseModel):
    """researcher が生成し、selector が人間に提示する候補"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    status: ArticleStatus = Field(default=ArticleStatus.CANDIDATE_GENERATED)

    pain_point_id: str = Field(..., description="元となったPainPointのpain_id")
    title: str = Field(..., description="提案タイトル")
    angle: str = Field(..., description="切り口・アングル")
    target_reader: str = Field(..., description="ターゲット読者像")
    price: int = Field(default=300, description="想定価格（円）。0=無料")
    estimated_chars: int = Field(default=2000, description="想定文字数")

    # 人間の承認情報
    approved: bool = Field(default=False)
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# noteの下書き
# ---------------------------------------------------------------------------

class NoteDraft(BaseModel):
    """
    note_writerが生成し、editorがレビューする下書き。

    Task 4 拡張:
        subtitle, free_part_markdown, paid_part_markdown を追加。
        quality_score を 0-10 → 0-100 スケールに変更。
        body_markdown は free_part + paid_part から自動計算。
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: ArticleStatus = Field(default=ArticleStatus.DRAFT_CREATED)

    candidate_id: str = Field(..., description="元となったTopicCandidate.candidate_id")
    title: str = Field(..., description="記事タイトル")
    subtitle: str = Field(default="", description="サブタイトル（キャッチコピー）")

    # コンテンツ（無料・有料を明確に分離）
    free_part_markdown: str = Field(default="", description="無料公開パート（Markdown）")
    paid_part_markdown: str = Field(default="", description="有料パート（Markdown）")

    # note投稿用の結合本文（model_post_init で自動計算）
    body_markdown: str = Field(default="", description="無料+有料の結合本文（自動計算）")
    char_count: int = Field(default=0, description="文字数（自動計算）")

    # 品質・レビュー（0-100 スケール）
    quality_score: Optional[float] = Field(None, ge=0, le=100, description="品質スコア（0-100）")
    editor_notes: Optional[str] = Field(None, description="editorからの総括フィードバック")
    editor_feedback: list[dict] = Field(
        default_factory=list,
        description="チェック項目別フィードバック [{'item': str, 'score': float, 'max_score': float, 'comment': str}]",
    )

    # 公開情報
    note_url: Optional[str] = None
    published_at: Optional[datetime] = None
    price: int = Field(default=300)
    tags: list[str] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        # body_markdown が空で free/paid が設定されていれば結合
        if not self.body_markdown and (self.free_part_markdown or self.paid_part_markdown):
            parts: list[str] = []
            if self.free_part_markdown:
                parts.append(self.free_part_markdown)
            if self.paid_part_markdown:
                parts.append("\n---\n\n<!-- 有料パートここから -->\n\n" + self.paid_part_markdown)
            self.body_markdown = "\n\n".join(parts)
        self.char_count = len(self.body_markdown)

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# note公開メタデータ（Task 5: NotePublisherAgentが生成）
# ---------------------------------------------------------------------------

class NotePublication(BaseModel):
    """
    noteへの公開を記録するメタデータ。
    manual モードではメタデータ作成のみ行い、実際の投稿は人間が行う。
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    published_at: datetime = Field(default_factory=datetime.now)

    draft_id: str = Field(..., description="元のNoteDraftのID")
    note_title: str = Field(..., description="公開済み記事タイトル")
    note_url: Optional[str] = Field(None, description="公開URL（確定後に設定）")
    note_slug: Optional[str] = Field(None, description="noteスラッグ（URL未確定時の参照用）")
    price: int = Field(default=300, description="販売価格（円）")
    tags: list[str] = Field(default_factory=list)

    attribution_id: str = Field(..., description="キャンペーン帰属ID（Threads運用部に渡す）")
    campaign_id: Optional[str] = Field(None, description="関連するキャンペーンID")

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# キャンペーン（noteとThreadsプロモの紐付け管理）
# ---------------------------------------------------------------------------

class Campaign(BaseModel):
    """
    1記事の公開プロモーションを1キャンペーンとして管理する。
    attribution_id を介してThreads投稿からの成果を帰属できる。
    """
    campaign_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)

    name: str = Field(..., description="キャンペーン名（例: claude-code-20260407）")
    attribution_id: str = Field(..., description="帰属トラッキングID")
    draft_id: str = Field(..., description="対象のNoteDraftのID")
    publication_id: Optional[str] = Field(None, description="NotePublicationのID（公開後に設定）")
    note_url: Optional[str] = Field(None, description="公開URL")
    status: str = Field(default="active", description="active | closed")

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# プロモブリーフ（Threads運用部への引き渡し資材）
# ---------------------------------------------------------------------------

class PromoBrief(BaseModel):
    """
    Threads運用部に渡す投稿ブリーフ。
    本システムはThreads投稿を直接行わない。

    Task 5 拡張:
        note_id, attribution_id, article_summary, target_audience,
        target_pains, promotion_angle, avoid_expressions,
        preferred_post_window, memo を追加。
        既存フィールドは後方互換を維持。
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)

    # 元データ参照
    draft_id: str = Field(..., description="元となったNoteDraftのID")
    note_id: str = Field(default="", description="NotePublicationのID（公開後に設定）")
    attribution_id: str = Field(default="", description="キャンペーン帰属ID")

    # 記事情報
    note_url: str = Field(default="", description="公開済みnote URL（未確定時は空文字）")
    article_title: str = Field(..., description="記事タイトル")
    article_summary: str = Field(default="", description="記事の要約（2-3文）")

    # ターゲット情報
    target_audience: str = Field(default="", description="ターゲット読者層")
    target_pains: list[str] = Field(default_factory=list, description="解決する悩みリスト")
    target_pain: str = Field(default="", description="ターゲットの悩み一言まとめ（後方互換）")

    # プロモーション設計
    promotion_angle: str = Field(default="", description="プロモーションの切り口")
    key_message: str = Field(..., description="訴求したいメインメッセージ")
    avoid_expressions: list[str] = Field(default_factory=list, description="使用禁止表現リスト")
    preferred_post_window: str = Field(default="平日朝7-9時", description="推奨投稿時間帯")

    # Threads運用部向け素材
    hook_options: list[str] = Field(default_factory=list, description="冒頭フック案（複数）")
    recommended_hashtags: list[str] = Field(default_factory=list)
    cta_note: str = Field(default="", description="noteへの誘導文言の方向性")
    memo: Optional[str] = Field(None, description="Threads運用部への補足メモ")
    notes_for_operator: Optional[str] = Field(None, description="補足メモ（旧フィールド、memoに統合）")

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# パフォーマンス記録（Threads運用部から受け取る）
# ---------------------------------------------------------------------------

class PerformanceRecord(BaseModel):
    """
    Threads運用部から受け取る投稿成績。
    performance_importerがJSONを読んでDBに保存する。

    Task 6 拡張:
        promo_brief_id を Optional に変更（attribution_id でも突合できるため）。
        Threads成績の新フィールドを追加（impressions, saves, note_clicks, ctr, etc.）。
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    imported_at: datetime = Field(default_factory=datetime.now)

    # 突合キー（いずれか1つ以上が必須）
    promo_brief_id: Optional[str] = Field(None, description="対応するPromoBriefのID")
    attribution_id: Optional[str] = Field(None, description="キャンペーン帰属ID")
    note_id: Optional[str] = Field(None, description="NotePublicationのID")

    # Threads投稿情報
    threads_post_id: str = Field(default="", description="Threads投稿ID（運用部から提供）")
    posted_at: Optional[datetime] = Field(None, description="投稿日時")
    measured_at: Optional[datetime] = Field(None, description="計測日時")
    post_type: str = Field(default="original", description="投稿種別: original | reply | repost")

    # Threadsエンゲージメント
    impressions: int = Field(default=0, description="表示数（インプレッション）")
    likes: int = Field(default=0)
    replies: int = Field(default=0)
    reposts: int = Field(default=0)
    saves: int = Field(default=0)
    views: int = Field(default=0, description="閲覧数（impressionsの別表記）")

    # note遷移
    note_clicks: int = Field(default=0, description="noteへのクリック数")
    ctr: Optional[float] = Field(None, description="クリック率（note_clicks / impressions）")

    # note成績
    note_views: Optional[int] = Field(None, description="note閲覧数")
    note_purchases: Optional[int] = Field(None, description="note購入数")
    note_revenue: Optional[int] = Field(None, description="note売上（円）")

    # 定性情報（Threads運用部からのメモ）
    good_phrases: list[str] = Field(default_factory=list, description="反応が良かったフレーズ")
    bad_phrases: list[str] = Field(default_factory=list, description="反応が悪かったフレーズ")
    comment_trends: list[str] = Field(default_factory=list, description="コメント傾向")
    field_memo: Optional[str] = Field(None, description="運用部からのメモ")

    model_config = ConfigDict(use_enum_values=True)

    @property
    def effective_impressions(self) -> int:
        """表示数（impressions と views の両方を考慮して大きい方を使う）"""
        return max(self.impressions, self.views)

    @property
    def reactions(self) -> int:
        """総反応数 (likes + replies + reposts + saves)"""
        return self.likes + self.replies + self.reposts + self.saves


# ---------------------------------------------------------------------------
# 分析レポート（Task 6: NoteAnalyzerAgentが生成）
# ---------------------------------------------------------------------------

class ThemeKPI(BaseModel):
    """アングル（テーマ）別KPI集計"""
    angle: str
    record_count: int = 0
    total_impressions: int = 0
    total_reactions: int = 0
    avg_reaction_rate: float = 0.0
    total_note_clicks: int = 0
    avg_transition_rate: float = 0.0
    total_note_views: int = 0
    total_note_purchases: int = 0
    avg_purchase_rate: float = 0.0
    total_revenue: int = 0

    model_config = ConfigDict(use_enum_values=True)


class PriceKPI(BaseModel):
    """価格帯別KPI集計"""
    price: int
    record_count: int = 0
    total_note_views: int = 0
    total_note_purchases: int = 0
    avg_purchase_rate: float = 0.0
    total_revenue: int = 0

    model_config = ConfigDict(use_enum_values=True)


class AnalyticsReport(BaseModel):
    """
    NoteAnalyzerAgentが生成する分析レポート。
    KnowledgeBaseAgentはこのレポートを参照してwinning_patterns.jsonを更新する。
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: datetime = Field(default_factory=datetime.now)
    period_label: str = Field(default="", description="分析対象期間ラベル（例: 2026-W14）")
    record_count: int = 0

    # 全体KPI
    total_impressions: int = 0
    total_reactions: int = 0
    avg_reaction_rate: float = 0.0        # 反応率 = reactions / impressions
    total_note_clicks: int = 0
    avg_transition_rate: float = 0.0      # 遷移率 = note_clicks / impressions
    total_note_views: int = 0
    total_note_purchases: int = 0
    avg_purchase_rate: float = 0.0        # 購入率 = note_purchases / note_views
    total_revenue: int = 0

    # 内訳
    by_theme: list[ThemeKPI] = Field(default_factory=list)
    by_price: list[PriceKPI] = Field(default_factory=list)

    # インサイト（人間が読める形式）
    top_performing_angles: list[str] = Field(default_factory=list)
    underperforming_angles: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    # knowledge_base 連携用
    winning_angles: list[str] = Field(default_factory=list, description="購入率5%以上のアングル")
    winning_draft_ids: list[str] = Field(default_factory=list, description="成績優秀なDraft ID")

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# dry-run用ダミーデータファクトリ
# ---------------------------------------------------------------------------

def make_dummy_pain_point() -> PainPoint:
    return PainPoint(
        original_text="Claude Codeを使ってみたいが、非エンジニアでも使えるか不安。コマンドが分からなくて途中で諦めた",
        pain_summary="非エンジニアがClaude Codeを使おうとして諦めた",
        source_type="manual_memo",
        severity=3,
        urgency=2,
        frequency=3,
        audience_type="非エンジニア",
        situation="Claude Codeの初期セットアップ",
        failed_attempts=["公式ドキュメントを読んだが理解できなかった"],
        related_tags=["AI", "ClaudeCode", "非エンジニア", "副業"],
    )


def make_dummy_candidate(pain_id: str) -> NoteCandidate:
    return NoteCandidate(
        pain_point_id=pain_id,
        title="【非エンジニアが2週間試した】Claude Code、正直に書く",
        angle="体験談＋本音レポート",
        target_reader="副業でAIを活用したいスキルワーカー",
        price=300,
        approved=True,
        approved_at=datetime.now(),
        status=ArticleStatus.HUMAN_APPROVED,
    )


def make_dummy_draft(candidate_id: str, price: int = 300) -> NoteDraft:
    free_part = (
        "# 【非エンジニアが2週間試した】Claude Code、正直に書く\n\n"
        "「自分には無理かも」と思ったことありませんか？\n\n"
        "副業でAIを使い始めて半年の私が、Claude Codeを2週間試した正直な記録です。\n\n"
        "## なぜうまくいかないのか\n\n"
        "Claude Codeはエンジニア向けのツールという印象が強く、"
        "非エンジニアが踏み出せない理由もここにあります。\n\n"
        "## この記事でわかること\n\n"
        "- 非エンジニアが最初に詰まる箇所\n"
        "- 2週間で実際に使えるようになった手順\n"
        "- コードを書かずに活用できる具体的なシーン3つ\n\n"
        "---\n\n**有料パート（300円）の内容：**\n\n"
        "- 実際に使ったプロンプトの具体例\n"
        "- つまずいた場面と抜け出し方\n"
        "- 1日30分でできる始め方ロードマップ\n"
    )
    paid_part = (
        "## 実践ステップ\n\n"
        "### ステップ1: 最初の設定（所要時間: 30分）\n\n"
        "まず、Claude Codeを起動してプロジェクトディレクトリを指定します。\n"
        "非エンジニアが最初に詰まるのはここです。具体的には以下の手順で進めます。\n\n"
        "1. ターミナルを開く（Macはアプリケーション→ユーティリティ→ターミナル）\n"
        "2. `claude` と入力してEnterキーを押す\n"
        "3. プロンプトに「日本語で答えてください」と最初に入力する\n\n"
        "### ステップ2: 最初のタスクを実行する（所要時間: 15分）\n\n"
        "最初は小さなタスクから始めます。"
        "「このテキストファイルの誤字を修正して」のような指示が最適です。\n\n"
        "### ステップ3: 失敗したときの対処法\n\n"
        "思った通りにいかないときは、指示を具体的にするだけで解決することが多いです。\n\n"
        "---\n\n"
        "## この記事が向いている人・向いていない人\n\n"
        "**向いている人**\n\n"
        "- AIを使って副業収入を増やしたいスキルワーカー\n"
        "- コードは書けないがAIツールは積極的に試したい人\n"
        "- 具体的な手順と実体験ベースの情報がほしい人\n\n"
        "**向いていない人（購入前にご確認ください）**\n\n"
        "- すでにClaude Codeを使いこなしているエンジニアの方\n"
        "- AIツールの理論的な解説を求めている方\n\n"
        "---\n\n"
        "## まとめ\n\n"
        "非エンジニアでも、Claude Codeは使えます。"
        "最初の30分さえ乗り越えれば、日常的なタスクに使えるレベルに達することができます。\n"
    )
    return NoteDraft(
        candidate_id=candidate_id,
        title="【非エンジニアが2週間試した】Claude Code、正直に書く",
        subtitle="コードが書けない私が、2週間試して分かったこと",
        free_part_markdown=free_part,
        paid_part_markdown=paid_part,
        price=price,
        tags=["AI", "ClaudeCode", "副業"],
        quality_score=82.0,
        status=ArticleStatus.PUBLISH_READY,
    )


def make_dummy_performance_record(
    promo_brief_id: Optional[str] = None,
    attribution_id: Optional[str] = "attr-20260407-abc123",
    note_id: Optional[str] = "pub-001",
) -> PerformanceRecord:
    return PerformanceRecord(
        promo_brief_id=promo_brief_id,
        attribution_id=attribution_id,
        note_id=note_id,
        threads_post_id="threads_post_001",
        posted_at=datetime.now(),
        measured_at=datetime.now(),
        post_type="original",
        impressions=5000,
        likes=250,
        replies=20,
        reposts=15,
        saves=30,
        views=5000,
        note_clicks=150,
        ctr=0.03,
        note_views=80,
        note_purchases=5,
        note_revenue=1500,
        good_phrases=["非エンジニアでも使える", "2週間で実践"],
        bad_phrases=["初心者向け"],
        comment_trends=["具体的な手順が知りたい"],
        field_memo="朝投稿が反応良かった",
    )


def make_dummy_publication(draft_id: str) -> NotePublication:
    attribution_id = f"attr-20260407-{draft_id[:6]}"
    return NotePublication(
        draft_id=draft_id,
        note_title="【非エンジニアが2週間試した】Claude Code、正直に書く",
        note_url="https://note.com/example/n/nxxxxxxxx",
        note_slug="claude-code-2weeks",
        price=300,
        tags=["AI", "ClaudeCode", "副業"],
        attribution_id=attribution_id,
    )


def make_dummy_campaign(draft_id: str, publication_id: str) -> Campaign:
    attribution_id = f"attr-20260407-{draft_id[:6]}"
    return Campaign(
        name="claude-code-20260407",
        attribution_id=attribution_id,
        draft_id=draft_id,
        publication_id=publication_id,
        note_url="https://note.com/example/n/nxxxxxxxx",
        status="active",
    )


def make_dummy_promo_brief(draft_id: str, note_url: str) -> PromoBrief:
    return PromoBrief(
        draft_id=draft_id,
        note_id="dummy-publication-id",
        attribution_id="attr-20260407-dummy1",
        note_url=note_url,
        article_title="【非エンジニアが2週間試した】Claude Code、正直に書く",
        article_summary="非エンジニアが2週間Claude Codeを使った正直な体験レポートです。"
                        "最初の壁とその乗り越え方、実際に使えるシーンを具体的にまとめています。",
        target_audience="副業でAIを活用したいスキルワーカー・非エンジニア",
        target_pains=[
            "AIツールを使いたいがエンジニアじゃないから無理かもと思っている",
            "Claude Codeの使い方が分からず諦めた",
        ],
        target_pain="AIツールを使いたいが、エンジニアじゃないから無理かもと思っている",
        promotion_angle="体験談＋本音レポート",
        key_message="非エンジニアでもClaude Codeは使えるが、壁もある（本音レポ）",
        avoid_expressions=["99%が", "絶対に稼げる", "今すぐやらないと損"],
        preferred_post_window="平日朝7-9時",
        hook_options=[
            "非エンジニアが2週間Claude Codeを使った結果→正直に書きます",
            "「コード書けなくても使える」は本当か？2週間検証した",
        ],
        recommended_hashtags=["AI", "ClaudeCode", "副業", "生成AI"],
        cta_note="「詳しい実践ログはnoteにまとめました」的な自然な誘導",
        memo="体験談メインなので煽り不要。本音トーンで投稿してください",
        notes_for_operator="体験談メインなので煽り不要。本音トーンで投稿してください",
    )
