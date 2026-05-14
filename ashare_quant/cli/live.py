"""实盘 / 模拟盘 CLI。

示例：
    # 模拟盘：基于本地历史数据回放
    python -m ashare_quant.cli.live paper --strategy cta.dual_ma \\
           --symbols 600519.SH,000858.SZ --start 2024-01-01

    # 实盘（需要 QMT 已登录）
    python -m ashare_quant.cli.live qmt --strategy multi_factor.value_quality \\
           --universe hs300

    # 启动监控大屏
    python -m ashare_quant.cli.live dashboard
"""
from __future__ import annotations

import json
import time

import click

from ashare_quant.logging_setup import logger


@click.group()
def cli() -> None:
    """ashare-quant 实盘工具。"""


@cli.command("paper")
@click.option("--strategy", required=True)
@click.option("--symbols", required=True, help="逗号分隔的标的列表")
@click.option("--start", default=None)
@click.option("--end", default=None)
@click.option("--cash", default=1_000_000.0, type=float)
@click.option("--params", default="{}")
@click.option("--tick-interval", default=1.0, type=float, help="回放速度（秒/Bar）")
def paper_cmd(strategy, symbols, start, end, cash, params, tick_interval) -> None:
    from ashare_quant.execution.sim_gateway import SimGateway
    from ashare_quant.live.runner import StrategyRunner
    from ashare_quant.strategies.registry import create_strategy

    syms = [s.strip() for s in symbols.split(",")]
    strat = create_strategy(strategy, **json.loads(params))
    gw = SimGateway(initial_cash=cash, tick_interval=tick_interval)
    gw.connect(replay_start=start, replay_end=end)
    runner = StrategyRunner(strategy=strat, gateway=gw, universe=syms)
    runner.start()
    gw.subscribe(syms)
    gw.start_replay()
    logger.info("模拟盘运行中，Ctrl-C 退出")
    try:
        while gw._running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()
    logger.info(f"模拟盘结束，最终 NAV: {gw.portfolio.nav():.2f}")


@cli.command("qmt")
@click.option("--strategy", required=True)
@click.option("--universe", default="hs300")
@click.option("--params", default="{}")
def qmt_cmd(strategy, universe, params) -> None:
    """实盘运行（QMT 通道）。"""
    from ashare_quant.data.universe import build_universe
    from ashare_quant.execution.qmt_gateway import QMTGateway
    from ashare_quant.live.runner import StrategyRunner
    from ashare_quant.strategies.registry import create_strategy

    syms = build_universe(universe)
    strat = create_strategy(strategy, **json.loads(params))
    gw = QMTGateway()
    gw.connect()
    runner = StrategyRunner(strategy=strat, gateway=gw, universe=syms)
    runner.start()
    logger.info("QMT 实盘运行中，Ctrl-C 退出")
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()


@cli.command("dashboard")
def dashboard_cmd() -> None:
    """启动 Dash 监控大屏（demo 模式，自动回放数据）。"""
    from ashare_quant.ui.live_dashboard import main as run
    run()


@cli.command("alert-test")
@click.option("--msg", default="ashare-quant 告警通道连通性测试")
def alert_test(msg) -> None:
    from ashare_quant.live.alert import alert
    alert("INFO", "TEST", msg)


if __name__ == "__main__":
    cli()
