"""
Safety guard for the Alpaca options-data connector (scripts/options_*.py):
asserts none of these scripts import or call anything that places, replaces,
or cancels an order, or closes a position. This connector is
research/backtesting-only -- see docs/options_flow_data_limitations.md and
the docstring of every options_*.py script. This test exists so a future
edit that adds trading can't land silently; it must fail loudly here first.

Pure source-text scan, same pattern as test_features.py's
test_no_pandas_in_source -- no imports of the scripts themselves, no API
calls, no DB.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

OPTIONS_SCRIPTS = sorted(SCRIPTS_DIR.glob("options_*.py"))

# Alpaca order-placing/order-modifying classes and the trading-client
# methods that submit/replace/cancel orders or close positions. Any of
# these appearing in an options_*.py script's source is the connector
# stepping outside read-only reference/market-data calls.
FORBIDDEN_IDENTIFIERS = [
    "OrderRequest",            # base class and all *OrderRequest subclasses
    "MarketOrderRequest",
    "LimitOrderRequest",
    "StopOrderRequest",
    "StopLimitOrderRequest",
    "TrailingStopOrderRequest",
    "ReplaceOrderRequest",
    "ClosePositionRequest",
    ".submit_order(",
    ".replace_order(",
    ".cancel_order(",
    ".cancel_orders(",
    ".close_position(",
    ".close_all_positions(",
]


def test_found_at_least_the_known_options_scripts():
    names = {p.name for p in OPTIONS_SCRIPTS}
    expected = {
        "options_check_account.py",
        "options_list_contracts.py",
        "options_market_data_test.py",
        "options_build_backtest_seed.py",
        "options_snapshot_universe.py",
        "options_build_oi_structure_features.py",
    }
    assert expected.issubset(names), f"expected scripts missing from scripts/: {expected - names}"


def test_no_order_placing_identifiers_in_any_options_script():
    violations = {}
    for path in OPTIONS_SCRIPTS:
        src = path.read_text(encoding="utf-8")
        hits = [ident for ident in FORBIDDEN_IDENTIFIERS if ident in src]
        if hits:
            violations[path.name] = hits
    assert not violations, (
        f"order-placing identifiers found in connector scripts (must stay "
        f"research/backtesting-only, read-only): {violations}"
    )


def test_default_paper_true_documented_in_account_check():
    src = (SCRIPTS_DIR / "options_check_account.py").read_text(encoding="utf-8")
    assert 'os.environ.get("ALPACA_PAPER", "true")' in src, (
        "options_check_account.py must default ALPACA_PAPER to true (paper mode) "
        "when the env var is unset"
    )
