"""
note-sales CLI エントリポイント

使い方:
    python -m src.cli --help
    python -m src.cli run-daily --dry-run
    python -m src.cli collect-pain --dry-run
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from src.core.logger import get_logger, setup_logging
from src.core.settings import get_settings
from src.services.orchestrator import Orchestrator

app = typer.Typer(
    name="note-sales",
    help="Threads→note 半自動販売システム",
    pretty_exceptions_enable=False,
)
console = Console()

# グローバルオプション: dry-run
_DRY_RUN_OPTION = typer.Option(False, "--dry-run", help="副作用を実行せず動作を確認する")


def _setup(dry_run: bool) -> tuple[object, Orchestrator]:
    settings = get_settings()
    setup_logging(level=settings.log_level, log_file=settings.log_file)
    logger = get_logger("cli")
    if dry_run:
        console.print("[bold yellow][DRY-RUN MODE][/bold yellow]")
    orchestrator = Orchestrator(settings=settings, dry_run=dry_run)
    return settings, orchestrator


# ---------------------------------------------------------------------------
# 個別コマンド（Task 2以降で本実装に差し替える）
# ---------------------------------------------------------------------------

@app.command()
def collect_pain(
    input_path: Optional[str] = typer.Option(
        None, "--input", "-i",
        help="入力ファイルまたはディレクトリ（省略時は data/raw/）",
    ),
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    読者の悩みを収集・登録する（pain_intake）

    入力: data/raw/ 以下の JSON ファイル（投稿履歴・コメント・手動メモなど）
    出力: data/processed/pain_points.json + SQLite
    """
    from pathlib import Path
    from src.agents.pain_intake import PainIntakeAgent

    settings, _ = _setup(dry_run)
    target = Path(input_path) if input_path else settings.raw_dir

    if not target.exists():
        console.print(f"[red]入力パスが存在しません: {target}[/red]")
        raise typer.Exit(1)

    agent = PainIntakeAgent(settings=settings, dry_run=dry_run)
    result = agent.run(target)

    status_color = "green" if result.extracted > 0 else "yellow"
    console.print(
        f"[{status_color}]抽出: {result.extracted}件[/{status_color}] "
        f"/ スキップ: {result.skipped}件 / エラー: {result.error_count}件"
    )
    if result.similar_linked > 0:
        console.print(f"  類似グループ検出: {result.similar_linked}件")
    if result.output_json:
        console.print(f"  出力: {result.output_json}")
    for w in result.warnings:
        console.print(f"  [yellow]WARN[/yellow]: {w}")


