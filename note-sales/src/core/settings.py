"""
設定ファイル読み込み

優先順位: 環境変数 > .env > config/settings.yaml
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# プロジェクトルートを決定
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _load_yaml() -> dict:
    yaml_path = PROJECT_ROOT / "config" / "settings.yaml"
    if yaml_path.exists():
        with yaml_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# .env を読み込む（存在しなくてもOK）
_env_path = PROJECT_ROOT / "config" / ".env"
if not _env_path.exists():
    _env_path = PROJECT_ROOT / ".env"
load_dotenv(_env_path, override=False)

_yaml = _load_yaml()


class AppSettings(BaseSettings):
    """アプリケーション設定。環境変数で上書き可能。"""

    # --- note.com 認証 ---
    note_email: Optional[str] = Field(None, alias="NOTE_EMAIL")
    note_password: Optional[str] = Field(None, alias="NOTE_PASSWORD")
    note_username: Optional[str] = Field(None, alias="NOTE_USERNAME")

    # --- Claude API ---
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")

    # --- ログ ---
    log_level: str = Field(
        default=_yaml.get("logging", {}).get("level", "INFO"),
        alias="LOG_LEVEL",
    )

    # --- パス（yamlから取得し、PROJECT_ROOTを基準に解決）---
    @property
    def db_path(self) -> Path:
        rel = _yaml.get("paths", {}).get("db", "data/db/note_sales.db")
        return PROJECT_ROOT / rel

    @property
    def raw_dir(self) -> Path:
        rel = _yaml.get("paths", {}).get("raw", "data/raw")
        return PROJECT_ROOT / rel

    @property
    def processed_dir(self) -> Path:
        rel = _yaml.get("paths", {}).get("processed", "data/processed")
        return PROJECT_ROOT / rel

    # --- 品質閾値 ---
    @property
    def min_quality_score(self) -> float:
        return _yaml.get("quality", {}).get("min_score", 7.0)

    @property
    def min_chars(self) -> int:
        return _yaml.get("quality", {}).get("min_chars", 1500)

    @property
    def max_chars(self) -> int:
        return _yaml.get("quality", {}).get("max_chars", 2500)

    # --- note 設定 ---
    @property
    def publish_mode(self) -> str:
        return _yaml.get("note", {}).get("publish_mode", "manual")

    @property
    def default_price(self) -> int:
        return _yaml.get("note", {}).get("default_price", 300)

    # --- プロモブリーフ出力先 ---
    @property
    def promo_brief_output_dir(self) -> Path:
        rel = _yaml.get("promo_brief", {}).get("output_dir", "data/processed/promo_briefs")
        return PROJECT_ROOT / rel

    # --- パフォーマンスインポート ---
    @property
    def performance_input_dir(self) -> Path:
        rel = _yaml.get("performance_import", {}).get("input_dir", "data/raw/performance")
        return PROJECT_ROOT / rel

    @property
    def performance_output_json(self) -> Path:
        rel = _yaml.get("performance_import", {}).get(
            "output_json", "data/processed/imported_performance.json"
        )
        return PROJECT_ROOT / rel

    # --- 分析・レポート ---
    @property
    def analytics_output_json(self) -> Path:
        rel = _yaml.get("analytics", {}).get("output_json", "data/processed/analytics_report.json")
        return PROJECT_ROOT / rel

    @property
    def weekly_report_dir(self) -> Path:
        rel = _yaml.get("analytics", {}).get("weekly_report_dir", "data/processed/weekly_reports")
        return PROJECT_ROOT / rel

    @property
    def analytics_good_reaction_rate(self) -> float:
        return float(_yaml.get("analytics", {}).get("good_reaction_rate", 0.05))

    @property
    def analytics_good_transition_rate(self) -> float:
        return float(_yaml.get("analytics", {}).get("good_transition_rate", 0.02))

    @property
    def analytics_good_purchase_rate(self) -> float:
        return float(_yaml.get("analytics", {}).get("good_purchase_rate", 0.05))

    @property
    def analytics_min_records_for_pattern(self) -> int:
        return int(_yaml.get("analytics", {}).get("min_records_for_pattern", 2))

    @property
    def log_file(self) -> Path:
        rel = _yaml.get("logging", {}).get("file", "data/processed/app.log")
        return PROJECT_ROOT / rel

    # --- researcher 設定 ---
    @property
    def topic_candidates_json(self) -> Path:
        rel = _yaml.get("researcher", {}).get("output_json", "data/processed/topic_candidates.json")
        return PROJECT_ROOT / rel

    @property
    def approvals_json(self) -> Path:
        rel = _yaml.get("researcher", {}).get("approvals_json", "data/processed/approvals.json")
        return PROJECT_ROOT / rel

    @property
    def winning_patterns_json(self) -> Path:
        rel = _yaml.get("researcher", {}).get("winning_patterns_json", "data/knowledge/winning_patterns.json")
        return PROJECT_ROOT / rel

    @property
    def candidates_min(self) -> int:
        return _yaml.get("researcher", {}).get("candidates_min", 3)

    @property
    def candidates_max(self) -> int:
        return _yaml.get("researcher", {}).get("candidates_max", 5)

    @property
    def researcher_similarity_threshold(self) -> float:
        return _yaml.get("researcher", {}).get("similarity_threshold", 0.6)

    @property
    def score_weights(self) -> dict[str, float]:
        defaults = {"demand": 0.30, "monetization": 0.25, "threads_fit": 0.20,
                    "expertise_fit": 0.15, "trend": 0.10}
        return _yaml.get("researcher", {}).get("score_weights", defaults)

    @property
    def expertise_tags(self) -> list[str]:
        return _yaml.get("researcher", {}).get("expertise_tags",
            ["AI活用", "Claude", "ClaudeCode", "生成AI", "副業", "note"])

    @property
    def trend_tags(self) -> list[str]:
        return _yaml.get("researcher", {}).get("trend_tags",
            ["ClaudeCode", "生成AI", "AI活用", "Claude", "副業", "プロンプト"])

    # --- note_writer 設定 ---
    @property
    def drafts_dir(self) -> Path:
        rel = _yaml.get("note_writer", {}).get("drafts_dir", "data/processed/drafts")
        return PROJECT_ROOT / rel

    @property
    def note_drafts_json(self) -> Path:
        rel = _yaml.get("note_writer", {}).get("drafts_json", "data/processed/note_drafts.json")
        return PROJECT_ROOT / rel

    @property
    def writer_default_price(self) -> int:
        return _yaml.get("note_writer", {}).get("default_price", 300)

    # --- publisher 設定 ---
    @property
    def publications_json(self) -> Path:
        rel = _yaml.get("publisher", {}).get("publications_json", "data/processed/publications.json")
        return PROJECT_ROOT / rel

    @property
    def campaigns_json(self) -> Path:
        rel = _yaml.get("publisher", {}).get("campaigns_json", "data/processed/campaigns.json")
        return PROJECT_ROOT / rel

    # --- editor 設定 ---
    @property
    def editor_min_score(self) -> float:
        return float(_yaml.get("editor", {}).get("min_score", 80.0))

    @property
    def editor_revise_threshold(self) -> float:
        return float(_yaml.get("editor", {}).get("revise_threshold", 60.0))

    # --- pain_intake 設定 ---
    @property
    def pain_points_json(self) -> Path:
        rel = _yaml.get("pain_intake", {}).get("output_json", "data/processed/pain_points.json")
        return PROJECT_ROOT / rel

    @property
    def pain_similarity_threshold(self) -> float:
        return _yaml.get("pain_intake", {}).get("similarity_threshold", 0.5)

    @property
    def pain_min_text_length(self) -> int:
        return _yaml.get("pain_intake", {}).get("min_text_length", 15)

    @property
    def pain_require_keyword(self) -> bool:
        return _yaml.get("pain_intake", {}).get("require_pain_keyword", True)

    model_config = {"populate_by_name": True, "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
