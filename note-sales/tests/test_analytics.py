"""
performance_importer / note_analyzer / knowledge_base のテスト

カバレッジ:
  - KPI計算純粋関数（calc_reaction_rate etc.）
  - PerformanceRecord 拡張フィールド
  - PerformanceImporterAgent: ファイル取り込み、backward-compat, dry_run
  - NoteAnalyzerAgent: KPI集計、テーマ別、価格別、推奨アクション
  - KnowledgeBaseAgent: パターン更新、追加、learned セクション
  - storage_json: PerformanceRecord / AnalyticsReport 入出力
  - 統合テスト: import → analyze → update
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest

from src.adapters.storage_json import (
    load_analytics_report,
    load_performance_records,
    save_analytics_report,
    save_performance_record_append,
    save_performance_records,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.agents.knowledge_base import KnowledgeBaseAgent
from src.agents.note_analyzer import (
    NoteAnalyzerAgent,
    calc_purchase_rate,
    calc_reaction_rate,
    calc_transition_rate,
    EnrichedRecord,
)
from src.agents.performance_importer import PerformanceImporterAgent
from src.core.models import (
    AnalyticsReport,
    ArticleStatus,
    NoteDraft,
    PerformanceRecord,
    PriceKPI,
    ThemeKPI,
    TopicCandidate,
    make_dummy_draft,
    make_dummy_pain_point,
    make_dummy_performance_record,
    make_dummy_publication,
)
from src.core.settings import AppSettings


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _write_perf_json(path: Path, data: dict | list) -> None:
    """テスト用パフォーマンスJSONを書き出す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _make_perf_dict(
    attribution_id: str = "attr-20260407-abc123",
    impressions: int = 5000,
    likes: int = 200,
    replies: int = 20,
    reposts: int = 10,
    saves: int = 30,
    note_clicks: int = 150,
    note_views: int = 80,
    note_purchases: int = 5,
    note_revenue: int = 1500,
    **kwargs,
) -> dict:
    return {
        "threads_post_id": f"post-{attribution_id[-6:]}",
        "attribution_id": attribution_id,
        "posted_at": "2026-04-07T08:00:00",
        "measured_at": "2026-04-07T10:00:00",
        "post_type": "original",
        "impressions": impressions,
        "likes": likes,
        "replies": replies,
        "reposts": reposts,
        "saves": saves,
        "note_clicks": note_clicks,
        "ctr": note_clicks / max(impressions, 1),
        "note_views": note_views,
        "note_purchases": note_purchases,
        "note_revenue": note_revenue,
        "good_phrases": ["非エンジニアでも使える"],
        "bad_phrases": ["初心者向け"],
        "comment_trends": ["手順が知りたい"],
        "field_memo": "朝投稿が良かった",
        **kwargs,
    }


def _make_publish_ready_draft(
    db: SQLiteStorage,
    candidate_id: str = "cand-001",
    price: int = 300,
) -> NoteDraft:
    draft = make_dummy_draft(candidate_id, price=price)
    draft.status = ArticleStatus.PUBLISH_READY
    db.save_draft(draft)
    return draft


def _make_candidate(
    db: SQLiteStorage,
    candidate_id: str = "cand-001",
    angle: str = "体験談＋本音レポート",
) -> TopicCandidate:
    pain = make_dummy_pain_point()
    db.save_pain_point(pain)
    candidate = TopicCandidate(
        candidate_id=candidate_id,
        target_pain_id_list=[pain.pain_id],
        topic_title="テストタイトル",
        hook="テストフック",
        angle=angle,
        why_now="今話題だから",
        expected_buyer_intent="使い方を知りたい",
        paid_reason="再現性あり",
        audience_type="非エンジニア",
        approved=True,
        approved_at=datetime.now(),
    )
    db.save_topic_candidate(candidate)
    return candidate


# ---------------------------------------------------------------------------
# KPI計算純粋関数のテスト
# ---------------------------------------------------------------------------

