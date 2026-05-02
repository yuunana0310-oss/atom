"""
オーケストレーター

run-daily / run-weekly の実行フローを管理する。
Task 1時点では全ステップがダミー実装。
Task 2以降で各ステップを本実装に差し替える。

ダミー実装 / 本実装の境界:
    [DUMMY] マークが付いているメソッドはTask 1のダミー
    [REAL]  マークが付いているメソッドはTask 2以降で実装する
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import ArticleStatus
from src.core.settings import AppSettings
from src.utils.dry_run import DryRunGuard

logger = get_logger(__name__)
console = Console()

# ASCII-safe ステータスアイコン（Windows cp932 対応）
_STATUS_ICON = {"ok": "[OK]", "skipped": "[--]", "error": "[NG]"}
_STATUS_COLOR = {"ok": "green", "skipped": "yellow", "error": "red"}


@dataclass
class StepResult:
    name: str
    status: str  # "ok" | "skipped" | "error"
    message: str = ""
    detail: str = ""


@dataclass
class RunSummary:
    run_type: str  # "daily" | "weekly"
    started_at: datetime = field(default_factory=datetime.now)
    dry_run: bool = False
    steps: list[StepResult] = field(default_factory=list)

    def add(self, result: StepResult) -> None:
        self.steps.append(result)
        icon = _STATUS_ICON.get(result.status, "[?]")
        color = _STATUS_COLOR.get(result.status, "white")
        console.print(f"  [{color}]{icon} {result.name}[/{color}]: {result.message}")

    def print_summary(self) -> None:
        table = Table(title=f"Run Summary ({self.run_type})", show_lines=True)
        table.add_column("Step", style="cyan")
        table.add_column("Status")
        table.add_column("Detail")
        for s in self.steps:
            color = _STATUS_COLOR.get(s.status, "white")
            table.add_row(
                s.name,
                f"[{color}]{s.status}[/{color}]",
                s.detail or s.message,
            )
        console.print(table)


class Orchestrator:
    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.guard = DryRunGuard(dry_run=dry_run)
        self.db = SQLiteStorage(settings.db_path)

    # ------------------------------------------------------------------
    # run-daily: 収集 → 生成 → 執筆 → レビュー → プロモブリーフ生成
    # ------------------------------------------------------------------

    def run_daily(self) -> RunSummary:
        summary = RunSummary(run_type="daily", dry_run=self.dry_run)
        console.print(
            Panel(
                f"[bold]run-daily[/bold]  dry_run={self.dry_run}",
                title="note-sales",
                border_style="blue",
            )
        )

        summary.add(self._step_collect_pain())
        summary.add(self._step_generate_candidates())
        summary.add(StepResult(
            name="select-candidate",
            status="skipped",
            message="人間承認が必要。`select-candidate` コマンドで承認してください",
        ))
        summary.add(self._step_write_note())
        summary.add(self._step_edit_note())
        summary.add(StepResult(
            name="publish-note",
            status="skipped",
            message="publish は manual モード。`publish-note` コマンドで実行してください",
        ))
        summary.add(self._step_generate_promo_brief())

        summary.print_summary()
        return summary

    # ------------------------------------------------------------------
    # run-weekly: パフォーマンス取り込み → 分析 → パターン更新
    # ------------------------------------------------------------------

    def run_weekly(self) -> RunSummary:
        summary = RunSummary(run_type="weekly", dry_run=self.dry_run)
        console.print(
            Panel(
                f"[bold]run-weekly[/bold]  dry_run={self.dry_run}",
                title="note-sales",
                border_style="magenta",
            )
        )

        summary.add(self._step_import_performance())
        summary.add(self._step_analyze_note())
        summary.add(self._step_update_patterns())

        summary.print_summary()
        return summary

    # ------------------------------------------------------------------
    # 各ステップの実装（Task 1: ダミー）
    # ------------------------------------------------------------------

    def _step_collect_pain(self, input_path=None) -> StepResult:
        """pain_intakeエージェントを呼び出して悩みポイントを収集する。"""
        from src.agents.pain_intake import PainIntakeAgent
        from pathlib import Path as _Path
        try:
            target = _Path(input_path) if input_path else self.settings.raw_dir
            self.guard.log_would_do(f"PainIntakeAgent.run({target})")

            if self.dry_run:
                pain = make_dummy_pain_point()
                return StepResult(
                    name="collect-pain",
                    status="skipped",
                    message="[DRY-RUN] would run PainIntakeAgent",
                    detail=f"target={target}",
                )

            agent = PainIntakeAgent(settings=self.settings, dry_run=False)
            result = agent.run(target)

            return StepResult(
                name="collect-pain",
                status="ok",
                message=f"抽出 {result.extracted}件 / スキップ {result.skipped}件",
                detail=str(result.output_json) if result.output_json else "no output",
            )
        except Exception as e:
            logger.error(f"collect-pain failed: {e}")
            return StepResult(name="collect-pain", status="error", message=str(e))

    def _step_generate_candidates(self) -> StepResult:
        """researcher エージェントを呼び出して pain_points から候補を生成する。"""
        from src.agents.researcher import ResearcherAgent
        try:
            self.guard.log_would_do("ResearcherAgent.run() -> [TopicCandidate, ...]")
            agent = ResearcherAgent(settings=self.settings, dry_run=self.dry_run)
            result = agent.run()

            if result.warnings:
                for w in result.warnings:
                    logger.warning(f"researcher: {w}")

            if not result.candidates:
                return StepResult(
                    name="generate-candidates",
                    status="skipped",
                    message="候補なし（pain_points が不足しています）",
                )

            status = "skipped" if self.dry_run else "ok"
            return StepResult(
                name="generate-candidates",
                status=status,
                message=f"{result.final_count}件生成 (dedup前: {result.generated}件)",
                detail=str(result.output_json) if result.output_json else "dry-run",
            )
        except Exception as e:
            logger.error(f"generate-candidates failed: {e}")
            return StepResult(name="generate-candidates", status="error", message=str(e))

    def _step_write_note(self) -> StepResult:
        """note_writer エージェントを呼び出して承認済み候補から下書きを生成する。"""
        from src.agents.note_writer import NoteWriterAgent
        try:
            self.guard.log_would_do("NoteWriterAgent.run() -> NoteDraft")
            agent = NoteWriterAgent(settings=self.settings, dry_run=self.dry_run)
            result = agent.run()

            if result.status == "no_candidate":
                return StepResult(
                    name="write-note",
                    status="skipped",
                    message="承認済み候補なし（select-candidate を先に実行してください）",
                )
            if result.status == "error":
                return StepResult(name="write-note", status="error", message=result.message)
            if result.status == "skipped":
                return StepResult(
                    name="write-note",
                    status="skipped",
                    message=result.message,
                )

            return StepResult(
                name="write-note",
                status="ok",
                message=result.message,
                detail=str(result.output_md) if result.output_md else "saved",
            )
        except Exception as e:
            logger.error(f"write-note failed: {e}")
            return StepResult(name="write-note", status="error", message=str(e))

    def _step_edit_note(self) -> StepResult:
        """editor エージェントを呼び出して下書きを品質評価する。"""
        from src.agents.editor import EditorAgent
        try:
            self.guard.log_would_do("EditorAgent.run() -> EditorResult")
            agent = EditorAgent(settings=self.settings, dry_run=self.dry_run)
            result = agent.run()

            if result.status == "no_draft":
                return StepResult(
                    name="edit-note",
                    status="skipped",
                    message="評価対象の下書きなし（write-note を先に実行してください）",
                )
            if result.status == "error":
                return StepResult(name="edit-note", status="error", message=result.message)

            verdict = "publish_ready" if result.passed else "revise"
            status = "ok" if result.passed or self.dry_run else "skipped"
            return StepResult(
                name="edit-note",
                status=status,
                message=f"score={result.quality_score:.1f}/100 → {verdict}: {result.message}",
            )
        except Exception as e:
            logger.error(f"edit-note failed: {e}")
            return StepResult(name="edit-note", status="error", message=str(e))

    def _step_generate_promo_brief(self) -> StepResult:
        """promo_brief_generator エージェントを呼び出してブリーフを生成する。"""
        from src.agents.promo_brief_generator import PromoBriefGeneratorAgent
        try:
            self.guard.log_would_do(
                f"PromoBriefGeneratorAgent.run() -> PromoBrief -> {self.settings.promo_brief_output_dir}"
            )
            agent = PromoBriefGeneratorAgent(settings=self.settings, dry_run=self.dry_run)
            result = agent.run()

            if result.status == "no_draft":
                return StepResult(
                    name="generate-promo-brief",
                    status="skipped",
                    message="公開済み記事なし（publish-note を先に実行してください）",
                )
            if result.status == "error":
                return StepResult(name="generate-promo-brief", status="error", message=result.message)
            if result.status == "skipped":
                return StepResult(
                    name="generate-promo-brief",
                    status="skipped",
                    message=result.message,
                )

            brief = result.brief
            return StepResult(
                name="generate-promo-brief",
                status="ok",
                message=f"PromoBrief 生成完了 attribution={brief.attribution_id or 'N/A'}",
                detail=str(result.output_json) if result.output_json else "saved",
            )
        except Exception as e:
            logger.error(f"generate-promo-brief failed: {e}")
            return StepResult(name="generate-promo-brief", status="error", message=str(e))

    def _step_import_performance(self) -> StepResult:
        """performance_importer エージェントを呼び出して成績データを取り込む。"""
        from src.agents.performance_importer import PerformanceImporterAgent
        try:
            self.guard.log_would_do(
                f"PerformanceImporterAgent.run({self.settings.performance_input_dir})"
            )
            agent = PerformanceImporterAgent(settings=self.settings, dry_run=self.dry_run)
            result = agent.run()

            if result.status == "no_files":
                return StepResult(
                    name="import-performance",
                    status="skipped",
                    message=result.message,
                )
            if result.status == "error":
                return StepResult(name="import-performance", status="error", message=result.message)

            return StepResult(
                name="import-performance",
                status="ok" if not self.dry_run else "skipped",
                message=result.message,
                detail=str(result.output_json) if result.output_json else "dry-run",
            )
        except Exception as e:
            logger.error(f"import-performance failed: {e}")
            return StepResult(name="import-performance", status="error", message=str(e))

    def _step_analyze_note(self) -> StepResult:
        """note_analyzer エージェントを呼び出してKPIを集計する。"""
        from src.agents.note_analyzer import NoteAnalyzerAgent
        try:
            self.guard.log_would_do("NoteAnalyzerAgent.run() -> AnalyticsReport")
            agent = NoteAnalyzerAgent(settings=self.settings, dry_run=self.dry_run)
            result = agent.run()

            if result.status == "no_data":
                return StepResult(
                    name="analyze-note",
                    status="skipped",
                    message=result.message,
                )
            if result.status == "error":
                return StepResult(name="analyze-note", status="error", message=result.message)
            if result.status == "skipped":
                return StepResult(name="analyze-note", status="skipped", message=result.message)

            report = result.report
            return StepResult(
                name="analyze-note",
                status="ok",
                message=result.message,
                detail=str(result.output_json) if result.output_json else "saved",
            )
        except Exception as e:
            logger.error(f"analyze-note failed: {e}")
            return StepResult(name="analyze-note", status="error", message=str(e))

    def _step_update_patterns(self) -> StepResult:
        """knowledge_base エージェントを呼び出してwinning_patternsを更新する。"""
        from src.agents.knowledge_base import KnowledgeBaseAgent
        try:
            self.guard.log_would_do("KnowledgeBaseAgent.run() -> winning_patterns.json updated")
            agent = KnowledgeBaseAgent(settings=self.settings, dry_run=self.dry_run)
            result = agent.run()

            if result.status == "no_report":
                return StepResult(
                    name="update-patterns",
                    status="skipped",
                    message=result.message,
                )
            if result.status == "error":
                return StepResult(name="update-patterns", status="error", message=result.message)
            if result.status == "skipped":
                return StepResult(name="update-patterns", status="skipped", message=result.message)

            return StepResult(
                name="update-patterns",
                status="ok",
                message=result.message,
                detail=str(result.output_json) if result.output_json else "saved",
            )
        except Exception as e:
            logger.error(f"update-patterns failed: {e}")
            return StepResult(name="update-patterns", status="error", message=str(e))
