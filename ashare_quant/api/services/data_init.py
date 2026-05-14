"""数据初始化后台任务。"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from loguru import logger

from ..database import SessionLocal
from ..models import DataJob


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 步骤模板（包含 workers 占位）
_STEPS = [
    "[1/5] 拉取全市场股票列表... 5247 只",
    "[2/5] 构建指数成分 HS300/ZZ500/ZZ800/ZZ1000",
    "[3/5] 拉取日 K 数据 (workers={workers})...",
    "[4/5] 拉取北向资金 / 龙虎榜 / 财报快报",
    "[5/5] 写入 MySQL daily_bar / fundamental",
    "完成 ✓",
]


def run_data_init_job(job_id: int, params: dict, step_delay: float = 1.0) -> None:
    """后台模拟数据初始化，按步骤更新进度。

    Args:
        job_id: data_job 主键
        params: 启动参数字典（至少需 ``workers``）
        step_delay: 每步等待秒（测试时可置 0）
    """
    workers = params.get("workers", 4)
    steps = [s.format(workers=workers) for s in _STEPS]
    session = SessionLocal()
    try:
        job = session.get(DataJob, job_id)
        if job is None:
            logger.warning(f"DataJob #{job_id} 不存在，跳过")
            return
        job.status = "running"
        job.started_at = _now()
        session.commit()

        log_buf = []
        for i, line in enumerate(steps, 1):
            if step_delay > 0:
                time.sleep(step_delay)
            log_buf.append(line)
            job = session.get(DataJob, job_id)
            if job is None:
                return
            job.progress = int(i / len(steps) * 100)
            job.log = "\n".join(log_buf) + "\n"
            session.commit()

        job = session.get(DataJob, job_id)
        if job is not None:
            job.status = "success"
            job.finished_at = _now()
            session.commit()
        logger.info(f"DataJob #{job_id} 初始化完成")
    except Exception as e:
        logger.exception(f"DataJob #{job_id} 失败: {e}")
        try:
            job = session.get(DataJob, job_id)
            if job is not None:
                job.status = "failed"
                job.log = (job.log or "") + f"\nERROR: {e}\n"
                job.finished_at = _now()
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()
