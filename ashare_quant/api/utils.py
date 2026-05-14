"""通用工具：mock 数据生成器、时间序列、随机收益等。

当数据库为空时，路由 fallback 返回这些 mock 数据，
保证前端 UI 始终可用、可演示。
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple


def gen_dates(n: int, end: datetime | None = None, weekday_only: bool = True) -> List[str]:
    end = end or datetime.now()
    out: List[str] = []
    d = end
    while len(out) < n:
        if not weekday_only or d.weekday() < 5:
            out.append(d.strftime("%Y-%m-%d"))
        d -= timedelta(days=1)
    return list(reversed(out))


def gen_price_series(n: int, s0: float = 1.0, mu: float = 0.0005, sigma: float = 0.013, seed: int = 1) -> List[float]:
    rng = random.Random(seed)
    s = s0
    out = []
    for _ in range(n):
        eps = rng.gauss(0.0, 1.0)
        s *= math.exp(mu + sigma * eps)
        out.append(round(s, 6))
    return out


def gen_drawdown(nav: List[float]) -> List[float]:
    peak = -1.0
    out = []
    for v in nav:
        peak = max(peak, v)
        out.append(round((v - peak) / peak, 6) if peak > 0 else 0.0)
    return out


def metrics_from_nav(nav: List[float], freq: int = 252) -> Dict[str, float]:
    if not nav or len(nav) < 2:
        return {"total_return": 0, "annual_return": 0, "sharpe": 0, "max_drawdown": 0, "calmar": 0, "win_rate": 0}
    rets = [nav[i] / nav[i - 1] - 1 for i in range(1, len(nav))]
    total = nav[-1] / nav[0] - 1
    years = len(nav) / freq
    ann = (1 + total) ** (1 / years) - 1 if years > 0 else 0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    sd = math.sqrt(var)
    sharpe = (mean * freq) / (sd * math.sqrt(freq)) if sd > 0 else 0
    dd = gen_drawdown(nav)
    mdd = min(dd)
    wr = sum(1 for r in rets if r > 0) / len(rets)
    calmar = ann / abs(mdd) if mdd < 0 else 0
    return {
        "total_return": round(total, 6),
        "annual_return": round(ann, 6),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(mdd, 6),
        "calmar": round(calmar, 4),
        "win_rate": round(wr, 4),
    }


def monthly_returns(dates: List[str], nav: List[float]) -> List[Dict]:
    if not dates:
        return []
    out: Dict[str, Tuple[float, float]] = {}
    for d, v in zip(dates, nav):
        ym = d[:7]
        if ym not in out:
            out[ym] = (v, v)
        else:
            first, _ = out[ym]
            out[ym] = (first, v)
    result = []
    for ym, (f, l) in sorted(out.items()):
        y, m = ym.split("-")
        result.append({"year": int(y), "month": int(m), "ret": round(l / f - 1, 6)})
    return result


STOCK_POOL = [
    ("600519.SH", "贵州茅台", "白酒",    1706.20, 21452, 27.8),
    ("000858.SZ", "五粮液",   "白酒",     138.20,  5820, 18.5),
    ("601318.SH", "中国平安", "保险",      50.18,  9128,  9.2),
    ("300750.SZ", "宁德时代", "电池",     239.55, 10520, 22.1),
    ("600276.SH", "恒瑞医药", "医药",      44.20,  2810, 35.2),
    ("002594.SZ", "比亚迪",   "汽车",     247.30,  7180, 19.6),
    ("600036.SH", "招商银行", "银行",      40.51, 10210,  6.8),
    ("000651.SZ", "格力电器", "家电",      38.50,  2150,  8.4),
    ("000333.SZ", "美的集团", "家电",      62.10,  4320, 11.2),
    ("600887.SH", "伊利股份", "消费",      28.30,  1820, 15.3),
    ("688981.SH", "中芯国际", "半导体",    63.50,  5012, 52.1),
    ("601166.SH", "兴业银行", "银行",      18.20,  3782,  4.9),
    ("002415.SZ", "海康威视", "电子",      32.10,  3010, 18.9),
    ("000725.SZ", "京东方A", "电子",        4.80,  1810, 22.5),
    ("600030.SH", "中信证券", "证券",      22.50,  3340, 14.8),
]


def sample_universe(n: int = 8) -> List[Dict]:
    return [
        {
            "symbol": s, "name": nm, "industry": ind,
            "last_price": p, "market_cap": mc, "pe_ttm": pe,
            "list_date": "2010-01-01", "in_pool": True,
        }
        for s, nm, ind, p, mc, pe in STOCK_POOL[:n]
    ]


INDUSTRY_WEIGHTS = {"白酒": 22, "银行": 18, "医药": 14, "新能源": 12, "电子": 10,
                    "地产": 8, "消费": 7, "其他": 9}
