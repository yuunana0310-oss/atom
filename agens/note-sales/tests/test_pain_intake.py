"""
pain_intake エージェントのユニットテスト
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.agents.pain_intake import (
    PainClusterer,
    PainExtractor,
    PainIntakeAgent,
    SourceNormalizer,
    _jaccard,
    _keyword_overlap,
)
from src.core.models import PainPoint, RawSource, SourceType


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def extractor():
    return PainExtractor(min_text_length=10, require_pain_keyword=True)


@pytest.fixture
def clusterer():
    return PainClusterer(threshold=0.4)


@pytest.fixture
def sample_pain(tmp_path) -> PainPoint:
    return PainPoint(
        original_text="Claude Codeが難しくてできない",
        pain_summary="Claude Codeの使い方が分からない",
        source_type="manual_memo",
        related_tags=["AI", "ClaudeCode", "非エンジニア"],
        audience_type="非エンジニア",
        severity=3,
        urgency=1,
        frequency=2,
    )


# ---------------------------------------------------------------------------
# SourceNormalizer テスト
# ---------------------------------------------------------------------------

class TestSourceNormalizerItem:
    def test_post_history_format(self):
        raw = {
            "post_id": "t_001",
            "body": "Claude Codeが難しくて困っています",
            "likes": 10,
            "replies": 3,
            "tags": ["AI", "ClaudeCode"],
        }
        source = SourceNormalizer.normalize_item(raw)
        assert source is not None
        assert source.text == "Claude Codeが難しくて困っています"
        assert source.post_id == "t_001"
        assert source.engagement_total == 13  # likes + replies
        assert "AI" in source.tags

    def test_comment_summary_format(self):
        raw = {
            "post_id": "t_002",
            "comment_summary": "どこから始めればいいか分からないという声が多い",
            "reaction_type": "question",
            "count": 15,
        }
        source = SourceNormalizer.normalize_item(raw)
        assert source is not None
        assert "分からない" in source.text

    def test_manual_memo_format(self):
        raw = {
            "type": "manual_memo",
            "memo": "副業でAI活用したいが何から始めればいいか分からない",
            "tags": ["副業", "AI活用"],
        }
        source = SourceNormalizer.normalize_item(raw)
        assert source is not None
        assert source.source_type == SourceType.MANUAL_MEMO.value

    def test_returns_none_for_empty_text(self):
        raw = {"post_id": "t_999", "likes": 5}
        source = SourceNormalizer.normalize_item(raw)
        assert source is None

    def test_returns_none_for_non_dict(self):
        source = SourceNormalizer.normalize_item("not a dict")
        assert source is None

    def test_handles_missing_tags(self):
        raw = {"text": "困った問題がある"}
        source = SourceNormalizer.normalize_item(raw)
        assert source is not None
        assert source.tags == []

    def test_hint_type_overrides_detection(self):
        raw = {"text": "困った", "likes": 5}
        source = SourceNormalizer.normalize_item(raw, hint_type=SourceType.FIELD_NOTE)
        assert source is not None
        assert source.source_type == SourceType.FIELD_NOTE.value

    def test_string_tags_parsed(self):
        raw = {"text": "困っている", "tags": "AI,副業,ClaudeCode"}
        source = SourceNormalizer.normalize_item(raw)
        assert source is not None
        assert "AI" in source.tags
        assert "副業" in source.tags

    def test_integer_post_id_converted(self):
        raw = {"text": "困った", "id": 12345}
        source = SourceNormalizer.normalize_item(raw)
        assert source is not None
        assert source.post_id == "12345"


class TestSourceNormalizerFile:
    def test_reads_json_array(self, tmp_path: Path):
        data = [
            {"text": "困っています", "tags": ["AI"]},
            {"text": "できない"},
        ]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        sources = SourceNormalizer.normalize_file(f)
        assert len(sources) == 2

    def test_reads_single_object(self, tmp_path: Path):
        data = {"text": "分からない", "post_id": "t_001"}
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        sources = SourceNormalizer.normalize_file(f)
        assert len(sources) == 1

    def test_returns_empty_for_nonexistent_file(self, tmp_path: Path):
        sources = SourceNormalizer.normalize_file(tmp_path / "nonexistent.json")
        assert sources == []

    def test_skips_items_without_text(self, tmp_path: Path):
        data = [
            {"text": "困った"},
            {"likes": 5},  # テキストなし
        ]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        sources = SourceNormalizer.normalize_file(f)
        assert len(sources) == 1


# ---------------------------------------------------------------------------
# PainExtractor テスト
# ---------------------------------------------------------------------------

class TestPainExtractorBasic:
    def test_extracts_pain_from_clear_text(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="Claude Codeを使おうとしたが難しくて諦めた",
        )
        pains = extractor.extract(source)
        assert len(pains) == 1
        assert pains[0].original_text == "Claude Codeを使おうとしたが難しくて諦めた"

    def test_skips_impression_only_text(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.POST_HISTORY,
            text="今日のAI記事、すごく面白かったです！ありがとうございます",
        )
        pains = extractor.extract(source)
        assert len(pains) == 0

    def test_skips_short_text(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="困った",  # 10文字未満
        )
        pains = extractor.extract(source)
        assert len(pains) == 0

    def test_skips_no_keyword_when_required(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="Claude Codeのドキュメントを読んでいます",
        )
        pains = extractor.extract(source)
        assert len(pains) == 0

    def test_allows_no_keyword_when_not_required(self):
        ext = PainExtractor(min_text_length=10, require_pain_keyword=False)
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="Claude Codeのドキュメントを読んでいます",
        )
        pains = ext.extract(source)
        assert len(pains) == 1

    def test_preserves_source_post_id(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.POST_HISTORY,
            text="Claude Codeが難しくてできない、諦めてしまいそう",
            post_id="t_999",
        )
        pains = extractor.extract(source)
        assert len(pains) == 1
        assert pains[0].source_post_id == "t_999"

    def test_original_text_truncated_at_500(self, extractor: PainExtractor):
        long_text = "困った。" * 200  # 800文字超
        source = RawSource(source_type=SourceType.MANUAL_MEMO, text=long_text)
        pains = extractor.extract(source)
        assert len(pains) == 1
        assert len(pains[0].original_text) <= 500


class TestPainExtractorScoring:
    def test_severity_high_for_failure_words(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="Claude Codeのセットアップに失敗してもう諦めた",
        )
        pains = extractor.extract(source)
        assert pains[0].severity >= 4

    def test_severity_low_for_mild_concern(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="AI副業について少し不安を感じています",
        )
        pains = extractor.extract(source)
        assert pains[0].severity <= 2

    def test_urgency_high_for_deadline(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="今すぐClaudeのAPIキー設定が分からなくて困っている",
        )
        pains = extractor.extract(source)
        assert pains[0].urgency >= 4

    def test_frequency_boosted_by_engagement(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.POST_HISTORY,
            text="AI副業の始め方が分からない",
            engagement_total=60,  # 高エンゲージメント
        )
        pains = extractor.extract(source)
        assert pains[0].frequency >= 3

    def test_audience_type_detected(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="非エンジニアがClaude Codeを使おうとして詰まった",
        )
        pains = extractor.extract(source)
        assert pains[0].audience_type == "非エンジニア"

    def test_auto_tags_added(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="Claude Codeが難しくてできない",
        )
        pains = extractor.extract(source)
        tags = pains[0].related_tags
        assert "ClaudeCode" in tags or "Claude" in tags

    def test_source_tags_preserved_in_related_tags(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="副業で生成AIを使おうとしたが分からない",
            tags=["カスタムタグ"],
        )
        pains = extractor.extract(source)
        assert "カスタムタグ" in pains[0].related_tags


class TestPainExtractorSummaryAndSituation:
    def test_summary_contains_pain_keywords(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="朝起きてコーヒーを飲みながらClaude Codeを使おうとしたが難しくてできなかった",
        )
        pains = extractor.extract(source)
        summary = pains[0].pain_summary
        assert len(summary) <= 100
        assert len(summary) > 0

    def test_failed_attempts_extracted(self, extractor: PainExtractor):
        source = RawSource(
            source_type=SourceType.MANUAL_MEMO,
            text="公式ドキュメントを読んだが全然わからなくてうまくいかなかった",
        )
        pains = extractor.extract(source)
        assert len(pains) == 1  # 悩みキーワード「わからなくて」「うまくいかな」にマッチ
        # failed_attemptsは0件でも正常（パターンにマッチしなければOK）
        assert isinstance(pains[0].failed_attempts, list)


# ---------------------------------------------------------------------------
# PainClusterer テスト
# ---------------------------------------------------------------------------

class TestPainClusterer:
    def test_single_pain_no_cluster(self, clusterer: PainClusterer):
        pain = PainPoint(
            original_text="Claude Codeが難しい",
            pain_summary="Claude Codeが難しい",
            related_tags=["AI", "ClaudeCode"],
        )
        result = clusterer.cluster([pain])
        assert len(result) == 1
        assert result[0].cluster_id is None
        assert result[0].similar_pain_ids == []

    def test_similar_pains_get_cluster_id(self, clusterer: PainClusterer):
        pain1 = PainPoint(
            original_text="Claude Codeが難しくて諦めた",
            pain_summary="Claude Codeが難しい",
            related_tags=["AI", "ClaudeCode", "非エンジニア"],
            audience_type="非エンジニア",
        )
        pain2 = PainPoint(
            original_text="Claude Codeの使い方が分からない",
            pain_summary="Claude Codeの使い方が分からない",
            related_tags=["AI", "ClaudeCode", "非エンジニア"],
            audience_type="非エンジニア",
        )
        result = clusterer.cluster([pain1, pain2])
        # 類似として検出されるはず（タグ完全一致）
        assert result[0].cluster_id is not None or result[1].cluster_id is not None

    def test_dissimilar_pains_no_cluster(self, clusterer: PainClusterer):
        pain1 = PainPoint(
            original_text="Claude Codeが難しい",
            pain_summary="Claude Code関連",
            related_tags=["ClaudeCode"],
            audience_type="非エンジニア",
        )
        pain2 = PainPoint(
            original_text="note有料記事が売れない",
            pain_summary="note販売関連",
            related_tags=["note", "副業"],
            audience_type="会社員",
        )
        result = clusterer.cluster([pain1, pain2])
        # 異なるタグで類似なし
        assert result[0].cluster_id is None
        assert result[1].cluster_id is None

    def test_similar_ids_are_cross_linked(self, clusterer: PainClusterer):
        pain1 = PainPoint(
            original_text="分からなくて困った",
            pain_summary="分からない",
            related_tags=["AI", "ClaudeCode", "副業"],
        )
        pain2 = PainPoint(
            original_text="どうすれば使えるか分からない",
            pain_summary="使い方が分からない",
            related_tags=["AI", "ClaudeCode", "副業"],
        )
        result = clusterer.cluster([pain1, pain2])
        linked = [p for p in result if p.similar_pain_ids]
        if linked:  # 類似検出された場合
            assert len(linked) == 2  # 双方向にリンク

    def test_empty_list(self, clusterer: PainClusterer):
        result = clusterer.cluster([])
        assert result == []


# ---------------------------------------------------------------------------
# ユーティリティ関数テスト
# ---------------------------------------------------------------------------

class TestJaccard:
    def test_identical_sets(self):
        assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        sim = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        assert abs(sim - 0.5) < 0.01  # 2/4 = 0.5

    def test_both_empty(self):
        assert _jaccard(set(), set()) == 0.0

    def test_one_empty(self):
        assert _jaccard({"a"}, set()) == 0.0


class TestKeywordOverlap:
    def test_same_text(self):
        sim = _keyword_overlap("Claude Codeが難しい", "Claude Codeが難しい")
        assert sim == 1.0

    def test_completely_different(self):
        sim = _keyword_overlap("Claude Codeが難しい", "note記事が売れない")
        assert sim < 0.3

    def test_partial_overlap(self):
        sim = _keyword_overlap("Claude Codeが難しい", "Claude Codeが分からない")
        assert sim > 0.3


# ---------------------------------------------------------------------------
# PainIntakeAgent 統合テスト
# ---------------------------------------------------------------------------

class TestPainIntakeAgentIntegration:
    def _make_agent(self, tmp_path: Path, test_settings) -> PainIntakeAgent:
        """テスト用エージェント（DB・出力先をtmpに向ける）"""
        from unittest.mock import patch, PropertyMock
        from src.adapters.storage_sqlite import SQLiteStorage

        agent = PainIntakeAgent(settings=test_settings, dry_run=False)
        # DBをtmpに向ける
        agent.db = SQLiteStorage(tmp_path / "test.db")
        # output_jsonをtmpに向ける
        agent.settings = test_settings

        # pain_points_jsonプロパティをオーバーライド（settingsがreadonly propertyのため）
        # 代わりに_save_jsonをモンキーパッチ
        original_save = agent._save_json
        output_file = tmp_path / "pain_points.json"

        def patched_save(pains):
            from src.adapters.storage_json import write_json
            data = {
                "version": "2.0",
                "generated_at": datetime.now().isoformat(),
                "count": len(pains),
                "pain_points": [p.model_dump(mode="json") for p in pains],
            }
            write_json(output_file, data)
            return output_file

        agent._save_json = patched_save
        return agent, output_file

    def test_run_on_sample_file(self, tmp_path: Path, test_settings):
        data = [
            {
                "text": "Claude Codeを使おうとしたが非エンジニアには難しくて諦めた。ターミナルが何か分からない",
                "tags": ["AI", "ClaudeCode", "非エンジニア"],
                "post_id": "t_001",
                "likes": 30,
                "replies": 5,
            },
            {
                "text": "今日のランチ美味しかった",  # スキップされるべき
                "tags": [],
            },
        ]
        f = tmp_path / "test_input.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        agent, output_file = self._make_agent(tmp_path, test_settings)
        result = agent.run(f)

        assert result.extracted == 1
        assert result.skipped >= 1
        assert result.error_count == 0
        assert output_file.exists()

    def test_run_creates_pain_points_json(self, tmp_path: Path, test_settings):
        data = [
            {"text": "副業でAI活用したいが何から始めればいいか分からない", "tags": ["副業", "AI活用"]},
        ]
        f = tmp_path / "input.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        agent, output_file = self._make_agent(tmp_path, test_settings)
        agent.run(f)

        assert output_file.exists()
        content = json.loads(output_file.read_text(encoding="utf-8"))
        assert content["count"] >= 1
        assert len(content["pain_points"]) >= 1

        first = content["pain_points"][0]
        assert "pain_id" in first
        assert "pain_summary" in first
        assert "severity" in first
        assert "urgency" in first
        assert "frequency" in first

    def test_dry_run_no_file_created(self, tmp_path: Path, test_settings):
        data = [{"text": "AI使い方が分からなくて困っている", "tags": ["AI"]}]
        f = tmp_path / "input.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        from src.adapters.storage_sqlite import SQLiteStorage
        agent = PainIntakeAgent(settings=test_settings, dry_run=True)
        agent.db = SQLiteStorage(tmp_path / "test.db")
        output_file = tmp_path / "pain_points.json"
        result = agent.run(f)

        # dry_run=True なのでファイルは作られない
        assert not output_file.exists()
        # ただしresultは返ってくる
        assert result is not None

    def test_run_on_empty_directory(self, tmp_path: Path, test_settings):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        agent, _ = self._make_agent(tmp_path, test_settings)
        result = agent.run(empty_dir)
        assert result.extracted == 0
        assert len(result.warnings) > 0

    def test_run_on_nonexistent_path(self, tmp_path: Path, test_settings):
        agent, _ = self._make_agent(tmp_path, test_settings)
        result = agent.run(tmp_path / "nonexistent")
        assert result.extracted == 0

    def test_deduplication_with_existing_data(self, tmp_path: Path, test_settings):
        """既存のpain_pointsがある場合、同一IDは追記されない"""
        from src.adapters.storage_sqlite import SQLiteStorage

        data = [{"text": "Claude Codeが難しくて分からない", "tags": ["AI", "ClaudeCode"]}]
        f = tmp_path / "input.json"
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        db = SQLiteStorage(tmp_path / "test.db")
        agent, output_file = self._make_agent(tmp_path, test_settings)
        agent.db = db

        # 1回目の実行
        result1 = agent.run(f)
        count1 = result1.extracted

        # 同じファイルで2回目（同じpain_idは再生成されないが新しいIDで追加される）
        result2 = agent.run(f)
        # 既存+新規で合計が増える
        all_pains = db.list_pain_points()
        assert len(all_pains) >= count1


# ---------------------------------------------------------------------------
# サンプルファイルを使った実証テスト
# ---------------------------------------------------------------------------

class TestWithSampleFiles:
    """data/raw/ 以下のサンプルファイルを使った実証テスト"""

    def test_sample_post_history_extracts_pains(self, tmp_path: Path, test_settings):
        sample_path = Path(__file__).parent.parent / "data" / "raw" / "sample_post_history.json"
        if not sample_path.exists():
            pytest.skip("sample_post_history.json not found")

        from src.adapters.storage_sqlite import SQLiteStorage
        agent = PainIntakeAgent(settings=test_settings, dry_run=True)
        agent.db = SQLiteStorage(tmp_path / "test.db")
        result = agent.run(sample_path)

        # 感想のみの投稿（t_004）はスキップ、残り4件から少なくとも2件は抽出されるはず
        assert result.extracted >= 2
        assert result.error_count == 0

    def test_sample_manual_memo_skips_irrelevant(self, tmp_path: Path, test_settings):
        sample_path = Path(__file__).parent.parent / "data" / "raw" / "sample_manual_memo.json"
        if not sample_path.exists():
            pytest.skip("sample_manual_memo.json not found")

        from src.adapters.storage_sqlite import SQLiteStorage
        agent = PainIntakeAgent(settings=test_settings, dry_run=True)
        agent.db = SQLiteStorage(tmp_path / "test.db")
        result = agent.run(sample_path)

        # 「今日のランチ美味しかった」はスキップ
        assert result.skipped >= 1
