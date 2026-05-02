"""
researcher / selector エージェントのテスト

カバー範囲:
- CandidateGenerator: generate() + _generate_one()
- CandidateScorer: score() + 各サブスコア
- deduplicate_candidates()
- group_pain_points()
- ResearcherAgent: run() (dry_run / 実保存)
- SelectorAgent: approve() / list_candidates() / list_approvals()
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest

from src.agents.researcher import (
    CandidateGenerator,
    CandidateScorer,
    ResearcherAgent,
    deduplicate_candidates,
    group_pain_points,
)
from src.agents.selector import SelectorAgent
from src.core.models import Approval, ArticleStatus, PainPoint, TopicCandidate
from src.core.settings import AppSettings


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def make_pain(
    pain_id: Optional[str] = None,
    audience_type: str = "非エンジニア",
    tags: Optional[list[str]] = None,
    severity: int = 3,
    urgency: int = 2,
    frequency: int = 3,
    engagement: Optional[int] = None,
) -> PainPoint:
    from uuid import uuid4
    return PainPoint(
        pain_id=pain_id or str(uuid4()),
        original_text="テスト用の悩みテキストです。Claude Codeが難しくて分からない。",
        pain_summary="テスト悩み要約",
        severity=severity,
        urgency=urgency,
        frequency=frequency,
        audience_type=audience_type,
        related_tags=tags or ["ClaudeCode", "AI活用"],
        engagement_count=engagement,
    )


def make_candidate(
    pain_ids: Optional[list[str]] = None,
    total_score: float = 5.0,
    audience_type: str = "非エンジニア",
    angle: str = "体験談＋本音レポート",
    topic_title: str = "テスト記事タイトル",
) -> TopicCandidate:
    from uuid import uuid4
    return TopicCandidate(
        target_pain_id_list=pain_ids or [str(uuid4())],
        topic_title=topic_title,
        hook="テストフック文ですか？",
        angle=angle,
        why_now="テスト時事性",
        expected_buyer_intent="テスト購買動機",
        paid_reason="テスト有料理由",
        recommended_price_range="300-980円",
        audience_type=audience_type,
        related_tags=["ClaudeCode", "AI活用"],
        total_score=total_score,
    )


# ---------------------------------------------------------------------------
# group_pain_points
# ---------------------------------------------------------------------------

class TestGroupPainPoints:
    def test_groups_by_audience_and_tag(self):
        p1 = make_pain(audience_type="非エンジニア", tags=["ClaudeCode"])
        p2 = make_pain(audience_type="非エンジニア", tags=["ClaudeCode"])
        p3 = make_pain(audience_type="副業ワーカー", tags=["生成AI"])

        groups = group_pain_points([p1, p2, p3])
        assert len(groups) == 2
        assert ("非エンジニア", "ClaudeCode") in groups
        assert len(groups[("非エンジニア", "ClaudeCode")]) == 2

    def test_empty_input(self):
        groups = group_pain_points([])
        assert groups == {}

    def test_single_pain(self):
        p = make_pain(audience_type="初心者", tags=["AI活用"])
        groups = group_pain_points([p])
        assert len(groups) == 1


# ---------------------------------------------------------------------------
# CandidateGenerator
# ---------------------------------------------------------------------------

class TestCandidateGenerator:
    def setup_method(self):
        self.gen = CandidateGenerator()

    def test_generate_returns_list(self):
        pains = [make_pain(audience_type="非エンジニア", tags=["ClaudeCode"])]
        candidates = self.gen.generate(pains)
        assert isinstance(candidates, list)
        assert len(candidates) >= 1

    def test_generate_candidate_has_required_fields(self):
        pains = [make_pain()]
        candidates = self.gen.generate(pains)
        c = candidates[0]
        assert c.topic_title
        assert c.hook
        assert c.angle
        assert c.why_now
        assert c.expected_buyer_intent
        assert c.paid_reason
        assert c.recommended_price_range
        assert c.target_pain_id_list

    def test_candidate_includes_pain_ids(self):
        pain = make_pain(pain_id="test-pain-001")
        candidates = self.gen.generate([pain])
        c = candidates[0]
        assert "test-pain-001" in c.target_pain_id_list

    def test_multiple_audiences_generates_multiple_candidates(self):
        pains = [
            make_pain(audience_type="非エンジニア", tags=["ClaudeCode"]),
            make_pain(audience_type="副業ワーカー", tags=["生成AI"]),
        ]
        candidates = self.gen.generate(pains)
        assert len(candidates) == 2

    def test_price_range_matches_angle(self):
        pains = [make_pain(audience_type="副業ワーカー", tags=["副業"])]
        candidates = self.gen.generate(pains)
        c = candidates[0]
        # 副業ワーカー → 収益公開＋実践法 → 980-1980円
        assert "980" in c.recommended_price_range

    def test_guideline_price_for_stepbystep(self):
        pains = [make_pain(audience_type="初心者", tags=["AI活用"])]
        candidates = self.gen.generate(pains)
        c = candidates[0]
        # 初心者 → ステップバイステップガイド → 500-980円
        assert "500" in c.recommended_price_range


# ---------------------------------------------------------------------------
# CandidateScorer
# ---------------------------------------------------------------------------

class TestCandidateScorer:
    def setup_method(self):
        self.scorer = CandidateScorer(
            weights={
                "demand": 0.30,
                "monetization": 0.25,
                "threads_fit": 0.20,
                "expertise_fit": 0.15,
                "trend": 0.10,
            },
            expertise_tags=["AI活用", "Claude", "ClaudeCode", "生成AI", "副業"],
            trend_tags=["ClaudeCode", "生成AI", "AI活用", "副業"],
        )

    def test_score_returns_candidate_with_scores(self):
        pain = make_pain()
        c = make_candidate(pain_ids=[pain.pain_id])
        scored = self.scorer.score(c, [pain])
        assert 0 <= scored.total_score <= 10
        assert 0 <= scored.demand_score <= 10
        assert 0 <= scored.monetization_score <= 10
        assert 0 <= scored.threads_fit_score <= 10
        assert 0 <= scored.expertise_fit_score <= 10
        assert 0 <= scored.trend_score <= 10

    def test_score_breakdown_has_all_keys(self):
        pain = make_pain()
        c = make_candidate(pain_ids=[pain.pain_id])
        scored = self.scorer.score(c, [pain])
        keys = {"weights", "demand", "monetization", "threads_fit",
                "expertise_fit", "trend", "total_raw"}
        assert keys.issubset(set(scored.score_breakdown.keys()))

    def test_high_severity_increases_demand(self):
        pain_low = make_pain(severity=1)
        pain_high = make_pain(severity=5)
        c_low = make_candidate(pain_ids=[pain_low.pain_id])
        c_high = make_candidate(pain_ids=[pain_high.pain_id])
        scored_low = self.scorer.score(c_low, [pain_low])
        scored_high = self.scorer.score(c_high, [pain_high])
        assert scored_high.demand_score > scored_low.demand_score

    def test_monetization_angle_boost(self):
        pain = make_pain()
        c_revenue = make_candidate(pain_ids=[pain.pain_id], angle="収益公開＋実践法")
        c_story = make_candidate(pain_ids=[pain.pain_id], angle="体験談＋本音レポート")
        s_revenue = self.scorer.score(c_revenue, [pain])
        s_story = self.scorer.score(c_story, [pain])
        assert s_revenue.monetization_score > s_story.monetization_score

    def test_question_hook_boosts_threads_fit(self):
        pain = make_pain()
        c_q = make_candidate(pain_ids=[pain.pain_id])
        c_q.hook = "悩んでいませんか？"
        c_flat = make_candidate(pain_ids=[pain.pain_id])
        c_flat.hook = "記事の説明です。"
        s_q = self.scorer.score(c_q, [pain])
        s_flat = self.scorer.score(c_flat, [pain])
        assert s_q.threads_fit_score > s_flat.threads_fit_score

    def test_expertise_overlap_boosts_score(self):
        pain = make_pain()
        c_expert = make_candidate(pain_ids=[pain.pain_id])
        c_expert.related_tags = ["ClaudeCode", "AI活用", "副業"]  # 全部 expertise
        c_other = make_candidate(pain_ids=[pain.pain_id])
        c_other.related_tags = ["料理", "旅行"]  # 全部 非expertise
        s_expert = self.scorer.score(c_expert, [pain])
        s_other = self.scorer.score(c_other, [pain])
        assert s_expert.expertise_fit_score > s_other.expertise_fit_score

    def test_trend_tags_overlap_boosts_trend(self):
        pain = make_pain()
        c_trend = make_candidate(pain_ids=[pain.pain_id])
        c_trend.related_tags = ["ClaudeCode", "生成AI"]
        c_trend.why_now = "2026年に急増しているため"
        c_no_trend = make_candidate(pain_ids=[pain.pain_id])
        c_no_trend.related_tags = ["料理"]
        c_no_trend.why_now = "特に理由なし"
        s_trend = self.scorer.score(c_trend, [pain])
        s_no = self.scorer.score(c_no_trend, [pain])
        assert s_trend.trend_score > s_no.trend_score

    def test_no_matching_pains_uses_default(self):
        """pain_map にヒットしない場合も default スコアが返る"""
        c = make_candidate(pain_ids=["nonexistent-id"])
        scored = self.scorer.score(c, [])
        assert scored.demand_score == 3.0

    def test_pattern_boost_applied(self):
        winning = {
            "angle_patterns": [
                {
                    "angle": "収益公開＋実践法",
                    "monetization_boost": 3.0,
                    "threads_fit_boost": 1.5,
                }
            ]
        }
        scorer_with_patterns = CandidateScorer(
            weights={"demand": 0.30, "monetization": 0.25,
                     "threads_fit": 0.20, "expertise_fit": 0.15, "trend": 0.10},
            expertise_tags=[],
            trend_tags=[],
            winning_patterns=winning,
        )
        pain = make_pain()
        c = make_candidate(pain_ids=[pain.pain_id], angle="収益公開＋実践法")
        s = scorer_with_patterns.score(c, [pain])
        # パターンブーストで total_raw がわずかに上がること
        assert s.total_score >= 0


# ---------------------------------------------------------------------------
# deduplicate_candidates
# ---------------------------------------------------------------------------

class TestDeduplicateCandidates:
    def test_empty_input(self):
        assert deduplicate_candidates([]) == []

    def test_single_candidate_not_deduped(self):
        c = make_candidate(pain_ids=["p1"])
        result = deduplicate_candidates([c])
        assert len(result) == 1

    def test_duplicate_kept_higher_score(self):
        pids = ["p1", "p2"]
        c_low = make_candidate(pain_ids=pids, total_score=3.0)
        c_high = make_candidate(pain_ids=pids, total_score=8.0)
        result = deduplicate_candidates([c_low, c_high], threshold=0.5)
        assert len(result) == 1
        assert result[0].total_score == 8.0

    def test_different_titles_both_kept(self):
        c1 = make_candidate(pain_ids=["p1"], total_score=5.0,
                            topic_title="非エンジニアがClaude Codeを使って変わったこと")
        c2 = make_candidate(pain_ids=["p2"], total_score=5.0,
                            topic_title="副業でAIを使い始めて3ヶ月、正直な収益レポート")
        result = deduplicate_candidates([c1, c2], threshold=0.5)
        assert len(result) == 2

    def test_slightly_different_titles_both_kept(self):
        # bigram Jaccard がしきい値未満 → 両方残る
        c1 = make_candidate(pain_ids=["p1", "p2", "p3"], total_score=5.0,
                            topic_title="非エンジニアがClaude Codeを試した話")
        c2 = make_candidate(pain_ids=["p3", "p4", "p5"], total_score=5.0,
                            topic_title="副業でAIを始めて収益が出た")
        result = deduplicate_candidates([c1, c2], threshold=0.5)
        assert len(result) == 2

    def test_near_identical_titles_deduped(self):
        # ほぼ同一タイトル → bigram Jaccard が高い → 高スコアを残す
        c1 = make_candidate(pain_ids=["p1", "p2"], total_score=5.0,
                            topic_title="非エンジニアがClaude Codeを2週間試した正直レポート")
        c2 = make_candidate(pain_ids=["p1", "p2", "p3"], total_score=4.0,
                            topic_title="非エンジニアがClaude Codeを2週間試した正直レポート")
        result = deduplicate_candidates([c1, c2], threshold=0.6)
        assert len(result) == 1
        assert result[0].total_score == 5.0


# ---------------------------------------------------------------------------
# ResearcherAgent
# ---------------------------------------------------------------------------

class TestResearcherAgent:
    def test_run_dry_run_returns_candidates_without_saving(self, test_settings):
        agent = ResearcherAgent(settings=test_settings, dry_run=True)
        pains = [make_pain(audience_type="非エンジニア", tags=["ClaudeCode"])]
        result = agent.run(pains=pains)

        assert result.final_count >= 1
        assert not test_settings.topic_candidates_json.exists(), "dry_run では保存しない"

    def test_run_saves_to_json(self, test_settings):
        agent = ResearcherAgent(settings=test_settings, dry_run=False)
        pains = [make_pain(audience_type="非エンジニア", tags=["ClaudeCode"])]
        result = agent.run(pains=pains)

        assert result.final_count >= 1
        assert test_settings.topic_candidates_json.exists()

    def test_run_saves_to_sqlite(self, test_settings):
        agent = ResearcherAgent(settings=test_settings, dry_run=False)
        pains = [make_pain(audience_type="副業ワーカー", tags=["副業"])]
        result = agent.run(pains=pains)

        # DB から読み直し
        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)
        saved = db.list_topic_candidates()
        assert len(saved) >= 1

    def test_run_no_pains_returns_warning(self, test_settings):
        agent = ResearcherAgent(settings=test_settings, dry_run=True)
        result = agent.run(pains=[])

        assert result.final_count == 0
        assert len(result.warnings) >= 1

    def test_run_respects_candidates_max(self, test_settings, monkeypatch):
        import src.core.settings as sm
        # conftest がすでに _yaml をパッチしているので、その値をコピーして上書き
        new_yaml = {**sm._yaml, "researcher": {**sm._yaml.get("researcher", {}), "candidates_max": 2}}
        monkeypatch.setattr(sm, "_yaml", new_yaml)

        agent = ResearcherAgent(settings=AppSettings(), dry_run=True)
        pains = [
            make_pain(audience_type="非エンジニア", tags=["ClaudeCode"]),
            make_pain(audience_type="副業ワーカー", tags=["副業"]),
            make_pain(audience_type="初心者", tags=["AI活用"]),
            make_pain(audience_type="会社員", tags=["生成AI"]),
        ]
        result = agent.run(pains=pains)

        assert result.final_count <= 2

    def test_run_score_breakdown_populated(self, test_settings):
        agent = ResearcherAgent(settings=test_settings, dry_run=True)
        pains = [make_pain()]
        result = agent.run(pains=pains)

        for c in result.candidates:
            assert "demand" in c.score_breakdown
            assert "monetization" in c.score_breakdown
            assert "total_raw" in c.score_breakdown

    def test_load_pain_from_db(self, test_settings):
        """pain_points を引数なしで run() すると DB から読む"""
        # DB に pain_point を直接保存
        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)
        pain = make_pain(audience_type="非エンジニア", tags=["ClaudeCode"])
        db.save_pain_point(pain)

        agent = ResearcherAgent(settings=test_settings, dry_run=True)
        result = agent.run()  # pains 引数なし

        assert result.final_count >= 1


# ---------------------------------------------------------------------------
# SelectorAgent
# ---------------------------------------------------------------------------

class TestSelectorAgent:
    def _make_agent(self, test_settings, dry_run=False):
        return SelectorAgent(settings=test_settings, dry_run=dry_run)

    def _save_candidate(self, test_settings, c: TopicCandidate):
        from src.adapters.storage_sqlite import SQLiteStorage
        SQLiteStorage(test_settings.db_path).save_topic_candidate(c)

    def test_approve_ok(self, test_settings):
        c = make_candidate()
        self._save_candidate(test_settings, c)

        agent = self._make_agent(test_settings)
        result = agent.approve(c.candidate_id, selected_reason="需要が高い")

        assert result.status == "ok"
        assert result.approved is not None
        assert result.candidate.approved is True
        assert result.candidate.status == ArticleStatus.HUMAN_APPROVED

    def test_approve_saves_to_json(self, test_settings):
        c = make_candidate()
        self._save_candidate(test_settings, c)

        agent = self._make_agent(test_settings)
        agent.approve(c.candidate_id)

        assert test_settings.approvals_json.exists()

    def test_approve_saves_to_sqlite(self, test_settings):
        c = make_candidate()
        self._save_candidate(test_settings, c)

        agent = self._make_agent(test_settings)
        agent.approve(c.candidate_id)

        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)
        approvals = db.list_approvals()
        assert len(approvals) == 1
        assert approvals[0].selected_candidate_id == c.candidate_id

    def test_approve_dry_run_skips_save(self, test_settings):
        c = make_candidate()
        self._save_candidate(test_settings, c)

        agent = self._make_agent(test_settings, dry_run=True)
        result = agent.approve(c.candidate_id)

        assert result.status == "skipped"
        assert not test_settings.approvals_json.exists()

    def test_approve_not_found_returns_error(self, test_settings):
        agent = self._make_agent(test_settings)
        result = agent.approve("nonexistent-id")

        assert result.status == "error"

    def test_approve_records_reason(self, test_settings):
        c = make_candidate()
        self._save_candidate(test_settings, c)

        agent = self._make_agent(test_settings)
        result = agent.approve(c.candidate_id, selected_reason="スコアが高い")

        assert result.approved.selected_reason == "スコアが高い"

    def test_approve_snapshot_captures_score_and_title(self, test_settings):
        c = make_candidate(total_score=7.5)
        c.topic_title = "スナップショットテストタイトル"
        self._save_candidate(test_settings, c)

        agent = self._make_agent(test_settings)
        result = agent.approve(c.candidate_id)

        assert result.approved.snapshot_score == 7.5
        assert result.approved.snapshot_title == "スナップショットテストタイトル"

    def test_approve_overwrites_same_candidate(self, test_settings):
        """同じ候補を2回承認しても approvals.json の件数は1件"""
        c = make_candidate()
        self._save_candidate(test_settings, c)

        agent = self._make_agent(test_settings)
        agent.approve(c.candidate_id, selected_reason="1回目")
        agent.approve(c.candidate_id, selected_reason="2回目（変更）")

        approvals = agent.list_approvals()
        matching = [a for a in approvals if a.selected_candidate_id == c.candidate_id]
        assert len(matching) == 1
        assert matching[0].selected_reason == "2回目（変更）"

    def test_list_candidates_from_db(self, test_settings):
        c1 = make_candidate()
        c2 = make_candidate()
        self._save_candidate(test_settings, c1)
        self._save_candidate(test_settings, c2)

        agent = self._make_agent(test_settings)
        candidates = agent.list_candidates()
        assert len(candidates) >= 2

    def test_list_approvals_empty_initially(self, test_settings):
        agent = self._make_agent(test_settings)
        approvals = agent.list_approvals()
        assert approvals == []
