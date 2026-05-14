# ashare-quant Web UI + API

完整覆盖系统所有功能的 Web 操作页面 + FastAPI 后端 + MySQL 持久化。

## 架构

```
浏览器 (Web UI · 静态 HTML)
   │  fetch / SSE
   ▼
FastAPI 后端 (ashare_quant.api)
   │  SQLAlchemy ORM
   ▼
MySQL  (utf8mb4 / InnoDB)
   │
   └── 行情 · 因子 · 策略 · 回测 · 模拟盘 · 实盘 · 风控 · 告警 · 报告
```

## 快速开始

### 1) 安装依赖

```bash
pip install -e .[ui]        # 至少需要 sqlalchemy / pymysql / fastapi / uvicorn
# 或者最小依赖：
pip install sqlalchemy pymysql cryptography fastapi "uvicorn[standard]" psutil
```

### 2) 准备 MySQL

```sql
CREATE DATABASE ashare_quant DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'aq'@'%' IDENTIFIED BY 'your_password';
GRANT ALL ON ashare_quant.* TO 'aq'@'%';
FLUSH PRIVILEGES;
```

完整 schema 见 `ashare_quant/api/sql/init_schema.sql`，
或交给 SQLAlchemy 自动建表（首次启动时自动执行）。

### 3) 配置连接

编辑 `config/settings.yaml`：

```yaml
mysql:
  host: 127.0.0.1
  port: 3306
  user: aq
  password: your_password
  database: ashare_quant
```

也可以用环境变量（覆盖一切）：

```bash
# Windows PowerShell
$env:ASHARE_MYSQL_URL = "mysql+pymysql://aq:your_password@127.0.0.1:3306/ashare_quant?charset=utf8mb4"

# bash
export ASHARE_MYSQL_URL='mysql+pymysql://aq:your_password@127.0.0.1:3306/ashare_quant?charset=utf8mb4'
```

### 4) 初始化数据库 + seed 演示数据（可选）

```bash
python -m ashare_quant.api.seed
# 或：
aq-init-db
```

### 5) 启动 API 服务

```bash
aq-api
# 等价于:
# uvicorn ashare_quant.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 6) 打开 Web UI

浏览器访问：

- **Web UI 首页**: <http://localhost:8000/>
- **API 文档 (Swagger)**: <http://localhost:8000/api/docs>
- **API 文档 (ReDoc)**: <http://localhost:8000/api/redoc>

> FastAPI 已经把 `web/` 目录挂载到 `/web` 路径下，前端通过相对路径访问 `/api/*`，无需额外 CORS 配置。

## 页面与 API 对应

| 页面 | 主要 API 端点 |
|---|---|
| `index.html`      | `GET /api/overview/` |
| `data.html`       | `GET /api/data/sources` `/warehouse` `/jobs` · `POST /api/data/init` `/universe` `/query` · `GET /api/data/calendar` |
| `factors.html`    | `GET /api/factors/` `/registry` · `POST /api/factors/compute` |
| `strategies.html` | `GET /api/strategies/` |
| `backtest.html`   | `POST /api/backtest/run` · `GET /api/backtest/status/{id}` `/result/{id}` |
| `risk.html`       | `GET/POST /api/risk/config` · `GET /api/risk/alerts` `/channels` `/drawdown` `/attribution` · `POST /api/risk/halt` |
| `portfolio.html`  | `POST /api/portfolio/optimize` |
| `paper.html`      | `POST /api/paper/start` `/stop` `/order` · `GET /api/paper/account` `/positions` `/orders` `/fills` `/nav` |
| `live.html`       | `POST /api/live/qmt/connect` `/order` · `GET /api/live/status` `/deployments` `/approvals` |
| `monitor.html`    | `GET /api/monitor/snapshot` `/system` · `GET /api/monitor/ticks/stream` (SSE) |
| `reports.html`    | `GET /api/reports/` `/{id}` `/compare?ids=...` |

## 关键设计

### 数据全部存 MySQL

| 模块 | 表名 |
|---|---|
| 行情     | `daily_bar` `instrument` `trade_calendar` `index_member` `fundamental` `north_flow` |
| 因子     | `factor_def` `factor_value` `factor_eval` |
| 策略/回测 | `strategy_def` `backtest_run` `backtest_nav` `backtest_trade` |
| 风控     | `risk_config` `alert` `alert_channel` |
| 账户/交易 | `account` `position` `order` `fill` `nav_snapshot` |
| 报告     | `report` |
| 任务     | `data_job` `data_source` |

`daily_bar` 表通过 `PARTITION BY KEY(symbol) PARTITIONS 16` 做哈希分区，
解决 A 股 5000 只 × 8 年 ≈ 1000 万行的查询性能问题。

### 容错：DB 空表自动 fallback

- 所有路由都做了"若表为空则返回演示数据"的兜底逻辑
- 第一次启动 / 还没采数据 / 还没运行回测，UI 也能完整展示
- 后续把 `ashare_quant.data.pipeline` 跑一遍写入真实数据后，UI 会自动切换为真实数据

### 后台任务

数据初始化、回测都是后台线程驱动，前端通过轮询接口拿进度：

```
POST /api/backtest/run             -> {run_id}
GET  /api/backtest/status/{run_id} -> {status, progress, log}
GET  /api/backtest/result/{run_id} -> {metrics, nav, trades, ...}
```

### 实时推送

监控大屏的 tick 流采用 **Server-Sent Events (SSE)**：
- 客户端：`new EventSource('/api/monitor/ticks/stream')`
- 服务端：`StreamingResponse` 持续 yield 数据

## 故障排查

| 现象 | 原因 / 解决 |
|---|---|
| `ModuleNotFoundError: pymysql` | `pip install pymysql cryptography` |
| `Access denied for user` | 检查 `config/settings.yaml` 中的用户名/密码，或 `ASHARE_MYSQL_URL` |
| `Unknown database 'ashare_quant'` | 手动执行 `CREATE DATABASE ashare_quant ...` |
| 启动时大量 `Table doesn't exist` | 首次启动会自动 `create_all`；若失败，手动执行 `python -m ashare_quant.api.seed` |
| Web UI 显示空白 | 看浏览器 Console 是否有 CORS 错误；正确做法是通过 `http://localhost:8000/` 访问，而不是直接打开 html 文件 |
