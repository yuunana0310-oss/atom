"""本文ライターAI。設計JSONからタイトル・リード・本文Markdownを生成。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from . import openai_client

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def write_article(
    plan: dict,
    theme: str,
    target: str,
    article_type: str,
    purpose: str,
    tone: str,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    product_cta: Optional[str] = None,
    quality: bool = False,
) -> dict:
    """記事本文を生成。{title, lead, body_markdown} を返す。"""
    system = _load("system_base.md") + "\n\n---\n\n" + _load("article_writer.md")

    payload = {
        "theme": theme,
        "target": target,
        "article_type": article_type,
        "purpose": purpose,
        "tone": tone,
        "product": {
            "name": product_name,
            "description": product_description,
            "cta": product_cta,
        }
        if product_name
        else None,
        "plan": plan,
    }

    user = (
        "以下のJSONをもとに記事本文を執筆してください。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    result = openai_client.chat_json(system, user, quality=quality)

    # 必須キーを保証
    result.setdefault("title", (plan.get("title_candidates") or [theme])[0])
    result.setdefault("lead", "")
    result.setdefault("body_markdown", "")
    return result