class TestKPIFunctions:
    def test_calc_reaction_rate_normal(self):
        rate = calc_reaction_rate(100, 10, 5, 5, 2000)
        assert abs(rate - 0.06) < 0.001  # (100+10+5+5)/2000 = 0.06

    def test_calc_reaction_rate_zero_impressions(self):
        assert calc_reaction_rate(0, 0, 0, 0, 0) == 0.0

    def test_calc_reaction_rate_high(self):
        rate = calc_reaction_rate(500, 50, 30, 20, 5000)
        assert rate > 0.1  # 12%

    def test_calc_transition_rate_normal(self):
        rate = calc_transition_rate(100, 5000)
        assert abs(rate - 0.02) < 0.001

    def test_calc_transition_rate_zero(self):
        assert calc_transition_rate(0, 0) == 0.0

    def test_calc_purchase_rate_normal(self):
        rate = calc_purchase_rate(5, 100)
        assert abs(rate - 0.05) < 0.001

    def test_calc_purchase_rate_zero_views(self):
        assert calc_purchase_rate(5, 0) == 0.0

    def test_calc_purchase_rate_high(self):
        rate = calc_purchase_rate(10, 100)
        assert rate == 0.1


# ---------------------------------------------------------------------------
# PerformanceRecord 拡張フィールドのテスト
# ---------------------------------------------------------------------------

class TestPerformanceRecordModel:
    def test_new_fields_have_defaults(self):
        record = PerformanceRecord(
            promo_brief_id="brief-001",
            threads_post_id="post-001",
            measured_at=datetime.now(),
        )
        assert record.impressions == 0
        assert record.saves == 0
        assert record.note_clicks == 0
        assert record.good_phrases == []
        assert record.attribution_id is None

    def test_effective_impressions_uses_max(self):
        record = PerformanceRecord(
            threads_post_id="p",
            impressions=5000,
            views=4000,
        )
        assert record.effective_impressions == 5000

    def test_effective_impressions_falls_back_to_views(self):
        record = PerformanceRecord(threads_post_id="p", views=3000)
        assert record.effective_impressions == 3000

    def test_reactions_sum(self):
        record = PerformanceRecord(
            threads_post_id="p",
            likes=100, replies=20, reposts=10, saves=15,
        )
        assert record.reactions == 145

    def test_promo_brief_id_optional(self):
        """promo_brief_id は Optional になった"""
        record = PerformanceRecord(
            attribution_id="attr-001",
            threads_post_id="post-001",
        )
        assert record.promo_brief_id is None

    def test_can_save_and_load_from_sqlite(self, tmp_db: SQLiteStorage):
        record = make_dummy_performance_record()
        tmp_db.save_performance(record)
        loaded = tmp_db.list_performance(attribution_id=record.attribution_id)
        assert len(loaded) == 1
        assert loaded[0].attribution_id == record.attribution_id
        assert loaded[0].impressions == record.impressions
        assert loaded[0].good_phrases == record.good_phrases


# ---------------------------------------------------------------------------
# PerformanceImporterAgent のテスト
# ---------------------------------------------------------------------------

