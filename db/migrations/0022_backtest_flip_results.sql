-- 0022_backtest_flip_results.sql
-- Stores aggregate backtest results for flip strategy comparison

CREATE TABLE IF NOT EXISTS backtest_flip_results (
  id            SERIAL PRIMARY KEY,
  run_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  strategy      TEXT    NOT NULL,           -- 'hold_jarvis' | 'flip_any' | 'flip_confirmed'
  universe_size INTEGER NOT NULL,
  date_from     DATE    NOT NULL,
  date_to       DATE    NOT NULL,
  total_trades  INTEGER NOT NULL,
  win_rate      NUMERIC(6,4),               -- 0.0 – 1.0
  avg_return_pct NUMERIC(8,4),              -- per-trade avg %
  total_return_pct NUMERIC(10,4),           -- sum across all trades
  max_drawdown_pct NUMERIC(8,4),            -- worst intra-trade drawdown
  sharpe_ratio  NUMERIC(8,4),
  vs_buy_hold_pct NUMERIC(10,4),            -- excess return vs passive B&H
  notes         TEXT,
  metadata      JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_backtest_flip_results_strategy
  ON backtest_flip_results (strategy, run_at DESC);
