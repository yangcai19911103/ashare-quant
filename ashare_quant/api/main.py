"""FastAPI 主应用入口。

启动方式：
    uvicorn ashare_quant.api.main:app --reload --host 0.0.0.0 --port 8000
或：
    aq-api  (见 pyproject.toml entry point)

日志：必须先加载统一 logging_setup，使 loguru 写入 logs/aq_*.log；
Uvicorn access/error 在应用加载后挂到 logs/api_access.log、logs/api_server.log。
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import ashare_quant.logging_setup  # noqa: F401 — 初始化 loguru -> stderr + logs/aq_*.log

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from ashare_quant.logging_setup import attach_uvicorn_file_logging

from .config import API, MYSQL, WEB_DIR
from .database import init_db
from .routers import (backtest, data, factors, live, monitor, overview, paper,
                      portfolio, reports, risk, strategies)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """启动/关闭生命周期。"""
    attach_uvicorn_file_logging()
    logger.info(f"启动 ashare-quant API @ {MYSQL.mask()}")
    if API.auto_init_db:
        try:
            init_db(seed=API.auto_seed)
        except Exception as e:  # pragma: no cover - 仅在 MySQL 异常时触发
            logger.warning(f"自动 DB 初始化失败（可能 MySQL 未就绪）：{e}")
    yield
    logger.info("ashare-quant API 已关闭")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ashare-quant API",
        description="A 股量化交易系统后端 API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=API.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_routers(app)

    if WEB_DIR.exists():
        app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
        logger.info(f"静态站点挂载于 /web -> {WEB_DIR}")

    @app.get("/", include_in_schema=False)
    def index():
        target = WEB_DIR / "index.html"
        if target.exists():
            return FileResponse(str(target))
        return HTMLResponse(
            "<h3>ashare-quant API</h3>"
            "<p>Web UI 尚未部署，访问 <a href='/api/docs'>/api/docs</a> 查看 API。</p>"
        )

    @app.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok", "service": "ashare-quant-api"}

    return app


def _register_routers(app: FastAPI) -> None:
    """集中注册所有路由，便于增删与排序。"""
    routes = [
        (overview,   "/api/overview",   "overview"),
        (data,       "/api/data",       "data"),
        (factors,    "/api/factors",    "factors"),
        (strategies, "/api/strategies", "strategies"),
        (backtest,   "/api/backtest",   "backtest"),
        (risk,       "/api/risk",       "risk"),
        (portfolio,  "/api/portfolio",  "portfolio"),
        (paper,      "/api/paper",      "paper"),
        (live,       "/api/live",       "live"),
        (monitor,    "/api/monitor",    "monitor"),
        (reports,    "/api/reports",    "reports"),
    ]
    for mod, prefix, tag in routes:
        app.include_router(mod.router, prefix=prefix, tags=[tag])


app = create_app()
# Uvicorn 在 import app 后可能再配置 logging；此处先挂一次，lifespan 内再幂等补挂
attach_uvicorn_file_logging()


def main():
    import uvicorn
    host = os.environ.get("ASHARE_API_HOST", API.host)
    port = int(os.environ.get("ASHARE_API_PORT", API.port))
    reload = os.environ.get("ASHARE_API_RELOAD", "0") == "1"
    uvicorn.run("ashare_quant.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
