"""画像生成の実行。失敗しても記事生成全体は止まらないようにする。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

from . import openai_client


def generate_all_images(
    prompts: Dict[str, str],
    images_dir: Path,
    cover_size: str = "1024x1536",
    body_size: str = "1536x1024",
) -> Tuple[Dict[str, Path], List[str]]:
    """各ロールの画像を生成。生成済みパスとエラーログを返す。

    cover は portrait、body は landscape をデフォルトにする。
    """
    images_dir.mkdir(parents=True, exist_ok=True)

    saved: Dict[str, Path] = {}
    errors: List[str] = []

    for role, prompt in prompts.items():
        out = images_dir / f"{role}.png"
        size = cover_size if role == "cover" else body_size
        try:
            openai_client.generate_image(prompt=prompt, out_path=out, size=size)
            saved[role] = out
        except Exception as e:  # noqa: BLE001 - ログに残して続行
            errors.append(f"{role}: {type(e).__name__}: {e}")
    return saved, errors


def save_prompts_text(prompts: Dict[str, str], path: Path) -> None:
    """生成プロンプトをテキストで保存（再生成・微調整に使う）。"""
    lines: List[str] = []
    for role, p in prompts.items():
        lines.append(f"## {role}")
        lines.append(p)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
