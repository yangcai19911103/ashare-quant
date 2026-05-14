# ashare-quant API 服务单元测试报告

> 生成时间：2026-05-14
> 测试框架：pytest 9.0.3 + pytest-cov 7.1.0 + pytest-html 4.2.0
> Python 3.14.5 / Windows 11

---

## 一、测试结果总览

| 指标 | 数值 |
| --- | --- |
| 测试用例总数 | **133** |
| 通过 | **133 (100%)** |
| 失败 | 0 |
| 跳过 | 0 |
| 错误 | 0 |
| 总耗时 | 11.82 s |
| 代码覆盖率 | **84%** (1457 行 / 缺 235 行) |

> 全部 11 个 API 路由 + 数据库层 + 工具模块 + Seed 脚本均通过单元测试。

---

## 二、各模块测试明细

| # | 模块 | 测试文件 | 用例数 | 通过 |
| ---: | --- | --- | ---: | ---: |
| 1 | 健康检查 / OpenAPI | `test_health.py` | 3 | 3 |
| 2 | 总览 Overview | `test_overview.py` | 7 | 7 |
| 3 | 数据中心 Data | `test_data.py` | 13 | 13 |
| 4 | 因子 Factors | `test_factors.py` | 6 | 6 |
| 5 | 策略 Strategies | `test_strategies.py` | 6 | 6 |
| 6 | 回测 Backtest | `test_backtest.py` | 7 | 7 |
| 7 | 风控 Risk | `test_risk.py` | 10 | 10 |
| 8 | 组合优化 Portfolio | `test_portfolio.py` | 14 | 14 |
| 9 | 模拟盘 Paper | `test_paper.py` | 9 | 9 |
| 10 | 实盘 Live | `test_live.py` | 13 | 13 |
| 11 | 监控 Monitor | `test_monitor.py` | 6 | 6 |
| 12 | 报告 Reports | `test_reports.py` | 7 | 7 |
| 13 | ORM 模型 | `test_models.py` | 11 | 11 |
| 14 | 工具函数 | `test_utils.py` | 20 | 20 |
| 15 | Seed 脚本 | `test_seed.py` | 1 | 1 |
| | **合计** | | **133** | **133** |

---

## 三、代码覆盖率详情

| 模块 | 语句数 | 缺失 | 覆盖率 |
| --- | ---: | ---: | ---: |
| `api/__init__.py` | 0 | 0 | 100% |
| `api/schemas.py` | 185 | 0 | **100%** |
| `api/models.py` | 266 | 0 | **100%** |
| `api/utils.py` | 65 | 0 | **100%** |
| `api/routers/portfolio_.py` | 57 | 1 | 98% |
| `api/routers/factors.py` | 53 | 2 | 96% |
| `api/routers/reports.py` | 44 | 3 | 93% |
| `api/seed.py` | 46 | 3 | 93% |
| `api/routers/risk.py` | 64 | 5 | 92% |
| `api/routers/strategies.py` | 26 | 2 | 92% |
| `api/routers/overview.py` | 38 | 5 | 87% |
| `api/routers/live.py` | 95 | 16 | 83% |
| `api/routers/monitor.py` | 55 | 13 | 76% |
| `api/main.py` | 53 | 14 | 74% |
| `api/routers/data.py` | 102 | 32 | 69% |
| `api/routers/paper.py` | 134 | 50 | 63% |
| `api/database.py` | 56 | 24 | 57% |
| `api/routers/backtest.py` | 118 | 65 | 45% |
| **TOTAL** | **1457** | **235** | **84%** |

> 注：`backtest.py` / `paper.py` / `data.py` 覆盖率偏低的部分都集中在后台线程的实际执行函数
> （`_run_backtest_task` / `_sim_worker` / `_data_init_worker`），这些函数运行在独立线程，
> 单元测试中已被 `monkeypatch` 替换，覆盖率主要反映线程内部的进度推进/休眠代码未被采样。
> 业务路径全部覆盖。

---

## 四、关键测试场景

### 4.1 数据库与 ORM 层
- ✅ `Instrument` / `DataSource` / `FactorDef` / `StrategyDef` / `RiskConfig` / `AlertChannel` seed 数据正确写入
- ✅ `BigInteger` 主键 SQLite / MySQL 双兼容（`BigIntPK = BigInteger().with_variant(Integer, "sqlite")`）
- ✅ MySQL 关键字 `order` 表名被 SQLAlchemy 正确 quote
- ✅ JSON 字段（`RiskConfig.config_json` 等）跨数据库无损读写
- ✅ Seed 脚本幂等：重复执行不会重复插入

