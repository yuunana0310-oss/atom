"""
knowledge_base エージェント

AnalyticsReport を読み込み、winning_patterns.json を更新する。

更新ルール:
  - 購入率 >= good_purchase_rate のアングル → monetization_boost +0.2 (上限 5.0)
  - 反応率 >= good_reaction_rate のアングル → threads_fit_boost +0.2 (上限 5.0)
  - 件数 < min_records_for_pattern のアングルは更新しない
  - 実績データを "learned" セクションに追記する

winning_patterns.json の構造:
  - title_patterns: タイトルパターンリスト
  - angle_patterns: アングルパターンリスト（researcher が読む）
  - price_rules: 価格ルール
  - learned: 実測データ（knowledge_base が更新する）

設計方針:
  - researcher が読む既存フィールドの構造を壊さない
  - 経験的データは "learned" セクションに分離する
  - analytics_report.json が存在しない場合はスキップ
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.adapters.storage_json import load_analytics_report, read_json, write_json
from src.core.logger import get_logger
from src.core.settings import AppSettings

logger = get_logger(__name__)

# ブースト値の上限・下限
_BOOST_MAX = 5.0
_BOOST_MIN = 0.0
_BOOST_STEP = 0.2


# ---------------------------------------------------------------------------
# 結果データクラス
# ---------------------------------------------------------------------------

@dataclass
class UpdateResult:
    """KnowledgeBaseAgent.run() の結果"""
    patterns_updated: int = 0
    patterns_added: int = 0
    status: str = "ok"      # "ok" | "skipped" | "error" | "no_report"
    message: str = ""
    output_json: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

class KnowledgeBaseAgent:
    """
    AnalyticsReport を参照して winning_patterns.json を更新するエージェント。

    使い方:
        agent = KnowledgeBaseAgent(settings=settings)
        result = agent.run()
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.good_reaction_rate = settings.analytics_good_reaction_rate
        self.good_purchase_rate = settings.analytics_good_purchase_rate
        self.min_records = settings.analytics_min_records_for_pattern

    def run(self) -> UpdateResult:
        """最新のAnalyticsReportを読み込み、winning_patterns.jsonを更新する。"""
        # 1. AnalyticsReport をロード
        report = load_analytics_report(self.settings.analytics_output_json)
        if report is None:
            return UpdateResult(
                status="no_report",
                message=(
                    "analytics_report.json が存在しません。"
                    "analyze-note を先に実行してください。"
                ),
            )

        # 2. winning_patterns.json をロード
        patterns_path = self.settings.winning_patterns_json
        patterns = self._load_patterns(patterns_path)

        # 3. パターンを更新
        result = UpdateResult()
        updated_patterns = self._update_angle_patterns(patterns, report, result)

        # 4. learned セクションを更新
        updated_patterns = self._update_learned_section(updated_patterns, report)

        if self.dry_run:
            result.status = "skipped"
            result.message = (
                f"[DRY-RUN] 更新予定: {result.patterns_updated}件, "
                f"追加予定: {result.patterns_added}件"
            )
            return result

        # 5. 保存
        output_path = self._save_patterns(updated_patterns, patterns_path)
        result.output_json = output_path
        result.status = "ok"
        result.message = (
            f"winning_patterns.json 更新完了: "
            f"更新={result.patterns_updated}件, 追加={result.patterns_added}件"
        )
        return result

    # ------------------------------------------------------------------
    # パターン更新ロジック
    # ------------------------------------------------------------------

    def _update_angle_patterns(
        self,
        patterns: dict[str, Any],
        report: Any,
        result: UpdateResult,
    ) -> dict[str, Any]:
        """
        report.by_theme の実績に基づいて angle_patterns を更新する。
        """
        updated = copy.deepcopy(patterns)
        angle_patterns: list[dict] = updated.get("angle_patterns", [])

        # angle → ThemeKPI のマッピング
        theme_map = {t.angle: t for t in report.by_theme}

        for pattern in angle_patterns:
            angle = pattern.get("angle", "")
            theme_kpi = theme_map.get(angle)
            if theme_kpi is None:
                continue  # 今回のデータにない angle はスキップ
            if theme_kpi.record_count < self.min_records:
                continue  # データ不足

            old_m = pattern.get("monetization_boost", 0.0)
            old_t = pattern.get("threads_fit_boost", 0.0)
            updated_flag = False

            # 購入率が良ければ monetization_boost を上げる
            if theme_kpi.avg_purchase_rate >= self.good_purchase_rate:
                new_m = min(_BOOST_MAX, old_m + _BOOST_STEP)
                if new_m != old_m:
                    pattern["monetization_boost"] = round(new_m, 2)
                    updated_flag = True
            else:
                # パフォーマンス低下: 微減
                new_m = max(_BOOST_MIN, old_m - _BOOST_STEP / 2)
                if new_m != old_m:
                    pattern["monetization_boost"] = round(new_m, 2)
                    updated_flag = True

            # 反応率が良ければ threads_fit_boost を上げる
            if theme_kpi.avg_reaction_rate >= self.good_reaction_rate:
                new_t = min(_BOOST_MAX, old_t + _BOOST_STEP)
                if new_t != old_t:
                    pattern["threads_fit_boost"] = round(new_t, 2)
                    updated_flag = True
            else:
                new_t = max(_BOOST_MIN, old_t - _BOOST_STEP / 2)
                if new_t != old_t:
                    pattern["threads_fit_boost"] = round(new_t, 2)
                    updated_flag = True

            # performance セクションを更新
            pattern["performance"] = {
                "total_purchases": theme_kpi.total_note_purchases,
                "avg_purchase_rate": round(theme_kpi.avg_purchase_rate, 4),
                "avg_reaction_rate": round(theme_kpi.avg_reaction_rate, 4),
                "sample_count": theme_kpi.record_count,
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
            }

            if updated_flag:
                result.patterns_updated += 1

        # 新規アングルの追加
        known_angles = {p.get("angle") for p in angle_patterns}
        for theme_kpi in report.by_theme:
            if (
                theme_kpi.angle not in known_angles
                and theme_kpi.angle != "不明"
                and theme_kpi.record_count >= self.min_records
            ):
                new_pattern = {
                    "angle": theme_kpi.angle,
                    "monetization_boost": (
                        _BOOST_STEP if theme_kpi.avg_purchase_rate >= self.good_purchase_rate else 0.0
                    ),
                    "threads_fit_boost": (
                        _BOOST_STEP if theme_kpi.avg_reaction_rate >= self.good_reaction_rate else 0.0
                    ),
                    "best_for": [],
                    "performance": {
                        "total_purchases": theme_kpi.total_note_purchases,
                        "avg_purchase_rate": round(theme_kpi.avg_purchase_rate, 4),
                        "avg_reaction_rate": round(theme_kpi.avg_reaction_rate, 4),
                        "sample_count": theme_kpi.record_count,
                        "last_updated": datetime.now().strftime("%Y-%m-%d"),
                    },
                }
                angle_patterns.append(new_pattern)
                result.patterns_added += 1
                logger.info(f"New angle pattern added: {theme_kpi.angle}")

        updated["angle_patterns"] = angle_patterns
        updated["version"] = "1.1"
        updated["updated_at"] = datetime.now().strftime("%Y-%m-%d")
        return updated

    def _update_learned_section(
        self,
        patterns: dict[str, Any],
        report: Any,
    ) -> dict[str, Any]:
        """実測データを learned セクションに追記する。"""
        updated = copy.deepcopy(patterns)
        learned = updated.get("learned", {})
        learned.update({
            "last_analysis_id": report.id,
            "period_label": report.period_label,
            "generated_at": datetime.now().strftime("%Y-%m-%d"),
            "winning_angles": report.winning_angles,
            "top_kpis": {
                "record_count": report.record_count,
                "avg_reaction_rate": report.avg_reaction_rate,
                "avg_transition_rate": report.avg_transition_rate,
                "avg_purchase_rate": report.avg_purchase_rate,
                "total_revenue": report.total_revenue,
            },
            "recommendations": report.recommendations[:3],  # 上位3件
        })
        updated["learned"] = learned
        return updated

    # ------------------------------------------------------------------
    # ファイル操作
    # ------------------------------------------------------------------

    def _load_patterns(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            logger.warning(f"winning_patterns.json が存在しません: {path}")
            return {
                "version": "1.0",
                "description": "自動生成",
                "updated_at": datetime.now().strftime("%Y-%m-%d"),
                "title_patterns": [],
                "angle_patterns": [],
                "price_rules": [],
            }
        data = read_json(path)
        return data if isinstance(data, dict) else {}

    def _save_patterns(self, patterns: dict[str, Any], path: Path) -> Path:
        write_json(path, patterns)
        logger.info(f"winning_patterns.json saved: {path}")
        return path
