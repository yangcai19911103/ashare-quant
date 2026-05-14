"""数据相关 CLI。

示例：
    python -m ashare_quant.cli.data init --start 2018-01-01
    python -m ashare_quant.cli.data update
    python -m ashare_quant.cli.data calendar --refresh
    python -m ashare_quant.cli.data index hs300
"""
from __future__ import annotations

import click

from ashare_quant.data import pipeline
from ashare_quant.data.calendar import get_calendar
from ashare_quant.logging_setup import logger


@click.group()
def cli() -> None:
    """ashare-quant 数据工具。"""


@cli.command("init")
@click.option("--start", default=None, help="历史数据起点 YYYY-MM-DD")
@click.option("--end", default=None, help="历史数据终点 YYYY-MM-DD")
@click.option("--no-index", is_flag=True, help="跳过指数成分")
@click.option("--no-north", is_flag=True, help="跳过北向资金")
def init_cmd(start: str | None, end: str | None, no_index: bool, no_north: bool) -> None:
    """全量初始化数据仓库（首次执行约 30-60 分钟）。"""
    logger.info("===== 初始化数据仓库 =====")
    pipeline.init_all(start=start, end=end,
                      include_index=not no_index, include_north=not no_north)
    logger.info("===== 完成 =====")


@cli.command("update")
def update_cmd() -> None:
    """每日盘后增量更新（自动跳过非交易日）。"""
    pipeline.update_daily()


@cli.command("calendar")
@click.option("--refresh", is_flag=True, help="强制重新拉取交易日历")
def calendar_cmd(refresh: bool) -> None:
    """查看 / 刷新交易日历。"""
    cal = get_calendar(force_refresh=refresh)
    click.echo(f"交易日总数：{len(cal.days)}")
    click.echo(f"最早：{cal.days[0].date()}   最新：{cal.days[-1].date()}")


@cli.command("index")
@click.argument("code")
def index_cmd(code: str) -> None:
    """单独抓取某指数成分。"""
    pipeline.init_index_members(index_codes=[code])


@cli.command("daily")
@click.option("--symbols", default=None, help="逗号分隔的股票代码列表（缺省=全部）")
@click.option("--start", default=None)
@click.option("--end", default=None)
@click.option("--full", is_flag=True, help="全量覆盖（默认增量）")
def daily_cmd(symbols: str | None, start: str | None, end: str | None, full: bool) -> None:
    """增量/全量拉取日 K。"""
    sym_list = [s.strip() for s in symbols.split(",")] if symbols else None
    pipeline.ingest_daily(symbols=sym_list, start=start, end=end, incremental=not full)


if __name__ == "__main__":
    cli()