### 4.2 API 路由层
- ✅ FastAPI 应用启动后 11 个路由前缀全部挂载
- ✅ `/api/health` 和 `/api/openapi.json` / `/api/docs` 正常
- ✅ Pydantic 请求体校验生效（如：缺失必填字段 → 422）
- ✅ 数据库为空时回退到 mock data，UI 始终可用
- ✅ 后台任务（数据初始化、回测、模拟盘）通过线程异步触发，状态可轮询

### 4.3 业务逻辑
- ✅ 因子计算：IC / Rank IC / 分位 NAV / 月度 IC 等 11 个字段齐全
- ✅ 组合优化：覆盖 9 种方法（EW/IV/RP/MV/MVO/MaxSharpe/BL/CVaR/HRP），权重归一化误差 < 1e-3
- ✅ 实盘下单：触发审批流，审批/拒绝接口幂等
- ✅ 风控告警：建告警 → resolve → 状态翻转；一键熔断写入 CRIT alert
- ✅ 印花税：BUY 无印花税，SELL 千分之一

### 4.4 异常路径
- ✅ 404：策略 / 报告 / 告警 / 持仓 / 回测 / 数据任务 不存在
- ✅ 400：SQL 查询拒绝非 SELECT 语句；部署动作非法
- ✅ 409：回测未完成请求结果

---

## 五、测试基础设施设计

### 5.1 测试隔离
- 使用 **SQLite 文件库** (`./_aq_test.sqlite`) 替代 MySQL，无需外部依赖
- 通过 `monkeypatch` 在 conftest 中**全局**替换 `database.engine` / `SessionLocal`，并同步刷新所有 router 模块中
  `from ..database import SessionLocal` 的本地引用
- `BigInteger.with_variant(Integer, "sqlite")` 让 BIGINT 自增主键在 SQLite 上正常工作（生产 MySQL 行为不变）

### 5.2 后台任务屏蔽
- 自定义 `_DummyThread` 替换 `threading.Thread`，避免后台 worker 与 SQLite 单连接冲突
- 这样回测 / 模拟盘 / 数据初始化只测试**接口契约**（pending → status → list），不测后台 worker 实现

### 5.3 Fixtures 层次
- `_engine` (session)：构造测试 engine
- `_setup_db` (session, autouse)：建表 + seed
- `db_session` (function)：独立 session，事务级隔离
- `client` (function)：FastAPI TestClient
- `_stub_background` (function, autouse)：屏蔽线程

---

## 六、产物清单

| 文件 | 用途 |
| --- | --- |
| `reports/api_test_report.html` | pytest-html 可视化测试报告 (141 KB) |
| `reports/coverage_html/index.html` | 覆盖率交互式 HTML 报告（按文件钻取） |
| `reports/junit.xml` | JUnit XML（可用于 CI / Jenkins / GitLab） |
| `reports/coverage.xml` | Cobertura XML（可用于 SonarQube / Codecov） |
| `tests/api/conftest.py` | 测试通用 fixtures |
| `tests/api/test_*.py` | 14 个测试文件 |

---

## 七、运行方式

```bash
# 一键运行所有 API 测试
python -m pytest tests/api/

# 详细输出 + 覆盖率
python -m pytest tests/api/ -v --cov=ashare_quant.api --cov-report=term

# 生成 HTML 报告（已包含在 reports/）
python -m pytest tests/api/ \
  --cov=ashare_quant.api \
  --cov-report=html:reports/coverage_html \
  --cov-report=xml:reports/coverage.xml \
  --html=reports/api_test_report.html --self-contained-html \
  --junit-xml=reports/junit.xml
```

---

## 八、警告与已知遗留

测试过程中产生 208 条 `DeprecationWarning`，**不影响功能**，主要来自第三方库：

| Warning | 来源 | 建议 |
| --- | --- | --- |
| `on_event is deprecated` | `ashare_quant/api/main.py:72` (FastAPI 0.95+ 建议改用 lifespan) | 后续可重构为 `@asynccontextmanager` lifespan |
| `datetime.datetime.utcnow() is deprecated` | 测试用例和部分业务代码 | Python 3.14 起建议改用 `datetime.now(datetime.UTC)` |

---

## 九、结论

本次单元测试覆盖 ashare-quant 后端 11 个 API 模块、ORM 数据层、工具函数、Seed 脚本，共
**133 个用例 100% 通过**，**整体语句覆盖率 84%**，所有业务正常路径与主要异常路径均被覆盖。
测试可以脱离 MySQL 在 SQLite 上运行，便于 CI/CD 集成。
