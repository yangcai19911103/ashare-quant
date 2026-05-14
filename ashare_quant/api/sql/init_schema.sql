-- ashare-quant MySQL Schema
-- charset: utf8mb4, engine: InnoDB
-- 字段 COMMENT 与 ashare_quant/api/models.py 中 mapped_column(comment=...) 对齐
-- ===========================================================

CREATE DATABASE IF NOT EXISTS ashare_quant DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ashare_quant;

-- ====================== 行情 / 元数据 ======================

CREATE TABLE IF NOT EXISTS instrument (
  symbol        VARCHAR(16)  NOT NULL PRIMARY KEY COMMENT '证券代码，如 600519.SH',
  name          VARCHAR(64)  NOT NULL COMMENT '证券简称',
  exchange      VARCHAR(8)   NOT NULL COMMENT '交易所代码，如 SH、SZ',
  industry      VARCHAR(32)  NULL COMMENT '行业分类',
  list_date     DATE         NULL COMMENT '上市日期',
  delist_date   DATE         NULL COMMENT '退市日期，未退市为空',
  is_st         TINYINT(1)   DEFAULT 0 COMMENT '是否 ST，0 否 1 是',
  status        VARCHAR(16)  DEFAULT 'L' COMMENT '上市状态，如 L 上市',
  total_share   DECIMAL(20,4) NULL COMMENT '总股本',
  float_share   DECIMAL(20,4) NULL COMMENT '流通股本',
  INDEX idx_industry (industry),
  INDEX idx_exchange (exchange)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='证券基础信息';

CREATE TABLE IF NOT EXISTS trade_calendar (
  trade_date  DATE NOT NULL PRIMARY KEY COMMENT '自然日',
  exchange    VARCHAR(8) NOT NULL DEFAULT 'SSE' COMMENT '交易所，默认 SSE',
  is_open     TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否交易日，1 交易 0 休市'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易日历';

CREATE TABLE IF NOT EXISTS daily_bar (
  symbol      VARCHAR(16)   NOT NULL COMMENT '证券代码',
  trade_date  DATE          NOT NULL COMMENT '交易日',
  open        DECIMAL(12,4) NULL COMMENT '开盘价',
  high        DECIMAL(12,4) NULL COMMENT '最高价',
  low         DECIMAL(12,4) NULL COMMENT '最低价',
  close       DECIMAL(12,4) NULL COMMENT '收盘价',
  pre_close   DECIMAL(12,4) NULL COMMENT '昨收价',
  volume      BIGINT        NULL COMMENT '成交量',
  amount      DECIMAL(20,4) NULL COMMENT '成交额',
  turnover    DECIMAL(10,6) NULL COMMENT '换手率',
  pct_chg     DECIMAL(10,6) NULL COMMENT '涨跌幅',
  adj_factor  DECIMAL(12,6) DEFAULT 1.0 COMMENT '复权因子',
  PRIMARY KEY (symbol, trade_date),
  INDEX idx_dbar_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 PARTITION BY KEY(symbol) PARTITIONS 16 COMMENT='日K线行情';

CREATE TABLE IF NOT EXISTS index_member (
  index_code  VARCHAR(16) NOT NULL COMMENT '指数代码，如 000300.SH',
  symbol      VARCHAR(16) NOT NULL COMMENT '成分证券代码',
  in_date     DATE        NOT NULL COMMENT '纳入指数日期',
  out_date    DATE        NULL COMMENT '调出指数日期，仍在池内为空',
  weight      DECIMAL(10,6) NULL COMMENT '指数权重',
  PRIMARY KEY (index_code, symbol, in_date),
  INDEX idx_sym (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指数成分';

CREATE TABLE IF NOT EXISTS fundamental (
  symbol         VARCHAR(16) NOT NULL COMMENT '证券代码',
  report_date    DATE        NOT NULL COMMENT '报告期',
  ann_date       DATE        NULL COMMENT '公告日',
  pe_ttm         DECIMAL(12,4) NULL COMMENT '市盈率 TTM',
  pb             DECIMAL(12,4) NULL COMMENT '市净率',
  ps_ttm         DECIMAL(12,4) NULL COMMENT '市销率 TTM',
  roe            DECIMAL(12,6) NULL COMMENT '净资产收益率',
  roa            DECIMAL(12,6) NULL COMMENT '总资产收益率',
  net_profit     DECIMAL(20,4) NULL COMMENT '净利润',
  net_profit_yoy DECIMAL(12,6) NULL COMMENT '净利润同比增速',
  revenue_yoy    DECIMAL(12,6) NULL COMMENT '营收同比增速',
  market_cap     DECIMAL(20,4) NULL COMMENT '市值',
  PRIMARY KEY (symbol, report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务与估值';

CREATE TABLE IF NOT EXISTS north_flow (
  trade_date  DATE          NOT NULL COMMENT '交易日',
  symbol      VARCHAR(16)   NOT NULL COMMENT '证券代码',
  net_amount  DECIMAL(20,4) NULL COMMENT '净流入金额',
  hold_amount DECIMAL(20,4) NULL COMMENT '持股金额或持仓量',
  hold_ratio  DECIMAL(10,6) NULL COMMENT '持股占比等',
  PRIMARY KEY (trade_date, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='北向资金';

-- ====================== 数据源 / 任务 ======================

CREATE TABLE IF NOT EXISTS data_source (
  name        VARCHAR(32)  NOT NULL PRIMARY KEY COMMENT '数据源标识，如 akshare',
  status      VARCHAR(16)  NOT NULL DEFAULT 'unknown' COMMENT '连接或健康状态',
  quota_used  INT          DEFAULT 0 COMMENT '已用配额',
  quota_limit INT          DEFAULT 0 COMMENT '配额上限',
  note        VARCHAR(255) NULL COMMENT '备注',
  updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据源配置';

CREATE TABLE IF NOT EXISTS data_job (
  id           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '任务主键',
  job_type     VARCHAR(32)  NOT NULL COMMENT '任务类型，如 data_init',
  params       JSON         NULL COMMENT '任务参数 JSON',
  status       VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT '状态 pending/running/success/failed',
  progress     INT          DEFAULT 0 COMMENT '进度 0-100',
  log          MEDIUMTEXT   NULL COMMENT '文本日志',
  started_at   DATETIME     NULL COMMENT '开始时间',
  finished_at  DATETIME     NULL COMMENT '结束时间',
  created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据任务';

-- ====================== 因子 ======================

CREATE TABLE IF NOT EXISTS factor_def (
  name        VARCHAR(64) NOT NULL PRIMARY KEY COMMENT '因子名称',
  category    VARCHAR(32) NOT NULL COMMENT '因子类别',
  direction   VARCHAR(8)  DEFAULT 'pos' COMMENT '因子方向 pos/neg',
  formula     TEXT        NULL COMMENT '公式或计算说明',
  params      JSON        NULL COMMENT '因子参数 JSON',
  description VARCHAR(255) NULL COMMENT '描述',
  created_at  DATETIME    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子定义';

CREATE TABLE IF NOT EXISTS factor_value (
  factor      VARCHAR(64) NOT NULL COMMENT '因子名称',
  symbol      VARCHAR(16) NOT NULL COMMENT '证券代码',
  trade_date  DATE        NOT NULL COMMENT '交易日',
  value       DECIMAL(20,8) NULL COMMENT '因子值',
  PRIMARY KEY (factor, trade_date, symbol),
  INDEX idx_fval_factor_date (factor, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子值';

CREATE TABLE IF NOT EXISTS factor_eval (
  factor      VARCHAR(64) NOT NULL COMMENT '因子名称',
  start_date  DATE        NOT NULL COMMENT '评价区间起始',
  end_date    DATE        NOT NULL COMMENT '评价区间结束',
  universe    VARCHAR(32) NOT NULL COMMENT '股票池或指数代码',
  ic_mean     DECIMAL(10,6) NULL COMMENT 'IC 均值',
  rank_ic_mean DECIMAL(10,6) NULL COMMENT 'Rank IC 均值',
  ic_ir       DECIMAL(10,6) NULL COMMENT 'IC 信息比',
  ic_win_rate DECIMAL(10,6) NULL COMMENT 'IC 胜率',
  ls_annual   DECIMAL(10,6) NULL COMMENT '多空组合年化收益',
  ls_sharpe   DECIMAL(10,6) NULL COMMENT '多空夏普',
  ls_maxdd    DECIMAL(10,6) NULL COMMENT '多空最大回撤',
  series_json JSON          NULL COMMENT '评价序列等扩展 JSON',
  evaluated_at DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '评价时间',
  PRIMARY KEY (factor, start_date, end_date, universe)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子评价';

-- ====================== 策略 / 回测 ======================

CREATE TABLE IF NOT EXISTS strategy_def (
  name        VARCHAR(64)  NOT NULL PRIMARY KEY COMMENT '策略唯一标识',
  cn_name     VARCHAR(64)  NULL COMMENT '中文名称',
  category    VARCHAR(32)  NOT NULL COMMENT '策略类别',
  description VARCHAR(512) NULL COMMENT '说明',
  freq        VARCHAR(16)  NULL COMMENT '调仓频率',
  risk_level  VARCHAR(8)   NULL COMMENT '风险等级',
  default_params JSON      NULL COMMENT '默认参数 JSON',
  created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略定义';

CREATE TABLE IF NOT EXISTS backtest_run (
  id           VARCHAR(32)  NOT NULL PRIMARY KEY COMMENT '回测任务 ID',
  strategy     VARCHAR(64)  NOT NULL COMMENT '策略名称',
  engine       VARCHAR(16)  NOT NULL DEFAULT 'event_driven' COMMENT '回测引擎类型',
  universe     VARCHAR(32)  NULL COMMENT '股票池或指数',
  start_date   DATE         NOT NULL COMMENT '回测起始日',
  end_date     DATE         NOT NULL COMMENT '回测结束日',
  init_capital DECIMAL(20,4) NOT NULL COMMENT '初始资金',
  benchmark    VARCHAR(16)  NULL COMMENT '基准代码',
  params       JSON         NULL COMMENT '运行参数 JSON',
  status       VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT '运行状态',
  progress     INT          DEFAULT 0 COMMENT '进度百分比',
  current_date_progress DATE NULL COMMENT '当前仿真到的交易日',
  log          MEDIUMTEXT   NULL COMMENT '运行日志',
  total_return DECIMAL(12,6) NULL COMMENT '总收益率',
  annual_return DECIMAL(12,6) NULL COMMENT '年化收益率',
  sharpe       DECIMAL(10,6) NULL COMMENT '夏普比率',
  max_drawdown DECIMAL(12,6) NULL COMMENT '最大回撤',
  calmar       DECIMAL(10,6) NULL COMMENT '卡玛比率',
  win_rate     DECIMAL(10,6) NULL COMMENT '胜率',
  turnover     DECIMAL(10,6) NULL COMMENT '换手率',
  result_json  LONGTEXT     NULL COMMENT '完整结果 JSON 文本',
  created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  finished_at  DATETIME     NULL COMMENT '完成时间',
  INDEX idx_bt_run_strategy (strategy),
  INDEX idx_bt_run_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测运行';

CREATE TABLE IF NOT EXISTS backtest_nav (
  run_id      VARCHAR(32) NOT NULL COMMENT '回测任务 ID',
  trade_date  DATE        NOT NULL COMMENT '交易日',
  nav         DECIMAL(20,8) NOT NULL COMMENT '组合净值',
  benchmark_nav DECIMAL(20,8) NULL COMMENT '基准净值',
  drawdown    DECIMAL(12,6) NULL COMMENT '回撤',
  PRIMARY KEY (run_id, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测净值';

CREATE TABLE IF NOT EXISTS backtest_trade (
  id          BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '成交记录主键',
  run_id      VARCHAR(32)  NOT NULL COMMENT '回测任务 ID',
  trade_date  DATE         NOT NULL COMMENT '成交日',
  symbol      VARCHAR(16)  NOT NULL COMMENT '标的代码',
  side        VARCHAR(4)   NOT NULL COMMENT '买卖方向 BUY/SELL',
  qty         INT          NOT NULL COMMENT '成交数量',
  price       DECIMAL(12,4) NOT NULL COMMENT '成交价格',
  amount      DECIMAL(20,4) NOT NULL COMMENT '成交金额',
  fee         DECIMAL(12,4) DEFAULT 0 COMMENT '手续费',
  pnl         DECIMAL(20,4) NULL COMMENT '盈亏',
  INDEX idx_bt_trd_run (run_id),
  INDEX idx_bt_trd_sym (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测成交';

-- ====================== 风控 ======================

CREATE TABLE IF NOT EXISTS risk_config (
  scope        VARCHAR(32)  NOT NULL PRIMARY KEY COMMENT '作用域标识',
  config_json  JSON         NOT NULL COMMENT '风控规则 JSON',
  updated_at   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控配置';

CREATE TABLE IF NOT EXISTS alert (
  id          BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '告警主键',
  ts          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '告警时间',
  level       VARCHAR(8)   NOT NULL COMMENT '级别 INFO/WARN/CRIT',
  source      VARCHAR(32)  NOT NULL COMMENT '来源模块',
  title       VARCHAR(128) NOT NULL COMMENT '标题',
  message     VARCHAR(512) NULL COMMENT '正文',
  resolved    TINYINT(1)   DEFAULT 0 COMMENT '是否已处理 0/1',
  INDEX idx_alert_ts (ts),
  INDEX idx_alert_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警记录';

CREATE TABLE IF NOT EXISTS alert_channel (
  name        VARCHAR(32) NOT NULL PRIMARY KEY COMMENT '渠道名称',
  channel_type VARCHAR(16) NOT NULL COMMENT '渠道类型 webhook 等',
  config_json JSON        NULL COMMENT '渠道配置 JSON',
  min_level   VARCHAR(8)  DEFAULT 'INFO' COMMENT '最低推送级别',
  enabled     TINYINT(1)  DEFAULT 1 COMMENT '是否启用 0/1'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警渠道';

-- ====================== 模拟盘 / 实盘 ======================

CREATE TABLE IF NOT EXISTS account (
  id            VARCHAR(32) NOT NULL PRIMARY KEY COMMENT '账户 ID',
  account_type  VARCHAR(16) NOT NULL COMMENT '账户类型 模拟或实盘',
  broker        VARCHAR(32) NULL COMMENT '券商或通道',
  total_asset   DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '总资产',
  cash          DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '可用现金',
  market_value  DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '持仓市值',
  frozen        DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '冻结资金',
  today_pnl     DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '当日盈亏',
  total_pnl     DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '累计盈亏',
  status        VARCHAR(16) NOT NULL DEFAULT 'idle' COMMENT '账户状态',
  updated_at    DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资金账户';

CREATE TABLE IF NOT EXISTS position (
  account_id  VARCHAR(32) NOT NULL COMMENT '账户 ID',
  symbol      VARCHAR(16) NOT NULL COMMENT '证券代码',
  qty         INT         NOT NULL DEFAULT 0 COMMENT '持仓数量',
  available   INT         NOT NULL DEFAULT 0 COMMENT '可卖数量',
  cost_price  DECIMAL(12,4) NOT NULL COMMENT '成本价',
  last_price  DECIMAL(12,4) NOT NULL COMMENT '最新价',
  market_value DECIMAL(20,4) NOT NULL COMMENT '持仓市值',
  pnl         DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '浮动盈亏',
  pnl_pct     DECIMAL(12,6) NOT NULL DEFAULT 0 COMMENT '浮动盈亏比例',
  weight      DECIMAL(10,6) NOT NULL DEFAULT 0 COMMENT '占组合权重',
  updated_at  DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (account_id, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='持仓';

CREATE TABLE IF NOT EXISTS `order` (
  id          VARCHAR(40) NOT NULL PRIMARY KEY COMMENT '订单 ID',
  account_id  VARCHAR(32) NOT NULL COMMENT '账户 ID',
  strategy    VARCHAR(64) NULL COMMENT '来源策略',
  symbol      VARCHAR(16) NOT NULL COMMENT '标的代码',
  side        VARCHAR(4)  NOT NULL COMMENT '买卖方向',
  order_type  VARCHAR(16) NOT NULL DEFAULT 'MKT' COMMENT '订单类型',
  qty         INT         NOT NULL COMMENT '委托数量',
  filled_qty  INT         NOT NULL DEFAULT 0 COMMENT '已成交数量',
  price       DECIMAL(12,4) NULL COMMENT '委托价格',
  avg_price   DECIMAL(12,4) NULL COMMENT '成交均价',
  status      VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT '订单状态',
  algo        VARCHAR(16) NULL COMMENT '算法单类型',
  algo_params JSON        NULL COMMENT '算法参数',
  ts          DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '下单时间',
  approved_by VARCHAR(32) NULL COMMENT '审批人',
  INDEX idx_ord_acct (account_id),
  INDEX idx_ord_status (status),
  INDEX idx_ord_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='委托单';

CREATE TABLE IF NOT EXISTS fill (
  id          BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '成交主键',
  order_id    VARCHAR(40)  NOT NULL COMMENT '关联委托 ID',
  account_id  VARCHAR(32)  NOT NULL COMMENT '账户 ID',
  symbol      VARCHAR(16)  NOT NULL COMMENT '标的代码',
  side        VARCHAR(4)   NOT NULL COMMENT '买卖方向',
  qty         INT          NOT NULL COMMENT '成交数量',
  price       DECIMAL(12,4) NOT NULL COMMENT '成交价格',
  amount      DECIMAL(20,4) NOT NULL COMMENT '成交金额',
  fee         DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '手续费',
  ts          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '成交时间',
  INDEX idx_fill_order (order_id),
  INDEX idx_fill_acct_ts (account_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成交回报';

CREATE TABLE IF NOT EXISTS nav_snapshot (
  account_id  VARCHAR(32) NOT NULL COMMENT '账户 ID',
  ts          DATETIME    NOT NULL COMMENT '快照时间',
  nav         DECIMAL(20,8) NOT NULL COMMENT '组合净值',
  benchmark   DECIMAL(20,8) NULL COMMENT '基准净值',
  PRIMARY KEY (account_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='净值快照';

-- ====================== 报告 ======================

CREATE TABLE IF NOT EXISTS report (
  id          VARCHAR(32)  NOT NULL PRIMARY KEY COMMENT '报告 ID',
  name        VARCHAR(128) NOT NULL COMMENT '报告标题',
  report_type VARCHAR(32)  NOT NULL COMMENT '报告类型',
  strategy    VARCHAR(64)  NULL COMMENT '关联策略',
  start_date  DATE         NULL COMMENT '区间起始',
  end_date    DATE         NULL COMMENT '区间结束',
  total_return DECIMAL(12,6) NULL COMMENT '总收益率',
  sharpe      DECIMAL(10,6) NULL COMMENT '夏普比率',
  max_drawdown DECIMAL(12,6) NULL COMMENT '最大回撤',
  payload_json LONGTEXT    NULL COMMENT '完整内容 JSON',
  created_at  DATETIME    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  INDEX idx_rpt_type (report_type),
  INDEX idx_rpt_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报告归档';
