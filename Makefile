.PHONY: help install dev lint format type test run clean

help:
	@echo "可用命令："
	@echo "  install   安装运行时依赖"
	@echo "  dev       安装开发依赖"
	@echo "  lint      运行 ruff 检查"
	@echo "  format    自动格式化代码"
	@echo "  type      运行 mypy 类型检查"
	@echo "  test      运行测试"
	@echo "  run       运行 CLI 示例：make run TOPIC='二叉树的中序遍历'"
	@echo "  clean     清理产物与缓存"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	pre-commit install || true

lint:
	ruff check src tests

format:
	ruff format src tests
	ruff check --fix src tests

type:
	mypy src

test:
	pytest

run:
	manimtool generate --topic "$(TOPIC)"

clean:
	rm -rf output .cache .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
