"""note_formatter のプレースホルダ置換テスト（OpenAI API不要）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import note_formatter


def test_placeholder_replace_markdown():
    body = "## 見出し1\n\n本文1\n\n{{IMAGE: body_01}}\n\n## 見出し2\n\n本文2\n"
    saved = {"body_01": "body_01.png"}
    md = note_formatter.to_article_md("タイトル", "リード", body, saved)
    assert "# タイトル" in md
    assert "リード" in md
    assert "![body_01](images/body_01.png)" in md


def test_placeholder_replace_paste():
    body = "本文\n\n{{IMAGE: body_01}}\n"
    saved = {"cover": "cover.png", "body_01": "body_01.png"}
    text = note_formatter.to_note_paste("T", "L", body, saved, hashtags=["AI", "医療"])
    assert "[ここに cover.png を挿入]" in text
    assert "[ここに body_01.png を挿入]" in text
    assert "#AI #医療" in text


def test_missing_image_falls_back_to_comment():
    body = "本文\n{{IMAGE: body_99}}\n"
    saved: dict = {}
    md = note_formatter.to_article_md("T", "L", body, saved)
    assert "生成失敗" in md


def test_skipped_images_use_skipped_label():
    body = "本文\n{{IMAGE: body_01}}\n"
    saved: dict = {}
    md = note_formatter.to_article_md("T", "L", body, saved, skipped=True)
    assert "生成スキップ" in md
    assert "生成失敗" not in md

    paste = note_formatter.to_note_paste("T", "L", body, saved, skipped=True)
    assert "スキップ" in paste

    insert = note_formatter.to_image_insert_map(body, saved, skipped=True)
    assert "生成スキップ" in insert


def test_image_insert_map():
    body = "## A\n本文\n{{IMAGE: body_01}}\n## B\n本文\n{{IMAGE: body_02}}\n"
    saved = {"cover": "cover.png", "body_01": "body_01.png", "body_02": "body_02.png"}
    out = note_formatter.to_image_insert_map(body, saved)
    assert "cover.png" in out
    assert "「A」" in out
    assert "「B」" in out


if __name__ == "__main__":
    test_placeholder_replace_markdown()
    test_placeholder_replace_paste()
    test_missing_image_falls_back_to_comment()
    test_image_insert_map()
    print("OK: all tests passed")
