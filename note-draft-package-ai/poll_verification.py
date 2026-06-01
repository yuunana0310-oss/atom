"""組織認証の反映を2分おきにチェックする使い捨てスクリプト。

成功したら exit 0、最大15分（8回）試して通らなければ exit 1。
"""
from __future__ import annotations

import sys
import time

from src import openai_client

MAX_TRIES = 8
INTERVAL_SEC = 120

for attempt in range(1, MAX_TRIES + 1):
    print(f"[try {attempt}/{MAX_TRIES}] gpt-image-2 認証チェック中...", flush=True)
    try:
        p = openai_client.generate_image(
            prompt="A simple abstract minimalist circle on plain background.",
            out_path="outputs/_verify_test.png",
            size="1024x1024",
        )
        print(f"OK: 認証反映済み → {p}", flush=True)
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        msg = str(e)[:200]
        if "verified" in msg or "403" in msg:
            print(f"  まだ未反映: {msg}", flush=True)
        else:
            print(f"  別エラー（中断）: {type(e).__name__}: {msg}", flush=True)
            sys.exit(2)

    if attempt < MAX_TRIES:
        print(f"  {INTERVAL_SEC}秒待機...", flush=True)
        time.sleep(INTERVAL_SEC)

print("NG: 15分経過しても反映されず", flush=True)
sys.exit(1)
