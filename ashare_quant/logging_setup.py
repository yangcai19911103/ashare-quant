"""统一日志配置，基于 loguru。"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from loguru import logger

from ashare_quant.config import get, logs_root


_INITIALIZED = False
_UVICORN_FILE_HANDLERS = False


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


def attach_uvicorn_file_logging() -> None:
    """把 Uvicorn 的 access / error 日志追加写入 logs/（与 loguru 应用日志并存）。

    在 FastAPI lifespan 启动阶段调用一次即可；幂等，重复调用不会重复挂 handler。
    """
    global _UVICORN_FILE_HANDLERS
    if _UVICORN_FILE_HANDLERS:
        return

    log_dir = logs_root()
    max_bytes = int(get("logging.uvicorn_max_bytes", 100 * 1024 * 1024))
    backup = int(get("logging.uvicorn_backup_count", 5))
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    def _has_rotating(path_suffix: str, lg: logging.Logger) -> bool:
        for h in lg.handlers:
            if isinstance(h, RotatingFileHandler):
                base = getattr(h, "baseFilename", "") or ""
                if base.replace("\\", "/").endswith(path_suffix):
                    return True
        return False

    access_log = log_dir / "api_access.log"
    server_log = log_dir / "api_server.log"

    acc = logging.getLogger("uvicorn.access")
    if not _has_rotating("api_access.log", acc):
        h = RotatingFileHandler(
            access_log, maxBytes=max_bytes, backupCount=backup, encoding="utf-8"
        )
        h.setFormatter(fmt)
        acc.addHandler(h)

    err = logging.getLogger("uvicorn.error")
    if not _has_rotating("api_server.log", err):
        h = RotatingFileHandler(
            server_log, maxBytes=max_bytes, backupCount=backup, encoding="utf-8"
        )
        h.setFormatter(fmt)
        err.addHandler(h)

    _UVICORN_FILE_HANDLERS = True


setup_logger()

__all__ = ["logger", "setup_logger", "attach_uvicorn_file_logging"]
