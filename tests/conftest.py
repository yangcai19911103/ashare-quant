"""pytest 全局 fixtures：用临时目录代替真实数据仓库，避免污染本地。"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolate_storage(tmp_path_factory):
    """所有测试共用一个临时数据仓库目录。"""
    tmp = tmp_path_factory.mktemp("aq_storage")
    os.environ["AQ_TEST_TMP"] = str(tmp)

    # 让 get_settings 用临时目录
    from ashare_quant import config as cfg
    cfg.get_settings.cache_clear()
    settings = cfg.get_settings()
    settings.setdefault("data", {})["storage_root"] = str(tmp)
    settings.setdefault("logging", {})["dir"] = str(tmp / "logs")

    # 清理 storage 单例
    from ashare_quant.data import storage as st
    st.get_storage.cache_clear()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def mock_adapter():
    from ashare_quant.data.ingest.mock_adapter import MockAdapter
    return MockAdapter()
