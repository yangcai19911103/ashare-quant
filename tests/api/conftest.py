"""API 测试 fixtures：用 SQLite in-memory 替换 MySQL。

要点：
* 必须在 import 任何 ashare_quant.api 子模块之前设置环境变量
* 必须 patch 所有路由模块中 `from ..database import SessionLocal` 的本地引用
"""
from __future__ import annotations

import os
import sys

import pytest

# 关闭启动时 auto init / seed，由我们手动控制
os.environ["ASHARE_API_AUTO_INIT"] = "0"
os.environ["ASHARE_API_SEED"] = "0"
# 即使 settings.yaml 里没 MySQL 配置，也能 fallback 到 SQLite
os.environ["ASHARE_MYSQL_URL"] = "sqlite:///./_aq_test.sqlite"


@pytest.fixture(scope="session")
def _engine():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    # 文件型 SQLite + StaticPool → 单连接共享，跨线程也能用
    engine = create_engine(
        "sqlite:///./_aq_test.sqlite",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    yield engine
    engine.dispose()
    try:
        os.unlink("./_aq_test.sqlite")
    except OSError:
        pass


@pytest.fixture(scope="session", autouse=True)
def _setup_db(_engine):
    """把全局 engine / SessionLocal 替换为测试库，并 patch 所有路由模块的引用。"""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, expire_on_commit=False, future=True
    )

    from ashare_quant.api import database
    database.engine = _engine
    database.SessionLocal = SessionLocal

    # 让 routers / services 模块里 `from ..database import SessionLocal`
    # 捕获的本地名指向测试 Session
    import ashare_quant.api.routers.backtest as r_bt
    import ashare_quant.api.routers.data as r_data
    import ashare_quant.api.routers.live as r_live
    import ashare_quant.api.routers.paper as r_paper
    import ashare_quant.api.services.backtest_runner as s_bt
    import ashare_quant.api.services.data_init as s_di
    import ashare_quant.api.services.paper_sim as s_ps
    for m in (r_bt, r_data, r_live, r_paper, s_bt, s_di, s_ps):
        if hasattr(m, "SessionLocal"):
            m.SessionLocal = SessionLocal

    # 建表
    from ashare_quant.api import models  # noqa: F401
    database.Base.metadata.create_all(_engine)

    # seed 演示数据
    from ashare_quant.api.seed import run_seed
    run_seed()

    yield SessionLocal


@pytest.fixture()
def db_session(_setup_db):
    """提供一个独立的数据库 session（事务级隔离）。"""
    session = _setup_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(_setup_db):
    """FastAPI TestClient。"""
    from fastapi.testclient import TestClient

    from ashare_quant.api.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _stub_background(monkeypatch):
    """把 threading.Thread 替换为 no-op，避免后台线程污染测试与 SQLite 单连接。"""
    import threading

    class _DummyThread:
        def __init__(self, *a, **kw):
            self._target = kw.get("target")
            self._args = kw.get("args", ())

        def start(self):  # 一律不执行后台任务
            return

        def join(self, *a, **kw):
            return

        @property
        def daemon(self):
            return True

        @daemon.setter
        def daemon(self, v):
            pass

    real_thread = threading.Thread
    monkeypatch.setattr(threading, "Thread", _DummyThread)
    yield
    monkeypatch.setattr(threading, "Thread", real_thread)
