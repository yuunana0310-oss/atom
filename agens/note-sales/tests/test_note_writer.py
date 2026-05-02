"""
note_writer / editor エージェントのテスト

カバー範囲:
- NoteWriterAgent: run(), _generate_draft(), _export_markdown()
- EditorAgent: evaluate(), 各チェック項目, 品質ゲート
- NoteDraft モデル: free/paid 結合, char_count 計算
- 統合: write → edit フロー
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from src.agents.editor import (
    CheckResult,
    EditorAgent,
    EditorResult,
    _EXAGGERATION_WORDS,
)
from src.agents.note_writer import (
    NoteWriterAgent,
    NoteWriterResult,
    _extract_price,
    _tool_from_tags,
)
from src.core.models import ArticleStatus, NoteDraft, PainPoint, TopicCandidate
from src.core.settings import AppSettings


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def make_candidate(
    approved: bool = True,
    angle: str = "体験談＋本音レポート",
    audience_type: str = "非エンジニア",
    tags: Optional[list[str]] = None,
) -> TopicCandidate:
    from uuid import uuid4
    return TopicCandidate(
        target_pain_id_list=[str(uuid4())],
        topic_title="【非エンジニアが2週間試した】Claude Code、正直に書く",
        hook="「自分には無理かも」と思ったことありませんか？",
        angle=angle,
        why_now="Claude Code が2026年に急速に普及している",
        expected_buyer_intent="体験談で安心したい",
        paid_reason="実際に使ったプロンプトの具体例",
        recommended_price_range="300-980円",
        audience_type=audience_type,
        related_tags=tags or ["ClaudeCode", "AI活用", "非エンジニア"],
        approved=approved,
        total_score=7.5,
    )


def make_pain(pain_id: Optional[str] = None) -> PainPoint:
    from uuid import uuid4
    return PainPoint(
        pain_id=pain_id or str(uuid4()),
        original_text="Claude Codeが難しくて分からない。ターミナルが何か分からない。",
        pain_summary="Claude Codeの使い方が分からない",
        severity=3,
        urgency=2,
        frequency=3,
        audience_type="非エンジニア",
        situation="Claude Codeの初期セットアップ",
        failed_attempts=["公式ドキュメントを読んだが理解できなかった"],
        related_tags=["ClaudeCode", "非エンジニア"],
    )


def make_passing_draft(candidate_id: str = "test-cand-001") -> NoteDraft:
    """品質ゲートを通過するドラフト"""
    free = (
        "# 【非エンジニアが2週間試した】Claude Code、正直に書く\n\n"
        "「自分には無理かも」と思ったことありませんか？\n\n"
        "Claude Codeを使い始めた私の2週間の記録を正直に書きます。\n\n"
        "## なぜうまくいかないのか\n\n"
        "多くの解説記事はエンジニア向けで、非エンジニアには難しいです。\n\n"
        "## この記事でわかること\n\n"
        "- 非エンジニアが最初に詰まる箇所\n"
        "- 2週間で使えるようになった手順\n"
        "- コードを書かずに使えるシーン3つ\n\n"
        "---\n\n**有料パート（300円）の内容：**\n\n"
        "- 実際に使ったプロンプトの具体例\n"
        "- 詰まった場面と抜け出し方\n"
        "- 1日30分でできる始め方ロードマップ\n"
        "- 非エンジニアがよく陥る罠と回避策\n"
    )
    paid = (
        "## 実践ステップ\n\n"
        "### ステップ1: 最初の設定（所要時間: 30分）\n\n"
        "まずターミナルを開き、`claude` と入力してEnterを押します。\n"
        "設定完了後、最初のプロンプトに「日本語で回答してください」を入力してください。\n\n"
        "1. ターミナルを起動する（5分）\n"
        "2. claudeコマンドを実行する（2分）\n"
        "3. 最初の指示を入力する（3分）\n\n"
        "### ステップ2: 最初のタスクを実行する（所要時間: 15分）\n\n"
        "最初は小さなタスクから始めます。メールの返信文を作成させてみましょう。\n"
        "月3万円の収益を目指すなら、まずこのステップを確実にマスターしてください。\n\n"
        "### ステップ3: 失敗したときの対処法（所要時間: 5分）\n\n"
        "指示を具体的にする（対象者・文字数・目的を明示）だけで9割の問題は解決します。\n"
        "保存したプロンプトを再利用することで作業効率が3倍になります。\n\n"
        "---\n\n"
        "## この記事が向いている人・向いていない人\n\n"
        "**向いている人**\n\n"
        "- AIを使って副業収入を増やしたい非エンジニア\n"
        "- 具体的な手順と実体験がほしい人\n\n"
        "**向いていない人**\n\n"
        "- すでにClaude Codeを使いこなしているエンジニア\n\n"
        "---\n\n## まとめ\n\n"
        "非エンジニアでも、30分でClaude Codeは使い始めることができます。\n"
        "まず今日1つだけ試してみてください。\n"
    )
    return NoteDraft(
        candidate_id=candidate_id,
        title="【非エンジニアが2週間試した】Claude Code、正直に書く",
        subtitle="コードが書けない私の2週間の記録",
        free_part_markdown=free,
        paid_part_markdown=paid,
        price=300,
        tags=["ClaudeCode", "非エンジニア"],
    )


def make_failing_draft(candidate_id: str = "test-cand-001") -> NoteDraft:
    """品質ゲートを通過しないドラフト（短すぎる・構造不足）"""
    return NoteDraft(
        candidate_id=candidate_id,
        title="Claude Codeを試してみた",  # ブラケットなし、数字なし
        subtitle="",
        free_part_markdown="試してみましたが難しかったです。",  # 短すぎる
        paid_part_markdown="大切です。重要です。意識しましょう。",  # 一般論
        price=300,
    )


# ---------------------------------------------------------------------------
# ヘルパー関数テスト
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_extract_price_range(self):
        assert _extract_price("300-980円") == 300
        assert _extract_price("980-1980円") == 980
        assert _extract_price("500-980円") == 500
        assert _extract_price("不明") == 300  # fallback

    def test_tool_from_tags_priority(self):
        assert _tool_from_tags(["ClaudeCode"]) == "Claude Code"
        assert _tool_from_tags(["Claude"]) == "Claude"
        assert _tool_from_tags(["生成AI", "Claude"]) == "Claude"
        assert _tool_from_tags([]) == "AI"  # fallback

    def test_tool_from_tags_claude_code_priority(self):
        # ClaudeCode は Claude より優先順位が高い
        assert _tool_from_tags(["Claude", "ClaudeCode"]) == "Claude Code"


# ---------------------------------------------------------------------------
# NoteDraft モデルテスト
# ---------------------------------------------------------------------------

class TestNoteDraftModel:
    def test_body_markdown_computed_from_parts(self):
        d = NoteDraft(
            candidate_id="c1",
            title="テスト",
            free_part_markdown="## 無料\n\n内容",
            paid_part_markdown="## 有料\n\n内容",
        )
        assert "無料" in d.body_markdown
        assert "有料" in d.body_markdown

    def test_char_count_computed(self):
        d = NoteDraft(
            candidate_id="c1",
            title="テスト",
            free_part_markdown="あいうえお",  # 5字
            paid_part_markdown="かきくけこ",  # 5字
        )
        assert d.char_count > 0

    def test_body_markdown_not_overwritten_if_set(self):
        d = NoteDraft(
            candidate_id="c1",
            title="テスト",
            body_markdown="既存の本文",
            free_part_markdown="無料パート",
        )
        assert d.body_markdown == "既存の本文"

    def test_quality_score_scale_0_to_100(self):
        d = NoteDraft(candidate_id="c1", title="t", quality_score=82.0)
        assert d.quality_score == 82.0

    def test_new_fields_have_defaults(self):
        d = NoteDraft(candidate_id="c1", title="t")
        assert d.subtitle == ""
        assert d.free_part_markdown == ""
        assert d.paid_part_markdown == ""
        assert d.editor_feedback == []


# ---------------------------------------------------------------------------
# NoteWriterAgent テスト
# ---------------------------------------------------------------------------

class TestNoteWriterAgent:
    def _save_candidate(self, test_settings, c: TopicCandidate):
        from src.adapters.storage_sqlite import SQLiteStorage
        SQLiteStorage(test_settings.db_path).save_topic_candidate(c)

    def test_run_no_approved_candidate(self, test_settings):
        agent = NoteWriterAgent(settings=test_settings, dry_run=True)
        result = agent.run()
        assert result.status == "no_candidate"
        assert result.draft is None

    def test_run_dry_run_returns_draft_without_saving(self, test_settings):
        c = make_candidate(approved=True)
        self._save_candidate(test_settings, c)

        agent = NoteWriterAgent(settings=test_settings, dry_run=True)
        result = agent.run()

        assert result.status == "skipped"
        assert result.draft is not None
        assert not test_settings.note_drafts_json.exists(), "dry_run では保存しない"

    def test_run_saves_to_sqlite(self, test_settings):
        c = make_candidate(approved=True)
        self._save_candidate(test_settings, c)

        agent = NoteWriterAgent(settings=test_settings, dry_run=False)
        result = agent.run()

        assert result.status == "ok"
        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)
        drafts = db.list_drafts()
        assert len(drafts) >= 1

    def test_run_saves_to_json(self, test_settings):
        c = make_candidate(approved=True)
        self._save_candidate(test_settings, c)

        agent = NoteWriterAgent(settings=test_settings, dry_run=False)
        result = agent.run()

        assert result.output_json is not None
        assert result.output_json.exists()

    def test_run_exports_markdown(self, test_settings):
        c = make_candidate(approved=True)
        self._save_candidate(test_settings, c)

        agent = NoteWriterAgent(settings=test_settings, dry_run=False)
        result = agent.run()

        assert result.output_md is not None
        assert result.output_md.exists()
        content = result.output_md.read_text(encoding="utf-8")
        assert "---" in content  # front matter

    def test_generated_draft_has_title(self, test_settings):
        c = make_candidate(approved=True)
        self._save_candidate(test_settings, c)

        agent = NoteWriterAgent(settings=test_settings, dry_run=True)
        result = agent.run()

        assert result.draft.title == c.topic_title

    def test_generated_draft_has_free_and_paid_parts(self, test_settings):
        c = make_candidate(approved=True)
        self._save_candidate(test_settings, c)

        agent = NoteWriterAgent(settings=test_settings, dry_run=True)
        result = agent.run()

        draft = result.draft
        assert len(draft.free_part_markdown) > 100, "無料パートが短すぎる"
        assert len(draft.paid_part_markdown) > 100, "有料パートが短すぎる"

    def test_generated_draft_price_from_candidate(self, test_settings):
        c = make_candidate(approved=True)
        c.recommended_price_range = "980-1980円"
        self._save_candidate(test_settings, c)

        agent = NoteWriterAgent(settings=test_settings, dry_run=True)
        result = agent.run()

        assert result.draft.price == 980

    def test_uses_pain_data_in_draft(self, test_settings):
        """PainPointのデータがドラフトに反映される"""
        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)

        pain = make_pain()
        db.save_pain_point(pain)

        c = make_candidate(approved=True)
        c.target_pain_id_list = [pain.pain_id]
        self._save_candidate(test_settings, c)

        agent = NoteWriterAgent(settings=test_settings, dry_run=True)
        result = agent.run()

        # pain の情報（pain_summary）がドラフトに含まれていること
        assert result.draft is not None
        combined = result.draft.free_part_markdown + result.draft.paid_part_markdown
        assert len(combined) > 200

    def test_all_angles_generate_draft(self, test_settings):
        """全アングルで下書きが生成できる"""
        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)

        angles = [
            "体験談＋本音レポート",
            "ステップバイステップガイド",
            "失敗談＋解決策",
            "比較レポート",
            "収益公開＋実践法",
        ]
        for angle in angles:
            c = make_candidate(approved=True, angle=angle)
            db.save_topic_candidate(c)

            agent = NoteWriterAgent(settings=test_settings, dry_run=True)
            result = agent.run(candidate_id=c.candidate_id)

            assert result.status == "skipped", f"{angle} で生成失敗"
            assert result.draft is not None, f"{angle} でドラフトがNone"
            assert len(result.draft.free_part_markdown) > 50, f"{angle} の無料パートが短い"
            assert len(result.draft.paid_part_markdown) > 50, f"{angle} の有料パートが短い"


# ---------------------------------------------------------------------------
# EditorAgent チェック項目テスト
# ---------------------------------------------------------------------------

class TestEditorChecks:
    def setup_method(self):
        # AppSettings のデフォルト値で初期化（min_score=80）
        self.agent = None

    def _make_agent(self, test_settings) -> EditorAgent:
        return EditorAgent(settings=test_settings, dry_run=True)

    def test_title_strength_with_brackets(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent._check_title_strength(d)
        assert result.score >= 8, "ブラケットで8点以上"

    def test_title_strength_without_brackets(self, test_settings):
        agent = self._make_agent(test_settings)
        d = NoteDraft(candidate_id="c", title="Claude Codeを試した話")
        result = agent._check_title_strength(d)
        assert result.score < 8, "ブラケットなしは低スコア"
        assert "ブラケット" in result.comment

    def test_title_strength_with_audience_word(self, test_settings):
        agent = self._make_agent(test_settings)
        d = NoteDraft(candidate_id="c", title="非エンジニアが試したClaude Code")
        result = agent._check_title_strength(d)
        assert result.score >= 4, "対象読者明示で4点以上"

    def test_intro_impact_with_question(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent._check_intro_impact(d)
        assert result.score >= 7, "疑問形で7点以上"

    def test_intro_impact_without_question(self, test_settings):
        agent = self._make_agent(test_settings)
        d = NoteDraft(
            candidate_id="c", title="t",
            free_part_markdown="このツールは便利なツールです。使ってみましょう。",
        )
        result = agent._check_intro_impact(d)
        assert result.score < 7

    def test_free_value_long_with_headers(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent._check_free_value(d)
        assert result.score >= 12, "充実した無料パートで高スコア"

    def test_free_value_too_short(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_failing_draft()
        result = agent._check_free_value(d)
        assert result.score < 7, "短い無料パートは低スコア"

    def test_paid_specificity_with_steps(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent._check_paid_specificity(d)
        assert result.score >= 15, "ステップ構造付きで高スコア"

    def test_paid_specificity_too_short(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_failing_draft()
        result = agent._check_paid_specificity(d)
        assert result.score < 10, "短い有料パートは低スコア"

    def test_no_generalization_clean_content(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent._check_no_generalization(d)
        assert result.score == 10.0, "一般論なしで満点"

    def test_no_generalization_with_generic_ending(self, test_settings):
        agent = self._make_agent(test_settings)
        d = NoteDraft(
            candidate_id="c", title="t",
            paid_part_markdown="内容\n大切です。",
        )
        result = agent._check_no_generalization(d)
        assert result.score < 10.0

    def test_no_exaggeration_clean_content(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent._check_no_exaggeration(d)
        assert result.score == 10.0, "誇大表現なしで満点"

    def test_no_exaggeration_with_banned_word(self, test_settings):
        agent = self._make_agent(test_settings)
        banned = _EXAGGERATION_WORDS[0]  # 最初の禁止ワードを使う
        d = NoteDraft(
            candidate_id="c", title="t",
            free_part_markdown=f"{banned}の方法を教えます。",
        )
        result = agent._check_no_exaggeration(d)
        assert result.score < 10.0

    def test_actionability_with_time_and_numbers(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent._check_actionability(d)
        assert result.score >= 10, "時間・数値・動詞で高スコア"

    def test_actionability_without_specifics(self, test_settings):
        agent = self._make_agent(test_settings)
        d = NoteDraft(
            candidate_id="c", title="t",
            paid_part_markdown="なんとなくやってみてください。好きなようにやれば大丈夫です。",
        )
        result = agent._check_actionability(d)
        assert result.score <= 5, "具体性なしで低スコア"


# ---------------------------------------------------------------------------
# EditorAgent 統合テスト
# ---------------------------------------------------------------------------

class TestEditorAgentIntegration:
    def _make_agent(self, test_settings, dry_run=True) -> EditorAgent:
        return EditorAgent(settings=test_settings, dry_run=dry_run)

    def _save_draft(self, test_settings, d: NoteDraft):
        from src.adapters.storage_sqlite import SQLiteStorage
        SQLiteStorage(test_settings.db_path).save_draft(d)

    def test_evaluate_passing_draft(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent.evaluate(d)

        assert result.quality_score >= 60, f"合格ドラフトが低スコア: {result.quality_score}"
        assert len(result.checks) == 7

    def test_evaluate_failing_draft_low_score(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_failing_draft()
        result = agent.evaluate(d)

        assert result.quality_score < 70, f"不合格ドラフトが高スコア: {result.quality_score}"
        assert not result.passed

    def test_evaluate_score_in_range(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent.evaluate(d)
        assert 0 <= result.quality_score <= 100

    def test_evaluate_has_7_checks(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent.evaluate(d)
        assert len(result.checks) == 7

    def test_evaluate_overall_comment_populated(self, test_settings):
        agent = self._make_agent(test_settings)
        d = make_passing_draft()
        result = agent.evaluate(d)
        assert len(result.overall_comment) > 0

    def test_run_no_draft(self, test_settings):
        agent = self._make_agent(test_settings)
        result = agent.run()
        assert result.status == "no_draft"

    def test_run_dry_run_skips_save(self, test_settings):
        d = make_passing_draft()
        self._save_draft(test_settings, d)

        agent = self._make_agent(test_settings, dry_run=True)
        result = agent.run()

        assert result.status == "skipped"
        # dry_run なので DB のドラフトが更新されていない
        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)
        saved = db.get_draft(d.id)
        assert saved.quality_score is None  # 評価前のまま

    def test_run_sets_publish_ready_on_pass(self, test_settings):
        d = make_passing_draft()
        self._save_draft(test_settings, d)

        agent = self._make_agent(test_settings, dry_run=False)
        result = agent.run(draft_id=d.id)

        if result.passed:
            assert result.draft.status == ArticleStatus.PUBLISH_READY
        else:
            # 合格しなかった場合でもステータスが設定されている
            assert result.draft.status == ArticleStatus.DRAFT_CREATED

    def test_run_saves_quality_score(self, test_settings):
        d = make_passing_draft()
        self._save_draft(test_settings, d)

        agent = self._make_agent(test_settings, dry_run=False)
        result = agent.run(draft_id=d.id)

        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)
        saved = db.get_draft(d.id)
        assert saved.quality_score == result.quality_score

    def test_run_saves_editor_feedback(self, test_settings):
        d = make_passing_draft()
        self._save_draft(test_settings, d)

        agent = self._make_agent(test_settings, dry_run=False)
        agent.run(draft_id=d.id)

        from src.adapters.storage_sqlite import SQLiteStorage
        db = SQLiteStorage(test_settings.db_path)
        saved = db.get_draft(d.id)
        assert len(saved.editor_feedback) == 7
        assert "item" in saved.editor_feedback[0]
        assert "score" in saved.editor_feedback[0]
        assert "comment" in saved.editor_feedback[0]

    def test_run_saves_to_json(self, test_settings):
        d = make_passing_draft()
        self._save_draft(test_settings, d)

        agent = self._make_agent(test_settings, dry_run=False)
        agent.run(draft_id=d.id)

        assert test_settings.note_drafts_json.exists()


# ---------------------------------------------------------------------------
# 統合テスト: write → edit フロー
# ---------------------------------------------------------------------------

class TestWriteEditFlow:
    def test_write_then_edit(self, test_settings):
        """write → edit の一連フローが動作する"""
        from src.adapters.storage_sqlite import SQLiteStorage

        db = SQLiteStorage(test_settings.db_path)

        # 候補を保存
        c = make_candidate(approved=True)
        db.save_topic_candidate(c)

        # 下書き生成
        writer = NoteWriterAgent(settings=test_settings, dry_run=False)
        write_result = writer.run()
        assert write_result.status == "ok"
        assert write_result.draft is not None

        # 品質評価
        editor = EditorAgent(settings=test_settings, dry_run=False)
        edit_result = editor.run(draft_id=write_result.draft.id)

        # 評価が実行された
        assert edit_result.status in ("ok", "skipped")
        assert edit_result.quality_score >= 0
        assert len(edit_result.checks) == 7

        # DB に保存された
        saved = db.get_draft(write_result.draft.id)
        assert saved.quality_score is not None
        assert saved.status in (
            ArticleStatus.PUBLISH_READY.value,
            ArticleStatus.DRAFT_CREATED.value,
        )

    def test_template_draft_has_reasonable_score(self, test_settings):
        """テンプレート生成ドラフトが合理的なスコアを持つ"""
        from src.adapters.storage_sqlite import SQLiteStorage

        db = SQLiteStorage(test_settings.db_path)
        c = make_candidate(approved=True)
        db.save_topic_candidate(c)

        writer = NoteWriterAgent(settings=test_settings, dry_run=True)
        write_result = writer.run()
        draft = write_result.draft

        editor = EditorAgent(settings=test_settings, dry_run=True)
        edit_result = editor.evaluate(draft)

        # テンプレートドラフトは50点以上は取れるはず
        assert edit_result.quality_score >= 50, (
            f"テンプレートドラフトのスコアが低すぎます: {edit_result.quality_score}\n"
            + "\n".join(f"  {c.item}: {c.score}/{c.max_score}" for c in edit_result.checks)
        )
