"""
note_publisher エージェント

publish_ready の NoteDraft を受け取り、公開用メタデータを生成する。

動作モード:
  manual  : 公開メタデータ（NotePublication）とキャンペーン（Campaign）を作成するだけ。
            実際のnote.com投稿は人間が手動で行う。
  ※ semi_auto / auto は将来拡張用（Task 6 以降）

フロー (manual モード):
  1. publish_ready の NoteDraft をロード
  2. ステータス確認（publish_ready 以外は拒否）
  3. attribution_id を生成
  4. Campaign を作成
  5. NotePublication を作成
  6. NoteDraft.status → published
  7. DB + JSON に保存
  8. PublishResult を返す

設計方針:
  - publish_ready 以外の原稿は publish できない（ガード必須）
  - note_url は未確定でも保存できる（後から update-publication で更新）
  - [FUTURE_LLM] note.com API 連携は semi_auto/auto モードで実装
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.adapters.storage_json import (
    load_note_drafts,
    save_campaign_append,
    save_publication_append,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import ArticleStatus, Campaign, NoteDraft, NotePublication
from src.core.settings import AppSettings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _generate_attribution_id(draft_id: str) -> str:
    """帰属トラッキングID: attr-{YYYYMMDD}-{draft_id 先頭6文字}"""
    date_str = datetime.now().strftime("%Y%m%d")
    return f"attr-{date_str}-{draft_id[:6]}"


def _campaign_name_from_title(title: str) -> str:
    """
    タイトルからキャンペーン名を生成する。
    例: "【非エンジニアが2週間試した】Claude Code" → "claude-code-20260407"
    """
    # 【】ブラケット内のテキストを除去
    clean = re.sub(r"【[^】]*】", "", title)
    # ASCII英数字のみ抽出してスラッグ化
    words = re.findall(r"[a-zA-Z0-9]+", clean)
    slug = "-".join(w.lower() for w in words[:3]) if words else "note"
    date_str = datetime.now().strftime("%Y%m%d")
    return f"{slug}-{date_str}"


def _note_slug_from_title(title: str) -> str:
    """タイトルから note スラッグ候補を生成する。"""
    clean = re.sub(r"【[^】]*】", "", title)
    words = re.findall(r"[a-zA-Z0-9]+", clean)
    if not words:
        # 日本語タイトルは頭4文字をローマ字代替
        return f"note-{datetime.now().strftime('%Y%m%d')}"
    slug = "-".join(w.lower() for w in words[:4])
    return slug[:40]


# ---------------------------------------------------------------------------
# 結果データクラス
# ---------------------------------------------------------------------------

@dataclass
class PublishResult:
    """NotePublisherAgent.publish() の結果"""
    publication: Optional[NotePublication] = None
    campaign: Optional[Campaign] = None
    draft: Optional[NoteDraft] = None
    status: str = "ok"      # "ok" | "skipped" | "error" | "no_draft" | "not_ready"
    message: str = ""
    output_json: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

class NotePublisherAgent:
    """
    publish_ready の NoteDraft から公開用メタデータを生成するエージェント。

    使い方:
        agent = NotePublisherAgent(settings=settings, dry_run=False)
        result = agent.publish()                      # 最新の publish_ready を対象
        result = agent.publish(draft_id="xxxx")       # 指定ドラフトを対象
        result = agent.publish(note_url="https://...") # 公開URLも同時に登録
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)

    def publish(
        self,
        draft_id: Optional[str] = None,
        note_url: Optional[str] = None,
        note_slug: Optional[str] = None,
        mode: str = "manual",
    ) -> PublishResult:
        """
        publish_ready の NoteDraft を公開処理する。

        Parameters
        ----------
        draft_id   : 対象の下書きID（省略時は最新 publish_ready を使用）
        note_url   : 公開済みURL（manual モードでは任意）
        note_slug  : noteスラッグ（URL未確定時の参照用、省略時はタイトルから生成）
        mode       : "manual"（将来 semi_auto / auto を追加予定）
        """
        # 1. ドラフトをロード
        draft = self._load_draft(draft_id)
        if draft is None:
            return PublishResult(
                status="no_draft",
                message="publish_ready の下書きがありません。edit-note を先に実行してください。",
            )

        # 2. ステータスガード
        if draft.status != ArticleStatus.PUBLISH_READY:
            return PublishResult(
                draft=draft,
                status="not_ready",
                message=(
                    f"ステータスが publish_ready ではありません: {draft.status} "
                    f"（title='{draft.title[:40]}'）"
                ),
            )

        # 3. attribution_id を生成
        attribution_id = _generate_attribution_id(draft.id)

        # 4. Campaign を作成
        campaign_name = _campaign_name_from_title(draft.title)
        campaign = Campaign(
            name=campaign_name,
            attribution_id=attribution_id,
            draft_id=draft.id,
            note_url=note_url,
        )

        # 5. NotePublication を作成
        slug = note_slug or _note_slug_from_title(draft.title)
        publication = NotePublication(
            draft_id=draft.id,
            note_title=draft.title,
            note_url=note_url,
            note_slug=slug,
            price=draft.price,
            tags=draft.tags,
            attribution_id=attribution_id,
            campaign_id=campaign.campaign_id,
        )
        # Campaign に publication_id を紐付け
        campaign.publication_id = publication.id

        # dry_run: 保存スキップ
        if self.dry_run:
            return PublishResult(
                publication=publication,
                campaign=campaign,
                draft=draft,
                status="skipped",
                message=(
                    f"[DRY-RUN] '{draft.title[:40]}' "
                    f"attribution={attribution_id}"
                ),
            )

        # 6. NoteDraft のステータスを更新
        draft.status = ArticleStatus.PUBLISHED
        if note_url:
            draft.note_url = note_url
        draft.published_at = publication.published_at
        draft.updated_at = datetime.now()

        # 7. 保存
        self.db.save_draft(draft)
        self.db.save_publication(publication)
        self.db.save_campaign(campaign)

        output_path = save_publication_append(publication, self.settings.publications_json)
        save_campaign_append(campaign, self.settings.campaigns_json)

        return PublishResult(
            publication=publication,
            campaign=campaign,
            draft=draft,
            status="ok",
            message=f"公開データ作成完了: '{draft.title[:40]}' attribution={attribution_id}",
            output_json=output_path,
        )

    # ------------------------------------------------------------------
    # ローダー
    # ------------------------------------------------------------------

    def _load_draft(self, draft_id: Optional[str] = None) -> Optional[NoteDraft]:
        """draft_id 指定があればそのドラフト、なければ最新の publish_ready。"""
        try:
            if draft_id:
                return self.db.get_draft(draft_id)
            drafts = self.db.list_drafts(status=ArticleStatus.PUBLISH_READY.value)
            return drafts[0] if drafts else None
        except Exception as e:
            logger.warning(f"Draft load from DB failed: {e}")

        # JSON フォールバック
        json_path = self.settings.note_drafts_json
        if json_path.exists():
            try:
                all_drafts = load_note_drafts(json_path)
                if draft_id:
                    for d in all_drafts:
                        if d.id == draft_id:
                            return d
                    return None
                ready = [d for d in all_drafts if d.status == ArticleStatus.PUBLISH_READY]
                return ready[0] if ready else None
            except Exception as e:
                logger.warning(f"Draft load from JSON failed: {e}")
        return None