@app.command()
def generate_candidates(
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    pain_points から候補テーマを生成する（researcher）

    入力: SQLite / data/processed/pain_points.json
    出力: data/processed/topic_candidates.json + SQLite
    """
    from src.agents.researcher import ResearcherAgent

    settings, _ = _setup(dry_run)
    agent = ResearcherAgent(settings=settings, dry_run=dry_run)
    result = agent.run()

    if result.warnings:
        for w in result.warnings:
            console.print(f"  [yellow]WARN[/yellow]: {w}")

    if not result.candidates:
        console.print("[yellow]候補が生成されませんでした。collect-pain を先に実行してください[/yellow]")
        return

    status_color = "green" if not dry_run else "yellow"
    console.print(
        f"[{status_color}]生成: {result.generated}件 → dedup後: {result.after_dedup}件 → 最終: {result.final_count}件[/{status_color}]"
    )

    # スコア内訳を表示
    from rich.table import Table
    table = Table(title="TopicCandidates", show_lines=True)
    table.add_column("ID", style="cyan", width=10)
    table.add_column("タイトル", width=40)
    table.add_column("アングル", width=18)
    table.add_column("対象読者", width=12)
    table.add_column("需要", justify="right")
    table.add_column("収益", justify="right")
    table.add_column("合計", justify="right", style="bold")

    for c in result.candidates:
        table.add_row(
            c.candidate_id[:8],
            c.topic_title[:40],
            c.angle[:18],
            c.audience_type[:12],
            f"{c.demand_score:.1f}",
            f"{c.monetization_score:.1f}",
            f"{c.total_score:.1f}",
        )
    console.print(table)

    if result.output_json:
        console.print(f"  出力: {result.output_json}")
    console.print("\n承認するには: select-candidate <candidate_id>")


@app.command()
def select_candidate(
    candidate_id: Optional[str] = typer.Argument(None, help="承認する候補ID"),
    dry_run: bool = _DRY_RUN_OPTION,
    list_all: bool = typer.Option(False, "--list", "-l", help="候補一覧を表示"),
    reason: Optional[str] = typer.Option(None, "--reason", "-r", help="選んだ理由（任意）"),
) -> None:
    """
    人間が候補を選んで承認する（selector）

    ※ 自動承認しない。人間が必ず選択する。
    承認結果は data/processed/approvals.json + SQLite に保存される。

    使い方:
        select-candidate --list                        # 候補一覧を表示
        select-candidate <candidate_id>                # 承認
        select-candidate <candidate_id> --reason "理由"  # 理由付き承認
    """
    from rich.table import Table
    from src.agents.selector import SelectorAgent

    settings, _ = _setup(dry_run)
    agent = SelectorAgent(settings=settings, dry_run=dry_run)

    # 一覧表示 or candidate_id 未指定のとき
    if list_all or candidate_id is None:
        candidates = agent.list_candidates()
        if not candidates:
            console.print("[yellow]候補がありません。generate-candidates を実行してください[/yellow]")
            return

        table = Table(title="TopicCandidates", show_lines=True)
        table.add_column("ID", style="cyan", width=10)
        table.add_column("タイトル", width=42)
        table.add_column("アングル", width=18)
        table.add_column("対象読者", width=12)
        table.add_column("合計", justify="right", style="bold")
        table.add_column("承認", justify="center")

        for c in candidates:
            approved_mark = "[green][OK][/green]" if c.approved else "[dim]--[/dim]"
            table.add_row(
                c.candidate_id[:8],
                c.topic_title[:42],
                c.angle[:18],
                c.audience_type[:12],
                f"{c.total_score:.1f}",
                approved_mark,
            )
        console.print(table)

        if candidate_id is None:
            console.print("\n承認するには: select-candidate <candidate_id>")
            return

    # 承認実行
    result = agent.approve(
        candidate_id=candidate_id,
        selected_reason=reason,
    )

    if result.status == "ok":
        c = result.candidate
        console.print(f"[green][OK] 承認しました[/green]: {c.candidate_id[:8]}")
        console.print(f"  タイトル : {c.topic_title}")
        console.print(f"  スコア   : {c.total_score:.1f}")
        console.print(f"  アングル : {c.angle}")
        console.print(f"  価格帯   : {c.recommended_price_range}")
        if reason:
            console.print(f"  理由     : {reason}")
        if result.output_json:
            console.print(f"  出力     : {result.output_json}")
    elif result.status == "skipped":
        console.print(f"[yellow]{result.message}[/yellow]")
    else:
        console.print(f"[red][NG] {result.message}[/red]")
        raise typer.Exit(1)

    for w in result.warnings:
        console.print(f"  [yellow]WARN[/yellow]: {w}")


@app.command()
def write_note(
    candidate_id: Optional[str] = typer.Argument(None, help="対象の候補ID（省略時は最新承認済みを使用）"),
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    承認済み候補から note 下書きを生成する（note_writer）

    入力: SQLite / data/processed/topic_candidates.json（承認済み候補）
    出力: data/processed/note_drafts.json + SQLite + Markdownファイル
    """
    from src.agents.note_writer import NoteWriterAgent

    settings, _ = _setup(dry_run)
    agent = NoteWriterAgent(settings=settings, dry_run=dry_run)
    result = agent.run(candidate_id=candidate_id)

    for w in result.warnings:
        console.print(f"  [yellow]WARN[/yellow]: {w}")

    if result.status == "no_candidate":
        console.print(f"[yellow]{result.message}[/yellow]")
        return
    if result.status == "error":
        console.print(f"[red][NG] {result.message}[/red]")
        raise typer.Exit(1)
    if result.status == "skipped":
        console.print(f"[yellow]{result.message}[/yellow]")
        return

    draft = result.draft
    console.print(f"[green][OK] 下書き生成完了[/green]")
    console.print(f"  タイトル  : {draft.title}")
    console.print(f"  サブタイトル: {draft.subtitle}")
    console.print(f"  無料パート : {len(draft.free_part_markdown)}字")
    console.print(f"  有料パート : {len(draft.paid_part_markdown)}字")
    console.print(f"  合計      : {draft.char_count}字")
    console.print(f"  価格      : {draft.price}円")
    if result.output_md:
        console.print(f"  Markdown  : {result.output_md}")
    if result.output_json:
        console.print(f"  JSON      : {result.output_json}")
    console.print(f"\n品質チェックするには: edit-note {draft.id[:8]}")


@app.command()
def edit_note(
    draft_id: Optional[str] = typer.Argument(None, help="対象の下書きID（省略時は最新ドラフトを評価）"),
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    下書きの品質レビューを行い publish_ready / revise を判定する（editor）

    品質ゲート: スコア80以上 → publish_ready、79以下 → revise（差し戻し）
    """
    from rich.table import Table
    from src.agents.editor import EditorAgent

    settings, _ = _setup(dry_run)
    agent = EditorAgent(settings=settings, dry_run=dry_run)
    result = agent.run(draft_id=draft_id)

    if result.status == "no_draft":
        console.print(f"[yellow]{result.message}[/yellow]")
        return
    if result.status == "error":
        console.print(f"[red][NG] {result.message}[/red]")
        raise typer.Exit(1)

    # スコア表示
    score_color = "green" if result.passed else "yellow"
    verdict = "publish_ready" if result.passed else "revise（差し戻し）"
    console.print(
        f"[{score_color}]品質スコア: {result.quality_score:.1f}/100 → {verdict}[/{score_color}]"
    )

    # チェック内訳テーブル
    table = Table(title="Editor チェック結果", show_lines=True)
    table.add_column("項目", width=22)
    table.add_column("取得", justify="right", width=6)
    table.add_column("満点", justify="right", width=6)
    table.add_column("コメント")

    for c in result.checks:
        color = "green" if c.passed else "yellow"
        table.add_row(
            c.item,
            f"[{color}]{c.score:.0f}[/{color}]",
            f"{c.max_score:.0f}",
            c.comment[:60],
        )
    console.print(table)

    console.print(f"\n[bold]総括:[/bold] {result.overall_comment[:200]}")

    if result.status == "skipped":
        console.print(f"\n[yellow][DRY-RUN] 保存をスキップしました[/yellow]")
    elif result.passed:
        console.print(f"\n[green]公開するには: publish-note[/green]")
    else:
        console.print(f"\n[yellow]修正して再評価: edit-note[/yellow]")


@app.command()
def publish_note(
    draft_id: Optional[str] = typer.Argument(None, help="公開する下書きID"),
    dry_run: bool = _DRY_RUN_OPTION,
    mode: str = typer.Option("manual", "--mode", "-m", help="公開モード（現在は manual のみ）"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="公開済みnote URL（任意）"),
    slug: Optional[str] = typer.Option(None, "--slug", help="noteスラッグ（URL未確定時の参照用）"),
    yes: bool = typer.Option(False, "--yes", "-y", help="確認プロンプトをスキップ"),
) -> None:
    """
    publish_ready の下書きを公開処理する（note_publisher）

    manual モードではメタデータ（NotePublication・Campaign）を作成するだけ。
    実際のnote.com投稿は人間が行う。attribution_id が生成され、promo_brief に引き継がれる。

    使い方:
        publish-note                          # 最新の publish_ready を対象
        publish-note <draft_id>               # 指定ドラフトを対象
        publish-note --url https://note.com/xxx  # 公開URLも同時に登録
    """
    from src.agents.note_publisher import NotePublisherAgent

    settings, _ = _setup(dry_run)
    agent = NotePublisherAgent(settings=settings, dry_run=dry_run)

    # 事前確認（dry_run / --yes 時はスキップ）
    if not dry_run and not yes:
        # 対象ドラフトを表示して確認
        target = agent._load_draft(draft_id)
        if target is None:
            console.print("[yellow]publish_ready の下書きがありません。edit-note を先に実行してください[/yellow]")
            return
        console.print(f"公開対象: [bold]{target.id[:8]}[/bold] - {target.title}")
        console.print(f"  価格: {target.price}円  文字数: {target.char_count}")
        console.print(f"  モード: {mode}")
        if url:
            console.print(f"  URL: {url}")
        typer.confirm("公開メタデータを作成しますか？", abort=True)

    result = agent.publish(
        draft_id=draft_id,
        note_url=url,
        note_slug=slug,
        mode=mode,
    )

    if result.status == "no_draft":
        console.print(f"[yellow]{result.message}[/yellow]")
        return
    if result.status == "not_ready":
        console.print(f"[red][NG] {result.message}[/red]")
        raise typer.Exit(1)
    if result.status == "error":
        console.print(f"[red][NG] {result.message}[/red]")
        raise typer.Exit(1)
    if result.status == "skipped":
        console.print(f"[yellow]{result.message}[/yellow]")
        return

    pub = result.publication
    camp = result.campaign
    console.print("[green][OK] 公開データ作成完了[/green]")
    console.print(f"  タイトル      : {pub.note_title}")
    console.print(f"  attribution_id: [bold]{pub.attribution_id}[/bold]")
    console.print(f"  campaign      : {camp.name} ({camp.campaign_id[:8]})")
    if pub.note_url:
        console.print(f"  URL           : {pub.note_url}")
    else:
        console.print(f"  slug (参照用) : {pub.note_slug}")
        console.print(f"  [dim]note.comで公開後、URLを記録してください[/dim]")
    if result.output_json:
        console.print(f"  出力          : {result.output_json}")
    console.print(f"\nプロモブリーフを生成するには: generate-promo-brief")


@app.command()
def generate_promo_brief(
    draft_id: Optional[str] = typer.Argument(None, help="対象の下書きID（省略時は最新公開済みを使用）"),
    publication_id: Optional[str] = typer.Option(None, "--publication-id", "-p", help="対象のNotePublicationID"),
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    Threads運用部へのプロモブリーフを生成する（promo_brief_generator）

    publish-note の後に実行する。attribution_id が PromoBrief に引き継がれる。
    ※ Threads投稿は行わない。ブリーフJSONを出力するのみ。
    """
    from rich.table import Table
    from src.agents.promo_brief_generator import PromoBriefGeneratorAgent

    settings, _ = _setup(dry_run)
    agent = PromoBriefGeneratorAgent(settings=settings, dry_run=dry_run)
    result = agent.run(draft_id=draft_id, publication_id=publication_id)

    if result.status in ("no_draft", "no_publication"):
        console.print(f"[yellow]{result.message}[/yellow]")
        return
    if result.status == "error":
        console.print(f"[red][NG] {result.message}[/red]")
        raise typer.Exit(1)
    if result.status == "skipped":
        console.print(f"[yellow]{result.message}[/yellow]")
        return

    brief = result.brief
    console.print("[green][OK] PromoBrief 生成完了[/green]")
    console.print(f"  ID            : {brief.id[:8]}")
    console.print(f"  タイトル      : {brief.article_title}")
    console.print(f"  attribution_id: [bold]{brief.attribution_id or 'N/A'}[/bold]")
    console.print(f"  ターゲット    : {brief.target_audience}")
    console.print(f"  推奨時間帯    : {brief.preferred_post_window}")

    # PromoBrief サマリーテーブル
    table = Table(title="PromoBrief サマリー", show_lines=True)
    table.add_column("項目", style="cyan", width=18)
    table.add_column("内容")

    table.add_row("キーメッセージ", brief.key_message[:60])
    table.add_row("プロモ切り口", brief.promotion_angle[:60])
    table.add_row("解決する悩み", "\n".join(f"・{p}" for p in brief.target_pains[:3]))
    table.add_row("フック案1", brief.hook_options[0][:60] if brief.hook_options else "")
    table.add_row("フック案2", brief.hook_options[1][:60] if len(brief.hook_options) > 1 else "")
    table.add_row("ハッシュタグ", " ".join(f"#{t}" for t in brief.recommended_hashtags))
    table.add_row("CTA方向性", brief.cta_note[:60])
    table.add_row("メモ", (brief.memo or "")[:60])
    console.print(table)

    if result.output_json:
        console.print(f"  出力: {result.output_json}")
    for w in result.warnings:
        console.print(f"  [yellow]WARN[/yellow]: {w}")


@app.command()
def import_performance(
    input_path: Optional[str] = typer.Option(
        None, "--input", "-i",
        help="入力ディレクトリ（省略時は data/raw/performance/）",
    ),
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    Threads運用部から受け取った成績JSONを取り込む（performance_importer）

    入力: data/raw/performance/ 以下のJSONファイル
    出力: SQLite + data/processed/imported_performance.json

    JSONフォーマット:
        attribution_id, threads_post_id, impressions, likes, replies, reposts,
        saves, note_clicks, note_views, note_purchases, note_revenue, good_phrases, ...
    """
    from pathlib import Path
    from src.agents.performance_importer import PerformanceImporterAgent

    settings, _ = _setup(dry_run)
    agent = PerformanceImporterAgent(settings=settings, dry_run=dry_run)
    target = Path(input_path) if input_path else None
    result = agent.run(input_dir=target)

    color = "green" if result.status == "ok" else "yellow"
    console.print(f"[{color}]{result.message}[/{color}]")
    if result.output_json:
        console.print(f"  出力: {result.output_json}")
    for w in result.warnings:
        console.print(f"  [yellow]WARN[/yellow]: {w}")

    if result.status not in ("ok", "skipped", "no_files"):
        raise typer.Exit(1)

    console.print(f"\n分析するには: analyze-note")


@app.command()
def analyze_note(
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    パフォーマンスデータを集計して分析レポートを生成する（note_analyzer）

    入力: SQLite の performance_records
    出力: data/processed/analytics_report.json + 週次レポートMarkdown
    """
    from rich.table import Table
    from src.agents.note_analyzer import NoteAnalyzerAgent

    settings, _ = _setup(dry_run)
    agent = NoteAnalyzerAgent(settings=settings, dry_run=dry_run)
    result = agent.run()

    if result.status == "no_data":
        console.print(f"[yellow]{result.message}[/yellow]")
        return
    if result.status == "error":
        console.print(f"[red][NG] {result.message}[/red]")
        raise typer.Exit(1)
    if result.status == "skipped":
        console.print(f"[yellow]{result.message}[/yellow]")
        return

    report = result.report
    color = "green" if result.status == "ok" else "yellow"
    console.print(f"[{color}][OK] 分析完了[/{color}]")

    # KPIサマリーテーブル
    table = Table(title=f"Analytics Report ({report.period_label})", show_lines=True)
    table.add_column("KPI", style="cyan", width=24)
    table.add_column("値", justify="right")

    table.add_row("Threads総表示数", f"{report.total_impressions:,}")
    table.add_row("Threads反応率", f"{report.avg_reaction_rate:.1%}")
    table.add_row("Threads→note遷移率", f"{report.avg_transition_rate:.1%}")
    table.add_row("note総閲覧数", f"{report.total_note_views:,}")
    table.add_row("note購入数", f"{report.total_note_purchases}件")
    table.add_row("note購入率", f"{report.avg_purchase_rate:.1%}")
    table.add_row("総売上", f"¥{report.total_revenue:,}")
    console.print(table)

    # テーマ別
    if report.by_theme:
        theme_table = Table(title="テーマ別成績", show_lines=True)
        theme_table.add_column("アングル", width=24)
        theme_table.add_column("件数", justify="right")
        theme_table.add_column("反応率", justify="right")
        theme_table.add_column("購入率", justify="right")
        theme_table.add_column("売上", justify="right")
        for t in sorted(report.by_theme, key=lambda x: x.avg_purchase_rate, reverse=True):
            theme_table.add_row(
                t.angle[:24],
                str(t.record_count),
                f"{t.avg_reaction_rate:.1%}",
                f"{t.avg_purchase_rate:.1%}",
                f"¥{t.total_revenue:,}",
            )
        console.print(theme_table)

    # 推奨アクション
    if report.recommendations:
        console.print("\n[bold]推奨アクション:[/bold]")
        for i, rec in enumerate(report.recommendations[:3], 1):
            console.print(f"  {i}. {rec}")

    if result.output_json:
        console.print(f"\n  レポート: {result.output_json}")
    if result.weekly_report_path:
        console.print(f"  週次Markdown: {result.weekly_report_path}")
    console.print(f"\nパターン更新するには: update-patterns")
    for w in result.warnings:
        console.print(f"  [yellow]WARN[/yellow]: {w}")


@app.command()
def update_patterns(
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    分析結果をwinning_patterns.jsonに反映する（knowledge_base）

    入力: data/processed/analytics_report.json
    出力: data/knowledge/winning_patterns.json（更新）
    """
    from src.agents.knowledge_base import KnowledgeBaseAgent

    settings, _ = _setup(dry_run)
    agent = KnowledgeBaseAgent(settings=settings, dry_run=dry_run)
    result = agent.run()

    if result.status == "no_report":
        console.print(f"[yellow]{result.message}[/yellow]")
        return
    if result.status == "error":
        console.print(f"[red][NG] {result.message}[/red]")
        raise typer.Exit(1)
    if result.status == "skipped":
        console.print(f"[yellow]{result.message}[/yellow]")
        return

    color = "green" if result.status == "ok" else "yellow"
    console.print(f"[{color}][OK] {result.message}[/{color}]")
    if result.output_json:
        console.print(f"  出力: {result.output_json}")
    for w in result.warnings:
        console.print(f"  [yellow]WARN[/yellow]: {w}")


# ---------------------------------------------------------------------------
# 複合コマンド
# ---------------------------------------------------------------------------

@app.command()
def run_daily(
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    デイリーワークフローを実行する

    フロー: collect-pain → generate-candidates → (手動: select-candidate)
           → write-note → edit-note → (手動: publish-note)
           → generate-promo-brief
    """
    settings, orch = _setup(dry_run)
    orch.run_daily()


@app.command()
def run_weekly(
    dry_run: bool = _DRY_RUN_OPTION,
) -> None:
    """
    ウィークリーワークフローを実行する

    フロー: import-performance → analyze-note → update-patterns
    """
    settings, orch = _setup(dry_run)
    orch.run_weekly()


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import io
    import sys
    # Windows ターミナルで UTF-8 を強制（pytest 実行時には影響しない）
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    app()
