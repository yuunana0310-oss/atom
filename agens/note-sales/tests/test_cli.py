"""
CLI コマンドのテスト

typer の CliRunner を使ってコマンドを実行し、
終了コードと出力を確認する。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def _invoke(*args: str) -> object:
    """コマンドを実行してResultを返す"""
    return runner.invoke(app, list(args))


class TestRunDailyCommand:
    def test_dry_run_exits_zero(self):
        result = _invoke("run-daily", "--dry-run")
        assert result.exit_code == 0, result.output

    def test_dry_run_contains_steps(self):
        result = _invoke("run-daily", "--dry-run")
        output = result.output
        assert "collect-pain" in output or "DRY-RUN" in output

    def test_shows_dry_run_label(self):
        result = _invoke("run-daily", "--dry-run")
        assert "DRY-RUN" in result.output


class TestRunWeeklyCommand:
    def test_dry_run_exits_zero(self):
        result = _invoke("run-weekly", "--dry-run")
        assert result.exit_code == 0, result.output

    def test_shows_import_step(self):
        result = _invoke("run-weekly", "--dry-run")
        assert "import-performance" in result.output or "performance" in result.output.lower()


class TestCollectPainCommand:
    def test_exits_zero(self):
        result = _invoke("collect-pain", "--dry-run")
        assert result.exit_code == 0, result.output


class TestGenerateCandidatesCommand:
    def test_exits_zero(self):
        result = _invoke("generate-candidates", "--dry-run")
        assert result.exit_code == 0, result.output


class TestSelectCandidateCommand:
    def test_list_with_no_candidates(self):
        result = _invoke("select-candidate", "--list")
        # 候補なしでもエラーにならない
        assert result.exit_code == 0, result.output


class TestWriteNoteCommand:
    def test_exits_zero(self):
        result = _invoke("write-note", "--dry-run")
        assert result.exit_code == 0, result.output


class TestEditNoteCommand:
    def test_exits_zero(self):
        result = _invoke("edit-note", "--dry-run")
        assert result.exit_code == 0, result.output


class TestPublishNoteCommand:
    def test_no_ready_drafts(self):
        result = _invoke("publish-note", "--dry-run")
        # 公開可能な下書きがなければメッセージを出して終了
        assert result.exit_code == 0, result.output


class TestGeneratePromoBriefCommand:
    def test_exits_zero(self):
        result = _invoke("generate-promo-brief", "--dry-run")
        assert result.exit_code == 0, result.output


class TestImportPerformanceCommand:
    def test_exits_zero(self):
        result = _invoke("import-performance", "--dry-run")
        assert result.exit_code == 0, result.output


class TestAnalyzeNoteCommand:
    def test_exits_zero(self):
        result = _invoke("analyze-note", "--dry-run")
        assert result.exit_code == 0, result.output


class TestUpdatePatternsCommand:
    def test_exits_zero(self):
        result = _invoke("update-patterns", "--dry-run")
        assert result.exit_code == 0, result.output


class TestHelpOutput:
    def test_main_help(self):
        result = _invoke("--help")
        assert result.exit_code == 0
        # 主要コマンドが表示される
        assert "run-daily" in result.output
        assert "run-weekly" in result.output

    def test_run_daily_help(self):
        result = _invoke("run-daily", "--help")
        assert result.exit_code == 0
        assert "--dry-run" in result.output
