"""共通ユーティリティ。日付整形、フォルダ名生成、安全なファイル名化など。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

try:
    from slugify import slugify as _slugify
except ImportError:
    _slugify = None


def today_str(fmt: str = "%Y-%m-%d") -> str:
    return datetime.now().strftime(fmt)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def safe_name(text: str, max_len: int = 60) -> str:
    """日本語OKのフォルダ名を作る（OS禁則文字を除去）。"""
    if not text:
        return "untitled"
    forbidden = r'[\\/:*?"<>|\r\n\t]'
    cleaned = re.sub(forbidden, "", text).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:max_len] or "untitled"


def slug(text: str) -> str:
    if _slugify:
        s = _slugify(text, allow_unicode=True)
        return s or "untitled"
    return safe_name(text).lower()


def make_output_dir(base: str | Path, theme: str) -> Path:
    base_p = Path(base)
    folder = f"{today_str()}_{safe_name(theme)}"
    target = base_p / folder
    (target / "images").mkdir(parents=True, exist_ok=True)
    return target


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: str | Path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
