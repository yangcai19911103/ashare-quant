"""Unified ashare-quant CLI."""
from __future__ import annotations

import click

from ashare_quant.cli.backtest import cli as backtest_cli
from ashare_quant.cli.data import cli as data_cli
from ashare_quant.cli.live import cli as live_cli


@click.group()
def main() -> None:
    """ashare-quant 全功能命令行。"""


main.add_command(data_cli, "data")
main.add_command(backtest_cli, "backtest")
main.add_command(live_cli, "live")


if __name__ == "__main__":
    main()
