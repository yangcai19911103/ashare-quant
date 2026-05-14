"""Streamlit 研究看板：因子探索 / 回测对比 / 报告查看。

启动：``streamlit run ashare_quant/ui/research_app.py``
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

try:
    import streamlit as st
    import plotly.graph_objects as go
except ImportError:
    raise SystemExit("请先安装：pip install streamlit plotly")

from ashare_quant.config import project_root
from ashare_quant.data.storage import get_storage
from ashare_quant.engine.event_driven.engine import BacktestEngine
from ashare_quant.factors import get_registry
from ashare_quant.factors.evaluation import compute_ic, layered_backtest, long_short_performance
from ashare_quant.reporting import generate_report
from ashare_quant.strategies.registry import create_strategy, list_strategies


st.set_page_config(page_title="ashare-quant 研究看板", layout="wide")
st.title("ashare-quant 研究看板")

tab1, tab2, tab3 = st.tabs(["因子探索", "策略回测", "历史报告"])


# ===================== Tab 1: 因子探索 =====================
with tab1:
    st.subheader("因子选择 & 评估")
    reg = get_registry()
    names = reg.names()
    factor_name = st.selectbox("因子", names)
    n_days = st.slider("回看天数", min_value=120, max_value=1500, value=500, step=60)

    storage = get_storage()
    syms = storage.list_symbols()[:50]
    st.caption(f"加载前 50 只股票（共 {len(storage.list_symbols())} 只）")

    if st.button("计算因子 & IC"):
        panel = storage.read_daily_panel(syms, fields=["close", "open", "high",
                                                        "low", "volume", "amount"],
                                           adjust="qfq")
        if not panel["close"].empty:
            close = panel["close"].tail(n_days)
            panel = {k: v.tail(n_days) for k, v in panel.items()}
            f = reg.get(factor_name)
            val = f.compute(panel)
            fwd = close.pct_change(5).shift(-5)
            rep = compute_ic(val, fwd, lag=1)
            st.metric("Mean IC", f"{rep.mean_ic:.4f}")
            st.metric("IC IR", f"{rep.ic_ir:.3f}")
            st.metric("正 IC 占比", f"{rep.pos_ratio:.2%}")
            st.line_chart(rep.ic_series.rename("IC"))

            layered = layered_backtest(val, fwd, n_groups=5)
            if not layered.empty:
                cum = (1 + layered).cumprod()
                st.line_chart(cum)
                perf = long_short_performance(layered)
                st.json(perf)
        else:
            st.warning("数据为空，请先运行 `aq-data init`")


# ===================== Tab 2: 策略回测 =====================
with tab2:
    st.subheader("一键回测")
    strat_name = st.selectbox("策略", list_strategies())
    universe = st.selectbox("股票池", ["hs300", "zz500", "all"], index=0)
    col1, col2 = st.columns(2)
    start = col1.date_input("开始日期", pd.Timestamp("2022-01-01"))
    end = col2.date_input("结束日期", pd.Timestamp.today())
    cash = st.number_input("初始资金", value=1_000_000.0, step=100_000.0)
    params_str = st.text_area("策略参数(JSON)", value="{}")

    if st.button("运行回测"):
        from ashare_quant.data.universe import build_universe
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError as exc:
            st.error(f"参数 JSON 解析失败：{exc}")
            params = None
        if params is not None:
            strat = create_strategy(strat_name, **params)
            syms = build_universe(universe)
            with st.spinner("回测中…"):
                engine = BacktestEngine(strategy=strat, universe=syms,
                                         start=start, end=end, initial_cash=cash)
                result = engine.run()
                report = generate_report(result, name=strat_name.replace(".", "_"))

            st.success("回测完成")
            st.dataframe(pd.DataFrame(list(report.metrics.items()),
                                       columns=["metric", "value"]))
            if not report.nav.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=report.nav.index, y=report.nav.values,
                                          name="Strategy NAV"))
                if report.benchmark_nav is not None and not report.benchmark_nav.empty:
                    fig.add_trace(go.Scatter(x=report.benchmark_nav.index,
                                              y=report.benchmark_nav.values,
                                              name="Benchmark"))
                st.plotly_chart(fig, use_container_width=True)
            alpha = report.alpha_vs_benchmark()
            if alpha:
                st.json(alpha)


# ===================== Tab 3: 历史报告 =====================
with tab3:
    st.subheader("历史回测报告")
    reports_dir = project_root() / "reports"
    if not reports_dir.exists():
        st.info("尚无历史报告")
    else:
        names = [p.name for p in reports_dir.iterdir() if p.is_dir()]
        if not names:
            st.info("尚无历史报告")
        else:
            sel = st.selectbox("选择报告", names)
            base = reports_dir / sel
            metrics = pd.read_csv(base / "metrics.csv") if (base / "metrics.csv").exists() else None
            nav = pd.read_parquet(base / "nav.parquet") if (base / "nav.parquet").exists() else None
            if metrics is not None:
                st.dataframe(metrics)
            if nav is not None:
                st.line_chart(nav)
