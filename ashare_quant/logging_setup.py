"""统一日志配置，基于 loguru。"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from ashare_quant.config import get, logs_root


_INITIALIZED = False


def setup_logger() -> None:
    """初始化日志（幂等）。"""
    global _INITIALIZED
    if _INITIALIZED:
        return

    level = get("logging.level", "INFO")
    rotation = get("logging.rotation", "100 MB")
    retention = get("logging.retention", "30 days")
    log_dir: Path = logs_root()

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "| <level>{level: <7}</level> "
            "| <cyan>{name}:{function}:{line}</cyan> "
            "- <level>{message}</level>"
        ),
    )
    logger.add(
        log_dir / "aq_{time:YYYY-MM-DD}.log",
        level=level,
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        enqueue=True,
    )
    _INITIALIZED = True


setup_logger()

__all__ = ["logger", "setup_logger"]
