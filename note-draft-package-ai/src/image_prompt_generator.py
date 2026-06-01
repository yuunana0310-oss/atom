"""画像生成用プロンプト（英語）を、記事設計から作る。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from . import openai_client

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def collect_image_roles(plan: dict, body_image_count: int) -> List[str]:
    """cover + body_01..body_NN のロール名一覧を返す。"""
    roles = ["cover"]
    for i in range(1, body_image_count + 1):
        roles.append(f"body_{i:02d}")
    return roles


def generate_prompts(
    plan: dict,
    theme: str,
    image_taste: str,
    body_image_count: int,
    quality: bool = False,
) -> dict:
    """各ロール向けの英語プロンプトを返す: {"cover": "...", "body_01": "...", ...}"""
    system = _load("system_base.md") + "\n\n---\n\n" + _load("image_prompt.md")

    roles = collect_image_roles(plan, body_image_count)

    payload = {
        "theme": theme,
        "image_taste": image_taste,
        "plan": plan,
        "image_roles": roles,
    }

    user = (
        "以下のJSONをもとに、各画像ロールの英語プロンプトを生成してください。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    result = openai_client.chat_json(system, user, quality=quality)
    prompts = result.get("prompts", {}) if isinstance(result, dict) else {}

    # 欠けているロールがあれば最低限のフォールバックを入れる
    for role in roles:
        if role not in prompts or not prompts[role]:
            prompts[role] = _fallback_prompt(role, theme, image_taste)
    return prompts


def _fallback_prompt(role: str, theme: str, taste: str) -> str:
    base = (
        f"A premium editorial visual for a Japanese note article about: {theme}. "
        f"Style: {taste}. Sophisticated, cinematic lighting, refined textures, "
        f"no readable text, no fake UI, generous negative space."
    )
    if role == "cover":
        return base + " Composition: portrait, one clear main subject, magazine cover quality."
    return base + " Composition: abstract conceptual illustration, no detailed anatomy."
