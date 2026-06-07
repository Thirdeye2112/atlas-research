[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "atlas-research"
version = "0.1.0"
description = "Institutional-grade research database for Atlas Alpha ML workflows"
requires-python = ">=3.11"

dependencies = [
    "yfinance>=0.2.40",
    "pandas>=2.2",
    "numpy>=1.26",
    "psycopg[binary]>=3.1",
    "sqlalchemy>=2.0",
    "python-dotenv>=1.0",
    "apscheduler>=3.10",
    "tenacity>=8.2",
    "structlog>=24.1",
    "rich>=13.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "mypy>=1.9",
]

[tool.setuptools.packages.find]
where = ["src"]
include = ["atlas_research*"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
pythonpath = ["src", "."]
