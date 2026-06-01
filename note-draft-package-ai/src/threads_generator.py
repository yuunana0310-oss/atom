"""Threads告知文の生成（Phase 3で利用予定。雛形だけ用意）。"""
from __future__ import annotations

import json
from pathlib import Path

from . import openai_client

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def generate_threads_posts(article: dict, plan: dict, quality: bool = False) -> dict:
    system = _load("system_base.md") + "\n\n---\n\n" + _load("threads_generator.md")

    payload = {
        "title": article.get("title"),
        "lead": article.get("lead"),
        "core_message": plan.get("core_message"),
        "sales_route": plan.get("sales_route"),
        "hashtags": plan.get("hashtags", []),
    }

    user = (
        "以下のJSONをもとに、Threads告知用の短文を生成してください。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    return openai_client.chat_json(system, user, quality=quality)
