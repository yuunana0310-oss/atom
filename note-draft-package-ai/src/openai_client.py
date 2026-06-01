"""OpenAI API ラッパー。テキスト・JSON・画像の3関数を提供。"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

_client: Any = None


def get_client():
    """OpenAI クライアントを返す。ライブラリ・キー未準備時は分かりやすい例外を出す。"""
    global _client
    if _client is None:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai パッケージが未インストールです。pip install -r requirements.txt"
            ) from e
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY が .env に設定されていません")
        _client = OpenAI(api_key=api_key)
    return _client


def model_name(kind: str = "text") -> str:
    """kind = text | quality | image"""
    mapping = {
        "text": ("TEXT_MODEL", "gpt-5-mini"),
        "quality": ("QUALITY_MODEL", "gpt-5"),
        "image": ("IMAGE_MODEL", "gpt-image-2"),
    }
    env_key, default = mapping.get(kind, ("TEXT_MODEL", "gpt-5-mini"))
    return os.getenv(env_key, default)


def chat(
    system: str,
    user: str,
    quality: bool = False,
    json_mode: bool = False,
) -> str:
    """シンプルな1往復チャット。json_mode=True なら JSON文字列を返す。"""
    client = get_client()
    model = model_name("quality" if quality else "text")

    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def chat_json(system: str, user: str, quality: bool = False) -> dict:
    """JSON応答を辞書で返す。失敗したら例外。"""
    text = chat(system, user, quality=quality, json_mode=True)
    return json.loads(text)


def generate_image(
    prompt: str,
    out_path: str | Path,
    size: Optional[str] = None,
) -> Path:
    """画像を生成して PNG ファイルに保存。out_path を返す。"""
    client = get_client()
    model = model_name("image")
    size = size or os.getenv("DEFAULT_IMAGE_SIZE", "1024x1536")

    resp = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        n=1,
    )

    item = resp.data[0]
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if getattr(item, "b64_json", None):
        out.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        # gpt-image-1 は b64 が基本だが、url が返るモデル/設定にも備える
        import requests

        r = requests.get(item.url, timeout=60)
        r.raise_for_status()
        out.write_bytes(r.content)
    else:
        raise RuntimeError("画像レスポンスに b64_json も url もありません")

    return out
