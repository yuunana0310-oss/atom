"""
JSONファイル ストレージアダプター

用途:
- プロモブリーフのファイル出力（Threads運用部への引き渡し）
- パフォーマンスJSONの読み込み（Threads運用部からの受け取り）
- 汎用的なJSON読み書きユーティリティ
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.core.logger import get_logger
from src.core.models import (
    AnalyticsReport,
    Approval,
    Campaign,
    NoteDraft,
    NotePublication,
    PerformanceRecord,
    PromoBrief,
    TopicCandidate,
)

logger = get_logger(__name__)


def _default_encoder(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    """任意のデータをJSONファイルに書き出す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, default=_default_encoder)
    logger.debug(f"JSON written: {path}")


def read_json(path: Path) -> Any:
    """JSONファイルを読み込む。ファイルが存在しない場合は None を返す。"""
    if not path.exists():
        logger.warning(f"JSON file not found: {path}")
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# プロモブリーフ: Threads運用部への出力
# ---------------------------------------------------------------------------

def export_promo_brief(brief: PromoBrief, output_dir: Path) -> Path:
    """
    PromoBriefをJSONファイルとして書き出す。
    ファイル名: promo_brief_{brief.id[:8]}_{yyyymmdd}.json
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = brief.created_at.strftime("%Y%m%d")
    filename = f"promo_brief_{brief.id[:8]}_{date_str}.json"
    path = output_dir / filename
    write_json(path, brief.model_dump(mode="json"))
    logger.info(f"PromoBrief exported: {path}")
    return path


# ---------------------------------------------------------------------------
# パフォーマンス: Threads運用部からの読み込み
# ---------------------------------------------------------------------------

def import_performance_records(input_dir: Path) -> list[PerformanceRecord]:
    """
    input_dir 内のJSONファイルを読み込み、PerformanceRecordのリストを返す。

    想定ファイル形式（Threads運用部が生成するJSON）:
    {
        "promo_brief_id": "...",
        "threads_post_id": "...",
        "measured_at": "2026-04-07T10:00:00",
        "likes": 42,
        "replies": 3,
        "reposts": 1,
        "views": 1200,
        "note_views": 80,
        "note_purchases": 5,
        "note_revenue": 1500
    }
    または上記のリスト形式。
    """
    if not input_dir.exists():
        logger.warning(f"Performance input dir not found: {input_dir}")
        return []

    records: list[PerformanceRecord] = []
    json_files = sorted(input_dir.glob("*.json"))

    for json_file in json_files:
        raw = read_json(json_file)
        if raw is None:
            continue

        # 単一オブジェクトでもリストでも受け付ける
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            try:
                record = PerformanceRecord.model_validate(item)
                records.append(record)
            except Exception as e:
                logger.error(f"Failed to parse record in {json_file}: {e}")

    logger.info(f"Imported {len(records)} performance records from {input_dir}")
    return records


# ---------------------------------------------------------------------------
# TopicCandidate: 候補JSON入出力
# ---------------------------------------------------------------------------

def save_topic_candidates(candidates: list[TopicCandidate], output_path: Path) -> Path:
    """TopicCandidateリストをJSONファイルに保存する。"""
    data = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "count": len(candidates),
        "candidates": [c.model_dump(mode="json") for c in candidates],
    }
    write_json(output_path, data)
    logger.info(f"TopicCandidates saved: {output_path} ({len(candidates)} items)")
    return output_path


def load_topic_candidates(path: Path) -> list[TopicCandidate]:
    """topic_candidates.json を読み込む。存在しない場合は空リストを返す。"""
    raw = read_json(path)
    if raw is None:
        return []
    items = raw.get("candidates", []) if isinstance(raw, dict) else raw
    result = []
    for item in items:
        try:
            result.append(TopicCandidate.model_validate(item))
        except Exception as e:
            logger.warning(f"Failed to parse TopicCandidate: {e}")
    return result


# ---------------------------------------------------------------------------
# Approval: 承認JSON入出力
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# NoteDraft: 下書きJSON入出力
# ---------------------------------------------------------------------------

def save_note_drafts(drafts: list[NoteDraft], output_path: Path) -> Path:
    """NoteDraftリストをnote_drafts.jsonに保存する（全件上書き）。"""
    data = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "count": len(drafts),
        "drafts": [d.model_dump(mode="json") for d in drafts],
    }
    write_json(output_path, data)
    logger.info(f"NoteDrafts saved: {output_path} ({len(drafts)} items)")
    return output_path


def load_note_drafts(path: Path) -> list[NoteDraft]:
    """note_drafts.json を読み込む。存在しない場合は空リストを返す。"""
    # from __future__ import annotations により文字列化されたアノテーションを
    # スレッド内から呼ばれる際に再解決する（Pydantic v2 + threading 対策）
    NoteDraft.model_rebuild()
    raw = read_json(path)
    if raw is None:
        return []
    items = raw.get("drafts", []) if isinstance(raw, dict) else raw
    result = []
    for item in items:
        try:
            result.append(NoteDraft.model_validate(item))
        except Exception as e:
            logger.warning(f"Failed to parse NoteDraft: {e}")
    return result


def save_note_drafts_append(draft: NoteDraft, output_path: Path) -> Path:
    """既存のnote_drafts.jsonに1件追記する（同IDは上書き）。"""
    existing = load_note_drafts(output_path) if output_path.exists() else []
    updated = [d for d in existing if d.id != draft.id]
    updated.append(draft)
    return save_note_drafts(updated, output_path)


def save_approvals(approvals: list[Approval], output_path: Path) -> Path:
    """Approvalリストをapprov als.json に保存する（追記ではなく全件上書き）。"""
    data = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "count": len(approvals),
        "approvals": [a.model_dump(mode="json") for a in approvals],
    }
    write_json(output_path, data)
    logger.info(f"Approvals saved: {output_path} ({len(approvals)} items)")
    return output_path


def load_approvals(path: Path) -> list[Approval]:
    """approvals.json を読み込む。存在しない場合は空リストを返す。"""
    raw = read_json(path)
    if raw is None:
        return []
    items = raw.get("approvals", []) if isinstance(raw, dict) else raw
    result = []
    for item in items:
        try:
            result.append(Approval.model_validate(item))
        except Exception as e:
            logger.warning(f"Failed to parse Approval: {e}")
    return result


# ---------------------------------------------------------------------------
# NotePublication: 公開メタデータJSON入出力
# ---------------------------------------------------------------------------

def save_publications(publications: list[NotePublication], output_path: Path) -> Path:
    """NotePublicationリストをpublications.jsonに保存する（全件上書き）。"""
    data = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "count": len(publications),
        "publications": [p.model_dump(mode="json") for p in publications],
    }
    write_json(output_path, data)
    logger.info(f"Publications saved: {output_path} ({len(publications)} items)")
    return output_path


def load_publications(path: Path) -> list[NotePublication]:
    """publications.json を読み込む。存在しない場合は空リストを返す。"""
    raw = read_json(path)
    if raw is None:
        return []
    items = raw.get("publications", []) if isinstance(raw, dict) else raw
    result = []
    for item in items:
        try:
            result.append(NotePublication.model_validate(item))
        except Exception as e:
            logger.warning(f"Failed to parse NotePublication: {e}")
    return result


def save_publication_append(publication: NotePublication, output_path: Path) -> Path:
    """既存のpublications.jsonに1件追記する（同IDは上書き）。"""
    existing = load_publications(output_path) if output_path.exists() else []
    updated = [p for p in existing if p.id != publication.id]
    updated.append(publication)
    return save_publications(updated, output_path)


# ---------------------------------------------------------------------------
# Campaign: キャンペーンJSON入出力
# ---------------------------------------------------------------------------

def save_campaigns(campaigns: list[Campaign], output_path: Path) -> Path:
    """Campaignリストをcampaigns.jsonに保存する（全件上書き）。"""
    data = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "count": len(campaigns),
        "campaigns": [c.model_dump(mode="json") for c in campaigns],
    }
    write_json(output_path, data)
    logger.info(f"Campaigns saved: {output_path} ({len(campaigns)} items)")
    return output_path


def load_campaigns(path: Path) -> list[Campaign]:
    """campaigns.json を読み込む。存在しない場合は空リストを返す。"""
    raw = read_json(path)
    if raw is None:
        return []
    items = raw.get("campaigns", []) if isinstance(raw, dict) else raw
    result = []
    for item in items:
        try:
            result.append(Campaign.model_validate(item))
        except Exception as e:
            logger.warning(f"Failed to parse Campaign: {e}")
    return result


def save_campaign_append(campaign: Campaign, output_path: Path) -> Path:
    """既存のcampaigns.jsonに1件追記する（同IDは上書き）。"""
    existing = load_campaigns(output_path) if output_path.exists() else []
    updated = [c for c in existing if c.campaign_id != campaign.campaign_id]
    updated.append(campaign)
    return save_campaigns(updated, output_path)


# ---------------------------------------------------------------------------
# PromoBrief: 一覧JSON入出力（単体エクスポートは export_promo_brief を使う）
# ---------------------------------------------------------------------------

def save_promo_briefs(briefs: list[PromoBrief], output_path: Path) -> Path:
    """PromoBriefリストをpromo_briefs.jsonに保存する（全件上書き）。"""
    data = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "count": len(briefs),
        "promo_briefs": [b.model_dump(mode="json") for b in briefs],
    }
    write_json(output_path, data)
    logger.info(f"PromoBriefs saved: {output_path} ({len(briefs)} items)")
    return output_path


def load_promo_briefs(path: Path) -> list[PromoBrief]:
    """promo_briefs.json を読み込む。存在しない場合は空リストを返す。"""
    raw = read_json(path)
    if raw is None:
        return []
    items = raw.get("promo_briefs", []) if isinstance(raw, dict) else raw
    result = []
    for item in items:
        try:
            result.append(PromoBrief.model_validate(item))
        except Exception as e:
            logger.warning(f"Failed to parse PromoBrief: {e}")
    return result


def save_promo_brief_append(brief: PromoBrief, output_path: Path) -> Path:
    """既存のpromo_briefs.jsonに1件追記する（同IDは上書き）。"""
    existing = load_promo_briefs(output_path) if output_path.exists() else []
    updated = [b for b in existing if b.id != brief.id]
    updated.append(brief)
    return save_promo_briefs(updated, output_path)


# ---------------------------------------------------------------------------
# PerformanceRecord: 取り込み済み記録のアーカイブJSON
# ---------------------------------------------------------------------------

def save_performance_records(records: list[PerformanceRecord], output_path: Path) -> Path:
    """PerformanceRecordリストをimported_performance.jsonに保存（全件上書き）。"""
    data = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "count": len(records),
        "records": [r.model_dump(mode="json") for r in records],
    }
    write_json(output_path, data)
    logger.info(f"PerformanceRecords saved: {output_path} ({len(records)} items)")
    return output_path


def load_performance_records(path: Path) -> list[PerformanceRecord]:
    """imported_performance.json を読み込む。存在しない場合は空リストを返す。"""
    raw = read_json(path)
    if raw is None:
        return []
    items = raw.get("records", []) if isinstance(raw, dict) else raw
    result = []
    for item in items:
        try:
            result.append(PerformanceRecord.model_validate(item))
        except Exception as e:
            logger.warning(f"Failed to parse PerformanceRecord: {e}")
    return result


def save_performance_record_append(record: PerformanceRecord, output_path: Path) -> Path:
    """既存のimported_performance.jsonに1件追記する（同threads_post_id or IDは上書き）。"""
    existing = load_performance_records(output_path) if output_path.exists() else []
    if record.threads_post_id:
        updated = [r for r in existing if r.threads_post_id != record.threads_post_id]
    else:
        updated = [r for r in existing if r.id != record.id]
    updated.append(record)
    return save_performance_records(updated, output_path)


# ---------------------------------------------------------------------------
# AnalyticsReport: 分析レポートJSON
# ---------------------------------------------------------------------------

def save_analytics_report(report: AnalyticsReport, output_path: Path) -> Path:
    """AnalyticsReport を analytics_report.json に保存する。"""
    write_json(output_path, report.model_dump(mode="json"))
    logger.info(f"AnalyticsReport saved: {output_path}")
    return output_path


def load_analytics_report(path: Path) -> Optional[AnalyticsReport]:
    """analytics_report.json を読み込む。存在しない場合は None を返す。"""
    raw = read_json(path)
    if raw is None:
        return None
    try:
        return AnalyticsReport.model_validate(raw)
    except Exception as e:
        logger.warning(f"Failed to parse AnalyticsReport: {e}")
        return None


# ---------------------------------------------------------------------------
# WeeklyReport: 週次レポートMarkdown
# ---------------------------------------------------------------------------

def save_weekly_report(markdown: str, output_dir: Path, label: str) -> Path:
    """週次レポートMarkdownをファイルに保存する。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_label = label.replace(":", "-").replace(" ", "_")
    path = output_dir / f"weekly_report_{safe_label}.md"
    path.write_text(markdown, encoding="utf-8")
    logger.info(f"WeeklyReport saved: {path}")
    return path
