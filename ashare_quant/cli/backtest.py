"""回测 CLI。

示例：
  python -m ashare_quant.cli.backtest list
  python -m ashare_quant.cli.backtest run --strategy multi_factor.value_quality \\
         --universe hs300 --start 2020-01-01 --end 2024-12-31
"""
from __future__ import annotations

import json

import click

from ashare_quant.config import get
from ashare_quant.data.universe import build_universe
from ashare_quant.engine.event_driven.engine import BacktestEngine
from ashare_quant.logging_setup import logger
from ashare_quant.reporting import generate_report
from ashare_quant.strategies.registry import create_strategy, list_strategies


@click.group()
def cli() -> None:
    """ashare-quant 回测工具。"""


@cli.command("list")
def list_cmd() -> None:
    """列出所有可用策略。"""
    for name in list_strategies():
        click.echo(name)


@cli.command("run")
@click.option("--strategy", required=True, help="策略短名，如 multi_factor.value_quality")
@click.option("--universe", default=None, help="股票池：all/hs300/zz500/...")
@click.option("--start", default=None)
@click.option("--end", default=None)
@click.option("--cash", default=None, type=float, help="初始资金")
@click.option("--adjust", default="qfq", help="复权：none/qfq/hfq")
@click.option("--params", default="{}", help="策略参数 JSON")
@click.option("--save", is_flag=True, help="保存回测报告到 reports/")
def run_cmd(strategy: str, universe: str | None, start: str | None, end: str | None,
            cash: float | None, adjust: str, params: str, save: bool) -> None:
    user_params = json.loads(params)
    strat = create_strategy(strategy, **user_params)
    syms = build_universe(universe)
    engine = BacktestEngine(
        strategy=strat,
        universe=syms,
        start=start,
        end=end,
        initial_cash=cash,
        adjust=adjust,
    )
    result = engine.run()
    report = generate_report(result, name=strategy.replace(".", "_"))
    logger.info("\n" + result.report().to_string(index=False))
    alpha = report.alpha_vs_benchmark()
    if alpha:
        logger.info(f"vs Benchmark：{alpha}")
    if save:
        report.save()


if __name__ == "__main__":
    cli()
