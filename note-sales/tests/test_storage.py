"""
SQLite・JSONストレージのテスト
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.adapters.storage_json import (
    export_promo_brief,
    import_performance_records,
    read_json,
    write_json,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.models import (
    NoteCandidate,
    NoteDraft,
    PainPoint,
    PerformanceRecord,
    PromoBrief,
    ArticleStatus,
    make_dummy_candidate,
    make_dummy_draft,
    make_dummy_pain_point,
    make_dummy_promo_brief,
)


# ---------------------------------------------------------------------------
# SQLiteStorage
# ---------------------------------------------------------------------------

class TestSQLiteStoragePainPoint:
    def test_save_and_get(self, tmp_db: SQLiteStorage):
        pain = make_dummy_pain_point()
        tmp_db.save_pain_point(pain)
        retrieved = tmp_db.get_pain_point(pain.pain_id)
        assert retrieved is not None
        assert retrieved.pain_id == pain.pain_id
        assert retrieved.original_text == pain.original_text

    def test_get_nonexistent(self, tmp_db: SQLiteStorage):
        result = tmp_db.get_pain_point("nonexistent-id")
        assert result is None

    def test_list_pain_points(self, tmp_db: SQLiteStorage):
        p1 = make_dummy_pain_point()
        p2 = make_dummy_pain_point()
        tmp_db.save_pain_point(p1)
        tmp_db.save_pain_point(p2)
        all_pains = tmp_db.list_pain_points()
        assert len(all_pains) == 2

    def test_save_replaces_existing(self, tmp_db: SQLiteStorage):
        pain = make_dummy_pain_point()
        tmp_db.save_pain_point(pain)
        pain.pain_summary = "更新された要約"
        tmp_db.save_pain_point(pain)
        retrieved = tmp_db.get_pain_point(pain.pain_id)
        assert retrieved.pain_summary == "更新された要約"
        assert len(tmp_db.list_pain_points()) == 1

    def test_list_by_source_type(self, tmp_db: SQLiteStorage):
        p1 = make_dummy_pain_point()  # source_type=manual_memo
        p2 = PainPoint(
            original_text="別のソースから来た悩み",
            pain_summary="別ソースの悩み",
            source_type="post_history",
        )
        tmp_db.save_pain_point(p1)
        tmp_db.save_pain_point(p2)

        manual = tmp_db.list_pain_points(source_type="manual_memo")
        post = tmp_db.list_pain_points(source_type="post_history")

        assert len(manual) == 1
        assert len(post) == 1

    def test_list_by_min_severity(self, tmp_db: SQLiteStorage):
        low = PainPoint(
            original_text="少し気になる",
            pain_summary="軽い悩み",
            severity=1,
        )
        high = PainPoint(
            original_text="全くできなくて詰まった",
            pain_summary="深刻な悩み",
            severity=4,
        )
        tmp_db.save_pain_point(low)
        tmp_db.save_pain_point(high)

        serious = tmp_db.list_pain_points(min_severity=3)
        assert len(serious) == 1
        assert serious[0].severity == 4


class TestSQLiteStorageCandidate:
    def test_save_and_get(self, tmp_db: SQLiteStorage):
        pain = make_dummy_pain_point()
        candidate = make_dummy_candidate(pain.pain_id)
        tmp_db.save_candidate(candidate)
        retrieved = tmp_db.get_candidate(candidate.id)
        assert retrieved is not None
        assert retrieved.title == candidate.title
        assert retrieved.approved is True

    def test_list_approved(self, tmp_db: SQLiteStorage):
        pain = make_dummy_pain_point()
        c1 = make_dummy_candidate(pain.pain_id)  # approved=True
        c2 = NoteCandidate(
            pain_point_id=pain.pain_id,
            title="未承認の候補",
            angle="test",
            target_reader="test",
            approved=False,
        )
        tmp_db.save_candidate(c1)
        tmp_db.save_candidate(c2)

        approved = tmp_db.list_candidates(approved=True)
        not_approved = tmp_db.list_candidates(approved=False)

        assert len(approved) == 1
        assert len(not_approved) == 1
        assert approved[0].title == c1.title


class TestSQLiteStorageDraft:
    def test_save_and_get(self, tmp_db: SQLiteStorage):
        pain = make_dummy_pain_point()
        candidate = make_dummy_candidate(pain.pain_id)
        draft = make_dummy_draft(candidate.id)
        tmp_db.save_draft(draft)
        retrieved = tmp_db.get_draft(draft.id)
        assert retrieved is not None
        assert retrieved.title == draft.title
        assert retrieved.quality_score == draft.quality_score

    def test_char_count_computed(self, tmp_db: SQLiteStorage):
        pain = make_dummy_pain_point()
        candidate = make_dummy_candidate(pain.pain_id)
        draft = make_dummy_draft(candidate.id)
        assert draft.char_count > 0
        assert draft.char_count == len(draft.body_markdown)

    def test_list_by_status(self, tmp_db: SQLiteStorage):
        pain = make_dummy_pain_point()
        candidate = make_dummy_candidate(pain.pain_id)
        draft = make_dummy_draft(candidate.id)
        draft.status = ArticleStatus.PUBLISH_READY
        tmp_db.save_draft(draft)

        ready = tmp_db.list_drafts(status="publish_ready")
        assert len(ready) == 1

        draft_status = tmp_db.list_drafts(status="draft_created")
        assert len(draft_status) == 0


class TestSQLiteStoragePromoBrief:
    def test_save_and_get(self, tmp_db: SQLiteStorage):
        pain = make_dummy_pain_point()
        candidate = make_dummy_candidate(pain.pain_id)
        draft = make_dummy_draft(candidate.id)
        brief = make_dummy_promo_brief(draft.id, "https://note.com/test/n/abc")
        tmp_db.save_promo_brief(brief)
        retrieved = tmp_db.get_promo_brief(brief.id)
        assert retrieved is not None
        assert retrieved.note_url == "https://note.com/test/n/abc"
        assert len(retrieved.hook_options) > 0


class TestSQLiteStoragePerformance:
    def test_save_and_list(self, tmp_db: SQLiteStorage):
        record = PerformanceRecord(
            promo_brief_id="brief-001",
            threads_post_id="thread-001",
            measured_at=datetime.now(),
            likes=42,
            views=1200,
        )
        tmp_db.save_performance(record)
        records = tmp_db.list_performance(promo_brief_id="brief-001")
        assert len(records) == 1
        assert records[0].likes == 42

    def test_list_all(self, tmp_db: SQLiteStorage):
        for i in range(3):
            r = PerformanceRecord(
                promo_brief_id=f"brief-{i:03}",
                threads_post_id=f"thread-{i:03}",
                measured_at=datetime.now(),
                likes=i * 10,
            )
            tmp_db.save_performance(r)
        all_records = tmp_db.list_performance()
        assert len(all_records) == 3


# ---------------------------------------------------------------------------
# JSONストレージ
# ---------------------------------------------------------------------------

class TestWriteReadJson:
    def test_write_and_read(self, tmp_path: Path):
        data = {"key": "value", "num": 42}
        path = tmp_path / "test.json"
        write_json(path, data)
        assert path.exists()
        loaded = read_json(path)
        assert loaded == data

    def test_read_nonexistent(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        result = read_json(path)
        assert result is None

    def test_write_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "a" / "b" / "c" / "file.json"
        write_json(path, {"x": 1})
        assert path.exists()


class TestExportPromoBrief:
    def test_export_creates_file(self, tmp_path: Path):
        pain = make_dummy_pain_point()
        candidate = make_dummy_candidate(pain.pain_id)
        draft = make_dummy_draft(candidate.id)
        brief = make_dummy_promo_brief(draft.id, "https://note.com/test/n/abc")

        output_dir = tmp_path / "promo_briefs"
        path = export_promo_brief(brief, output_dir)

        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["id"] == brief.id
        assert loaded["note_url"] == "https://note.com/test/n/abc"

    def test_export_filename_format(self, tmp_path: Path):
        pain = make_dummy_pain_point()
        candidate = make_dummy_candidate(pain.pain_id)
        draft = make_dummy_draft(candidate.id)
        brief = make_dummy_promo_brief(draft.id, "https://note.com/test/n/abc")
        output_dir = tmp_path / "out"
        path = export_promo_brief(brief, output_dir)
        assert path.name.startswith("promo_brief_")
        assert path.name.endswith(".json")


class TestImportPerformanceRecords:
    def test_import_empty_dir(self, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        records = import_performance_records(empty_dir)
        assert records == []

    def test_import_nonexistent_dir(self, tmp_path: Path):
        records = import_performance_records(tmp_path / "nonexistent")
        assert records == []

    def test_import_single_record(self, tmp_path: Path):
        input_dir = tmp_path / "performance"
        input_dir.mkdir()
        data = {
            "promo_brief_id": "brief-abc",
            "threads_post_id": "thread-xyz",
            "measured_at": "2026-04-07T10:00:00",
            "likes": 55,
            "replies": 3,
            "views": 800,
        }
        (input_dir / "perf_001.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        records = import_performance_records(input_dir)
        assert len(records) == 1
        assert records[0].likes == 55
        assert records[0].promo_brief_id == "brief-abc"

    def test_import_list_format(self, tmp_path: Path):
        input_dir = tmp_path / "performance"
        input_dir.mkdir()
        data = [
            {
                "promo_brief_id": "brief-001",
                "threads_post_id": "t-001",
                "measured_at": "2026-04-07T10:00:00",
                "likes": 10,
            },
            {
                "promo_brief_id": "brief-002",
                "threads_post_id": "t-002",
                "measured_at": "2026-04-07T11:00:00",
                "likes": 20,
            },
        ]
        (input_dir / "perf_batch.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        records = import_performance_records(input_dir)
        assert len(records) == 2
