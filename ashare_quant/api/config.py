"""API 模块统一配置加载。

集中处理：
1. MySQL URL 拼装（环境变量 > settings.yaml > 默认值）
2. FastAPI 应用配置
3. 路径常量

避免散落各处重复读 settings。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

try:
    from ashare_quant.config import get_settings
except Exception:  # 兼容尚未安装为包的情况
    get_settings = None  # type: ignore


# ------------------------- 路径常量 -------------------------

API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parents[1]
WEB_DIR = PROJECT_ROOT / "web"
SQL_DIR = API_DIR / "sql"


# ------------------------- 数据类 -------------------------

@dataclass
class MysqlConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "ashare_quant"
    charset: str = "utf8mb4"
    pool_size: int = 10
    pool_recycle: int = 3600
    auto_create_database: bool = True

    @property
    def url(self) -> str:
        """SQLAlchemy URL（连接到指定 database）。"""
        return (f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/"
                f"{self.database}?charset={self.charset}")

    @property
    def server_url(self) -> str:
        """SQLAlchemy URL（不指定 database，用于建库）。"""
        return (f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/"
                f"?charset={self.charset}")

    def mask(self) -> str:
        pwd = "***" if self.password else "(empty)"
        return f"mysql://{self.user}:{pwd}@{self.host}:{self.port}/{self.database}"


@dataclass
class ApiConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    auto_init_db: bool = True
    auto_seed: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["*"])


# ------------------------- 加载 -------------------------

def _load_settings() -> Dict[str, Any]:
    if get_settings is None:
        return {}
    try:
        return get_settings()
    except Exception as e:
        logger.warning(f"读取 settings.yaml 失败：{e}")
        return {}


def load_mysql() -> MysqlConfig:
    """优先级：ASHARE_MYSQL_URL > 各 ASHARE_MYSQL_* > settings.yaml > 默认值。"""
    cfg = MysqlConfig()

    # 1) 单一 URL 环境变量（适合容器化部署）
    env_url = os.environ.get("ASHARE_MYSQL_URL")
    if env_url:
        # 从 URL 反解：mysql+pymysql://user:pwd@host:port/db?charset=utf8mb4
        # 这里只用于显示，create_engine 直接用 URL
        cfg.password = "<from_env_url>"
        return _MysqlFromUrl(env_url, cfg)

    # 2) settings.yaml
    sect = (_load_settings().get("mysql") or {})
    for k in ("host", "port", "user", "password", "database", "charset",
              "pool_size", "pool_recycle", "auto_create_database"):
        if k in sect and sect[k] is not None:
            setattr(cfg, k, sect[k])

    # 3) 细粒度环境变量覆盖
    cfg.host = os.environ.get("ASHARE_MYSQL_HOST", cfg.host)
    cfg.port = int(os.environ.get("ASHARE_MYSQL_PORT", cfg.port))
    cfg.user = os.environ.get("ASHARE_MYSQL_USER", cfg.user)
    cfg.password = os.environ.get("ASHARE_MYSQL_PASSWORD", cfg.password)
    cfg.database = os.environ.get("ASHARE_MYSQL_DB", cfg.database)
    return cfg


class _MysqlFromUrl(MysqlConfig):
    """直接使用环境变量提供的完整 URL，覆盖 url/server_url 计算。"""

    def __init__(self, url: str, base: MysqlConfig):
        super().__init__(**base.__dict__)
        self._url = url

    @property
    def url(self) -> str:
        return self._url

    @property
    def server_url(self) -> str:
        # 把 /<db> 部分去掉
        head, _, tail = self._url.rpartition("/")
        if "?" in tail:
            tail = tail.split("?", 1)[1]
            return f"{head}/?{tail}"
        return head + "/"


def load_api() -> ApiConfig:
    cfg = ApiConfig()
    sect = (_load_settings().get("api") or {})
    for k in ("host", "port", "auto_init_db", "auto_seed", "cors_origins"):
        if k in sect and sect[k] is not None:
            setattr(cfg, k, sect[k])
    # env 覆盖
    cfg.host = os.environ.get("ASHARE_API_HOST", cfg.host)
    cfg.port = int(os.environ.get("ASHARE_API_PORT", cfg.port))
    if "ASHARE_API_AUTO_INIT" in os.environ:
        cfg.auto_init_db = os.environ["ASHARE_API_AUTO_INIT"] != "0"
    if "ASHARE_API_SEED" in os.environ:
        cfg.auto_seed = os.environ["ASHARE_API_SEED"] != "0"
    return cfg


# 单例（首次 import 时缓存）
MYSQL: MysqlConfig = load_mysql()
API: ApiConfig = load_api()
