"""
note-sales TUI

Textual ベースのターミナル UI。
起動: python -m src.tui  または  note-sales-tui
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────
APP_CSS = """
Screen {
    background: $surface;
}

/* ── ダッシュボード ── */
.stats-row {
    height: 7;
    margin: 1 0;
}

.stat-card {
    width: 1fr;
    height: 5;
    border: round $primary;
    content-align: center middle;
    text-align: center;
    margin: 0 1;
    background: $panel;
}

.action-row {
    height: 3;
    margin-bottom: 1;
}

.action-row Button {
    margin-right: 1;
}

.steps-row {
    height: 3;
    margin-bottom: 1;
}

.steps-row Button {
    margin-right: 1;
    min-width: 16;
}

#log {
    height: 1fr;
    border: round $panel;
    margin-top: 1;
    min-height: 10;
}

/* ── テーブル共通 ── */
DataTable {
    height: 1fr;
}

.table-actions {
    height: 3;
    margin-top: 1;
}

.table-actions Button {
    margin-right: 1;
}

/* ── 下書きタブ専用 ── */
#drafts-pane {
    layout: vertical;
}

#drafts-top {
    height: 40%;
    min-height: 8;
}

#draft-preview {
    height: 1fr;
    border: round $accent;
    padding: 1 2;
    margin-top: 1;
    overflow-y: auto;
}

/* ── 分析タブ ── */
.kpi-row {
    height: 7;
    margin: 1 0;
}

.kpi-card {
    width: 1fr;
    height: 5;
    border: round $success;
    content-align: center middle;
    text-align: center;
    margin: 0 1;
    background: $panel;
}

.kpi-section {
    border: round $panel;
    padding: 1;
    margin-bottom: 1;
    height: auto;
}

.section-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}

TabPane {
    padding: 1 2;
}

