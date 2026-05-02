"""
note_publisher / promo_brief_generator のテスト

カバレッジ:
  - NotePublisherAgent: publish フロー、ステータスガード、dry_run
  - PromoBriefGeneratorAgent: 生成、保存、attribution 引き継ぎ
  - NotePublication / Campaign モデル
  - storage_json 入出力（publications / campaigns / promo_briefs）
  - 統合テスト: publish → generate_promo_brief
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.adapters.storage_json import (
    load_campaigns,
    load_promo_briefs,
    load_publications,
    save_campaign_append,
    save_promo_brief_append,
    save_publication_append,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.agents.note_publisher import (
    NotePublisherAgent,
    _campaign_name_from_title,
    _generate_attribution_id,
    _note_slug_from_title,
)
from src.agents.promo_brief_generator import PromoBriefGeneratorAgent
from src.core.models import (
    ArticleStatus,
    Campaign,
    NoteDraft,
    NotePublication,
    PainPoint,
    PromoBrief,
    TopicCandidate,
    make_dummy_campaign,
    make_dummy_draft,
    make_dummy_pain_point,
    make_dummy_promo_brief,
    make_dummy_publication,
)
from src.core.settings import AppSettings


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _make_publish_ready_draft(db: SQLiteStorage, candidate_id: str = "cand-001") -> NoteDraft:
    """publish_ready のドラフトをDBに保存して返す。"""
    draft = make_dummy_draft(candidate_id)
    draft.status = ArticleStatus.PUBLISH_READY
    db.save_draft(draft)
    return draft


def _make_approved_candidate(db: SQLiteStorage) -> TopicCandidate:
    """承認済み TopicCandidate を DB に保存して返す。"""
    pain = make_dummy_pain_point()
    db.save_pain_point(pain)

    candidate = TopicCandidate(
        candidate_id="cand-001",
        target_pain_id_list=[pain.pain_id],
        topic_title="【非エンジニアが2週間試した】Claude Code、正直に書く",
        hook="非エンジニアでも使えるか不安でしたか？",
        angle="体験談＋本音レポート",
        why_now="Claude Codeが話題になっているから",
        expected_buyer_intent="実際の使い方を知りたい",
        paid_reason="実践プロンプトが再現性あり",
        audience_type="非エンジニア・副業ワーカー",
        related_tags=["AI", "ClaudeCode", "副業"],
        approved=True,
        approved_at=datetime.now(),
        status=ArticleStatus.HUMAN_APPROVED,
    )
    db.save_topic_candidate(candidate)
    return candidate


# ---------------------------------------------------------------------------
# ヘルパー関数のテスト
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_attribution_id_format(self):
        draft_id = "abc123-xyz"
        attr_id = _generate_attribution_id(draft_id)
        assert attr_id.startswith("attr-")
        parts = attr_id.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD

    def test_generate_attribution_id_uses_draft_prefix(self):
        draft_id = "abc123xyz"
        attr_id = _generate_attribution_id(draft_id)
        assert attr_id.endswith("abc123")

    def test_campaign_name_ascii_title(self):
        title = "【非エンジニアが試した】Claude Code 2weeks"
        name = _campaign_name_from_title(title)
        assert "claude" in name
        assert name.endswith(datetime.now().strftime("%Y%m%d"))

    def test_campaign_name_japanese_only_title(self):
        title = "生成AIの使い方まとめ"
        name = _campaign_name_from_title(title)
        # ASCII ワードがない場合も動く
        assert len(name) > 0

    def test_note_slug_from_title(self):
        title = "【非エンジニア】Claude Code 入門"
        slug = _note_slug_from_title(title)
        assert "claude" in slug.lower()
        assert len(slug) <= 40


# ---------------------------------------------------------------------------
# NotePublication / Campaign モデル
# ---------------------------------------------------------------------------

class TestNotePublicationModel:
    def test_creation_with_required_fields(self):
        pub = NotePublication(
            draft_id="draft-001",
            note_title="テストタイトル",
            attribution_id="attr-20260407-abc123",
        )
        assert pub.id
        assert pub.draft_id == "draft-001"
        assert pub.attribution_id == "attr-20260407-abc123"
        assert pub.note_url is None

    def test_creation_with_url(self):
        pub = NotePublication(
            draft_id="draft-001",
            note_title="テストタイトル",
            attribution_id="attr-test",
            note_url="https://note.com/user/n/nxxxxxxxx",
        )
        assert pub.note_url == "https://note.com/user/n/nxxxxxxxx"

    def test_price_default(self):
        pub = NotePublication(
            draft_id="d1", note_title="t", attribution_id="a1"
        )
        assert pub.price == 300


class TestCampaignModel:
    def test_creation(self):
        camp = Campaign(
            name="test-campaign-20260407",
            attribution_id="attr-20260407-abc",
            draft_id="draft-001",
        )
        assert camp.campaign_id
        assert camp.status == "active"
        assert camp.publication_id is None

    def test_can_set_publication_id(self):
        camp = Campaign(
            name="camp", attribution_id="attr", draft_id="d1"
        )
        camp.publication_id = "pub-001"
        assert camp.publication_id == "pub-001"


# ---------------------------------------------------------------------------
# NotePublisherAgent
# ---------------------------------------------------------------------------

class TestNotePublisherAgent:
    def _make_agent(self, test_settings: AppSettings, dry_run: bool = False) -> NotePublisherAgent:
        return NotePublisherAgent(settings=test_settings, dry_run=dry_run)

    def test_publish_no_draft(self, test_settings: AppSettings):
        agent = self._make_agent(test_settings)
        result = agent.publish()
        assert result.status == "not_ready" or result.status == "no_draft"

    def test_publish_rejects_non_publish_ready(self, test_settings: AppSettings, tmp_db: SQLiteStorage):
        # DRAFT_CREATED ステータスのドラフトでは publish できない
        draft = make_dummy_draft("cand-001")
        draft.status = ArticleStatus.DRAFT_CREATED
        tmp_db.save_draft(draft)

        import src.core.settings as sm
        tmp_db2 = SQLiteStorage(test_settings.db_path)
        tmp_db2.save_draft(draft)

        agent = NotePublisherAgent(settings=test_settings, dry_run=False)
        result = agent.publish(draft_id=draft.id)
        assert result.status == "not_ready"
        assert "publish_ready" in result.message

    def test_publish_dry_run(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings, dry_run=True)
        result = agent.publish(draft_id=draft.id)
        assert result.status == "skipped"
        assert "[DRY-RUN]" in result.message
        assert result.publication is not None
        assert result.campaign is not None

    def test_publish_dry_run_does_not_change_draft_status(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings, dry_run=True)
        agent.publish(draft_id=draft.id)

        # DB 上のドラフトはまだ publish_ready のまま
        refreshed = db.get_draft(draft.id)
        assert refreshed.status == ArticleStatus.PUBLISH_READY

    def test_publish_ok_creates_publication(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.publish(draft_id=draft.id)
        assert result.status == "ok"
        assert result.publication is not None
        assert result.publication.draft_id == draft.id

    def test_publish_ok_creates_campaign(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.publish(draft_id=draft.id)
        assert result.campaign is not None
        assert result.campaign.attribution_id == result.publication.attribution_id

    def test_publish_ok_generates_attribution_id(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.publish(draft_id=draft.id)
        assert result.publication.attribution_id.startswith("attr-")

    def test_publish_ok_updates_draft_status(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        agent.publish(draft_id=draft.id)

        refreshed = db.get_draft(draft.id)
        assert refreshed.status == ArticleStatus.PUBLISHED

    def test_publish_saves_to_sqlite(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.publish(draft_id=draft.id)

        pub = db.get_publication(result.publication.id)
        assert pub is not None
        camp = db.get_campaign(result.campaign.campaign_id)
        assert camp is not None

    def test_publish_saves_to_json(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.publish(draft_id=draft.id)
        assert result.output_json is not None
        assert result.output_json.exists()

        pubs = load_publications(test_settings.publications_json)
        assert any(p.id == result.publication.id for p in pubs)

    def test_publish_with_url(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.publish(
            draft_id=draft.id,
            note_url="https://note.com/testuser/n/nxxxxxxxx",
        )
        assert result.publication.note_url == "https://note.com/testuser/n/nxxxxxxxx"

        # ドラフトにも URL が反映されている
        refreshed = db.get_draft(draft.id)
        assert refreshed.note_url == "https://note.com/testuser/n/nxxxxxxxx"

    def test_publish_without_url_has_slug(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.publish(draft_id=draft.id)
        assert result.publication.note_slug is not None
        assert len(result.publication.note_slug) > 0


# ---------------------------------------------------------------------------
# PromoBriefGeneratorAgent
# ---------------------------------------------------------------------------

class TestPromoBriefGeneratorAgent:
    def _make_agent(self, test_settings: AppSettings, dry_run: bool = False) -> PromoBriefGeneratorAgent:
        return PromoBriefGeneratorAgent(settings=test_settings, dry_run=dry_run)

    def test_run_no_draft(self, test_settings: AppSettings):
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.status == "no_draft"

    def test_run_with_publish_ready_draft(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        _make_approved_candidate(db)
        draft = _make_publish_ready_draft(db, "cand-001")

        agent = self._make_agent(test_settings)
        result = agent.run(draft_id=draft.id)
        assert result.status == "ok"
        assert result.brief is not None

    def test_run_with_published_draft(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        _make_approved_candidate(db)
        draft = _make_publish_ready_draft(db, "cand-001")
        draft.status = ArticleStatus.PUBLISHED
        db.save_draft(draft)

        agent = self._make_agent(test_settings)
        result = agent.run(draft_id=draft.id)
        assert result.status == "ok"

    def test_run_dry_run(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings, dry_run=True)
        result = agent.run(draft_id=draft.id)
        assert result.status == "skipped"
        assert "[DRY-RUN]" in result.message
        assert result.brief is not None

    def test_run_dry_run_does_not_save(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings, dry_run=True)
        result = agent.run(draft_id=draft.id)

        # DB に保存されていない
        promo_briefs_json = test_settings.promo_brief_output_dir / "promo_briefs.json"
        assert not promo_briefs_json.exists()

    def test_run_brief_has_required_fields(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        _make_approved_candidate(db)
        draft = _make_publish_ready_draft(db, "cand-001")

        agent = self._make_agent(test_settings)
        result = agent.run(draft_id=draft.id)
        brief = result.brief

        assert brief.article_title
        assert brief.key_message
        assert brief.target_audience
        assert isinstance(brief.target_pains, list)
        assert isinstance(brief.avoid_expressions, list)
        assert brief.preferred_post_window
        assert len(brief.hook_options) >= 1

    def test_run_brief_article_summary_populated(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.run(draft_id=draft.id)
        assert len(result.brief.article_summary) > 0

    def test_run_brief_avoid_expressions_not_empty(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.run(draft_id=draft.id)
        assert len(result.brief.avoid_expressions) > 0

    def test_run_saves_to_sqlite(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.run(draft_id=draft.id)

        saved = db.get_promo_brief(result.brief.id)
        assert saved is not None
        assert saved.draft_id == draft.id

    def test_run_exports_json_file(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        result = agent.run(draft_id=draft.id)
        assert result.output_json is not None
        assert result.output_json.exists()
        assert result.output_json.name.startswith("promo_brief_")

    def test_run_updates_draft_status(self, test_settings: AppSettings):
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        agent = self._make_agent(test_settings)
        agent.run(draft_id=draft.id)

        refreshed = db.get_draft(draft.id)
        assert refreshed.status == ArticleStatus.PROMO_BRIEF_READY

    def test_run_with_publication_has_attribution_id(self, test_settings: AppSettings):
        """publish-note 後に generate-promo-brief すると attribution_id が引き継がれる。"""
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        # publish
        publisher = NotePublisherAgent(settings=test_settings)
        pub_result = publisher.publish(draft_id=draft.id)
        assert pub_result.status == "ok"

        # generate promo brief
        gen = self._make_agent(test_settings)
        result = gen.run(draft_id=draft.id)
        assert result.status == "ok"
        assert result.brief.attribution_id == pub_result.publication.attribution_id
        assert result.brief.note_id == pub_result.publication.id

    def test_run_target_pains_from_candidate(self, test_settings: AppSettings):
        """TopicCandidate + PainPoint が揃っていると target_pains が埋まる。"""
        db = SQLiteStorage(test_settings.db_path)
        _make_approved_candidate(db)
        draft = _make_publish_ready_draft(db, "cand-001")

        agent = self._make_agent(test_settings)
        result = agent.run(draft_id=draft.id)
        assert len(result.brief.target_pains) > 0


# ---------------------------------------------------------------------------
# storage_json: publications / campaigns / promo_briefs 入出力
# ---------------------------------------------------------------------------

class TestStorageJsonPublications:
    def test_save_and_load_publications(self, tmp_path: Path):
        output = tmp_path / "publications.json"
        pub = make_dummy_publication("draft-001")
        save_publication_append(pub, output)

        loaded = load_publications(output)
        assert len(loaded) == 1
        assert loaded[0].id == pub.id
        assert loaded[0].attribution_id == pub.attribution_id

    def test_append_deduplicates(self, tmp_path: Path):
        output = tmp_path / "publications.json"
        pub = make_dummy_publication("draft-001")
        save_publication_append(pub, output)
        save_publication_append(pub, output)  # 同じIDを2回

        loaded = load_publications(output)
        assert len(loaded) == 1

    def test_load_nonexistent_returns_empty(self, tmp_path: Path):
        result = load_publications(tmp_path / "nonexistent.json")
        assert result == []


class TestStorageJsonCampaigns:
    def test_save_and_load_campaigns(self, tmp_path: Path):
        output = tmp_path / "campaigns.json"
        pub = make_dummy_publication("draft-001")
        camp = make_dummy_campaign("draft-001", pub.id)
        save_campaign_append(camp, output)

        loaded = load_campaigns(output)
        assert len(loaded) == 1
        assert loaded[0].campaign_id == camp.campaign_id

    def test_append_deduplicates(self, tmp_path: Path):
        output = tmp_path / "campaigns.json"
        pub = make_dummy_publication("draft-001")
        camp = make_dummy_campaign("draft-001", pub.id)
        save_campaign_append(camp, output)
        save_campaign_append(camp, output)

        loaded = load_campaigns(output)
        assert len(loaded) == 1


class TestStorageJsonPromoBriefs:
    def test_save_and_load_promo_briefs(self, tmp_path: Path):
        output = tmp_path / "promo_briefs.json"
        draft = make_dummy_draft("cand-001")
        brief = make_dummy_promo_brief(draft.id, "https://note.com/test/n/abc")
        save_promo_brief_append(brief, output)

        loaded = load_promo_briefs(output)
        assert len(loaded) == 1
        assert loaded[0].id == brief.id
        assert loaded[0].attribution_id == brief.attribution_id

    def test_append_deduplicates(self, tmp_path: Path):
        output = tmp_path / "promo_briefs.json"
        draft = make_dummy_draft("cand-001")
        brief = make_dummy_promo_brief(draft.id, "https://note.com/test")
        save_promo_brief_append(brief, output)
        save_promo_brief_append(brief, output)

        loaded = load_promo_briefs(output)
        assert len(loaded) == 1


# ---------------------------------------------------------------------------
# SQLiteStorage: publications / campaigns CRUD
# ---------------------------------------------------------------------------

class TestSQLiteStoragePublications:
    def test_save_and_get(self, tmp_db: SQLiteStorage):
        pub = make_dummy_publication("draft-001")
        tmp_db.save_publication(pub)
        retrieved = tmp_db.get_publication(pub.id)
        assert retrieved is not None
        assert retrieved.id == pub.id
        assert retrieved.attribution_id == pub.attribution_id

    def test_get_by_draft_id(self, tmp_db: SQLiteStorage):
        pub = make_dummy_publication("draft-abc")
        tmp_db.save_publication(pub)
        retrieved = tmp_db.get_publication_by_draft_id("draft-abc")
        assert retrieved is not None
        assert retrieved.id == pub.id

    def test_get_nonexistent(self, tmp_db: SQLiteStorage):
        assert tmp_db.get_publication("nonexistent") is None
        assert tmp_db.get_publication_by_draft_id("nonexistent") is None

    def test_list_publications(self, tmp_db: SQLiteStorage):
        pub1 = make_dummy_publication("draft-001")
        pub2 = make_dummy_publication("draft-002")
        tmp_db.save_publication(pub1)
        tmp_db.save_publication(pub2)
        pubs = tmp_db.list_publications()
        assert len(pubs) == 2


class TestSQLiteStorageCampaigns:
    def test_save_and_get(self, tmp_db: SQLiteStorage):
        pub = make_dummy_publication("draft-001")
        camp = make_dummy_campaign("draft-001", pub.id)
        tmp_db.save_campaign(camp)
        retrieved = tmp_db.get_campaign(camp.campaign_id)
        assert retrieved is not None
        assert retrieved.attribution_id == camp.attribution_id

    def test_get_by_draft_id(self, tmp_db: SQLiteStorage):
        pub = make_dummy_publication("draft-001")
        camp = make_dummy_campaign("draft-001", pub.id)
        tmp_db.save_campaign(camp)
        retrieved = tmp_db.get_campaign_by_draft_id("draft-001")
        assert retrieved is not None

    def test_list_campaigns(self, tmp_db: SQLiteStorage):
        for i in range(3):
            pub = make_dummy_publication(f"draft-{i:03}")
            camp = make_dummy_campaign(f"draft-{i:03}", pub.id)
            tmp_db.save_campaign(camp)
        camps = tmp_db.list_campaigns()
        assert len(camps) == 3

    def test_list_campaigns_filter_by_status(self, tmp_db: SQLiteStorage):
        pub = make_dummy_publication("draft-001")
        camp = make_dummy_campaign("draft-001", pub.id)
        camp.status = "closed"
        tmp_db.save_campaign(camp)

        active = tmp_db.list_campaigns(status="active")
        closed = tmp_db.list_campaigns(status="closed")
        assert len(active) == 0
        assert len(closed) == 1


# ---------------------------------------------------------------------------
# 統合テスト: publish → generate_promo_brief パイプライン
# ---------------------------------------------------------------------------

class TestPublishToPromoBriefPipeline:
    def test_full_pipeline(self, test_settings: AppSettings):
        """publish → generate_promo_brief の一連フローが動作する。"""
        db = SQLiteStorage(test_settings.db_path)
        _make_approved_candidate(db)
        draft = _make_publish_ready_draft(db, "cand-001")

        # Step 1: publish
        publisher = NotePublisherAgent(settings=test_settings)
        pub_result = publisher.publish(
            draft_id=draft.id,
            note_url="https://note.com/testuser/n/ntest123",
        )
        assert pub_result.status == "ok"

        # Step 2: generate promo brief
        generator = PromoBriefGeneratorAgent(settings=test_settings)
        brief_result = generator.run(draft_id=draft.id)
        assert brief_result.status == "ok"

        brief = brief_result.brief
        assert brief.attribution_id == pub_result.publication.attribution_id
        assert brief.note_id == pub_result.publication.id
        assert brief.note_url == "https://note.com/testuser/n/ntest123"
        assert brief.draft_id == draft.id

    def test_pipeline_draft_status_progression(self, test_settings: AppSettings):
        """ドラフトのステータスが publish_ready → published → promo_brief_ready に進む。"""
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)
        assert db.get_draft(draft.id).status == ArticleStatus.PUBLISH_READY

        publisher = NotePublisherAgent(settings=test_settings)
        publisher.publish(draft_id=draft.id)
        assert db.get_draft(draft.id).status == ArticleStatus.PUBLISHED

        generator = PromoBriefGeneratorAgent(settings=test_settings)
        generator.run(draft_id=draft.id)
        assert db.get_draft(draft.id).status == ArticleStatus.PROMO_BRIEF_READY

    def test_pipeline_json_files_created(self, test_settings: AppSettings):
        """publications.json / campaigns.json / promo_brief_xxx.json が生成される。"""
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        publisher = NotePublisherAgent(settings=test_settings)
        publisher.publish(draft_id=draft.id)

        generator = PromoBriefGeneratorAgent(settings=test_settings)
        generator.run(draft_id=draft.id)

        assert test_settings.publications_json.exists()
        assert test_settings.campaigns_json.exists()
        assert any(test_settings.promo_brief_output_dir.glob("promo_brief_*.json"))

    def test_pipeline_attribution_id_consistency(self, test_settings: AppSettings):
        """publication / campaign / promo_brief の attribution_id が全て一致する。"""
        db = SQLiteStorage(test_settings.db_path)
        draft = _make_publish_ready_draft(db)

        publisher = NotePublisherAgent(settings=test_settings)
        pub_result = publisher.publish(draft_id=draft.id)
        attr_id = pub_result.publication.attribution_id

        generator = PromoBriefGeneratorAgent(settings=test_settings)
        brief_result = generator.run(draft_id=draft.id)

        # NotePublication の attribution_id
        pub = db.get_publication(pub_result.publication.id)
        assert pub.attribution_id == attr_id

        # Campaign の attribution_id
        camp = db.get_campaign_by_draft_id(draft.id)
        assert camp.attribution_id == attr_id

        # PromoBrief の attribution_id
        assert brief_result.brief.attribution_id == attr_id
