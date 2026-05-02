"""
selector エージェント

researcher が生成した TopicCandidate を人間に提示し、
1件の承認を受け付けて Approval として保存する。

設計方針:
- 自動承認は行わない（人間が必ず選択する）
- 承認結果は approvals.json + SQLite に保存する
- 複数の承認済みを防ぐ（再承認は上書き保存）
- dry_run=True のときは保存をスキップ
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.adapters.storage_json import load_approvals, load_topic_candidates, save_approvals
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import Approval, ArticleStatus, TopicCandidate
from src.core.settings import AppSettings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 結果サマリー
# ---------------------------------------------------------------------------

@dataclass
class SelectorResult:
    """select() の結果サマリー"""
    approved: Optional[Approval] = None
    candidate: Optional[TopicCandidate] = None
    status: str = "ok"          # "ok" | "skipped" | "error"
    message: str = ""
    output_json: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

class SelectorAgent:
    """
    TopicCandidate の承認フローを担当するエージェント。

    使い方:
        agent = SelectorAgent(settings=settings, dry_run=False)

        # 候補一覧取得
        candidates = agent.list_candidates()

        # 承認実行
        result = agent.approve(
            candidate_id="xxxx-...",
            selected_reason="需要が高く、自分の体験とも一致しているため",
        )
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)

    # ------------------------------------------------------------------
    # 候補一覧
    # ------------------------------------------------------------------

    def list_candidates(
        self,
        approved_only: bool = False,
        min_score: Optional[float] = None,
    ) -> list[TopicCandidate]:
        """
        保存済みの TopicCandidate を返す。
        DB → JSON fallback の順で読み込む。
        """
        try:
            candidates = self.db.list_topic_candidates(
                approved=True if approved_only else None,
                min_score=min_score,
            )
            if candidates:
                return candidates
        except Exception as e:
            logger.warning(f"Could not load from DB: {e}")

        # fallback: JSON ファイル
        json_path = self.settings.topic_candidates_json
        if json_path.exists():
            try:
                all_c = load_topic_candidates(json_path)
                if approved_only:
                    all_c = [c for c in all_c if c.approved]
                if min_score is not None:
                    all_c = [c for c in all_c if c.total_score >= min_score]
                return all_c
            except Exception as e:
                logger.warning(f"Could not load from JSON: {e}")
        return []

    def get_candidate(self, candidate_id: str) -> Optional[TopicCandidate]:
        """IDで1件取得。DB → JSON fallback。"""
        try:
            c = self.db.get_topic_candidate(candidate_id)
            if c:
                return c
        except Exception as e:
            logger.warning(f"DB lookup failed: {e}")

        # fallback: JSON scan
        json_path = self.settings.topic_candidates_json
        if json_path.exists():
            try:
                for c in load_topic_candidates(json_path):
                    if c.candidate_id == candidate_id:
                        return c
            except Exception as e:
                logger.warning(f"JSON lookup failed: {e}")
        return None

    # ------------------------------------------------------------------
    # 承認
    # ------------------------------------------------------------------

    def approve(
        self,
        candidate_id: str,
        selected_reason: Optional[str] = None,
        selected_by: str = "human",
    ) -> SelectorResult:
        """
        指定した TopicCandidate を承認する。

        - 自動承認は行わない（外部からの明示的な呼び出しが必要）
        - dry_run=True のときは保存をスキップ
        - 既存の承認がある場合でも上書き保存する（再考後の承認変更を許容）

        Returns:
            SelectorResult: 承認結果のサマリー
        """
        result = SelectorResult()

        # 1. 候補を取得
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            result.status = "error"
            result.message = f"TopicCandidate not found: {candidate_id}"
            logger.error(result.message)
            return result

        # 2. Approval オブジェクトを作成
        approval = Approval(
            selected_candidate_id=candidate.candidate_id,
            selected_by=selected_by,
            selected_reason=selected_reason,
            snapshot_score=candidate.total_score,
            snapshot_title=candidate.topic_title,
        )

        # 3. 候補を approved=True に更新
        candidate.approved = True
        candidate.approved_at = approval.approved_at
        candidate.status = ArticleStatus.HUMAN_APPROVED

        result.approved = approval
        result.candidate = candidate

        if self.dry_run:
            result.status = "skipped"
            result.message = (
                f"[DRY-RUN] would approve: {candidate.candidate_id[:8]} "
                f"'{candidate.topic_title[:50]}'"
            )
            logger.info(result.message)
            return result

        # 4. DB に保存
        try:
            self.db.save_topic_candidate(candidate)
            self.db.save_approval(approval)
        except Exception as e:
            result.status = "error"
            result.message = f"DB save failed: {e}"
            logger.error(result.message)
            return result

        # 5. JSON に保存（approvals.json は全件上書き）
        try:
            output_path = self._save_approval_to_json(approval)
            result.output_json = output_path
        except Exception as e:
            result.warnings.append(f"JSON save warning: {e}")
            logger.warning(f"Could not save approval to JSON: {e}")

        result.status = "ok"
        result.message = (
            f"Approved: {candidate.candidate_id[:8]} "
            f"'{candidate.topic_title[:50]}' "
            f"(score={candidate.total_score:.1f})"
        )
        logger.info(result.message)
        return result

    # ------------------------------------------------------------------
    # 承認一覧
    # ------------------------------------------------------------------

    def list_approvals(self) -> list[Approval]:
        """保存済みの Approval を返す。DB → JSON fallback。"""
        try:
            approvals = self.db.list_approvals()
            if approvals:
                return approvals
        except Exception as e:
            logger.warning(f"DB list_approvals failed: {e}")

        json_path = self.settings.approvals_json
        if json_path.exists():
            try:
                return load_approvals(json_path)
            except Exception as e:
                logger.warning(f"JSON load_approvals failed: {e}")
        return []

    # ------------------------------------------------------------------
    # 内部メソッド
    # ------------------------------------------------------------------

    def _save_approval_to_json(self, new_approval: Approval) -> Path:
        """
        approvals.json に承認を保存する。
        既存の approvals を読み込んで同じ candidate_id があれば上書き、
        なければ追記する。
        """
        json_path = self.settings.approvals_json
        existing: list[Approval] = []
        if json_path.exists():
            try:
                existing = load_approvals(json_path)
            except Exception:
                pass

        # 同じ candidate_id の承認を上書き（再承認を許容）
        updated = [a for a in existing
                   if a.selected_candidate_id != new_approval.selected_candidate_id]
        updated.append(new_approval)

        return save_approvals(updated, json_path)
