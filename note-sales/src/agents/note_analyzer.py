"""
note_analyzer エージェント

PerformanceRecord を集計して AnalyticsReport を生成する。

KPI一覧:
  - Threads表示数 (total_impressions)
  - Threads反応率 = reactions / impressions
  - Threads→note遷移率 = note_clicks / impressions
  - note閲覧数 (total_note_views)
  - note購入数 (total_note_purchases)
  - note購入率 = note_purchases / note_views
  - 売上 (total_revenue)
  - テーマ別成績 (by_theme: angle単位でグループ化)
  - 価格別成績 (by_price: draft.price単位でグループ化)

設計方針:
  - KPI計算関数は純粋関数として分離（テスト容易性）
  - データ結合に失敗しても angle="不明" で集計継続
  - [FUTURE_LLM] recommendations 生成を Claude API に置き換え可能
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.adapters.storage_json import (
    save_analytics_report,
    save_weekly_report,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import (
    AnalyticsReport,
    NoteDraft,
    PerformanceRecord,
    PriceKPI,
    ThemeKPI,
    TopicCandidate,
)
from src.core.settings import AppSettings

logger = get_logger(__name__)

# アングル不明時のラベル
_UNKNOWN_ANGLE = "不明"
_UNKNOWN_PRICE = 0


# ---------------------------------------------------------------------------
# 純粋なKPI計算関数（テスト容易）
# ---------------------------------------------------------------------------

def calc_reaction_rate(
    likes: int, replies: int, reposts: int, saves: int, impressions: int
) -> float:
    """反応率 = (likes + replies + reposts + saves) / impressions"""
    if impressions <= 0:
        return 0.0
    return (likes + replies + reposts + saves) / impressions


def calc_transition_rate(note_clicks: int, impressions: int) -> float:
    """遷移率 = note_clicks / impressions"""
    if impressions <= 0:
        return 0.0
    return note_clicks / impressions


def calc_purchase_rate(note_purchases: int, note_views: int) -> float:
    """購入率 = note_purchases / note_views"""
    if note_views <= 0:
        return 0.0
    return note_purchases / note_views


def calc_ctr(note_clicks: int, impressions: int) -> float:
    """CTR = note_clicks / impressions"""
    return calc_transition_rate(note_clicks, impressions)


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------

@dataclass
class EnrichedRecord:
    """PerformanceRecord に Draft / Candidate の情報を結合したもの"""
    record: PerformanceRecord
    draft: Optional[NoteDraft] = None
    candidate: Optional[TopicCandidate] = None

    @property
    def angle(self) -> str:
        if self.candidate and self.candidate.angle:
            return self.candidate.angle
        return _UNKNOWN_ANGLE

    @property
    def price(self) -> int:
        return self.draft.price if self.draft else _UNKNOWN_PRICE

    @property
    def draft_id(self) -> str:
        return self.draft.id if self.draft else ""

    @property
    def effective_impressions(self) -> int:
        r = self.record
        return max(r.impressions, r.views)

    @property
    def reactions(self) -> int:
        r = self.record
        return r.likes + r.replies + r.reposts + r.saves


@dataclass
class AnalyzeResult:
    """NoteAnalyzerAgent.run() の結果"""
    report: Optional[AnalyticsReport] = None
    status: str = "ok"      # "ok" | "skipped" | "error" | "no_data"
    message: str = ""
    output_json: Optional[Path] = None
    weekly_report_path: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

class NoteAnalyzerAgent:
    """
    PerformanceRecord を集計して AnalyticsReport を生成するエージェント。

    使い方:
        agent = NoteAnalyzerAgent(settings=settings)
        result = agent.run()
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)
        self.good_reaction_rate = settings.analytics_good_reaction_rate
        self.good_transition_rate = settings.analytics_good_transition_rate
        self.good_purchase_rate = settings.analytics_good_purchase_rate

    def run(self) -> AnalyzeResult:
        """全PerformanceRecordを集計してAnalyticsReportを生成する。"""
        records = self.db.list_performance()
        if not records:
            return AnalyzeResult(
                status="no_data",
                message="分析対象のパフォーマンスデータがありません。import-performance を先に実行してください。",
            )

        # 各レコードに Draft / Candidate の情報を結合
        enriched = [self._enrich(r) for r in records]

        # KPI を集計
        report = self._build_report(enriched, records)

        if self.dry_run:
            return AnalyzeResult(
                report=report,
                status="skipped",
                message=(
                    f"[DRY-RUN] {report.record_count}件分析 "
                    f"purchase_rate={report.avg_purchase_rate:.1%}"
                ),
            )

        # レポートを保存
        output_path = save_analytics_report(report, self.settings.analytics_output_json)
        self.db.save_analytics_report(report)

        # 週次レポートMarkdownを生成・保存
        md = self._generate_weekly_markdown(report)
        week_label = datetime.now().strftime("%Y-W%V")
        weekly_path = save_weekly_report(md, self.settings.weekly_report_dir, week_label)

        result = AnalyzeResult(
            report=report,
            status="ok",
            message=(
                f"分析完了: {report.record_count}件 "
                f"purchase_rate={report.avg_purchase_rate:.1%} "
                f"revenue=¥{report.total_revenue:,}"
            ),
            output_json=output_path,
            weekly_report_path=weekly_path,
        )
        return result

    # ------------------------------------------------------------------
    # データ結合
    # ------------------------------------------------------------------

    def _enrich(self, record: PerformanceRecord) -> EnrichedRecord:
        """PerformanceRecord に Draft / Candidate を結合する。"""
        draft: Optional[NoteDraft] = None
        candidate: Optional[TopicCandidate] = None

        # 結合戦略1: promo_brief_id → PromoBrief → draft_id
        if record.promo_brief_id:
            try:
                brief = self.db.get_promo_brief(record.promo_brief_id)
                if brief:
                    draft = self.db.get_draft(brief.draft_id)
            except Exception as e:
                logger.debug(f"promo_brief join failed: {e}")

        # 結合戦略2: attribution_id → Campaign → draft_id
        if draft is None and record.attribution_id:
            try:
                campaign = self.db.get_campaign_by_draft_id.__func__  # type: ignore
            except Exception:
                pass
            try:
                campaigns = self.db.list_campaigns()
                for c in campaigns:
                    if c.attribution_id == record.attribution_id:
                        draft = self.db.get_draft(c.draft_id)
                        break
            except Exception as e:
                logger.debug(f"campaign join failed: {e}")

        # 結合戦略3: note_id → NotePublication → draft_id
        if draft is None and record.note_id:
            try:
                pub = self.db.get_publication(record.note_id)
                if pub:
                    draft = self.db.get_draft(pub.draft_id)
            except Exception as e:
                logger.debug(f"publication join failed: {e}")

        # TopicCandidate を取得
        if draft:
            try:
                candidate = self.db.get_topic_candidate(draft.candidate_id)
            except Exception as e:
                logger.debug(f"candidate join failed: {e}")

        return EnrichedRecord(record=record, draft=draft, candidate=candidate)

    # ------------------------------------------------------------------
    # KPI集計
    # ------------------------------------------------------------------

    def _build_report(
        self,
        enriched: list[EnrichedRecord],
        records: list[PerformanceRecord],
    ) -> AnalyticsReport:
        """EnrichedRecord リストから AnalyticsReport を構築する。"""
        # 全体集計
        total_impressions = sum(e.effective_impressions for e in enriched)
        total_reactions = sum(e.reactions for e in enriched)
        total_note_clicks = sum(e.record.note_clicks for e in enriched)
        total_note_views = sum(
            (e.record.note_views or 0) for e in enriched
        )
        total_note_purchases = sum(
            (e.record.note_purchases or 0) for e in enriched
        )
        total_revenue = sum(
            (e.record.note_revenue or 0) for e in enriched
        )

        avg_reaction_rate = calc_reaction_rate(
            sum(e.record.likes for e in enriched),
            sum(e.record.replies for e in enriched),
            sum(e.record.reposts for e in enriched),
            sum(e.record.saves for e in enriched),
            total_impressions,
        )
        avg_transition_rate = calc_transition_rate(total_note_clicks, total_impressions)
        avg_purchase_rate = calc_purchase_rate(total_note_purchases, total_note_views)

        # テーマ別
        by_theme = self._aggregate_by_theme(enriched)

        # 価格別
        by_price = self._aggregate_by_price(enriched)

        # インサイト
        top_angles = [
            t.angle for t in sorted(by_theme, key=lambda x: x.avg_purchase_rate, reverse=True)
            if t.avg_purchase_rate >= self.good_purchase_rate
        ]
        under_angles = [
            t.angle for t in by_theme
            if t.avg_purchase_rate < self.good_purchase_rate / 2 and t.record_count >= 2
        ]
        recommendations = self._generate_recommendations(
            avg_reaction_rate, avg_transition_rate, avg_purchase_rate,
            by_theme, by_price, enriched,
        )

        # knowledge_base 連携用
        winning_angles = top_angles
        winning_draft_ids = list({
            e.draft_id for e in enriched
            if e.draft_id and (e.record.note_purchases or 0) >= 3
        })

        week_label = datetime.now().strftime("%Y-W%V")
        return AnalyticsReport(
            period_label=week_label,
            record_count=len(records),
            total_impressions=total_impressions,
            total_reactions=total_reactions,
            avg_reaction_rate=round(avg_reaction_rate, 4),
            total_note_clicks=total_note_clicks,
            avg_transition_rate=round(avg_transition_rate, 4),
            total_note_views=total_note_views,
            total_note_purchases=total_note_purchases,
            avg_purchase_rate=round(avg_purchase_rate, 4),
            total_revenue=total_revenue,
            by_theme=by_theme,
            by_price=by_price,
            top_performing_angles=top_angles,
            underperforming_angles=under_angles,
            recommendations=recommendations,
            winning_angles=winning_angles,
            winning_draft_ids=winning_draft_ids,
        )

    def _aggregate_by_theme(self, enriched: list[EnrichedRecord]) -> list[ThemeKPI]:
        """アングル別に集計する。"""
        groups: dict[str, list[EnrichedRecord]] = defaultdict(list)
        for e in enriched:
            groups[e.angle].append(e)

        result = []
        for angle, items in sorted(groups.items()):
            imp = sum(i.effective_impressions for i in items)
            reac = sum(i.reactions for i in items)
            clicks = sum(i.record.note_clicks for i in items)
            views = sum((i.record.note_views or 0) for i in items)
            purchases = sum((i.record.note_purchases or 0) for i in items)
            revenue = sum((i.record.note_revenue or 0) for i in items)

            result.append(ThemeKPI(
                angle=angle,
                record_count=len(items),
                total_impressions=imp,
                total_reactions=reac,
                avg_reaction_rate=round(calc_reaction_rate(
                    sum(i.record.likes for i in items),
                    sum(i.record.replies for i in items),
                    sum(i.record.reposts for i in items),
                    sum(i.record.saves for i in items),
                    imp,
                ), 4),
                total_note_clicks=clicks,
                avg_transition_rate=round(calc_transition_rate(clicks, imp), 4),
                total_note_views=views,
                total_note_purchases=purchases,
                avg_purchase_rate=round(calc_purchase_rate(purchases, views), 4),
                total_revenue=revenue,
            ))
        return result

    def _aggregate_by_price(self, enriched: list[EnrichedRecord]) -> list[PriceKPI]:
        """価格別に集計する。"""
        groups: dict[int, list[EnrichedRecord]] = defaultdict(list)
        for e in enriched:
            groups[e.price].append(e)

        result = []
        for price, items in sorted(groups.items()):
            views = sum((i.record.note_views or 0) for i in items)
            purchases = sum((i.record.note_purchases or 0) for i in items)
            revenue = sum((i.record.note_revenue or 0) for i in items)
            result.append(PriceKPI(
                price=price,
                record_count=len(items),
                total_note_views=views,
                total_note_purchases=purchases,
                avg_purchase_rate=round(calc_purchase_rate(purchases, views), 4),
                total_revenue=revenue,
            ))
        return result

    def _generate_recommendations(
        self,
        reaction_rate: float,
        transition_rate: float,
        purchase_rate: float,
        by_theme: list[ThemeKPI],
        by_price: list[PriceKPI],
        enriched: list[EnrichedRecord],
    ) -> list[str]:
        """
        [FUTURE_LLM] ルールベースで推奨アクションを生成する。
        将来 Claude API に置き換え可能。
        """
        recs = []

        if reaction_rate >= self.good_reaction_rate:
            recs.append(
                f"Threads反応率 {reaction_rate:.1%} は良好です。"
                "現在のフック・投稿スタイルを維持してください。"
            )
        else:
            recs.append(
                f"Threads反応率 {reaction_rate:.1%} は改善余地があります。"
                "フック文の見直しとgood_phrasesの活用を検討してください。"
            )

        if transition_rate >= self.good_transition_rate:
            recs.append(
                f"note遷移率 {transition_rate:.1%} は良好です。CTA文言は効果的です。"
            )
        else:
            recs.append(
                f"note遷移率 {transition_rate:.1%} は低めです。"
                "CTA文言を「詳しくはnoteに→」形式に変更することを推奨します。"
            )

        if purchase_rate >= self.good_purchase_rate:
            recs.append(
                f"note購入率 {purchase_rate:.1%} は目標を達成しています。"
                "現在の価格設定と内容構成を継続してください。"
            )
        else:
            recs.append(
                f"note購入率 {purchase_rate:.1%} は改善余地があります。"
                "無料パートの価値提供を強化し、有料への橋渡しを明確にしてください。"
            )

        # 最高成績アングルの推薦
        if by_theme:
            best = max(by_theme, key=lambda t: t.avg_purchase_rate)
            if best.avg_purchase_rate > 0:
                recs.append(
                    f"「{best.angle}」アングルが最高購入率 {best.avg_purchase_rate:.1%} です。"
                    "次の記事テーマに優先的に採用することを推奨します。"
                )

        # good_phrasesのまとめ
        all_good = []
        for e in enriched:
            all_good.extend(e.record.good_phrases)
        if all_good:
            top_phrases = list(dict.fromkeys(all_good))[:3]
            recs.append(
                f"効果的だったフレーズ: {', '.join(top_phrases)}。"
                "次回の投稿でも積極的に使用してください。"
            )

        return recs

    # ------------------------------------------------------------------
    # 週次レポートMarkdown生成
    # ------------------------------------------------------------------

    def _generate_weekly_markdown(self, report: AnalyticsReport) -> str:
        """AnalyticsReport から週次レポートMarkdownを生成する。"""
        now = datetime.now()
        lines = [
            f"# 週次レポート {report.period_label}",
            f"\n生成日時: {now.strftime('%Y-%m-%d %H:%M')}",
            "\n## サマリー\n",
            "| KPI | 値 |",
            "|---|---|",
            f"| Threads総表示数 | {report.total_impressions:,} |",
            f"| Threads総反応数 | {report.total_reactions:,} |",
            f"| Threads反応率 | {report.avg_reaction_rate:.1%} |",
            f"| Threads→note遷移率 | {report.avg_transition_rate:.1%} |",
            f"| note総閲覧数 | {report.total_note_views:,} |",
            f"| note購入数 | {report.total_note_purchases}件 |",
            f"| note購入率 | {report.avg_purchase_rate:.1%} |",
            f"| 総売上 | ¥{report.total_revenue:,} |",
        ]

        if report.by_theme:
            lines += [
                "\n## テーマ別成績\n",
                "| アングル | 件数 | 表示数 | 反応率 | 遷移率 | 購入率 | 売上 |",
                "|---|---|---|---|---|---|---|",
            ]
            for t in sorted(report.by_theme, key=lambda x: x.avg_purchase_rate, reverse=True):
                lines.append(
                    f"| {t.angle} | {t.record_count} "
                    f"| {t.total_impressions:,} "
                    f"| {t.avg_reaction_rate:.1%} "
                    f"| {t.avg_transition_rate:.1%} "
                    f"| {t.avg_purchase_rate:.1%} "
                    f"| ¥{t.total_revenue:,} |"
                )

        if report.by_price:
            lines += [
                "\n## 価格帯別成績\n",
                "| 価格 | 件数 | 閲覧数 | 購入数 | 購入率 | 売上 |",
                "|---|---|---|---|---|---|",
            ]
            for p in sorted(report.by_price, key=lambda x: x.price):
                price_label = f"¥{p.price:,}" if p.price > 0 else "無料"
                lines.append(
                    f"| {price_label} | {p.record_count} "
                    f"| {p.total_note_views:,} "
                    f"| {p.total_note_purchases}件 "
                    f"| {p.avg_purchase_rate:.1%} "
                    f"| ¥{p.total_revenue:,} |"
                )

        if report.recommendations:
            lines += ["\n## 推奨アクション\n"]
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {rec}")

        if report.winning_angles:
            lines += ["\n## 勝ちパターン候補\n"]
            for angle in report.winning_angles:
                lines.append(f"- {angle}")

        return "\n".join(lines) + "\n"
