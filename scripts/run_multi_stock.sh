#!/usr/bin/env bash
# Full deep-dive pipeline across the 10-stock basket, then cross-stock summary.
set -u
cd /c/Atlas/atlas-research
PY=.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
TICKERS="AAPL NVDA MSFT GOOGL AMZN META TSLA JPM XOM WMT"
LOG=/c/Atlas/logs/multi_stock.log
: > "$LOG"
run(){ echo "  >> $*" | tee -a "$LOG"; "$@" >>"$LOG" 2>&1 || echo "    !! FAILED: $*" | tee -a "$LOG"; }

for T in $TICKERS; do
  echo "=========== $T ===========" | tee -a "$LOG"
  run $PY scripts/aapl_deep_dive.py     --ticker "$T" --parquet "data/intraday_5m/by_ticker/$T.parquet"
  run $PY scripts/aapl_deep_dive.py     --ticker "$T" --timeframe daily
  run $PY scripts/aapl_edge_analysis.py --ticker "$T" --timeframe daily
  run $PY scripts/aapl_edge_analysis.py --ticker "$T" --timeframe intraday
  run $PY scripts/aapl_setup_forensics.py --ticker "$T" --timeframe daily
  run $PY scripts/aapl_setup_forensics.py --ticker "$T" --timeframe intraday
  run $PY scripts/aapl_evidence.py      --ticker "$T"
  echo "=========== $T done ===========" | tee -a "$LOG"
done

echo "=========== CROSS-STOCK SUMMARY ===========" | tee -a "$LOG"
run $PY scripts/cross_stock_summary.py --tickers $TICKERS
echo "ALL DONE" | tee -a "$LOG"
