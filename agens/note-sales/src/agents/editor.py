"""
editor エージェント

NoteDraft を品質評価し、publish_ready / revise を判定する。

チェック項目（合計100点）:
  1. タイトルの強さ        15点  ブラケット・数字・対象読者
  2. 導入の刺さり          15点  疑問形・共感ワード・自己開示
  3. 無料部分の価値        15点  文字数・見出し・リスト
  4. 有料部分の具体性      20点  文字数・ステップ構造・具体的手順
  5. 一般論で終わっていないか 10点 抽象的な締めくくりがないか
  6. 誇大表現がないか      10点  煽り・誇張がないか
  7. 実行可能性            15点  数字・期間・具体的行動

品質ゲート:
  score >= editor_min_score (デフォルト80) → publish_ready
  score <  editor_min_score              → revise（修正指示つき）

設計方針:
- [FUTURE_LLM] evaluate() を Claude API に置き換え可能
- 修正指示は人間が読める日本語で残す
- dry_run=True のときは評価のみ・保存スキップ
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.adapters.storage_json import load_note_drafts, save_note_drafts_append
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import ArticleStatus, NoteDraft
from src.core.settings import AppSettings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 誇大表現・一般論ワードリスト
# ---------------------------------------------------------------------------

_EXAGGERATION_WORDS = [
    "99%が", "100%稼げる", "絶対に稼げる", "必ず稼げる",
    "誰でも簡単に", "すぐに稼げる", "最強の", "革命的な",
    "魔法のような", "一瞬で", "完璧な方法",
]

_GENERALIZATION_PATTERNS = [
    r"大切です。$", r"重要です。$", r"意識しましょう。$",
    r"心がけましょう。$", r"気をつけましょう。$",
    r"ポイントです。$", r"必要です。$",
]

_ACTIONABLE_TIME_WORDS = ["分", "時間", "日", "週", "ヶ月", "週間", "秒"]
_ACTIONABLE_VERBS = ["設定", "入力", "送信", "保存", "クリック", "選択", "実行",
                     "貼り付け", "コピー", "ダウンロード", "インストール", "起動"]
_AUDIENCE_WORDS = ["非エンジニア", "副業", "初心者", "会社員", "エンジニア", "スキルワーカー"]
_EMPATHY_WORDS = ["悩み", "困", "分から", "できない", "諦め", "不安", "難し"]


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """1チェック項目の結果"""
    item: str
    score: float
    max_score: float
    comment: str

    @property
    def passed(self) -> bool:
        return self.max_score > 0 and (self.score / self.max_score) >= 0.6


@dataclass
class EditorResult:
    """evaluate() の結果サマリー"""
    draft: Optional[NoteDraft] = None
    quality_score: float = 0.0
    passed: bool = False
    checks: list[CheckResult] = field(default_factory=list)
    overall_comment: str = ""
    status: str = "ok"          # "ok" | "skipped" | "error" | "no_draft"
    message: str = ""


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

class EditorAgent:
    """
    NoteDraft の品質評価を担当するエージェント。

    使い方:
        agent = EditorAgent(settings=settings, dry_run=False)
        result = agent.run()                   # 最新の未評価ドラフトを評価
        result = agent.run(draft_id="xxxx")    # 指定ドラフトを評価
        result = agent.evaluate(draft)         # NoteDraft を直接渡して評価
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)
        self.min_score = settings.editor_min_score

    def run(self, draft_id: Optional[str] = None) -> EditorResult:
        """DBからドラフトを取得して評価する。"""
        draft = self._load_draft(draft_id)
        if draft is None:
            return EditorResult(
                status="no_draft",
                message="評価対象の下書きがありません。`write-note` を先に実行してください。",
            )

        result = self.evaluate(draft)

        if self.dry_run:
            result.status = "skipped"
            result.message = (
                f"[DRY-RUN] score={result.quality_score:.1f} "
                f"({'PASS' if result.passed else 'REVISE'}) "
                f"'{draft.title[:40]}'"
            )
            return result

        # 評価結果をドラフトに反映して保存
        self._apply_and_save(draft, result)

        result.status = "ok"
        result.message = (
            f"score={result.quality_score:.1f} "
            f"({'publish_ready' if result.passed else 'revise'}) "
            f"'{draft.title[:40]}'"
        )
        return result

    def evaluate(self, draft: NoteDraft) -> EditorResult:
        """
        [FUTURE_LLM] NoteDraft を7項目で採点する。
        現状: ルールベース。将来 Claude API に置き換え可能。
        """
        checks = [
            self._check_title_strength(draft),
            self._check_intro_impact(draft),
            self._check_free_value(draft),
            self._check_paid_specificity(draft),
            self._check_no_generalization(draft),
            self._check_no_exaggeration(draft),
            self._check_actionability(draft),
        ]

        total = sum(c.score for c in checks)
        passed = total >= self.min_score

        failed_items = [c for c in checks if not c.passed]
        if failed_items:
            overall = "以下の点を改善してください：\n" + "\n".join(
                f"・{c.item}: {c.comment}" for c in failed_items
            )
        else:
            overall = "品質チェックを通過しました。このまま公開できます。"

        return EditorResult(
            draft=draft,
            quality_score=round(total, 1),
            passed=passed,
            checks=checks,
            overall_comment=overall,
        )

    # ------------------------------------------------------------------
    # 7 チェック項目
    # ------------------------------------------------------------------

    def _check_title_strength(self, draft: NoteDraft) -> CheckResult:
        """タイトルの強さ（15点）"""
        title = draft.title
        score = 0.0
        comments: list[str] = []

        if "【" in title and "】" in title:
            score += 8
        else:
            comments.append("【】ブラケットでクリック率が上がります（例: 【非エンジニアが試した】〜）")

        if any(w in title for w in _AUDIENCE_WORDS):
            score += 4
        else:
            comments.append("対象読者を明示するとターゲットに刺さりやすくなります")

        if re.search(r"\d", title):
            score += 3
        else:
            comments.append("期間・件数など具体的な数字を入れると説得力が上がります")

        comment = "良好" if not comments else "、".join(comments)
        return CheckResult(item="タイトルの強さ", score=score, max_score=15.0, comment=comment)

    def _check_intro_impact(self, draft: NoteDraft) -> CheckResult:
        """導入の刺さり（15点）"""
        intro = (draft.free_part_markdown or "")[:200]
        score = 0.0
        comments: list[str] = []

        if "？" in intro or "ませんか" in intro or "でしょうか" in intro:
            score += 7
        else:
            comments.append("冒頭に疑問形を入れると読者が「自分のことだ」と感じやすくなります")

        if any(w in intro for w in _EMPATHY_WORDS):
            score += 5
        else:
            comments.append("読者の悩みに共感する言葉を冒頭に入れてください")

        if "私" in intro or "自分" in intro:
            score += 3
        else:
            comments.append("書き手の自己開示（私が/自分が）があると信頼感が増します")

        comment = "良好" if not comments else "、".join(comments)
        return CheckResult(item="導入の刺さり", score=score, max_score=15.0, comment=comment)

    def _check_free_value(self, draft: NoteDraft) -> CheckResult:
        """無料部分の価値（15点）"""
        free = draft.free_part_markdown or ""
        score = 0.0
        comments: list[str] = []

        if len(free) >= 300:
            score += 7
        else:
            comments.append(f"無料パートが短すぎます（現在{len(free)}字、推奨300字以上）")

        header_count = len(re.findall(r"^#{1,3} ", free, re.MULTILINE))
        if header_count >= 2:
            score += 5
        else:
            comments.append(f"見出し(##)が不足しています（現在{header_count}個、2個以上推奨）")

        list_items = len(re.findall(r"^[-*] ", free, re.MULTILINE))
        if list_items >= 2:
            score += 3
        else:
            comments.append("箇条書きを使って情報を整理すると読みやすくなります")

        comment = "良好" if not comments else "、".join(comments)
        return CheckResult(item="無料部分の価値", score=score, max_score=15.0, comment=comment)

    def _check_paid_specificity(self, draft: NoteDraft) -> CheckResult:
        """有料部分の具体性（20点）"""
        paid = draft.paid_part_markdown or ""
        score = 0.0
        comments: list[str] = []

        if len(paid) >= 500:
            score += 7
        else:
            comments.append(f"有料パートが短すぎます（現在{len(paid)}字、推奨500字以上）")

        step_count = len(re.findall(r"(ステップ\d|^#{1,3} )", paid, re.MULTILINE))
        if step_count >= 2:
            score += 8
        else:
            comments.append("有料パートにはステップ構造（ステップ1/2/3）を含めてください")

        if any(v in paid for v in _ACTIONABLE_VERBS):
            score += 5
        else:
            comments.append("「設定する」「入力する」など具体的な行動動詞を含めてください")

        comment = "良好" if not comments else "、".join(comments)
        return CheckResult(item="有料部分の具体性", score=score, max_score=20.0, comment=comment)

    def _check_no_generalization(self, draft: NoteDraft) -> CheckResult:
        """一般論で終わっていないか（10点）"""
        # 有料パートの末尾200文字で一般論チェック
        tail = (draft.paid_part_markdown or "")[-200:]
        score = 10.0
        comments: list[str] = []

        for pattern in _GENERALIZATION_PATTERNS:
            for line in tail.split("\n"):
                line = line.strip()
                if line and re.search(pattern, line):
                    score = 5.0
                    comments.append(
                        f"「{line[:30]}」は一般論的な締めです。"
                        "具体的なアクション・数字で締めくくってください"
                    )
                    break

        comment = "良好" if not comments else comments[0]
        return CheckResult(
            item="一般論で終わっていないか", score=score, max_score=10.0, comment=comment
        )

    def _check_no_exaggeration(self, draft: NoteDraft) -> CheckResult:
        """誇大表現がないか（10点）"""
        full_text = (draft.free_part_markdown or "") + (draft.paid_part_markdown or "")
        score = 10.0
        found: list[str] = []

        for word in _EXAGGERATION_WORDS:
            if word in full_text:
                found.append(word)
                score = max(0.0, score - 3.0)

        if found:
            comment = f"誇大表現を削除してください: {', '.join(found)}"
        else:
            comment = "良好"
        return CheckResult(item="誇大表現がないか", score=score, max_score=10.0, comment=comment)

    def _check_actionability(self, draft: NoteDraft) -> CheckResult:
        """実行可能性（15点）"""
        paid = draft.paid_part_markdown or ""
        score = 0.0
        comments: list[str] = []

        if any(w in paid for w in _ACTIONABLE_TIME_WORDS):
            score += 5
        else:
            comments.append("所要時間や期間（分・週・ヶ月など）を明記すると実行しやすくなります")

        if re.search(r"\d+[円万千百]|\d+件|\d+本|\d+回", paid):
            score += 5
        else:
            comments.append("具体的な数値（金額・件数・回数）を入れると信頼性が上がります")

        if any(v in paid for v in _ACTIONABLE_VERBS):
            score += 5
        else:
            comments.append("「〇〇してください」など具体的な行動指示を含めてください")

        comment = "良好" if not comments else "、".join(comments)
        return CheckResult(item="実行可能性", score=score, max_score=15.0, comment=comment)

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def _apply_and_save(self, draft: NoteDraft, result: EditorResult) -> None:
        """評価結果をドラフトに書き込んで保存する。"""
        draft.quality_score = result.quality_score
        draft.editor_notes = result.overall_comment
        draft.editor_feedback = [
            {
                "item": c.item,
                "score": c.score,
                "max_score": c.max_score,
                "comment": c.comment,
            }
            for c in result.checks
        ]
        draft.updated_at = datetime.now()

        if result.passed:
            draft.status = ArticleStatus.PUBLISH_READY
        else:
            draft.status = ArticleStatus.DRAFT_CREATED  # revise = 差し戻し

        # DB
        self.db.save_draft(draft)

        # JSON
        try:
            save_note_drafts_append(draft, self.settings.note_drafts_json)
        except Exception as e:
            logger.warning(f"JSON save warning: {e}")

    # ------------------------------------------------------------------
    # ローダー
    # ------------------------------------------------------------------

    def _load_draft(self, draft_id: Optional[str] = None) -> Optional[NoteDraft]:
        """draft_id 指定があればそのドラフト、なければ最新の未評価ドラフト。"""
        try:
            if draft_id:
                return self.db.get_draft(draft_id)
            # 最新の draft_created ステータスを優先
            drafts = self.db.list_drafts(status=ArticleStatus.DRAFT_CREATED.value)
            if drafts:
                return drafts[0]
            # なければ全件から最新
            all_drafts = self.db.list_drafts()
            return all_drafts[0] if all_drafts else None
        except Exception as e:
            logger.warning(f"Draft load failed: {e}")

        # JSON fallback
        json_path = self.settings.note_drafts_json
        if json_path.exists():
            try:
                drafts = load_note_drafts(json_path)
                if draft_id:
                    for d in drafts:
                        if d.id == draft_id:
                            return d
                    return None
                return drafts[0] if drafts else None
            except Exception as e:
                logger.warning(f"JSON load failed: {e}")
        return None
