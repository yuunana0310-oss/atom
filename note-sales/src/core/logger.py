"""
ロガー設定

使い方:
    from src.core.logger import get_logger
    logger = get_logger(__name__)
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """ルートロガーを設定する。アプリ起動時に1回呼ぶ。"""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """モジュール用ロガーを返す。"""
    return logging.getLogger(name)
