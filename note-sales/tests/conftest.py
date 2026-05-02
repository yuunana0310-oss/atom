"""
pytestの共通フィクスチャ
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.storage_sqlite import SQLiteStorage
from src.core.settings import AppSettings


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """テスト用の一時ディレクトリ"""
    return tmp_path


@pytest.fixture
def tmp_db(tmp_path: Path) -> SQLiteStorage:
    """テスト用インメモリ相当のSQLiteStorage（一時ファイル使用）"""
    db_path = tmp_path / "test.db"
    return SQLiteStorage(db_path)


@pytest.fixture
def test_settings(tmp_path: Path, monkeypatch) -> AppSettings:
    """
    テスト用設定。

    src.core.settings モジュールの _yaml をモンキーパッチして
    全パスを tmp_path 以下に向ける。

    これにより AppSettings の @property が全て tmp_path ベースの
    パスを返すようになり、実プロジェクトのDBやJSONファイルを汚さない。
    """
    import os
    import shutil
    import src.core.settings as settings_module

    os.environ["LOG_LEVEL"] = "WARNING"

    # winning_patterns.json を tmp にコピー（knowledge_base テストが実ファイルを汚さないように）
    real_winning_src = settings_module.PROJECT_ROOT / "data" / "knowledge" / "winning_patterns.json"
    tmp_winning = tmp_path / "winning_patterns.json"
    shutil.copy(real_winning_src, tmp_winning)
    real_winning = str(tmp_winning)

    patched_yaml = {
        "logging": {
            "level": "WARNING",
            "file": str(tmp_path / "app.log"),
        },
        "paths": {
            "db": str(tmp_path / "test.db"),
            "raw": str(tmp_path / "raw"),
            "processed": str(tmp_path / "processed"),
        },
        "quality": {
            "min_score": 80,
            "min_chars": 1500,
            "max_chars": 2500,
        },
        "note_writer": {
            "drafts_dir": str(tmp_path / "drafts"),
            "drafts_json": str(tmp_path / "note_drafts.json"),
            "default_price": 300,
        },
        "editor": {
            "min_score": 80,
            "revise_threshold": 60,
        },
        "note": {
            "publish_mode": "manual",
            "default_price": 300,
        },
        "publisher": {
            "publications_json": str(tmp_path / "publications.json"),
            "campaigns_json": str(tmp_path / "campaigns.json"),
        },
        "promo_brief": {
            "output_dir": str(tmp_path / "promo_briefs"),
        },
        "performance_import": {
            "input_dir": str(tmp_path / "performance"),
            "output_json": str(tmp_path / "imported_performance.json"),
        },
        "analytics": {
            "output_json": str(tmp_path / "analytics_report.json"),
            "weekly_report_dir": str(tmp_path / "weekly_reports"),
            "good_reaction_rate": 0.05,
            "good_transition_rate": 0.02,
            "good_purchase_rate": 0.05,
            "min_records_for_pattern": 1,
        },
        "pain_intake": {
            "output_json": str(tmp_path / "pain_points.json"),
            "similarity_threshold": 0.5,
            "min_text_length": 15,
            "require_pain_keyword": True,
        },
        "researcher": {
            "output_json": str(tmp_path / "topic_candidates.json"),
            "approvals_json": str(tmp_path / "approvals.json"),
            "winning_patterns_json": real_winning,
            "candidates_min": 3,
            "candidates_max": 5,
            "similarity_threshold": 0.6,
            "score_weights": {
                "demand": 0.30,
                "monetization": 0.25,
                "threads_fit": 0.20,
                "expertise_fit": 0.15,
                "trend": 0.10,
            },
            "expertise_tags": [
                "AI活用", "Claude", "ClaudeCode", "生成AI", "副業", "note", "プロンプト",
            ],
            "trend_tags": [
                "ClaudeCode", "生成AI", "AI活用", "Claude", "副業", "プロンプト", "noteで稼ぐ",
            ],
        },
    }

    monkeypatch.setattr(settings_module, "_yaml", patched_yaml)
    return AppSettings()
