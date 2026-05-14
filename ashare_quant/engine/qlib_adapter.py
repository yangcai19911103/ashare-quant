"""Qlib 适配器：把本项目的 Parquet 数据 → Qlib bin 格式，并跑因子/ML 训练。

可选依赖：``pip install pyqlib``。如果未安装，本模块的函数会抛出 ImportError 但不影响其它模块。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ashare_quant.data.storage import get_storage
from ashare_quant.logging_setup import logger


def _ensure_qlib():
    try:
        import qlib  # noqa: F401
    except ImportError as exc:  # noqa: F841
        raise ImportError(
            "未安装 qlib：pip install pyqlib（可选依赖）"
        ) from exc


def export_to_qlib(qlib_dir: str | Path, freq: str = "day") -> None:
    """把 data_warehouse/daily/*.parquet 转成 qlib 期望的 bin/csv 目录。

    简化版：直接生成 CSV 给 qlib 的 dump_bin.py 处理（用户离线运行）。
    """
    qlib_dir = Path(qlib_dir)
    raw_csv = qlib_dir / "csv_raw"
    raw_csv.mkdir(parents=True, exist_ok=True)
    storage = get_storage()
    for sym in storage.list_symbols():
        df = storage.read_daily(sym, adjust="hfq")
        if df.empty:
            continue
        df = df.rename(columns={"trade_date": "date"})
        # qlib 默认列名小写
        out = df[["date", "open", "high", "low", "close", "volume",
                  "amount", "adj_factor"]].copy()
        out["symbol"] = sym
        out.to_csv(raw_csv / f"{sym}.csv", index=False)
    logger.info(f"已导出 {len(list(raw_csv.glob('*.csv')))} 个 CSV 到 {raw_csv}")
    logger.info(f"接下来手工执行（Qlib 自带工具）：\n"
                f"python -m qlib.run.scripts.dump_bin "
                f"dump_all --csv_path {raw_csv} --qlib_dir {qlib_dir / 'qlib_data'} "
                f"--freq {freq} --date_field_name date --include_fields "
                f"open,high,low,close,volume,amount,adj_factor")


def qlib_init(provider_uri: str | Path, region: str = "cn") -> None:
    """初始化 qlib 环境。"""
    _ensure_qlib()
    import qlib
    qlib.init(provider_uri=str(provider_uri), region=region)
    logger.info(f"Qlib 已初始化 provider_uri={provider_uri}")


def alpha158_features(start: str, end: str, instruments: list[str] | str = "csi300"):
    """直接调用 qlib 的 Alpha158 特征。"""
    _ensure_qlib()
    from qlib.contrib.data.handler import Alpha158

    handler = Alpha158(
        instruments=instruments,
        start_time=start,
        end_time=end,
        infer_processors=[],
        learn_processors=[],
    )
    return handler.fetch()
