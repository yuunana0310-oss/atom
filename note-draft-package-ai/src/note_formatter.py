"""note向けに本文を整形する。

- article.md: 標準Markdown（画像はMarkdown記法で挿入）
- note_paste.txt: noteエディタに貼り付けやすい形（画像は [ここに XXX を挿入] のメモ）
- image_insert_map.txt: どの位置にどの画像を入れるかのメモ
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

PLACEHOLDER_RE = re.compile(r"\{\{IMAGE:\s*([a-zA-Z0-9_]+)\s*\}\}")


def to_article_md(
    title: str,
    lead: str,
    body_markdown: str,
    saved_images: Dict[str, str],
    skipped: bool = False,
) -> str:
    """Markdownファイル用：画像プレースホルダを ![](images/xxx.png) に置換。"""
    parts: List[str] = [f"# {title}", ""]
    if lead:
        parts.append(lead)
        parts.append("")

    # cover を冒頭に挿入
    if "cover" in saved_images:
        parts.append(f"![cover](images/cover.png)")
        parts.append("")
    elif skipped:
        parts.append("<!-- cover画像：生成スキップ（必要に応じて手動で追加） -->")
        parts.append("")

    body = _replace_placeholders(body_markdown, saved_images, mode="markdown", skipped=skipped)
    parts.append(body)
    return "\n".join(parts).rstrip() + "\n"


def to_note_paste(
    title: str,
    lead: str,
    body_markdown: str,
    saved_images: Dict[str, str],
    hashtags: List[str] | None = None,
    skipped: bool = False,
) -> str:
    """note貼り付け用：画像位置はメモ。タグは末尾に。"""
    parts: List[str] = [f"# {title}", ""]
    if lead:
        parts.append(lead)
        parts.append("")

    if "cover" in saved_images:
        parts.append("[ここに cover.png を挿入]")
        parts.append("")
    elif skipped:
        parts.append("[cover画像：生成スキップ／必要なら自分で用意]")
        parts.append("")

    body = _replace_placeholders(body_markdown, saved_images, mode="paste", skipped=skipped)
    parts.append(body)

    if hashtags:
        parts.append("")
        parts.append(" ".join(f"#{t}" for t in hashtags))

    return "\n".join(parts).rstrip() + "\n"


def to_image_insert_map(
    body_markdown: str,
    saved_images: Dict[str, str],
    skipped: bool = False,
) -> str:
    """どの見出し直後にどの画像を入れるかをテキストで残す。"""
    lines: List[str] = []
    lines.append("# 画像挿入位置メモ")
    lines.append("")
    if skipped:
        lines.append("（このパッケージは画像生成をスキップしています）")
        lines.append("")
    if "cover" in saved_images:
        lines.append("- 冒頭リード文の直後 → cover.png")
    elif skipped:
        lines.append("- 冒頭リード文の直後 → cover（生成スキップ／任意）")

    current_heading = "(冒頭)"
    for raw in body_markdown.splitlines():
        h = re.match(r"^#{1,6}\s+(.*)", raw)
        if h:
            current_heading = h.group(1).strip()
            continue
        for m in PLACEHOLDER_RE.finditer(raw):
            role = m.group(1)
            if role in saved_images:
                lines.append(f"- 「{current_heading}」セクション内 → {role}.png")
            elif skipped:
                lines.append(f"- 「{current_heading}」セクション内 → {role}（生成スキップ／任意）")
            else:
                lines.append(f"- 「{current_heading}」セクション内 → {role}（生成失敗：手動挿入）")
    return "\n".join(lines) + "\n"


def _replace_placeholders(
    body: str, saved: Dict[str, str], mode: str, skipped: bool = False
) -> str:
    def repl(m: re.Match) -> str:
        role = m.group(1)
        if role not in saved:
            if skipped:
                if mode == "markdown":
                    return f"<!-- 画像「{role}」：生成スキップ（必要なら手動で追加） -->"
                return f"[画像「{role}」：生成スキップ／任意]"
            # 生成失敗
            if mode == "markdown":
                return f"<!-- 画像「{role}」生成失敗：手動で挿入してください -->"
            return f"[画像「{role}」生成失敗：手動で挿入]"
        if mode == "markdown":
            return f"![{role}](images/{role}.png)"
        return f"[ここに {role}.png を挿入]"

    return PLACEHOLDER_RE.sub(repl, body)


def title_candidates_text(candidates: List[str]) -> str:
    if not candidates:
        return "(タイトル候補なし)\n"
    return "\n".join(f"- {t}" for t in candidates) + "\n"


def hashtags_text(tags: List[str]) -> str:
    if not tags:
        return ""
    return " ".join(f"#{t}" for t in tags) + "\n"
