"""Seed 脚本测试：再次运行不应重复写入。"""
from __future__ import annotations

from sqlalchemy import func, select


def test_seed_is_idempotent(db_session):
    from ashare_quant.api.models import DataSource, FactorDef
    from ashare_quant.api.seed import run_seed

    n1 = db_session.scalar(select(func.count()).select_from(DataSource))
    f1 = db_session.scalar(select(func.count()).select_from(FactorDef))
    run_seed()
    db_session.expire_all()
    n2 = db_session.scalar(select(func.count()).select_from(DataSource))
    f2 = db_session.scalar(select(func.count()).select_from(FactorDef))
    assert n1 == n2
    assert f1 == f2
