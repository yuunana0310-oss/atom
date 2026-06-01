"""package_writer の保存処理テスト（API不要、画像なしで実行）。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import package_writer, utils


def test_write_package_minimal():
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = utils.make_output_dir(tmp, "テスト記事")
        plan = {
            "title_candidates": ["案1", "案2"],
            "hashtags": ["AI", "医療"],
            "sections": [],
        }
        article = {
            "title": "テスト記事タイトル",
            "lead": "リード文。",
            "body_markdown": "## 見出し\n\n本文だ。\n",
        }
        inputs = {
            "theme": "テスト記事",
            "target": "テスト読者",
        }

        result = package_writer.write_package(
            out_dir=out_dir,
            inputs=inputs,
            plan=plan,
            article=article,
            image_prompts={},
            saved_images={},
            image_errors=[],
        )

        assert (result / "article.md").exists()
        assert (result / "note_paste.txt").exists()
        assert (result / "title_candidates.txt").exists()
        assert (result / "hashtags.txt").exists()
        assert (result / "image_insert_map.txt").exists()
        assert (result / "metadata.json").exists()
        assert (result / "plan.json").exists()
        assert (result / "images").is_dir()

        article_md = (result / "article.md").read_text(encoding="utf-8")
        assert "# テスト記事タイトル" in article_md
        assert "## 見出し" in article_md


if __name__ == "__main__":
    test_write_package_minimal()
    print("OK: all tests passed")
