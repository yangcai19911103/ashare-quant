"""组合优化路由。

注意：本模块名与 PyPI 包 ``portfolio`` 同名，但因 routers 子包内置导入路径
``ashare_quant.api.routers.portfolio``，不会与外部包冲突。
"""
from __future__ import annotations

import math
import random
from typing import List

from fastapi import APIRouter

from ..schemas import OptimizeRequest

router = APIRouter()


def _normalize(w: List[float]) -> List[float]:
    s = sum(w) or 1.0
    return [round(x / s, 6) for x in w]


def _compute_weights(method: str, n: int, seed: int = 1) -> List[float]:
    """根据方法名生成 n 维权重；非真实优化，仅供 demo 演示。"""
    rng = random.Random(seed + hash(method) & 0xFF)
    if method == "ew":
        return [1.0 / n] * n
    if method == "iv":
        vols = [0.10 + rng.random() * 0.15 for _ in range(n)]
        return _normalize([1 / v for v in vols])
    if method == "rp":
        return _normalize([1 / (0.12 + rng.random() * 0.08) for _ in range(n)])
    if method == "mv":
        return _normalize([rng.uniform(0.02, 0.25) for _ in range(n)])
    if method == "mvo":
        return _normalize([0.08 + rng.random() * 0.12 for _ in range(n)])
    if method == "maxsharpe":
        return _normalize([rng.uniform(0.05, 0.25) for _ in range(n)])
    if method == "bl":
        ew = [1.0 / n] * n
        views = [rng.gauss(0, 0.03) for _ in range(n)]
        return _normalize([max(0.01, ew[i] + views[i]) for i in range(n)])
    if method == "cvar":
        return _normalize([rng.uniform(0.05, 0.20) for _ in range(n)])
    if method == "hrp":
        return _normalize([rng.uniform(0.08, 0.18) for _ in range(n)])
    return [1.0 / n] * n


@router.post("/optimize")
def optimize(req: OptimizeRequest):
    n = len(req.symbols)
    if n == 0:
        return {"error": "no symbols"}

    weights = _compute_weights(req.method, n)
    weights = [min(req.max_weight, max(req.min_weight, w)) for w in weights]
    weights = _normalize(weights)

    rng = random.Random(42)
    vols = [0.10 + rng.random() * 0.15 for _ in range(n)]
    rets = [0.06 + rng.random() * 0.10 for _ in range(n)]
    port_ret = sum(w * r for w, r in zip(weights, rets))
    port_vol = math.sqrt(sum((w * v) ** 2 for w, v in zip(weights, vols)) * 1.2)
    sharpe = (port_ret - 0.03) / port_vol if port_vol > 0 else 0

    risk_contrib = {sym: round(w * v, 6) for sym, w, v in zip(req.symbols, weights, vols)}

    frontier = []
    for i in range(25):
        vol = 0.08 + i * 0.012
        r = 0.04 + math.sqrt(max(0, vol - 0.06)) * 0.35
        frontier.append({"vol": round(vol, 4), "ret": round(r, 4)})

    return {
        "weights": {sym: w for sym, w in zip(req.symbols, weights)},
        "expected_return": round(port_ret, 6),
        "volatility": round(port_vol, 6),
        "sharpe": round(sharpe, 4),
        "risk_contrib": risk_contrib,
        "frontier": frontier,
        "current_point": {"vol": round(port_vol, 4), "ret": round(port_ret, 4)},
        "asset_stats": [
            {"symbol": s, "expected_return": round(r, 4), "volatility": round(v, 4)}
            for s, r, v in zip(req.symbols, rets, vols)
        ],
    }