/* ── ボタン ── */
Button.run-btn {
    min-width: 18;
}
"""


# ─────────────────────────────────────────────────────────────
# StatCard ウィジェット
# ─────────────────────────────────────────────────────────────
class StatCard(Static):
    """数値 + ラベルを中央表示するカード。"""

    def __init__(self, stat_id: str, label: str, color: str = "bright_cyan", **kwargs):
        self._label = label
        self._color = color
        self._value: str = "—"
        # 初期コンテンツを __init__ で渡す（on_mount 前に Textual が参照するため）
        initial = f"[bold {color}]—[/bold {color}]\n[dim]{label}[/dim]"
        super().__init__(initial, id=stat_id, classes="stat-card", **kwargs)

    def set_value(self, value: str | int) -> None:
        self._value = str(value)
        self.update(
            f"[bold {self._color}]{self._value}[/bold {self._color}]\n"
            f"[dim]{self._label}[/dim]"
        )


# ─────────────────────────────────────────────────────────────
# メインアプリ
# ─────────────────────────────────────────────────────────────
class NoteSalesApp(App):
    TITLE = "note-sales"
    CSS = APP_CSS
    BINDINGS = [
        Binding("q", "quit", "終了", priority=True),
        Binding("r", "refresh_all", "更新"),
        Binding("1", "switch_tab('tab-dashboard')", "ダッシュボード"),
        Binding("2", "switch_tab('tab-candidates')", "候補"),
        Binding("3", "switch_tab('tab-drafts')", "下書き"),
        Binding("4", "switch_tab('tab-analytics')", "分析"),
    ]

    # ──────────────────────────────────────────
    # レイアウト
    # ──────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-dashboard"):
            with TabPane("ダッシュボード [1]", id="tab-dashboard"):
                yield from self._dashboard()
            with TabPane("候補一覧 [2]", id="tab-candidates"):
                yield from self._candidates_view()
            with TabPane("下書き [3]", id="tab-drafts"):
                yield from self._drafts_view()
            with TabPane("分析 [4]", id="tab-analytics"):
                yield from self._analytics_view()
        yield Footer()

    def _dashboard(self):
        with Horizontal(classes="stats-row"):
            yield StatCard("stat-pain",       "悩みポイント",  color="cyan")
            yield StatCard("stat-candidates",  "記事候補",      color="blue")
            yield StatCard("stat-drafts",      "下書き",        color="magenta")
            yield StatCard("stat-published",   "公開済み",      color="green")
        with Horizontal(classes="action-row"):
            yield Button("▶  run-daily",   id="btn-daily",   variant="primary",  classes="run-btn")
            yield Button("▶  run-weekly",  id="btn-weekly",  variant="success",  classes="run-btn")
            yield Button("⟳  更新",         id="btn-refresh", variant="default")
        # デイリー個別ステップ
        with Horizontal(classes="steps-row"):
            yield Button("悩み収集",     id="btn-collect-pain",    variant="default")
            yield Button("候補生成",     id="btn-gen-candidates",  variant="default")
            yield Button("下書き生成",   id="btn-write-note",      variant="warning")
            yield Button("品質チェック", id="btn-edit-note",       variant="default")
            yield Button("プロモBrief",  id="btn-promo-brief",     variant="default")
        yield RichLog(id="log", highlight=True, markup=True, wrap=True)

    def _candidates_view(self):
        table = DataTable(id="tbl-candidates", cursor_type="row", zebra_stripes=True)
        table.add_columns("タイトル候補", "アングル", "スコア", "ステータス", "作成日")
        yield table
        with Horizontal(classes="table-actions"):
            yield Button("✓  承認する",         id="btn-approve",            variant="success")
            yield Button("✍  この候補で生成",    id="btn-write-from-candidate", variant="warning")
            yield Button("⟳  更新",              id="btn-refresh-candidates", variant="default")

    def _drafts_view(self):
        with Vertical(id="drafts-pane"):
            with Vertical(id="drafts-top"):
                table = DataTable(id="tbl-drafts", cursor_type="row", zebra_stripes=True)
                table.add_columns("タイトル", "ステータス", "スコア", "価格", "作成日")
                yield table
                with Horizontal(classes="table-actions"):
                    yield Button("⟳  更新",         id="btn-refresh-drafts", variant="default")
                    yield Button("📂  ファイルを開く", id="btn-open-draft",    variant="default")
                    yield Button("🗑  削除",          id="btn-delete-draft",  variant="error")
            yield Static(
                "[dim]← 上の行を選択するとここに内容が表示されます[/dim]",
                id="draft-preview",
            )

    def _analytics_view(self):
        with Horizontal(classes="kpi-row"):
            yield StatCard("kpi-records",   "記録件数",     color="bright_cyan")
            yield StatCard("kpi-reaction",  "平均反応率",   color="bright_blue")
            yield StatCard("kpi-purchase",  "平均購入率",   color="bright_green")
            yield StatCard("kpi-revenue",   "合計収益",     color="yellow")
        yield Static("", id="analytics-detail")
        with Horizontal(classes="table-actions"):
            yield Button("⟳  更新", id="btn-refresh-analytics", variant="default")

    # ──────────────────────────────────────────
    # ライフサイクル
    # ──────────────────────────────────────────
    def on_mount(self) -> None:
        self._log("note-sales TUI 起動")
        # 最初のレンダリングが完了してからデータを読み込む
        self.call_after_refresh(self.action_refresh_all)

    # ──────────────────────────────────────────
    # ボタンイベント
    # ──────────────────────────────────────────
    @on(Button.Pressed, "#btn-daily")
    def handle_daily(self) -> None:
        self._run_pipeline("daily")

    @on(Button.Pressed, "#btn-weekly")
    def handle_weekly(self) -> None:
        self._run_pipeline("weekly")

    @on(Button.Pressed, "#btn-refresh")
    def handle_refresh(self) -> None:
        self.action_refresh_all()

    @on(Button.Pressed, "#btn-approve")
    def handle_approve(self) -> None:
        table = self.query_one("#tbl-candidates", DataTable)
        if table.row_count == 0:
            self.notify("承認できる候補がありません", severity="warning")
            return
        try:
            cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
            candidate_id = cell_key.row_key.value
        except Exception as e:
            self.notify(f"行の選択に失敗: {e}", severity="error")
            return
        if not candidate_id:
            self.notify("候補IDが取得できませんでした", severity="error")
            return
        self._approve_candidate(str(candidate_id))

    @on(Button.Pressed, "#btn-collect-pain")
    def handle_collect_pain(self) -> None:
        self._run_step("collect-pain")

    @on(Button.Pressed, "#btn-gen-candidates")
    def handle_gen_candidates(self) -> None:
        self._run_step("generate-candidates")

    @on(Button.Pressed, "#btn-write-note")
    def handle_write_note(self) -> None:
        self._run_step("write-note")

    @on(Button.Pressed, "#btn-edit-note")
    def handle_edit_note(self) -> None:
        self._run_step("edit-note")

    @on(Button.Pressed, "#btn-promo-brief")
    def handle_promo_brief(self) -> None:
        self._run_step("generate-promo-brief")

    @on(Button.Pressed, "#btn-write-from-candidate")
    def handle_write_from_candidate(self) -> None:
        table = self.query_one("#tbl-candidates", DataTable)
        if table.row_count == 0:
            self.notify("候補がありません", severity="warning")
            return
        try:
            cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
            candidate_id = cell_key.row_key.value
        except Exception as e:
            self.notify(f"行の選択に失敗: {e}", severity="error")
            return
        if not candidate_id:
            self.notify("候補IDが取得できませんでした", severity="error")
            return
        self._run_write_note(str(candidate_id))

    @on(Button.Pressed, "#btn-refresh-candidates")
    def handle_refresh_candidates(self) -> None:
        self._load_candidates()

    @on(Button.Pressed, "#btn-refresh-drafts")
    def handle_refresh_drafts(self) -> None:
        self._load_drafts()

    @on(Button.Pressed, "#btn-delete-draft")
    def handle_delete_draft(self) -> None:
        table = self.query_one("#tbl-drafts", DataTable)
        if table.row_count == 0:
            self.notify("削除できる下書きがありません", severity="warning")
            return
        try:
            cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
            draft_id = cell_key.row_key.value
        except Exception as e:
            self.notify(f"行の選択に失敗: {e}", severity="error")
            return
        if draft_id:
            self._delete_draft(str(draft_id))

    @on(Button.Pressed, "#btn-open-draft")
    def handle_open_draft(self) -> None:
        table = self.query_one("#tbl-drafts", DataTable)
        if table.row_count == 0:
            self.notify("下書きがありません", severity="warning")
            return
        try:
            cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
            draft_id = cell_key.row_key.value
            self._open_draft_file(str(draft_id))
        except Exception as e:
            self.notify(f"ファイルを開けません: {e}", severity="error")

    @on(DataTable.RowHighlighted, "#tbl-drafts")
    def handle_draft_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """下書きテーブルの選択行が変わったらプレビューを更新する。"""
        draft_id = event.row_key.value
        if draft_id:
            self._update_draft_preview(str(draft_id))

    @on(Button.Pressed, "#btn-refresh-analytics")
    def handle_refresh_analytics(self) -> None:
        self._load_analytics()

    # ──────────────────────────────────────────
    # ワーカー: run-daily / run-weekly
    # ──────────────────────────────────────────
    @work(thread=True, exclusive=True)
    def _run_pipeline(self, mode: str) -> None:
        from src.services.orchestrator import Orchestrator
        from src.core.settings import get_settings

        label = "run-daily" if mode == "daily" else "run-weekly"
        color = "cyan" if mode == "daily" else "green"
        self.call_from_thread(
            self._log,
            f"\n[bold {color}]▶ {label} 開始[/bold {color}]  "
            f"{datetime.now().strftime('%H:%M:%S')}",
        )
        # ボタンを一時無効化
        self.call_from_thread(self._set_run_buttons, False)
        try:
            settings = get_settings()
            orch = Orchestrator(settings=settings, dry_run=False)
            summary = orch.run_daily() if mode == "daily" else orch.run_weekly()

            _STATUS_COLOR = {"ok": "green", "skipped": "yellow", "error": "red"}
            for step in summary.steps:
                c = _STATUS_COLOR.get(step.status, "white")
                self.call_from_thread(
                    self._log,
                    f"  [{c}][{step.status.upper():7}][/{c}] {step.name}: {step.message}",
                )
            self.call_from_thread(
                self._log,
                f"[bold {color}]✓ {label} 完了[/bold {color}]",
            )
            self.call_from_thread(self.notify, f"{label} 完了", severity="information")
            self.call_from_thread(self.action_refresh_all)
        except Exception as exc:
            self.call_from_thread(self._log, f"[red bold]ERROR:[/red bold] {exc}")
            self.call_from_thread(self.notify, f"エラー: {exc}", severity="error")
        finally:
            self.call_from_thread(self._set_run_buttons, True)

    # ──────────────────────────────────────────
    # ワーカー: 個別ステップ実行
    # ──────────────────────────────────────────
    @work(thread=True)
    def _run_step(self, step: str) -> None:
        """デイリーパイプラインの個別ステップを実行する。"""
        from src.core.settings import get_settings
        from src.services.orchestrator import Orchestrator

        self.call_from_thread(self._log, f"\n[bold yellow]▶ {step}[/bold yellow]")
        self.call_from_thread(self._set_step_buttons, False)
        try:
            settings = get_settings()
            orch = Orchestrator(settings=settings, dry_run=False)
            step_map = {
                "collect-pain":        orch._step_collect_pain,
                "generate-candidates": orch._step_generate_candidates,
                "write-note":          orch._step_write_note,
                "edit-note":           orch._step_edit_note,
                "generate-promo-brief": orch._step_generate_promo_brief,
            }
            fn = step_map.get(step)
            if fn is None:
                self.call_from_thread(self.notify, f"不明なステップ: {step}", severity="error")
                return
            result = fn()
            color = {"ok": "green", "skipped": "yellow", "error": "red"}.get(result.status, "white")
            self.call_from_thread(
                self._log,
                f"  [{color}][{result.status.upper():7}][/{color}] {result.message}",
            )
            if result.status == "error":
                self.call_from_thread(self.notify, f"[{step}] {result.message}", severity="error")
            else:
                self.call_from_thread(self.notify, f"✓ {step} 完了", severity="information")
            self.call_from_thread(self.action_refresh_all)
        except Exception as exc:
            self.call_from_thread(self._log, f"[red bold]ERROR:[/red bold] {exc}")
            self.call_from_thread(self.notify, f"エラー: {exc}", severity="error")
        finally:
            self.call_from_thread(self._set_step_buttons, True)

    # ──────────────────────────────────────────
    # ワーカー: 候補承認
    @work(thread=True)
    def _run_write_note(self, candidate_id: str) -> None:
        """指定した候補 ID から下書きを生成する（未承認なら自動で承認してから生成）。"""
        from src.agents.note_writer import NoteWriterAgent
        from src.agents.selector import SelectorAgent
        from src.adapters.storage_sqlite import SQLiteStorage
        from src.core.settings import get_settings

        self.call_from_thread(self.notify, "下書き生成中…", severity="information")
        try:
            settings = get_settings()
            db = SQLiteStorage(settings.db_path)

            # 未承認なら自動承認
            c = db.get_topic_candidate(candidate_id)
            if c and not c.approved:
                selector = SelectorAgent(settings=settings)
                selector.approve(candidate_id)
                self.call_from_thread(
                    self._log, f"[yellow]自動承認:[/yellow] {candidate_id[:8]}"
                )

            agent = NoteWriterAgent(settings=settings, dry_run=False)
            result = agent.run(candidate_id=candidate_id)
            if result.status == "ok":
                self.call_from_thread(
                    self.notify,
                    f"✓ 下書き生成完了: {result.draft.title[:30]}",
                    severity="information",
                )
                self.call_from_thread(
                    self._log, f"[green]✓ 下書き生成[/green] {result.message}"
                )
            else:
                self.call_from_thread(self.notify, result.message, severity="error")
            self.call_from_thread(self.action_refresh_all)
        except Exception as exc:
            self.call_from_thread(self.notify, f"生成失敗: {exc}", severity="error")
            self.call_from_thread(self._log, f"[red]生成失敗: {exc}[/red]")

    @work(thread=True)
    def _delete_draft(self, draft_id: str) -> None:
        """下書きを削除する（SQLite + Markdown）。"""
        from src.adapters.storage_sqlite import SQLiteStorage
        from src.core.settings import get_settings

        try:
            settings = get_settings()
            db = SQLiteStorage(settings.db_path)
            deleted = db.delete_draft(draft_id)
            if not deleted:
                self.call_from_thread(self.notify, "削除対象が見つかりません", severity="warning")
                return
            # Markdown ファイルも削除（存在する場合）
            for md in settings.drafts_dir.glob(f"{draft_id[:8]}*.md"):
                md.unlink(missing_ok=True)
            self.call_from_thread(self.notify, "✓ 削除しました", severity="information")
            self.call_from_thread(self.action_refresh_all)
        except Exception as exc:
            self.call_from_thread(self.notify, f"削除失敗: {exc}", severity="error")

    # ──────────────────────────────────────────
    @work(thread=True)
    def _approve_candidate(self, candidate_id: str) -> None:
        from src.agents.selector import SelectorAgent
        from src.core.settings import get_settings

        self.call_from_thread(
            self.notify, f"承認中: {candidate_id[:8]}…", severity="information"
        )
        try:
            settings = get_settings()
            agent = SelectorAgent(settings=settings)
            result = agent.approve(candidate_id)
            self.call_from_thread(
                self.notify, "✓ 承認完了 — write-note で下書き生成できます", severity="information"
            )
            self.call_from_thread(self._log, f"[green]✓ 承認完了[/green] {candidate_id[:8]}")
            self.call_from_thread(self._load_candidates)
            self.call_from_thread(self._load_stats)
        except Exception as exc:
            self.call_from_thread(self.notify, f"承認失敗: {exc}", severity="error")
            self.call_from_thread(self._log, f"[red]承認失敗: {exc}[/red]")

    # ──────────────────────────────────────────
    # データ読み込み
    # ──────────────────────────────────────────
    def action_refresh_all(self) -> None:
        self._load_stats()
        self._load_candidates()
        self._load_drafts()
        self._load_analytics()

    def _load_stats(self) -> None:
        from src.core.settings import get_settings
        from src.adapters.storage_sqlite import SQLiteStorage
        from src.adapters.storage_json import read_json

        settings = get_settings()
        db = SQLiteStorage(settings.db_path)

        # 悩みポイント（pain_points.json はモデルなしで読める）
        try:
            raw = read_json(settings.pain_points_json)
            count = len(raw.get("pain_points", [])) if isinstance(raw, dict) else 0
            self.query_one("#stat-pain", StatCard).set_value(count)
        except Exception:
            self.query_one("#stat-pain", StatCard).set_value("?")

        # 候補（SQLite）
        try:
            self.query_one("#stat-candidates", StatCard).set_value(
                len(db.list_topic_candidates())
            )
        except Exception:
            self.query_one("#stat-candidates", StatCard).set_value("?")

        # 下書き（SQLite）
        try:
            self.query_one("#stat-drafts", StatCard).set_value(
                len(db.list_drafts())
            )
        except Exception:
            self.query_one("#stat-drafts", StatCard).set_value("?")

        # 公開済み（SQLite）
        try:
            self.query_one("#stat-published", StatCard).set_value(
                len(db.list_publications())
            )
        except Exception:
            self.query_one("#stat-published", StatCard).set_value("?")

    def _load_candidates(self) -> None:
        from src.core.settings import get_settings
        from src.adapters.storage_sqlite import SQLiteStorage

        table = self.query_one("#tbl-candidates", DataTable)
        table.clear()
        try:
            settings = get_settings()
            # SQLite が最新（approve 後も反映済み）
            db = SQLiteStorage(settings.db_path)
            candidates = db.list_topic_candidates()

            _STATUS_COLOR = {
                "human_approved": "bright_green",
                "candidate_generated": "white",
            }
            for c in sorted(candidates, key=lambda x: x.total_score, reverse=True):
                st = c.status.value if hasattr(c.status, "value") else str(c.status)
                color = _STATUS_COLOR.get(st, "dim")
                table.add_row(
                    c.topic_title[:42],
                    c.angle[:20],
                    f"{c.total_score:.3f}",
                    f"[{color}]{st}[/{color}]",
                    c.created_at.strftime("%m/%d %H:%M"),
                    key=c.candidate_id,
                )
        except Exception:
            pass

    def _load_drafts(self) -> None:
        from src.core.settings import get_settings
        from src.adapters.storage_sqlite import SQLiteStorage

        table = self.query_one("#tbl-drafts", DataTable)
        table.clear()
        try:
            settings = get_settings()
            # SQLite から直接読む（Pydantic スレッド問題を回避）
            db = SQLiteStorage(settings.db_path)
            drafts = db.list_drafts()
            _STATUS_COLOR = {
                "publish_ready":     "bright_green",
                "published":         "green",
                "promo_brief_ready": "cyan",
                "editor_review":     "yellow",
                "draft_created":     "blue",
            }
            for d in sorted(drafts, key=lambda x: x.created_at, reverse=True):
                st = d.status.value if hasattr(d.status, "value") else str(d.status)
                color = _STATUS_COLOR.get(st, "white")
                score = f"{d.quality_score:.0f}" if d.quality_score is not None else "—"
                table.add_row(
                    (d.title or "（無題）")[:42],
                    f"[{color}]{st}[/{color}]",
                    score,
                    f"¥{d.price}" if d.price else "無料",
                    d.created_at.strftime("%m/%d %H:%M"),
                    key=d.id,
                )
        except Exception:
            pass

    def _load_analytics(self) -> None:
        from src.core.settings import get_settings
        from src.adapters.storage_json import load_analytics_report

        settings = get_settings()
        report = load_analytics_report(settings.analytics_output_json)

        if report is None:
            self.query_one("#kpi-records",  StatCard).set_value("—")
            self.query_one("#kpi-reaction", StatCard).set_value("—")
            self.query_one("#kpi-purchase", StatCard).set_value("—")
            self.query_one("#kpi-revenue",  StatCard).set_value("—")
            self.query_one("#analytics-detail", Static).update(
                "[dim]分析データがありません。run-weekly を実行してください。[/dim]"
            )
            return

        self.query_one("#kpi-records",  StatCard).set_value(report.record_count)
        self.query_one("#kpi-reaction", StatCard).set_value(f"{report.avg_reaction_rate*100:.1f}%")
        self.query_one("#kpi-purchase", StatCard).set_value(f"{report.avg_purchase_rate*100:.1f}%")
        self.query_one("#kpi-revenue",  StatCard).set_value(f"¥{report.total_revenue:,}")

        # 詳細テキスト
        lines = [f"[bold]期間:[/bold] {report.period_label}"]

        if report.winning_angles:
            lines.append(
                "[bold bright_green]勝ちアングル:[/bold bright_green] "
                + "  /  ".join(report.winning_angles[:3])
            )
        if report.recommendations:
            lines.append("[bold yellow]推奨アクション:[/bold yellow]")
            for rec in report.recommendations[:3]:
                lines.append(f"  • {rec}")

        if report.by_theme:
            lines.append("\n[bold]テーマ別 KPI:[/bold]")
            lines.append(f"{'アングル':<20} {'反応率':>8} {'購入率':>8} {'購入数':>6}")
            lines.append("─" * 48)
            for t in sorted(report.by_theme, key=lambda x: x.avg_purchase_rate, reverse=True)[:5]:
                lines.append(
                    f"{t.angle:<20} "
                    f"{t.avg_reaction_rate*100:>7.1f}% "
                    f"{t.avg_purchase_rate*100:>7.1f}% "
                    f"{t.total_note_purchases:>6}"
                )

        self.query_one("#analytics-detail", Static).update("\n".join(lines))

    # ──────────────────────────────────────────
    # ユーティリティ
    # ──────────────────────────────────────────
    def _log(self, message: str) -> None:
        """ダッシュボードのログパネルに書き込む。"""
        try:
            log_widget = self.query_one("#log", RichLog)
            log_widget.write(message)
        except Exception:
            pass

    def _set_run_buttons(self, enabled: bool) -> None:
        for btn_id in ("#btn-daily", "#btn-weekly"):
            try:
                self.query_one(btn_id, Button).disabled = not enabled
            except Exception:
                pass

    def _update_draft_preview(self, draft_id: str) -> None:
        """選択中の下書き内容をプレビューパネルに表示する。"""
        from src.core.settings import get_settings
        from src.adapters.storage_sqlite import SQLiteStorage

        preview = self.query_one("#draft-preview", Static)
        try:
            settings = get_settings()
            db = SQLiteStorage(settings.db_path)
            draft = db.get_draft(draft_id)
            if draft is None:
                preview.update("[dim]下書きが見つかりません[/dim]")
                return

            st = draft.status.value if hasattr(draft.status, "value") else str(draft.status)
            score = f"{draft.quality_score:.0f}/100" if draft.quality_score is not None else "未採点"
            lines = [
                f"[bold]{draft.title}[/bold]",
                f"[dim]{draft.subtitle or ''}[/dim]" if draft.subtitle else "",
                f"",
                f"[dim]ステータス:[/dim] {st}  [dim]スコア:[/dim] {score}  [dim]価格:[/dim] ¥{draft.price}",
                f"[dim]{'─' * 60}[/dim]",
                f"[bold yellow]── 無料パート ──[/bold yellow]",
                draft.free_part_markdown or "[dim](なし)[/dim]",
            ]
            if draft.paid_part_markdown:
                lines += [
                    f"",
                    f"[bold red]── 有料パート ──[/bold red]",
                    draft.paid_part_markdown,
                ]
            preview.update("\n".join(l for l in lines if l is not None))
        except Exception as e:
            preview.update(f"[red]プレビュー失敗: {e}[/red]")

    def _open_draft_file(self, draft_id: str) -> None:
        """下書きの Markdown ファイルをシステムのエディタで開く。"""
        import os, subprocess
        from src.core.settings import get_settings

        settings = get_settings()
        drafts_dir = settings.drafts_dir
        # ファイル名はdraft_idの先頭8文字でマッチング
        matches = list(drafts_dir.glob(f"{draft_id[:8]}*.md"))
        if not matches:
            # IDが短い場合フルマッチも試みる
            matches = list(drafts_dir.glob(f"{draft_id}*.md"))
        if not matches:
            self.notify(f"Markdownファイルが見つかりません: {draft_id[:8]}", severity="warning")
            return
        path = matches[0]
        try:
            os.startfile(str(path))  # Windows
        except AttributeError:
            subprocess.Popen(["open", str(path)])  # macOS fallback

    def _set_step_buttons(self, enabled: bool) -> None:
        for btn_id in (
            "#btn-collect-pain", "#btn-gen-candidates",
            "#btn-write-note", "#btn-edit-note", "#btn-promo-brief",
        ):
            try:
                self.query_one(btn_id, Button).disabled = not enabled
            except Exception:
                pass

    # ──────────────────────────────────────────
    # アクション
    # ──────────────────────────────────────────
    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id


# ─────────────────────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────────────────────
def main() -> None:
    NoteSalesApp().run()


if __name__ == "__main__":
    main()
