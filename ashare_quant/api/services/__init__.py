"""业务服务层（业务逻辑、后台 worker 等）。

存放无状态/有状态的业务函数，使 routers 保持薄层（仅做 HTTP IO 与 DB 提交）。
"""
from .data_init import run_data_init_job
from .backtest_runner import run_backtest_job
from .paper_sim import (DEFAULT_PAPER_ACCOUNT, ensure_paper_account,
                        start_paper_sim, stop_paper_sim, is_paper_running)

__all__ = [
    "run_data_init_job",
    "run_backtest_job",
    "DEFAULT_PAPER_ACCOUNT",
    "ensure_paper_account",
    "start_paper_sim",
    "stop_paper_sim",
    "is_paper_running",
]
