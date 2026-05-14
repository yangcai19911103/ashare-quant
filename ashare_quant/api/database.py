"""数据库连接和 Session 管理。

特性：
* 配置通过 :mod:`ashare_quant.api.config` 集中加载
* 启动时如目标 database 不存在则自动 CREATE DATABASE（MySQL 专属，受 settings 控制）
* 暴露 :class:`Base` (DeclarativeBase) / :func:`get_db` (依赖注入) / :func:`db_session` (脚本)
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import MYSQL


def _build_engine() -> Engine:
    return create_engine(
        MYSQL.url,
        pool_pre_ping=True,
        pool_recycle=MYSQL.pool_recycle,
        pool_size=MYSQL.pool_size,
        max_overflow=20,
        echo=False,
        future=True,
    )


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """ORM Declarative Base"""
    pass


def get_db() -> Iterator[Session]:
    """FastAPI 依赖注入：每次请求一个独立 session。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def db_session() -> Iterator[Session]:
    """脚本/任务用 context manager。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_database_exists() -> None:
    """如果目标 MySQL database 不存在，则自动创建。

    只针对 MySQL 方言生效；SQLite/其他方言直接 noop。
    """
    if not MYSQL.url.startswith("mysql"):
        return
    if not getattr(MYSQL, "auto_create_database", True):
        return
    try:
        srv = create_engine(MYSQL.server_url, future=True, isolation_level="AUTOCOMMIT")
        with srv.connect() as conn:
            conn.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL.database}` "
                f"DEFAULT CHARACTER SET {MYSQL.charset} "
                f"DEFAULT COLLATE {MYSQL.charset}_unicode_ci"
            ))
        srv.dispose()
        logger.info(f"确保 MySQL database 存在：{MYSQL.database}")
    except (OperationalError, ProgrammingError) as e:
        logger.warning(f"无法预创建 database（请确认 MySQL 已启动 / 账号权限）：{e}")


def init_db(seed: bool = False) -> None:
    """建库 + 建表 + 可选 seed。"""
    ensure_database_exists()
    from . import models  # noqa: F401  trigger metadata
    Base.metadata.create_all(engine)
    logger.info(f"DB schema ready: {MYSQL.mask()}")
    if seed:
        from .seed import run_seed
        run_seed()
