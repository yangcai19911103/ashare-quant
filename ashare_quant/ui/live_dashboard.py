"""Dash 实盘监控大屏（轻量版）。

启动：``python -m ashare_quant.ui.live_dashboard``
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

try:
    from dash import Dash, dash_table, dcc, html
    from dash.dependencies import Input, Output
    import plotly.graph_objects as go
except ImportError:
    raise SystemExit("请安装：pip install dash plotly")


from ashare_quant.execution.sim_gateway import SimGateway
from ashare_quant.logging_setup import logger


def make_app(gateway: SimGateway) -> Dash:
    app = Dash(__name__, title="ashare-quant 实盘监控")

    app.layout = html.Div([
        html.H2("ashare-quant 实盘 / 模拟监控"),
        dcc.Interval(id="tick", interval=2000, n_intervals=0),
        html.Div([
            html.Div(id="account_summary", style={"flex": 1}),
            html.Div(id="halt_status", style={"flex": 1, "color": "red"}),
        ], style={"display": "flex", "marginBottom": "12px"}),
        html.H4("持仓"),
        dash_table.DataTable(id="positions",
                              style_table={"overflowX": "auto"}),
        html.H4("NAV 曲线"),
        dcc.Graph(id="nav_chart"),
        html.H4("最近成交"),
        dash_table.DataTable(id="fills",
                              page_size=20,
                              style_table={"overflowX": "auto"}),
    ])

    @app.callback(
        Output("account_summary", "children"),
        Output("halt_status", "children"),
        Output("positions", "data"),
        Output("positions", "columns"),
        Output("nav_chart", "figure"),
        Output("fills", "data"),
        Output("fills", "columns"),
        Input("tick", "n_intervals"),
    )
    def refresh(_):
        acc = gateway.query_account()
        pos = gateway.query_positions()
        pos_rows = [{"symbol": k, **v} for k, v in pos.items()]
        pos_cols = ([{"name": c, "id": c} for c in pos_rows[0].keys()]
                    if pos_rows else [])

        # NAV
        hist = gateway.portfolio.nav_history
        nav_df = pd.DataFrame(hist, columns=["time", "nav"]) if hist else pd.DataFrame()
        fig = go.Figure()
        if not nav_df.empty:
            fig.add_trace(go.Scatter(x=nav_df["time"], y=nav_df["nav"], mode="lines"))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))

        # Fills
        fills_data = [{
            "trade_date": f.trade_date.strftime("%Y-%m-%d"),
            "symbol": f.symbol,
            "side": f.side.value,
            "quantity": f.quantity,
            "price": round(f.price, 2),
        } for f in gateway.portfolio.fills_history[-50:]]
        fills_cols = ([{"name": c, "id": c} for c in fills_data[0].keys()]
                      if fills_data else [])

        summary = html.Pre(
            f"NAV: {acc['nav']:.2f}\n"
            f"Cash: {acc['cash']:.2f}\n"
            f"MV: {acc['market_value']:.2f}\n"
            f"Positions: {acc['n_positions']}\n"
            f"Fills: {acc['n_fills']}\n"
            f"Realized PnL: {acc['realized_pnl']:.2f}"
        )
        halt = ""
        return summary, halt, pos_rows, pos_cols, fig, fills_data, fills_cols

    return app


def main():
    """Demo 启动：自动连接 sim gateway + 一些示例订阅。"""
    gw = SimGateway(initial_cash=1_000_000)
    gw.connect(replay_start=(datetime.today() - pd.Timedelta(days=90)).strftime("%Y-%m-%d"),
                replay_end=datetime.today().strftime("%Y-%m-%d"))
    gw.subscribe(["600519.SH", "000858.SZ"])
    gw.start_replay()
    app = make_app(gw)
    logger.info("启动 Dash 实盘监控 http://127.0.0.1:8050")
    app.run(debug=False, host="127.0.0.1", port=8050)


if __name__ == "__main__":
    main()
