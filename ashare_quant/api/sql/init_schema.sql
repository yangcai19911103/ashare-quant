-- ashare-quant MySQL Schema
-- charset: utf8mb4, engine: InnoDB
-- ===========================================================

CREATE DATABASE IF NOT EXISTS ashare_quant DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ashare_quant;

-- ====================== 行情 / 元数据 ======================

CREATE TABLE IF NOT EXISTS instrument (
  symbol        VARCHAR(16)  NOT NULL PRIMARY KEY,
  name          VARCHAR(64)  NOT NULL,
  exchange      VARCHAR(8)   NOT NULL,
  industry      VARCHAR(32)  NULL,
  list_date     DATE         NULL,
  delist_date   DATE         NULL,
  is_st         TINYINT(1)   DEFAULT 0,
  status        VARCHAR(16)  DEFAULT 'L',
  total_share   DECIMAL(20,4) NULL,
  float_share   DECIMAL(20,4) NULL,
  INDEX idx_industry (industry),
  INDEX idx_exchange (exchange)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trade_calendar (
  trade_date  DATE NOT NULL PRIMARY KEY,
  exchange    VARCHAR(8) NOT NULL DEFAULT 'SSE',
  is_open     TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS daily_bar (
  symbol      VARCHAR(16)   NOT NULL,
  trade_date  DATE          NOT NULL,
  open        DECIMAL(12,4) NULL,
  high        DECIMAL(12,4) NULL,
  low         DECIMAL(12,4) NULL,
  close       DECIMAL(12,4) NULL,
  pre_close   DECIMAL(12,4) NULL,
  volume      BIGINT        NULL,
  amount      DECIMAL(20,4) NULL,
  turnover    DECIMAL(10,6) NULL,
  pct_chg     DECIMAL(10,6) NULL,
  adj_factor  DECIMAL(12,6) DEFAULT 1.0,
  PRIMARY KEY (symbol, trade_date),
  INDEX idx_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 PARTITION BY KEY(symbol) PARTITIONS 16;

CREATE TABLE IF NOT EXISTS index_member (
  index_code  VARCHAR(16) NOT NULL,
  symbol      VARCHAR(16) NOT NULL,
  in_date     DATE        NOT NULL,
  out_date    DATE        NULL,
  weight      DECIMAL(10,6) NULL,
  PRIMARY KEY (index_code, symbol, in_date),
  INDEX idx_sym (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fundamental (
  symbol         VARCHAR(16) NOT NULL,
  report_date    DATE        NOT NULL,
  ann_date       DATE        NULL,
  pe_ttm         DECIMAL(12,4) NULL,
  pb             DECIMAL(12,4) NULL,
  ps_ttm         DECIMAL(12,4) NULL,
  roe            DECIMAL(12,6) NULL,
  roa            DECIMAL(12,6) NULL,
  net_profit     DECIMAL(20,4) NULL,
  net_profit_yoy DECIMAL(12,6) NULL,
  revenue_yoy    DECIMAL(12,6) NULL,
  market_cap     DECIMAL(20,4) NULL,
  PRIMARY KEY (symbol, report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS north_flow (
  trade_date  DATE          NOT NULL,
  symbol      VARCHAR(16)   NOT NULL,
  net_amount  DECIMAL(20,4) NULL,
  hold_amount DECIMAL(20,4) NULL,
  hold_ratio  DECIMAL(10,6) NULL,
  PRIMARY KEY (trade_date, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ====================== 数据源 / 任务 ======================

CREATE TABLE IF NOT EXISTS data_source (
  name        VARCHAR(32)  NOT NULL PRIMARY KEY,
  status      VARCHAR(16)  NOT NULL DEFAULT 'unknown',
  quota_used  INT          DEFAULT 0,
  quota_limit INT          DEFAULT 0,
  note        VARCHAR(255) NULL,
  updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS data_job (
  id           BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  job_type     VARCHAR(32)  NOT NULL,
  params       JSON         NULL,
  status       VARCHAR(16)  NOT NULL DEFAULT 'pending',
  progress     INT          DEFAULT 0,
  log          MEDIUMTEXT   NULL,
  started_at   DATETIME     NULL,
  finished_at  DATETIME     NULL,
  created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ====================== 因子 ======================

CREATE TABLE IF NOT EXISTS factor_def (
  name        VARCHAR(64) NOT NULL PRIMARY KEY,
  category    VARCHAR(32) NOT NULL,
  direction   VARCHAR(8)  DEFAULT 'pos',
  formula     TEXT        NULL,
  params      JSON        NULL,
  description VARCHAR(255) NULL,
  created_at  DATETIME    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS factor_value (
  factor      VARCHAR(64) NOT NULL,
  symbol      VARCHAR(16) NOT NULL,
  trade_date  DATE        NOT NULL,
  value       DECIMAL(20,8) NULL,
  PRIMARY KEY (factor, trade_date, symbol),
  INDEX idx_factor_date (factor, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS factor_eval (
  factor      VARCHAR(64) NOT NULL,
  start_date  DATE        NOT NULL,
  end_date    DATE        NOT NULL,
  universe    VARCHAR(32) NOT NULL,
  ic_mean     DECIMAL(10,6) NULL,
  rank_ic_mean DECIMAL(10,6) NULL,
  ic_ir       DECIMAL(10,6) NULL,
  ic_win_rate DECIMAL(10,6) NULL,
  ls_annual   DECIMAL(10,6) NULL,
  ls_sharpe   DECIMAL(10,6) NULL,
  ls_maxdd    DECIMAL(10,6) NULL,
  series_json JSON          NULL,
  evaluated_at DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (factor, start_date, end_date, universe)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ====================== 策略 / 回测 ======================

CREATE TABLE IF NOT EXISTS strategy_def (
  name        VARCHAR(64)  NOT NULL PRIMARY KEY,
  cn_name     VARCHAR(64)  NULL,
  category    VARCHAR(32)  NOT NULL,
  description VARCHAR(512) NULL,
  freq        VARCHAR(16)  NULL,
  risk_level  VARCHAR(8)   NULL,
  default_params JSON      NULL,
  created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS backtest_run (
  id           VARCHAR(32)  NOT NULL PRIMARY KEY,
  strategy     VARCHAR(64)  NOT NULL,
  engine       VARCHAR(16)  NOT NULL DEFAULT 'event_driven',
  universe     VARCHAR(32)  NULL,
  start_date   DATE         NOT NULL,
  end_date     DATE         NOT NULL,
  init_capital DECIMAL(20,4) NOT NULL,
  benchmark    VARCHAR(16)  NULL,
  params       JSON         NULL,
  status       VARCHAR(16)  NOT NULL DEFAULT 'pending',
  progress     INT          DEFAULT 0,
  current_date_progress DATE NULL,
  log          MEDIUMTEXT   NULL,
  total_return DECIMAL(12,6) NULL,
  annual_return DECIMAL(12,6) NULL,
  sharpe       DECIMAL(10,6) NULL,
  max_drawdown DECIMAL(12,6) NULL,
  calmar       DECIMAL(10,6) NULL,
  win_rate     DECIMAL(10,6) NULL,
  turnover     DECIMAL(10,6) NULL,
  result_json  LONGTEXT     NULL,
  created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
  finished_at  DATETIME     NULL,
  INDEX idx_strategy (strategy),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS backtest_nav (
  run_id      VARCHAR(32) NOT NULL,
  trade_date  DATE        NOT NULL,
  nav         DECIMAL(20,8) NOT NULL,
  benchmark_nav DECIMAL(20,8) NULL,
  drawdown    DECIMAL(12,6) NULL,
  PRIMARY KEY (run_id, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS backtest_trade (
  id          BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  run_id      VARCHAR(32)  NOT NULL,
  trade_date  DATE         NOT NULL,
  symbol      VARCHAR(16)  NOT NULL,
  side        VARCHAR(4)   NOT NULL,
  qty         INT          NOT NULL,
  price       DECIMAL(12,4) NOT NULL,
  amount      DECIMAL(20,4) NOT NULL,
  fee         DECIMAL(12,4) DEFAULT 0,
  pnl         DECIMAL(20,4) NULL,
  INDEX idx_run (run_id),
  INDEX idx_sym (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ====================== 风控 ======================

CREATE TABLE IF NOT EXISTS risk_config (
  scope        VARCHAR(32)  NOT NULL PRIMARY KEY,
  config_json  JSON         NOT NULL,
  updated_at   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alert (
  id          BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  ts          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  level       VARCHAR(8)   NOT NULL,
  source      VARCHAR(32)  NOT NULL,
  title       VARCHAR(128) NOT NULL,
  message     VARCHAR(512) NULL,
  resolved    TINYINT(1)   DEFAULT 0,
  INDEX idx_ts (ts),
  INDEX idx_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alert_channel (
  name        VARCHAR(32) NOT NULL PRIMARY KEY,
  channel_type VARCHAR(16) NOT NULL,
  config_json JSON        NULL,
  min_level   VARCHAR(8)  DEFAULT 'INFO',
  enabled     TINYINT(1)  DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ====================== 模拟盘 / 实盘 ======================

CREATE TABLE IF NOT EXISTS account (
  id            VARCHAR(32) NOT NULL PRIMARY KEY,
  account_type  VARCHAR(16) NOT NULL,
  broker        VARCHAR(32) NULL,
  total_asset   DECIMAL(20,4) NOT NULL DEFAULT 0,
  cash          DECIMAL(20,4) NOT NULL DEFAULT 0,
  market_value  DECIMAL(20,4) NOT NULL DEFAULT 0,
  frozen        DECIMAL(20,4) NOT NULL DEFAULT 0,
  today_pnl     DECIMAL(20,4) NOT NULL DEFAULT 0,
  total_pnl     DECIMAL(20,4) NOT NULL DEFAULT 0,
  status        VARCHAR(16) NOT NULL DEFAULT 'idle',
  updated_at    DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS position (
  account_id  VARCHAR(32) NOT NULL,
  symbol      VARCHAR(16) NOT NULL,
  qty         INT         NOT NULL DEFAULT 0,
  available   INT         NOT NULL DEFAULT 0,
  cost_price  DECIMAL(12,4) NOT NULL,
  last_price  DECIMAL(12,4) NOT NULL,
  market_value DECIMAL(20,4) NOT NULL,
  pnl         DECIMAL(20,4) NOT NULL DEFAULT 0,
  pnl_pct     DECIMAL(12,6) NOT NULL DEFAULT 0,
  weight      DECIMAL(10,6) NOT NULL DEFAULT 0,
  updated_at  DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (account_id, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `order` (
  id          VARCHAR(40) NOT NULL PRIMARY KEY,
  account_id  VARCHAR(32) NOT NULL,
  strategy    VARCHAR(64) NULL,
  symbol      VARCHAR(16) NOT NULL,
  side        VARCHAR(4)  NOT NULL,
  order_type  VARCHAR(16) NOT NULL DEFAULT 'MKT',
  qty         INT         NOT NULL,
  filled_qty  INT         NOT NULL DEFAULT 0,
  price       DECIMAL(12,4) NULL,
  avg_price   DECIMAL(12,4) NULL,
  status      VARCHAR(16) NOT NULL DEFAULT 'pending',
  algo        VARCHAR(16) NULL,
  algo_params JSON        NULL,
  ts          DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  approved_by VARCHAR(32) NULL,
  INDEX idx_acct (account_id),
  INDEX idx_status (status),
  INDEX idx_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fill (
  id          BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
  order_id    VARCHAR(40)  NOT NULL,
  account_id  VARCHAR(32)  NOT NULL,
  symbol      VARCHAR(16)  NOT NULL,
  side        VARCHAR(4)   NOT NULL,
  qty         INT          NOT NULL,
  price       DECIMAL(12,4) NOT NULL,
  amount      DECIMAL(20,4) NOT NULL,
  fee         DECIMAL(12,4) NOT NULL DEFAULT 0,
  ts          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_order (order_id),
  INDEX idx_acct_ts (account_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS nav_snapshot (
  account_id  VARCHAR(32) NOT NULL,
  ts          DATETIME    NOT NULL,
  nav         DECIMAL(20,8) NOT NULL,
  benchmark   DECIMAL(20,8) NULL,
  PRIMARY KEY (account_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ====================== 报告 ======================

CREATE TABLE IF NOT EXISTS report (
  id          VARCHAR(32)  NOT NULL PRIMARY KEY,
  name        VARCHAR(128) NOT NULL,
  report_type VARCHAR(32)  NOT NULL,
  strategy    VARCHAR(64)  NULL,
  start_date  DATE         NULL,
  end_date    DATE         NULL,
  total_return DECIMAL(12,6) NULL,
  sharpe      DECIMAL(10,6) NULL,
  max_drawdown DECIMAL(12,6) NULL,
  payload_json LONGTEXT    NULL,
  created_at  DATETIME    DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_type (report_type),
  INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
