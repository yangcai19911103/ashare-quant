"""配置加载：settings.yaml + secrets.yaml + 环境变量，三层合并。

加载顺序（后者覆盖前者）：
1. config/settings.yaml
2. config/secrets.yaml（可选，git 忽略）
3. 环境变量：TUSHARE_TOKEN / QMT_ACCOUNT 等
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并字典。"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    """读取并缓存全局配置（单例）。"""
    settings = _load_yaml(CONFIG_DIR / "settings.yaml")
    secrets = _load_yaml(CONFIG_DIR / "secrets.yaml")
    merged = _deep_merge(settings, secrets)

    # 环境变量覆盖
    if os.environ.get("TUSHARE_TOKEN"):
        merged.setdefault("data", {})["tushare_token"] = os.environ["TUSHARE_TOKEN"]
    if os.environ.get("QMT_ACCOUNT"):
        merged.setdefault("live", {})["account_id"] = os.environ["QMT_ACCOUNT"]

    # 数据目录绝对化
    storage_root = merged.get("data", {}).get("storage_root", "./data_warehouse")
    if not Path(storage_root).is_absolute():
        merged["data"]["storage_root"] = str(PROJECT_ROOT / storage_root)

    return merged


def get(key_path: str, default: Any = None) -> Any:
    """点分路径取值：get('risk.max_position_per_stock')."""
    node: Any = get_settings()
    for part in key_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def project_root() -> Path:
    return PROJECT_ROOT


def storage_root() -> Path:
    root = Path(get("data.storage_root", str(PROJECT_ROOT / "data_warehouse")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def logs_root() -> Path:
    root = Path(get("logging.dir", str(PROJECT_ROOT / "logs")))
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    return root
