"""
dry-run サポート

dry_run=True の場合、副作用（DB書き込み・ファイル出力・API呼び出し）を
実行せず、代わりにログで意図を出力する。

使い方:
    from src.utils.dry_run import DryRunGuard

    guard = DryRunGuard(dry_run=True)

    # 副作用をスキップ
    if guard.should_run("SQLite書き込み: pain_points"):
        db.save(pain_point)

    # dry-runで「本来ならこうする」を出力
    guard.log_would_do("researcher.generate(pain) → NoteCandidate[]")
"""

from __future__ import annotations

import functools
from typing import Callable

from rich.console import Console

console = Console()


class DryRunGuard:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def should_run(self, action_description: str) -> bool:
        """
        dry_run=True なら False を返しログを出す。
        dry_run=False なら True を返す（実行して良い）。

        使い方:
            if guard.should_run("DB書き込み: pain_points"):
                db.save(pain_point)
        """
        if self.dry_run:
            console.print(f"[bold yellow][DRY-RUN][/bold yellow] skip: {action_description}")
            return False
        return True

    def skip_if_dry(self, action_description: str) -> Callable:
        """関数デコレーター版。dry_run=True なら関数をスキップする。"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self.should_run(action_description):
                    return None
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def log_would_do(self, message: str) -> None:
        """dry-run時に「本来ならこうする」を出力する。"""
        if self.dry_run:
            console.print(f"[bold cyan][DRY-RUN] would:[/bold cyan] {message}")
