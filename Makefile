.PHONY: install dev test lint fmt clean data-init backtest-demo api db-init mysql-schema

install:
	pip install -e .

dev:
	pip install -e .[ml,opt,ui,dev]

test:
	pytest tests/ -v

test-fast:
	pytest tests/ -x -q

lint:
	ruff check ashare_quant tests

fmt:
	ruff format ashare_quant tests
	ruff check --fix ashare_quant tests

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +

data-init:
	aq-data init --start 2018-01-01

backtest-demo:
	aq-backtest run --strategy multi_factor.value_quality --universe hs300 \
		--start 2020-01-01 --end 2024-12-31 --save

ui:
	streamlit run ashare_quant/ui/research_app.py

dashboard:
	aq-live dashboard

# -------- Web UI + FastAPI 后端 --------
api:
	aq-api

db-init:
	python -m ashare_quant.api.seed

mysql-schema:
	@echo "执行 schema (需要 mysql 客户端):"
	@echo "  mysql -uroot -p < ashare_quant/api/sql/init_schema.sql"
	@echo "或直接启动 API 服务，自动 create_all。"
