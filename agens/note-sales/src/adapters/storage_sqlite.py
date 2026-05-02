"""
SQLite ストレージアダプター

各モデルのCRUDを提供する。
Task 1時点ではスキーマ定義とCRUD骨格のみ。
Task 2以降で各モジュールが必要なメソッドを追加する。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from src.core.logger import get_logger
from src.core.models import (
    AnalyticsReport,
    Approval,
    Campaign,
    NoteCandidate,
    NoteDraft,
    NotePublication,
    PainPoint,
    PerformanceRecord,
    PromoBrief,
    TopicCandidate,
)

logger = get_logger(__name__)

# DDL: テーブル定義
# Task 2 breaking change: pain_points.id → pain_points.pain_id
# 既存DBがある場合は data/db/note_sales.db を削除して再作成してください
_DDL = """
CREATE TABLE IF NOT EXISTS pain_points (
    pain_id     TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    severity    INTEGER NOT NULL DEFAULT 1,
    source_type TEXT NOT NULL DEFAULT 'manual_memo',
    data        TEXT NOT NULL  -- JSON全体
);

CREATE TABLE IF NOT EXISTS note_candidates (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL,
    pain_point_id   TEXT NOT NULL,
    approved        INTEGER NOT NULL DEFAULT 0,
    data            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS note_drafts (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    status          TEXT NOT NULL,
    candidate_id    TEXT NOT NULL,
    quality_score   REAL,
    data            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_briefs (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    draft_id    TEXT NOT NULL,
    data        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS performance_records (
    id              TEXT PRIMARY KEY,
    imported_at     TEXT NOT NULL,
    promo_brief_id  TEXT,
    attribution_id  TEXT,
    data            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_candidates (
    candidate_id    TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'candidate_generated',
    total_score     REAL NOT NULL DEFAULT 0.0,
    approved        INTEGER NOT NULL DEFAULT 0,
    data            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id         TEXT PRIMARY KEY,
    approved_at         TEXT NOT NULL,
    selected_candidate_id TEXT NOT NULL,
    data                TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publications (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    draft_id        TEXT NOT NULL,
    attribution_id  TEXT NOT NULL,
    note_url        TEXT,
    data            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id     TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    attribution_id  TEXT NOT NULL,
    draft_id        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    data            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics_reports (
    id              TEXT PRIMARY KEY,
    generated_at    TEXT NOT NULL,
    period_label    TEXT NOT NULL,
    record_count    INTEGER NOT NULL DEFAULT 0,
    data            TEXT NOT NULL
);
"""


class SQLiteStorage:
    """SQLiteへのアクセスをラップするアダプター"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_DDL)
        logger.debug(f"SQLite initialized: {self.db_path}")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # PainPoint
    # ------------------------------------------------------------------

    def save_pain_point(self, pain: PainPoint) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO pain_points
                   (pain_id, created_at, severity, source_type, data)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    pain.pain_id,
                    pain.created_at.isoformat(),
                    pain.severity,
                    pain.source_type,
                    pain.model_dump_json(),
                ),
            )
        logger.info(f"PainPoint saved: {pain.pain_id}")

    def get_pain_point(self, pain_id: str) -> Optional[PainPoint]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM pain_points WHERE pain_id = ?", (pain_id,)
            ).fetchone()
        if row is None:
            return None
        return PainPoint.model_validate_json(row["data"])

    def list_pain_points(
        self,
        source_type: Optional[str] = None,
        min_severity: Optional[int] = None,
    ) -> list[PainPoint]:
        query = "SELECT data FROM pain_points"
        params: list = []
        conditions: list[str] = []
        if source_type is not None:
            conditions.append("source_type = ?")
            params.append(source_type)
        if min_severity is not None:
            conditions.append("severity >= ?")
            params.append(min_severity)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [PainPoint.model_validate_json(r["data"]) for r in rows]

    # ------------------------------------------------------------------
    # NoteCandidate
    # ------------------------------------------------------------------

    def save_candidate(self, candidate: NoteCandidate) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO note_candidates
                   (id, created_at, status, pain_point_id, approved, data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    candidate.id,
                    candidate.created_at.isoformat(),
                    candidate.status,
                    candidate.pain_point_id,
                    int(candidate.approved),
                    candidate.model_dump_json(),
                ),
            )
        logger.info(f"NoteCandidate saved: {candidate.id}")

    def get_candidate(self, candidate_id: str) -> Optional[NoteCandidate]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM note_candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
        if row is None:
            return None
        return NoteCandidate.model_validate_json(row["data"])

    def list_candidates(self, approved: Optional[bool] = None) -> list[NoteCandidate]:
        query = "SELECT data FROM note_candidates"
        params: list = []
        if approved is not None:
            query += " WHERE approved = ?"
            params.append(int(approved))
        query += " ORDER BY created_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [NoteCandidate.model_validate_json(r["data"]) for r in rows]

    # ------------------------------------------------------------------
    # NoteDraft
    # ------------------------------------------------------------------

    def save_draft(self, draft: NoteDraft) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO note_drafts
                   (id, created_at, updated_at, status, candidate_id, quality_score, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    draft.id,
                    draft.created_at.isoformat(),
                    draft.updated_at.isoformat(),
                    draft.status,
                    draft.candidate_id,
                    draft.quality_score,
                    draft.model_dump_json(),
                ),
            )
        logger.info(f"NoteDraft saved: {draft.id}")

    def get_draft(self, draft_id: str) -> Optional[NoteDraft]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM note_drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            return None
        return NoteDraft.model_validate_json(row["data"])

    def list_drafts(self, status: Optional[str] = None) -> list[NoteDraft]:
        query = "SELECT data FROM note_drafts"
        params: list = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [NoteDraft.model_validate_json(r["data"]) for r in rows]

    def delete_draft(self, draft_id: str) -> bool:
        """下書きを削除する。削除できた場合 True を返す。"""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM note_drafts WHERE id = ?", (draft_id,))
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"NoteDraft deleted: {draft_id}")
        return deleted

    # ------------------------------------------------------------------
    # PromoBrief
    # ------------------------------------------------------------------

    def save_promo_brief(self, brief: PromoBrief) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO promo_briefs
                   (id, created_at, draft_id, data)
                   VALUES (?, ?, ?, ?)""",
                (
                    brief.id,
                    brief.created_at.isoformat(),
                    brief.draft_id,
                    brief.model_dump_json(),
                ),
            )
        logger.info(f"PromoBrief saved: {brief.id}")

    def get_promo_brief(self, brief_id: str) -> Optional[PromoBrief]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM promo_briefs WHERE id = ?", (brief_id,)
            ).fetchone()
        if row is None:
            return None
        return PromoBrief.model_validate_json(row["data"])

    # ------------------------------------------------------------------
    # PerformanceRecord
    # ------------------------------------------------------------------

    def save_performance(self, record: PerformanceRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO performance_records
                   (id, imported_at, promo_brief_id, attribution_id, data)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.imported_at.isoformat(),
                    record.promo_brief_id,
                    record.attribution_id,
                    record.model_dump_json(),
                ),
            )
        logger.info(f"PerformanceRecord saved: {record.id}")

    def list_performance(
        self,
        promo_brief_id: Optional[str] = None,
        attribution_id: Optional[str] = None,
    ) -> list[PerformanceRecord]:
        query = "SELECT data FROM performance_records"
        params: list = []
        conditions: list[str] = []
        if promo_brief_id is not None:
            conditions.append("promo_brief_id = ?")
            params.append(promo_brief_id)
        if attribution_id is not None:
            conditions.append("attribution_id = ?")
            params.append(attribution_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY imported_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [PerformanceRecord.model_validate_json(r["data"]) for r in rows]

    # ------------------------------------------------------------------
    # AnalyticsReport
    # ------------------------------------------------------------------

    def save_analytics_report(self, report: AnalyticsReport) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO analytics_reports
                   (id, generated_at, period_label, record_count, data)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    report.id,
                    report.generated_at.isoformat(),
                    report.period_label,
                    report.record_count,
                    report.model_dump_json(),
                ),
            )
        logger.info(f"AnalyticsReport saved: {report.id}")

    def get_latest_analytics_report(self) -> Optional[AnalyticsReport]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM analytics_reports ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return AnalyticsReport.model_validate_json(row["data"])

    # ------------------------------------------------------------------
    # TopicCandidate
    # ------------------------------------------------------------------

    def save_topic_candidate(self, candidate: TopicCandidate) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO topic_candidates
                   (candidate_id, created_at, status, total_score, approved, data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    candidate.candidate_id,
                    candidate.created_at.isoformat(),
                    candidate.status,
                    candidate.total_score,
                    int(candidate.approved),
                    candidate.model_dump_json(),
                ),
            )
        logger.info(f"TopicCandidate saved: {candidate.candidate_id}")

    def clear_unreviewed_candidates(self) -> int:
        """承認・却下されていない候補_generated 状態の候補を全削除する。"""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM topic_candidates WHERE approved = 0 AND status = 'candidate_generated'"
            )
            deleted = cursor.rowcount
        if deleted:
            logger.info(f"Cleared {deleted} unreviewed topic candidates")
        return deleted

    def get_topic_candidate(self, candidate_id: str) -> Optional[TopicCandidate]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM topic_candidates WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
        if row is None:
            return None
        return TopicCandidate.model_validate_json(row["data"])

    def list_topic_candidates(
        self,
        approved: Optional[bool] = None,
        min_score: Optional[float] = None,
    ) -> list[TopicCandidate]:
        query = "SELECT data FROM topic_candidates"
        params: list = []
        conditions: list[str] = []
        if approved is not None:
            conditions.append("approved = ?")
            params.append(int(approved))
        if min_score is not None:
            conditions.append("total_score >= ?")
            params.append(min_score)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY total_score DESC, created_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [TopicCandidate.model_validate_json(r["data"]) for r in rows]

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    def save_approval(self, approval: Approval) -> None:
        with self._conn() as conn:
            # 同じ candidate に対する既存の承認を削除してから挿入（再承認を許容）
            conn.execute(
                "DELETE FROM approvals WHERE selected_candidate_id = ?",
                (approval.selected_candidate_id,),
            )
            conn.execute(
                """INSERT INTO approvals
                   (approval_id, approved_at, selected_candidate_id, data)
                   VALUES (?, ?, ?, ?)""",
                (
                    approval.approval_id,
                    approval.approved_at.isoformat(),
                    approval.selected_candidate_id,
                    approval.model_dump_json(),
                ),
            )
        logger.info(f"Approval saved: {approval.approval_id}")

    def list_approvals(self) -> list[Approval]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT data FROM approvals ORDER BY approved_at DESC"
            ).fetchall()
        return [Approval.model_validate_json(r["data"]) for r in rows]

    # ------------------------------------------------------------------
    # NotePublication
    # ------------------------------------------------------------------

    def save_publication(self, publication: NotePublication) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO publications
                   (id, created_at, draft_id, attribution_id, note_url, data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    publication.id,
                    publication.created_at.isoformat(),
                    publication.draft_id,
                    publication.attribution_id,
                    publication.note_url,
                    publication.model_dump_json(),
                ),
            )
        logger.info(f"NotePublication saved: {publication.id}")

    def get_publication(self, publication_id: str) -> Optional[NotePublication]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM publications WHERE id = ?", (publication_id,)
            ).fetchone()
        if row is None:
            return None
        return NotePublication.model_validate_json(row["data"])

    def get_publication_by_draft_id(self, draft_id: str) -> Optional[NotePublication]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM publications WHERE draft_id = ? ORDER BY created_at DESC LIMIT 1",
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        return NotePublication.model_validate_json(row["data"])

    def list_publications(self) -> list[NotePublication]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT data FROM publications ORDER BY created_at DESC"
            ).fetchall()
        return [NotePublication.model_validate_json(r["data"]) for r in rows]

    # ------------------------------------------------------------------
    # Campaign
    # ------------------------------------------------------------------

    def save_campaign(self, campaign: Campaign) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO campaigns
                   (campaign_id, created_at, attribution_id, draft_id, status, data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    campaign.campaign_id,
                    campaign.created_at.isoformat(),
                    campaign.attribution_id,
                    campaign.draft_id,
                    campaign.status,
                    campaign.model_dump_json(),
                ),
            )
        logger.info(f"Campaign saved: {campaign.campaign_id}")

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM campaigns WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
        if row is None:
            return None
        return Campaign.model_validate_json(row["data"])

    def get_campaign_by_draft_id(self, draft_id: str) -> Optional[Campaign]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM campaigns WHERE draft_id = ? ORDER BY created_at DESC LIMIT 1",
                (draft_id,),
            ).fetchone()
        if row is None:
            return None
        return Campaign.model_validate_json(row["data"])

    def list_campaigns(self, status: Optional[str] = None) -> list[Campaign]:
        query = "SELECT data FROM campaigns"
        params: list = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Campaign.model_validate_json(r["data"]) for r in rows]