class TestPerformanceImporterAgent:
    def _make_agent(self, settings: AppSettings, dry_run=False) -> PerformanceImporterAgent:
        return PerformanceImporterAgent(settings=settings, dry_run=dry_run)

    def test_run_no_directory(self, test_settings: AppSettings):
        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=Path("/nonexistent/dir"))
        assert result.status == "no_files"

    def test_run_empty_directory(self, test_settings: AppSettings, tmp_path: Path):
        empty_dir = tmp_path / "empty_perf"
        empty_dir.mkdir()
        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=empty_dir)
        assert result.status == "no_files"

    def test_run_imports_single_file(self, test_settings: AppSettings, tmp_path: Path):
        perf_dir = tmp_path / "performance"
        _write_perf_json(perf_dir / "record1.json", _make_perf_dict())

        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=perf_dir)
        assert result.status == "ok"
        assert result.imported == 1

    def test_run_imports_list_format(self, test_settings: AppSettings, tmp_path: Path):
        perf_dir = tmp_path / "performance"
        records = [_make_perf_dict(attribution_id=f"attr-{i:03}") for i in range(3)]
        _write_perf_json(perf_dir / "batch.json", records)

        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=perf_dir)
        assert result.imported == 3

    def test_run_saves_to_sqlite(self, test_settings: AppSettings, tmp_path: Path):
        perf_dir = tmp_path / "performance"
        _write_perf_json(perf_dir / "r.json", _make_perf_dict(attribution_id="attr-test"))

        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=perf_dir)
        db = SQLiteStorage(test_settings.db_path)
        records = db.list_performance(attribution_id="attr-test")
        assert len(records) == 1

    def test_run_saves_to_json(self, test_settings: AppSettings, tmp_path: Path):
        perf_dir = tmp_path / "performance"
        _write_perf_json(perf_dir / "r.json", _make_perf_dict())

        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=perf_dir)
        assert result.output_json is not None
        assert result.output_json.exists()

        loaded = load_performance_records(result.output_json)
        assert len(loaded) == 1

    def test_run_dry_run_skips_save(self, test_settings: AppSettings, tmp_path: Path):
        perf_dir = tmp_path / "performance"
        _write_perf_json(perf_dir / "r.json", _make_perf_dict())

        agent = self._make_agent(test_settings, dry_run=True)
        result = agent.run(input_dir=perf_dir)
        assert result.status == "skipped"
        assert result.imported == 1
        assert not test_settings.performance_output_json.exists()

    def test_run_backward_compat_old_format(self, test_settings: AppSettings, tmp_path: Path):
        """旧形式（promo_brief_id + views + measured_at）も読み込める"""
        perf_dir = tmp_path / "performance"
        old_format = {
            "promo_brief_id": "brief-001",
            "threads_post_id": "post-001",
            "measured_at": "2026-04-01T10:00:00",
            "likes": 100,
            "replies": 10,
            "reposts": 5,
            "views": 3000,
            "note_views": 50,
            "note_purchases": 3,
            "note_revenue": 900,
        }
        _write_perf_json(perf_dir / "old.json", old_format)

        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=perf_dir)
        assert result.imported == 1

    def test_run_skips_record_without_join_key(self, test_settings: AppSettings, tmp_path: Path):
        """突合キーが1つもないレコードはスキップ"""
        perf_dir = tmp_path / "performance"
        bad_record = {"threads_post_id": "post-001", "likes": 10}
        _write_perf_json(perf_dir / "bad.json", bad_record)

        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=perf_dir)
        assert result.skipped == 1
        assert result.imported == 0

    def test_run_parses_new_fields(self, test_settings: AppSettings, tmp_path: Path):
        perf_dir = tmp_path / "performance"
        _write_perf_json(perf_dir / "r.json", _make_perf_dict(
            good_phrases=["フレーズA", "フレーズB"],
            bad_phrases=["NG"],
            field_memo="テストメモ",
        ))

        agent = self._make_agent(test_settings)
        result = agent.run(input_dir=perf_dir)
        assert result.records[0].good_phrases == ["フレーズA", "フレーズB"]
        assert result.records[0].field_memo == "テストメモ"


# ---------------------------------------------------------------------------
# NoteAnalyzerAgent のテスト
# ---------------------------------------------------------------------------

