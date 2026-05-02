"""
performance_importer エージェント

Threads運用部から受け取った投稿成績JSONを読み込み、SQLiteとJSONに保存する。

入力JSON形式（1ファイル = 1レコード or リスト）:
    {
        "threads_post_id": "...",
        "attribution_id": "attr-20260407-abc123",   ← 推奨
        "note_id": "publication-uuid",               ← 任意
        "promo_brief_id": "brief-uuid",             ← 任意（旧形式との互換）
        "posted_at": "2026-04-07T08:00:00",
        "measured_at": "2026-04-07T10:00:00",
        "post_type": "original",
        "impressions": 5000,
        "likes": 250, "replies": 20, "reposts": 15, "saves": 30,
        "note_clicks": 150, "ctr": 0.03,
        "note_views": 80, "note_purchases": 5, "note_revenue": 1500,
        "good_phrases": [...], "bad_phrases": [...],
        "comment_trends": [...], "field_memo": "..."
    }

backward-compat:
    旧形式（promo_brief_id + views + measured_at のみ）でも読み込める。
    views → impressions として扱う（どちらかがあれば有効）。

設計方針:
    - 欠損フィールドは Optional / デフォルト値で吸収する
    - 同じ threads_post_id が存在する場合は上書き（INSERT OR REPLACE）
    - dry_run=True のとき、解析のみ行い保存はスキップ
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.adapters.storage_json import (
    load_performance_records,
    save_performance_records,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import PerformanceRecord
from src.core.settings import AppSettings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 結果データクラス
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    """PerformanceImporterAgent.run() の結果"""
    imported: int = 0
    skipped: int = 0
    error_count: int = 0
    records: list[PerformanceRecord] = field(default_factory=list)
    status: str = "ok"      # "ok" | "skipped" | "error" | "no_files"
    message: str = ""
    output_json: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

class PerformanceImporterAgent:
    """
    data/raw/performance/ 以下のJSONから PerformanceRecord を取り込むエージェント。

    使い方:
        agent = PerformanceImporterAgent(settings=settings)
        result = agent.run()                         # デフォルト input_dir
        result = agent.run(input_dir=Path("..."))    # 任意のディレクトリ
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)

    def run(self, input_dir: Optional[Path] = None) -> ImportResult:
        """
        input_dir 以下のJSONを読み込み、PerformanceRecord として保存する。
        """
        target = input_dir or self.settings.performance_input_dir

        if not target.exists():
            return ImportResult(
                status="no_files",
                message=f"入力ディレクトリが存在しません: {target}",
            )

        json_files = sorted(target.glob("*.json"))
        if not json_files:
            return ImportResult(
                status="no_files",
                message=f"JSONファイルが見つかりません: {target}",
            )

        result = ImportResult()

        for json_file in json_files:
            try:
                items = self._load_file(json_file)
                for item in items:
                    record = self._parse_record(item)
                    if record is None:
                        result.skipped += 1
                        continue

                    if not self.dry_run:
                        self.db.save_performance(record)

                    result.records.append(record)
                    result.imported += 1

            except Exception as e:
                logger.error(f"Failed to import {json_file.name}: {e}")
                result.error_count += 1
                result.warnings.append(f"{json_file.name}: {e}")

        if self.dry_run:
            result.status = "skipped"
            result.message = (
                f"[DRY-RUN] {result.imported}件を解析 "
                f"(スキップ: {result.skipped}, エラー: {result.error_count})"
            )
            return result

        # JSON アーカイブに追記
        try:
            existing = (
                load_performance_records(self.settings.performance_output_json)
                if self.settings.performance_output_json.exists()
                else []
            )
            # threads_post_id がある場合はそれで重複排除、なければ id で排除
            new_post_ids = {r.threads_post_id for r in result.records if r.threads_post_id}
            new_record_ids = {r.id for r in result.records}
            merged = [
                r for r in existing
                if not (
                    (r.threads_post_id and r.threads_post_id in new_post_ids)
                    or r.id in new_record_ids
                )
            ] + result.records
            output_path = save_performance_records(merged, self.settings.performance_output_json)
            result.output_json = output_path
        except Exception as e:
            logger.warning(f"JSON archive save failed: {e}")
            result.warnings.append(f"JSON保存失敗: {e}")

        result.status = "ok"
        result.message = (
            f"{result.imported}件取り込み完了 "
            f"(スキップ: {result.skipped}, エラー: {result.error_count})"
        )
        return result

    # ------------------------------------------------------------------
    # パース処理
    # ------------------------------------------------------------------

    def _load_file(self, path: Path) -> list[dict]:
        """JSONファイルを読み込む。単一オブジェクトでもリストでも対応。"""
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, list) else [raw]

    def _parse_record(self, item: dict[str, Any]) -> Optional[PerformanceRecord]:
        """
        dict から PerformanceRecord を生成する。

        - 旧形式（promo_brief_id + views）と新形式（attribution_id + impressions）の両方を処理
        - 突合キーが1つもない場合は None を返してスキップ
        """
        # 突合キーのチェック
        promo_brief_id = item.get("promo_brief_id")
        attribution_id = item.get("attribution_id")
        note_id = item.get("note_id")

        if not promo_brief_id and not attribution_id and not note_id:
            logger.warning(f"突合キーなし、スキップ: {item.get('threads_post_id', 'unknown')}")
            return None

        # measured_at: 旧形式との互換
        measured_at_raw = item.get("measured_at") or item.get("posted_at")
        measured_at = None
        if measured_at_raw:
            try:
                measured_at = datetime.fromisoformat(str(measured_at_raw))
            except (ValueError, TypeError):
                measured_at = datetime.now()

        posted_at_raw = item.get("posted_at")
        posted_at = None
        if posted_at_raw:
            try:
                posted_at = datetime.fromisoformat(str(posted_at_raw))
            except (ValueError, TypeError):
                pass

        # impressions: 旧形式の views との互換
        impressions = int(item.get("impressions", 0))
        views = int(item.get("views", 0))
        # どちらかを effective_impressions として使うが、両フィールドはそのまま保持

        try:
            return PerformanceRecord(
                promo_brief_id=promo_brief_id,
                attribution_id=attribution_id,
                note_id=note_id,
                threads_post_id=str(item.get("threads_post_id", "")),
                posted_at=posted_at,
                measured_at=measured_at,
                post_type=str(item.get("post_type", "original")),
                impressions=impressions,
                likes=int(item.get("likes", 0)),
                replies=int(item.get("replies", 0)),
                reposts=int(item.get("reposts", 0)),
                saves=int(item.get("saves", 0)),
                views=views,
                note_clicks=int(item.get("note_clicks", 0)),
                ctr=_safe_float(item.get("ctr")),
                note_views=_safe_int(item.get("note_views")),
                note_purchases=_safe_int(item.get("note_purchases")),
                note_revenue=_safe_int(item.get("note_revenue")),
                good_phrases=list(item.get("good_phrases", [])),
                bad_phrases=list(item.get("bad_phrases", [])),
                comment_trends=list(item.get("comment_trends", [])),
                field_memo=item.get("field_memo"),
            )
        except Exception as e:
            logger.error(f"PerformanceRecord parse error: {e} | item={item}")
            return None


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
