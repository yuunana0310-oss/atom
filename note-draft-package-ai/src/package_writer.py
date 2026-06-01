"""記事パッケージ（articleファイル群 + 画像）をディレクトリに保存。"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from . import note_formatter, openai_client, utils


def write_package(
    *,
    out_dir: Path,
    inputs: dict,
    plan: dict,
    article: dict,
    image_prompts: Dict[str, str],
    saved_images: Dict[str, Path],
    image_errors: List[str],
) -> Path:
    """全成果物をフォルダに保存し、ルートパスを返す。

    out_dir は事前に make_output_dir 等で作成済みであること。images/ は
    既に画像が配置されている前提（または skip）。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "images").mkdir(parents=True, exist_ok=True)

    theme = inputs.get("theme", "")
    title = article.get("title") or theme
    lead = article.get("lead", "")
    body_md = article.get("body_markdown", "")
    skipped = bool(inputs.get("skip_images"))

    # ファイル名は "role.png" 形式に揃えて保存済みなので、role->name のmapを作る
    saved_map = {role: f"{role}.png" for role in saved_images.keys()}

    # article.md
    article_md = note_formatter.to_article_md(
        title, lead, body_md, saved_map, skipped=skipped
    )
    utils.write_text(out_dir / "article.md", article_md)

    # note_paste.txt
    paste_text = note_formatter.to_note_paste(
        title,
        lead,
        body_md,
        saved_map,
        hashtags=plan.get("hashtags") or [],
        skipped=skipped,
    )
    utils.write_text(out_dir / "note_paste.txt", paste_text)

    # title_candidates.txt
    utils.write_text(
        out_dir / "title_candidates.txt",
        note_formatter.title_candidates_text(plan.get("title_candidates") or []),
    )

    # hashtags.txt
    utils.write_text(
        out_dir / "hashtags.txt",
        note_formatter.hashtags_text(plan.get("hashtags") or []),
    )

    # image_insert_map.txt
    utils.write_text(
        out_dir / "image_insert_map.txt",
        note_formatter.to_image_insert_map(body_md, saved_map, skipped=skipped),
    )

    # image_prompts.txt（再生成・微調整用）
    if image_prompts:
        from . import image_generator

        image_generator.save_prompts_text(image_prompts, out_dir / "image_prompts.txt")

    # plan.json（透明性確保）
    utils.write_json(out_dir / "plan.json", plan)

    # metadata.json
    metadata = {
        **inputs,
        "theme": inputs.get("theme"),
        "title_used": title,
        "saved_images": list(saved_images.keys()),
        "image_errors": image_errors,
        "created_at": utils.now_iso(),
        "text_model": openai_client.model_name("text"),
        "quality_model": openai_client.model_name("quality"),
        "image_model": openai_client.model_name("image"),
        "status": "draft_package_generated",
    }
    utils.write_json(out_dir / "metadata.json", metadata)

    return out_dir