class TestNoteAnalyzerAgent:
    def _make_agent(self, settings: AppSettings, dry_run=False) -> NoteAnalyzerAgent:
        return NoteAnalyzerAgent(settings=settings, dry_run=dry_run)

    def _seed_performance(self, db: SQLiteStorage, count: int = 3) -> list[PerformanceRecord]:
        records = []
        for i in range(count):
            r = make_dummy_performance_record(
                attribution_id=f"attr-{i:03}",
            )
            db.save_performance(r)
            records.append(r)
        return records

    def test_run_no_data(self, test_settings: AppSettings):
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.status == "no_data"

    def test_run_ok_with_data(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=2)
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.status == "ok"
        assert result.report is not None

    def test_run_dry_run(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=1)
        agent = self._make_agent(test_settings, dry_run=True)
        result = agent.run()
        assert result.status == "skipped"
        assert "[DRY-RUN]" in result.message

    def test_run_dry_run_does_not_save(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=1)
        agent = self._make_agent(test_settings, dry_run=True)
        agent.run()
        assert not test_settings.analytics_output_json.exists()

    def test_report_total_impressions(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=2)
        agent = self._make_agent(test_settings)
        result = agent.run()
        # 各レコードが impressions=5000 → 合計 10000
        assert result.report.total_impressions == 10000

    def test_report_total_purchases(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=3)
        agent = self._make_agent(test_settings)
        result = agent.run()
        # 各レコードが note_purchases=5 → 合計 15
        assert result.report.total_note_purchases == 15

    def test_report_total_revenue(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=2)
        agent = self._make_agent(test_settings)
        result = agent.run()
        # 各 note_revenue=1500 → 合計 3000
        assert result.report.total_revenue == 3000

    def test_report_avg_reaction_rate(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=1)
        agent = self._make_agent(test_settings)
        result = agent.run()
        # likes=250, replies=20, reposts=15, saves=30, impressions=5000
        expected = calc_reaction_rate(250, 20, 15, 30, 5000)
        assert abs(result.report.avg_reaction_rate - expected) < 0.001

    def test_report_avg_purchase_rate(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=1)
        agent = self._make_agent(test_settings)
        result = agent.run()
        # note_purchases=5, note_views=80
        expected = calc_purchase_rate(5, 80)
        assert abs(result.report.avg_purchase_rate - expected) < 0.001

    def test_report_by_theme_unknown_without_candidate(self, test_settings: AppSettings):
        """Candidateが結合できない場合は angle='不明' に集計される"""
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=2)
        agent = self._make_agent(test_settings)
        result = agent.run()
        angles = [t.angle for t in result.report.by_theme]
        assert "不明" in angles

    def test_report_by_theme_with_candidate(self, test_settings: AppSettings):
        """Campaign経由でCandidateが結合できるとテーマ名が入る"""
        from src.agents.note_publisher import NotePublisherAgent
        from src.adapters.storage_json import save_campaign_append

        db = SQLiteStorage(test_settings.db_path)
        candidate = _make_candidate(db, candidate_id="cand-001", angle="体験談＋本音レポート")
        draft = _make_publish_ready_draft(db, candidate_id="cand-001")

        # publish してキャンペーンを作成
        publisher = NotePublisherAgent(settings=test_settings)
        pub_result = publisher.publish(draft_id=draft.id)
        attr_id = pub_result.publication.attribution_id

        # attribution_id が一致するパフォーマンスレコードを保存
        record = make_dummy_performance_record(attribution_id=attr_id)
        db.save_performance(record)

        agent = self._make_agent(test_settings)
        result = agent.run()
        angles = [t.angle for t in result.report.by_theme]
        assert "体験談＋本音レポート" in angles

    def test_report_by_price_with_draft(self, test_settings: AppSettings):
        """Draft が結合できると価格が入る"""
        from src.agents.note_publisher import NotePublisherAgent

        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db, price=500)
        publisher = NotePublisherAgent(settings=test_settings)
        pub_result = publisher.publish(draft_id=draft.id)

        record = make_dummy_performance_record(
            attribution_id=pub_result.publication.attribution_id,
        )
        db.save_performance(record)

        agent = self._make_agent(test_settings)
        result = agent.run()
        prices = [p.price for p in result.report.by_price]
        assert 500 in prices

    def test_report_saves_to_json(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=1)
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.output_json.exists()
        loaded = load_analytics_report(result.output_json)
        assert loaded is not None
        assert loaded.record_count == 1

    def test_report_saves_weekly_markdown(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=1)
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.weekly_report_path is not None
        assert result.weekly_report_path.exists()
        content = result.weekly_report_path.read_text(encoding="utf-8")
        assert "週次レポート" in content

    def test_report_has_recommendations(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=2)
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert len(result.report.recommendations) > 0

    def test_report_record_count(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        self._seed_performance(db, count=4)
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.report.record_count == 4


# ---------------------------------------------------------------------------
# KnowledgeBaseAgent のテスト
# ---------------------------------------------------------------------------

class TestKnowledgeBaseAgent:
    def _make_agent(self, settings: AppSettings, dry_run=False) -> KnowledgeBaseAgent:
        return KnowledgeBaseAgent(settings=settings, dry_run=dry_run)

    def _seed_analytics_report(self, settings: AppSettings, **kwargs) -> AnalyticsReport:
        """テスト用 AnalyticsReport を作成して analytics_output_json に保存する。"""
        report = AnalyticsReport(
            period_label="2026-W14",
            record_count=kwargs.get("record_count", 3),
            total_impressions=15000,
            total_reactions=780,
            avg_reaction_rate=kwargs.get("avg_reaction_rate", 0.052),
            total_note_clicks=450,
            avg_transition_rate=0.03,
            total_note_views=240,
            total_note_purchases=kwargs.get("total_note_purchases", 15),
            avg_purchase_rate=kwargs.get("avg_purchase_rate", 0.0625),
            total_revenue=4500,
            by_theme=[
                ThemeKPI(
                    angle="体験談＋本音レポート",
                    record_count=kwargs.get("theme_count", 3),
                    total_impressions=15000,
                    total_reactions=780,
                    avg_reaction_rate=kwargs.get("avg_reaction_rate", 0.052),
                    total_note_clicks=450,
                    avg_transition_rate=0.03,
                    total_note_views=240,
                    total_note_purchases=kwargs.get("total_note_purchases", 15),
                    avg_purchase_rate=kwargs.get("avg_purchase_rate", 0.0625),
                    total_revenue=4500,
                ),
            ],
            by_price=[PriceKPI(price=300, record_count=3, total_note_purchases=15, total_revenue=4500)],
            winning_angles=["体験談＋本音レポート"],
            recommendations=["体験談アングルを継続してください。"],
        )
        save_analytics_report(report, settings.analytics_output_json)
        return report

    def test_run_no_report(self, test_settings: AppSettings):
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.status == "no_report"

    def test_run_ok_with_report(self, test_settings: AppSettings):
        self._seed_analytics_report(test_settings)
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.status == "ok"

    def test_run_dry_run(self, test_settings: AppSettings):
        self._seed_analytics_report(test_settings)
        agent = self._make_agent(test_settings, dry_run=True)
        result = agent.run()
        assert result.status == "skipped"

    def test_run_updates_monetization_boost_for_winning_angle(self, test_settings: AppSettings):
        """購入率 >= 5% のアングルは monetization_boost が増加する"""
        self._seed_analytics_report(test_settings, avg_purchase_rate=0.07)
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.patterns_updated >= 1

        # winning_patterns.json を読み込んで確認
        import json
        updated = json.loads(result.output_json.read_text(encoding="utf-8"))
        for p in updated["angle_patterns"]:
            if p["angle"] == "体験談＋本音レポート":
                # もともと 0.0 → 0.2 以上になっているはず
                assert p["monetization_boost"] > 0.0
                break

    def test_run_updates_threads_fit_boost_for_good_reaction(self, test_settings: AppSettings):
        """反応率 >= 5% のアングルは threads_fit_boost が増加する"""
        self._seed_analytics_report(test_settings, avg_reaction_rate=0.07)
        agent = self._make_agent(test_settings)
        result = agent.run()

        import json
        updated = json.loads(result.output_json.read_text(encoding="utf-8"))
        for p in updated["angle_patterns"]:
            if p["angle"] == "体験談＋本音レポート":
                # もともと 1.5 → 1.7 になるはず
                assert p["threads_fit_boost"] > 1.5
                break

    def test_run_adds_performance_section(self, test_settings: AppSettings):
        """パターンに performance セクションが追加される"""
        self._seed_analytics_report(test_settings)
        agent = self._make_agent(test_settings)
        result = agent.run()

        import json
        updated = json.loads(result.output_json.read_text(encoding="utf-8"))
        for p in updated["angle_patterns"]:
            if p["angle"] == "体験談＋本音レポート":
                assert "performance" in p
                assert p["performance"]["sample_count"] >= 1
                break

    def test_run_adds_learned_section(self, test_settings: AppSettings):
        """learned セクションが追加・更新される"""
        self._seed_analytics_report(test_settings)
        agent = self._make_agent(test_settings)
        result = agent.run()

        import json
        updated = json.loads(result.output_json.read_text(encoding="utf-8"))
        assert "learned" in updated
        assert "winning_angles" in updated["learned"]
        assert "top_kpis" in updated["learned"]

    def test_run_adds_new_angle_pattern(self, test_settings: AppSettings):
        """既存にないアングルは新規追加される"""
        # 「比較レポート」は winning_patterns.json には存在する
        # テスト用に「まったく新しいアングル」を作る
        report = AnalyticsReport(
            period_label="2026-W14",
            record_count=2,
            by_theme=[
                ThemeKPI(
                    angle="完全新規アングル",
                    record_count=2,
                    avg_purchase_rate=0.08,
                    avg_reaction_rate=0.06,
                    total_note_purchases=5,
                    total_revenue=1500,
                )
            ],
        )
        save_analytics_report(report, test_settings.analytics_output_json)
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.patterns_added >= 1

        import json
        updated = json.loads(result.output_json.read_text(encoding="utf-8"))
        angles = [p["angle"] for p in updated["angle_patterns"]]
        assert "完全新規アングル" in angles

    def test_run_skips_unknown_angle(self, test_settings: AppSettings):
        """'不明' アングルは追加しない"""
        report = AnalyticsReport(
            period_label="2026-W14",
            record_count=2,
            by_theme=[
                ThemeKPI(
                    angle="不明",
                    record_count=2,
                    avg_purchase_rate=0.1,
                )
            ],
        )
        save_analytics_report(report, test_settings.analytics_output_json)
        agent = self._make_agent(test_settings)
        result = agent.run()

        import json
        updated = json.loads(result.output_json.read_text(encoding="utf-8"))
        angles = [p["angle"] for p in updated["angle_patterns"]]
        assert "不明" not in angles

    def test_run_preserves_existing_patterns(self, test_settings: AppSettings):
        """既存のパターンが消えない"""
        self._seed_analytics_report(test_settings)
        agent = self._make_agent(test_settings)
        result = agent.run()

        import json
        updated = json.loads(result.output_json.read_text(encoding="utf-8"))
        angles = [p["angle"] for p in updated["angle_patterns"]]
        # 既存のパターンが全て残っている
        assert "体験談＋本音レポート" in angles
        assert "ステップバイステップガイド" in angles


# ---------------------------------------------------------------------------
# storage_json: PerformanceRecord / AnalyticsReport 入出力
# ---------------------------------------------------------------------------

class TestStorageJsonPerformance:
    def test_save_and_load(self, tmp_path: Path):
        output = tmp_path / "perf.json"
        record = make_dummy_performance_record()
        save_performance_record_append(record, output)
        loaded = load_performance_records(output)
        assert len(loaded) == 1
        assert loaded[0].attribution_id == record.attribution_id

    def test_append_deduplicates(self, tmp_path: Path):
        output = tmp_path / "perf.json"
        record = make_dummy_performance_record()
        save_performance_record_append(record, output)
        save_performance_record_append(record, output)
        loaded = load_performance_records(output)
        assert len(loaded) == 1

    def test_load_nonexistent_returns_empty(self, tmp_path: Path):
        assert load_performance_records(tmp_path / "none.json") == []


class TestStorageJsonAnalyticsReport:
    def test_save_and_load(self, tmp_path: Path):
        output = tmp_path / "report.json"
        report = AnalyticsReport(period_label="2026-W14", record_count=5)
        save_analytics_report(report, output)
        loaded = load_analytics_report(output)
        assert loaded is not None
        assert loaded.record_count == 5
        assert loaded.period_label == "2026-W14"

    def test_load_nonexistent_returns_none(self, tmp_path: Path):
        assert load_analytics_report(tmp_path / "none.json") is None


# ---------------------------------------------------------------------------
# 統合テスト: import → analyze → update
# ---------------------------------------------------------------------------

class TestWeeklyPipeline:
    def test_full_pipeline(self, test_settings: AppSettings, tmp_path: Path):
        """import-performance → analyze-note → update-patterns の一連フローが動作する。"""
        # Step 1: パフォーマンスJSONを用意
        perf_dir = tmp_path / "performance"
        for i in range(3):
            _write_perf_json(
                perf_dir / f"record_{i}.json",
                _make_perf_dict(attribution_id=f"attr-20260407-{i:06}"),
            )

        # Step 2: import
        importer = PerformanceImporterAgent(settings=test_settings)
        import_result = importer.run(input_dir=perf_dir)
        assert import_result.status == "ok"
        assert import_result.imported == 3

        # Step 3: analyze
        analyzer = NoteAnalyzerAgent(settings=test_settings)
        analyze_result = analyzer.run()
        assert analyze_result.status == "ok"
        assert analyze_result.report.record_count == 3

        # Step 4: update patterns
        kb = KnowledgeBaseAgent(settings=test_settings)
        update_result = kb.run()
        assert update_result.status == "ok"

    def test_pipeline_creates_all_outputs(self, test_settings: AppSettings, tmp_path: Path):
        """全ステップ実行後に必要ファイルが揃っている。"""
        perf_dir = tmp_path / "performance"
        _write_perf_json(perf_dir / "r.json", _make_perf_dict())

        PerformanceImporterAgent(settings=test_settings).run(input_dir=perf_dir)
        NoteAnalyzerAgent(settings=test_settings).run()
        KnowledgeBaseAgent(settings=test_settings).run()

        assert test_settings.performance_output_json.exists()
        assert test_settings.analytics_output_json.exists()
        assert test_settings.winning_patterns_json.exists()
        assert any(test_settings.weekly_report_dir.glob("weekly_report_*.md"))

    def test_pipeline_kpis_are_correct(self, test_settings: AppSettings, tmp_path: Path):
        """パイプライン実行後のKPI値が正しい。"""
        perf_dir = tmp_path / "performance"
        # 購入率: 10/100 = 10%
        _write_perf_json(perf_dir / "r1.json", _make_perf_dict(
            impressions=2000, likes=100, note_clicks=60,
            note_views=100, note_purchases=10, note_revenue=3000,
        ))
        _write_perf_json(perf_dir / "r2.json", _make_perf_dict(
            attribution_id="attr-20260407-xxxxxx",
            impressions=3000, likes=150, note_clicks=90,
            note_views=150, note_purchases=15, note_revenue=4500,
        ))

        PerformanceImporterAgent(settings=test_settings).run(input_dir=perf_dir)
        result = NoteAnalyzerAgent(settings=test_settings).run()
        report = result.report

        # 合計
        assert report.total_impressions == 5000
        assert report.total_note_purchases == 25
        assert report.total_revenue == 7500
        # 購入率: 25 / 250 = 10%
        assert abs(report.avg_purchase_rate - 0.10) < 0.001

    def test_pipeline_idempotent(self, test_settings: AppSettings, tmp_path: Path):
        """同じデータを2回importしても重複しない。"""
        perf_dir = tmp_path / "performance"
        _write_perf_json(perf_dir / "r.json", _make_perf_dict())

        importer = PerformanceImporterAgent(settings=test_settings)
        importer.run(input_dir=perf_dir)
        importer.run(input_dir=perf_dir)  # 2回目（同じファイル）

        loaded = load_performance_records(test_settings.performance_output_json)
        assert len(loaded) == 1  # 重複なし
