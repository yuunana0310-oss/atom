"""
promo_brief_generator エージェント

公開済み NoteDraft から Threads運用部への投稿ブリーフ（PromoBrief）を生成する。

フロー:
  1. 公開済み (published) の NoteDraft をロード
  2. NotePublication をロード（attribution_id の取得）
  3. TopicCandidate をロード（角度・ターゲット情報）
  4. 関連 PainPoint をロード（解決する悩みリスト）
  5. テンプレートベースで PromoBrief を生成
  6. DB + JSON + 個別ファイルに保存
  7. NoteDraft.status → promo_brief_ready
  8. PromoBriefResult を返す

設計方針:
  - [FUTURE_LLM] _generate_brief() を Claude API に置き換え可能
  - Threads投稿本文の最終生成や実投稿はしない（材料を作るだけ）
  - avoid_expressions は CLAUDE.md のガイドラインに準拠
  - attribution_id は NotePublication から引き継ぐ
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.adapters.storage_json import (
    export_promo_brief,
    load_note_drafts,
    save_promo_brief_append,
)
from src.adapters.storage_sqlite import SQLiteStorage
from src.core.logger import get_logger
from src.core.models import (
    ArticleStatus,
    NoteDraft,
    NotePublication,
    PainPoint,
    PromoBrief,
    TopicCandidate,
)
from src.core.settings import AppSettings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# CLAUDE.md 準拠の禁止表現リスト
_AVOID_EXPRESSIONS = [
    "99%が知らない",
    "今すぐやらないと損",
    "絶対に稼げる",
    "必ず稼げる",
    "誰でも簡単に",
    "すぐに稼げる",
    "最強の",
    "革命的な",
    "魔法のような",
    "完璧な方法",
    "一瞬で",
]

# 推奨投稿時間帯マッピング（ターゲット属性別）
_POST_WINDOW_MAP = {
    "会社員": "平日朝7-9時、昼12-13時",
    "副業ワーカー": "平日朝7-9時",
    "フリーランス": "平日朝10-12時",
    "非エンジニア": "平日朝7-9時",
    "スキルワーカー": "平日朝7-9時",
}
_DEFAULT_POST_WINDOW = "平日朝7-9時"

# ハッシュタグマッピング（アングル別追加タグ）
_EXTRA_HASHTAGS = {
    "体験談": ["体験談", "副業"],
    "収益公開": ["副業", "収益報告"],
    "比較": ["AIツール", "比較"],
    "初心者向け": ["初心者", "入門"],
}


# ---------------------------------------------------------------------------
# 結果データクラス
# ---------------------------------------------------------------------------

@dataclass
class PromoBriefResult:
    """PromoBriefGeneratorAgent.run() の結果"""
    brief: Optional[PromoBrief] = None
    draft: Optional[NoteDraft] = None
    status: str = "ok"      # "ok" | "skipped" | "error" | "no_publication" | "no_draft"
    message: str = ""
    output_json: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# メインエージェント
# ---------------------------------------------------------------------------

class PromoBriefGeneratorAgent:
    """
    公開済み NoteDraft から PromoBrief を生成するエージェント。

    使い方:
        agent = PromoBriefGeneratorAgent(settings=settings, dry_run=False)
        result = agent.run()                        # 最新の published を対象
        result = agent.run(draft_id="xxxx")         # 指定ドラフトを対象
        result = agent.run(publication_id="xxxx")   # 指定publicationを対象
    """

    def __init__(self, settings: AppSettings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.db = SQLiteStorage(settings.db_path)

    def run(
        self,
        draft_id: Optional[str] = None,
        publication_id: Optional[str] = None,
    ) -> PromoBriefResult:
        """
        published / publish_ready の NoteDraft から PromoBrief を生成する。
        """
        # 1. ドラフトをロード
        draft = self._load_draft(draft_id)
        if draft is None:
            return PromoBriefResult(
                status="no_draft",
                message=(
                    "ブリーフ生成の対象となる下書きがありません。"
                    "publish-note を先に実行してください。"
                ),
            )

        # 2. NotePublication をロード
        publication = self._load_publication(publication_id, draft.id)
        if publication is None:
            # publish_ready でも生成を許容（note_url なしで生成）
            logger.warning(
                f"NotePublication not found for draft {draft.id[:8]}. "
                "attribution_id を空で生成します。"
            )

        # 3. TopicCandidate をロード
        candidate = self._load_candidate(draft.candidate_id)

        # 4. PainPoints をロード
        pains = self._load_pain_points(candidate)

        # 5. PromoBrief を生成
        brief = self._generate_brief(draft, publication, candidate, pains)

        if self.dry_run:
            return PromoBriefResult(
                brief=brief,
                draft=draft,
                status="skipped",
                message=(
                    f"[DRY-RUN] brief={brief.id[:8]} "
                    f"attribution={brief.attribution_id or 'N/A'} "
                    f"'{draft.title[:40]}'"
                ),
            )

        # 6. 保存
        self.db.save_promo_brief(brief)

        output_path = export_promo_brief(brief, self.settings.promo_brief_output_dir)
        try:
            promo_briefs_json = self.settings.promo_brief_output_dir / "promo_briefs.json"
            save_promo_brief_append(brief, promo_briefs_json)
        except Exception as e:
            logger.warning(f"promo_briefs.json append failed: {e}")

        # 7. ドラフトステータスを更新
        draft.status = ArticleStatus.PROMO_BRIEF_READY
        draft.updated_at = datetime.now()
        self.db.save_draft(draft)

        return PromoBriefResult(
            brief=brief,
            draft=draft,
            status="ok",
            message=(
                f"PromoBrief 生成完了: '{draft.title[:40]}' "
                f"attribution={brief.attribution_id or 'N/A'}"
            ),
            output_json=output_path,
        )

    # ------------------------------------------------------------------
    # ブリーフ生成
    # ------------------------------------------------------------------

    def _generate_brief(
        self,
        draft: NoteDraft,
        publication: Optional[NotePublication],
        candidate: Optional[TopicCandidate],
        pains: list[PainPoint],
    ) -> PromoBrief:
        """
        [FUTURE_LLM] テンプレートベースで PromoBrief を生成する。
        将来 Claude API に置き換え可能。
        """
        note_url = ""
        note_id = ""
        attribution_id = ""

        if publication:
            note_url = publication.note_url or f"https://note.com/{{slug}}/{publication.note_slug}"
            note_id = publication.id
            attribution_id = publication.attribution_id

        article_summary = self._extract_summary(draft)
        target_audience = (candidate.audience_type if candidate else "") or "スキルワーカー・副業志向者"
        target_pains = [p.pain_summary for p in pains] if pains else [
            "AIツールを使いたいが、方法が分からない",
        ]
        target_pain = target_pains[0] if target_pains else ""
        promotion_angle = (candidate.angle if candidate else "") or "体験談＋本音レポート"
        key_message = self._build_key_message(draft, candidate)
        hook_options = self._build_hook_options(draft, candidate, promotion_angle)
        hashtags = self._build_hashtags(draft, candidate)
        cta_note = self._build_cta(draft)
        post_window = self._build_post_window(target_audience)
        memo = self._build_memo(draft, candidate)

        return PromoBrief(
            draft_id=draft.id,
            note_id=note_id,
            attribution_id=attribution_id,
            note_url=note_url,
            article_title=draft.title,
            article_summary=article_summary,
            target_audience=target_audience,
            target_pains=target_pains,
            target_pain=target_pain,
            promotion_angle=promotion_angle,
            key_message=key_message,
            avoid_expressions=_AVOID_EXPRESSIONS,
            preferred_post_window=post_window,
            hook_options=hook_options,
            recommended_hashtags=hashtags,
            cta_note=cta_note,
            memo=memo,
            notes_for_operator=memo,
        )

    def _extract_summary(self, draft: NoteDraft) -> str:
        """free_part_markdown から記事サマリーを抽出する。"""
        text = draft.free_part_markdown or ""
        # タイトル行（# で始まる）を除去
        lines = [l for l in text.split("\n") if l and not l.startswith("#")]
        # マークダウン記法を除去
        clean_lines = []
        for line in lines[:5]:
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            line = re.sub(r"^[-*] ", "", line.strip())
            line = line.strip()
            if line and not line.startswith("---"):
                clean_lines.append(line)
        summary = "　".join(clean_lines[:3])
        return summary[:200] if summary else f"{draft.title}についての実践ガイドです。"

    def _build_key_message(
        self,
        draft: NoteDraft,
        candidate: Optional[TopicCandidate],
    ) -> str:
        """訴求メッセージを構築する。"""
        if candidate and candidate.hook:
            # フックから過剰な煽り表現を除去
            msg = candidate.hook
            for expr in _AVOID_EXPRESSIONS:
                msg = msg.replace(expr, "")
            return msg.strip()[:100]
        # タイトルから【】部分を除いてメッセージ化
        clean = re.sub(r"【[^】]*】", "", draft.title).strip()
        return clean[:80] if clean else draft.title[:80]

    def _build_hook_options(
        self,
        draft: NoteDraft,
        candidate: Optional[TopicCandidate],
        angle: str,
    ) -> list[str]:
        """冒頭フック案を2つ生成する。"""
        title_clean = re.sub(r"【[^】]*】", "", draft.title).strip()

        hooks = []
        # フック1: タイトル直訳型
        if "体験" in angle or "レポ" in angle:
            hooks.append(f"{title_clean}→正直に書きます")
        elif "比較" in angle:
            hooks.append(f"{title_clean}を比較してみた")
        elif "収益" in angle:
            hooks.append(f"{title_clean}、実際の数字を公開します")
        else:
            hooks.append(f"{title_clean}について書きました")

        # フック2: 問いかけ型
        if candidate and candidate.hook:
            hook_clean = re.sub(r"【[^】]*】", "", candidate.hook).strip()[:80]
            hooks.append(hook_clean)
        else:
            hooks.append(f"「{title_clean}」は本当に可能か？2週間検証した結果")

        return hooks

    def _build_hashtags(
        self,
        draft: NoteDraft,
        candidate: Optional[TopicCandidate],
    ) -> list[str]:
        """ハッシュタグリストを構築する（重複排除）。"""
        tags: list[str] = list(draft.tags)
        if candidate:
            tags.extend(candidate.related_tags)
        # アングル別追加タグ
        if candidate:
            for key, extra in _EXTRA_HASHTAGS.items():
                if key in candidate.angle:
                    tags.extend(extra)
        # 重複排除・最大8タグ
        seen: set[str] = set()
        result = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result[:8]

    def _build_cta(self, draft: NoteDraft) -> str:
        """noteへの誘導文言の方向性を生成する。"""
        if draft.price > 0:
            return (
                f"「続きの実践ログ（{draft.price}円）はnoteにまとめました」"
                "という自然な誘導。値段を前面に出さず、内容の密度を伝える。"
            )
        return "「無料のnoteにまとめています」という自然な誘導。"

    def _build_post_window(self, audience: str) -> str:
        """ターゲット属性から推奨投稿時間帯を決定する。"""
        for key, window in _POST_WINDOW_MAP.items():
            if key in audience:
                return window
        return _DEFAULT_POST_WINDOW

    def _build_memo(
        self,
        draft: NoteDraft,
        candidate: Optional[TopicCandidate],
    ) -> str:
        """Threads運用部向けメモを生成する。"""
        parts = []
        if candidate and "体験" in candidate.angle:
            parts.append("体験談メインなので煽り表現は不要。本音・等身大のトーンで投稿してください。")
        if draft.price <= 300:
            parts.append(f"価格は{draft.price}円と手に取りやすいため、価格訴求より内容の具体性を前面に。")
        parts.append("[FUTURE_LLM] より詳細なメモはClaude APIで生成予定。")
        return "　".join(parts)

    # ------------------------------------------------------------------
    # ローダー
    # ------------------------------------------------------------------

    def _load_draft(self, draft_id: Optional[str] = None) -> Optional[NoteDraft]:
        """published または publish_ready の NoteDraft をロードする。"""
        try:
            if draft_id:
                return self.db.get_draft(draft_id)
            # published を優先
            drafts = self.db.list_drafts(status=ArticleStatus.PUBLISHED.value)
            if drafts:
                return drafts[0]
            # なければ publish_ready
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
                for status in (ArticleStatus.PUBLISHED, ArticleStatus.PUBLISH_READY):
                    candidates = [d for d in all_drafts if d.status == status]
                    if candidates:
                        return candidates[0]
            except Exception as e:
                logger.warning(f"Draft load from JSON failed: {e}")
        return None

    def _load_publication(
        self,
        publication_id: Optional[str],
        draft_id: str,
    ) -> Optional[NotePublication]:
        try:
            if publication_id:
                return self.db.get_publication(publication_id)
            return self.db.get_publication_by_draft_id(draft_id)
        except Exception as e:
            logger.warning(f"Publication load failed: {e}")
        return None

    def _load_candidate(self, candidate_id: str) -> Optional[TopicCandidate]:
        try:
            return self.db.get_topic_candidate(candidate_id)
        except Exception as e:
            logger.warning(f"TopicCandidate load failed: {e}")
        return None

    def _load_pain_points(
        self, candidate: Optional[TopicCandidate]
    ) -> list[PainPoint]:
        if candidate is None:
            return []
        pains = []
        for pain_id in candidate.target_pain_id_list:
            try:
                pain = self.db.get_pain_point(pain_id)
                if pain:
                    pains.append(pain)
            except Exception as e:
                logger.warning(f"PainPoint load failed for {pain_id}: {e}")
        return pains
