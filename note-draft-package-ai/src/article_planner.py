"""記事設計AI。ユーザー入力を受けて構成設計JSONを返す。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import openai_client

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def plan_article(
    theme: str,
    target: str,
    article_type: str,
    purpose: str,
    tone: str,
    body_image_count: int,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    quality: bool = False,
) -> dict:
    """記事の構成設計をJSONで返す。"""
    system = _load("system_base.md") + "\n\n---\n\n" + _load("article_planner.md")

    user_lines = [
        f"記事テーマ: {theme}",
        f"ターゲット: {target}",
        f"記事タイプ: {article_type}",
        f"記事の目的: {purpose}",
        f"文体: {tone}",
        f"本文画像枚数: {body_image_count}",
    ]
    if product_name:
        user_lines.append(f"売りたい商品: {product_name}")
    if product_description:
        user_lines.append(f"商品説明: {product_description}")

    user = "\n".join(user_lines)
    plan = openai_client.chat_json(system, user, quality=quality)

    # body_image_count に合わせて image_needed を補正
    plan = _enforce_image_count(plan, body_image_count)
    return plan


def _enforce_image_count(plan: dict, target_body_count: int) -> dict:
    sections = plan.get("sections") or []
    needed = [i for i, s in enumerate(sections) if s.get("image_needed")]

    # 多すぎる場合は後ろから False に
    while len(needed) > target_body_count and needed:
        idx = needed.pop()
        sections[idx]["image_needed"] = False
        sections[idx].pop("image_role", None)

    # 足りない場合は image_needed=False のセクションに True を立てる
    while len(needed) < target_body_count:
        added = False
        for i, s in enumerate(sections):
            if not s.get("image_needed"):
                s["image_needed"] = True
                s.setdefault("image_role", "概念図")
                needed.append(i)
                added = True
                break
        if not added:
            break

    plan["sections"] = sections
    return plan
