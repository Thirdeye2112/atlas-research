# Atlas Candlestick Knowledge Layer v1
# Backtest Script - Pattern Detection & Outcome Analysis

import argparse, os, sys, logging
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PATTERN_DETECTORS = {
    'Doji': 'detect_doji', 'Long-legged doji': 'detect_long_legged_doji',
    'Hammer': 'detect_hammer', 'Inverted hammer': 'detect_inverted_hammer',
    'Shooting star': 'detect_shooting_star', 'Hanging man': 'detect_hanging_man',
    'Marubozu': 'detect_marubozu', 'Spinning top': 'detect_spinning_top',
    'Bullish engulfing': 'detect_bullish_engulfing', 'Bearish engulfing': 'detect_bearish_engulfing',
    'Inside bar': 'detect_inside_bar', 'Outside bar': 'detect_outside_bar',
    'Harami': 'detect_harami', 'Tweezer top': 'detect_tweezer_top',
    'Tweezer bottom': 'detect_tweezer_bottom', 'Morning star': 'detect_morning_star',
    'Evening star': 'detect_evening_star', 'Three white soldiers': 'detect_three_white_soldiers',
    'Three black crows': 'detect_three_black_crows'
}

DIRECTION_MAP = {
    'Doji': 'neutral', 'Long-legged doji': 'neutral', 'Hammer': 'bullish',
    'Inverted hammer': 'bullish', 'Shooting star': 'bearish', 'Hanging man': 'bearish',
    'Marubozu': 'neutral', 'Spinning top': 'neutral', 'Bullish engulfing': 'bullish',
    'Bearish engulfing': 'bearish', 'Inside bar': 'neutral', 'Outside bar': 'neutral',
    'Harami': 'neutral', 'Tweezer top': 'bearish', 'Tweezer bottom': 'bullish',
    'Morning star': 'bullish', 'Evening star': 'bearish',
    'Three white soldiers': 'bullish', 'Three black crows': 'bearish'
}

CATEGORY_MAP = {
    'Doji': 'single', 'Long-legged doji': 'single', 'Hammer': 'single',
    'Inverted hammer': 'single', 'Shooting star': 'single', 'Hanging man': 'single',
    'Marubozu': 'single', 'Spinning top': 'single', 'Bullish engulfing': 'double',
    'Bearish engulfing': 'double', 'Inside bar': 'double', 'Outside bar': 'double',
    'Harami': 'double', 'Tweezer top': 'double', 'Tweezer bottom': 'double',
    'Morning star': 'triple', 'Evening star': 'triple',
    'Three white soldiers': 'triple', 'Three black crows': 'triple'
}

def get_db_connection(db_url):
    return psycopg2.connect(db_url)

def calculate_candle_properties(df):
    df = df.copy()
    df['body'] = np.abs(df['close'] - df['open'])
    df['range'] = df['high'] - df['low']
    df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
    df['body_pct'] = df['body'] / df['range'].replace(0, np.nan)
    df['upper_shadow_pct'] = df['upper_shadow'] / df['range'].replace(0, np.nan)
    df['lower_shadow_pct'] = df['lower_shadow'] / df['range'].replace(0, np.nan)
    df['body_position'] = (df[['open', 'close']].min(axis=1) - df['low']) / df['range'].replace(0, np.nan)
    df['is_bullish'] = df['close'] > df['open']
    df['is_bearish'] = df['close'] < df['open']
    return df

def calculate_rolling_stats(df, window=20):
    df = df.copy()
    df['avg_range_20'] = df['range'].rolling(window=window).mean()
    df['avg_body_20'] = df['body'].rolling(window=window).mean()
    df['avg_volume_20'] = df['volume'].rolling(window=window).mean()
    df['prior_trend'] = 'neutral'
    df.loc[df['close'].rolling(3).apply(lambda x: all(x.diff().dropna() > 0), raw=False), 'prior_trend'] = 'up'
    df.loc[df['close'].rolling(3).apply(lambda x: all(x.diff().dropna() < 0), raw=False), 'prior_trend'] = 'down'
    return df

# Pattern detectors
def detect_doji(df, idx):
    row = df.iloc[idx]
    return row['body_pct'] < 0.05 and row['upper_shadow'] >= 2 * row['body'] and row['lower_shadow'] >= 2 * row['body']

def detect_long_legged_doji(df, idx):
    row = df.iloc[idx]
    return row['body_pct'] < 0.05 and row['upper_shadow'] >= 3 * row['body'] and row['lower_shadow'] >= 3 * row['body'] and row['range'] >= 1.5 * row['avg_range_20']

def detect_hammer(df, idx):
    if idx < 2: return False
    row = df.iloc[idx]
    return row['lower_shadow'] >= 2 * row['body'] and row['body_position'] <= 0.25 and row['prior_trend'] == 'down' and row['upper_shadow'] <= 0.25 * row['body']

def detect_inverted_hammer(df, idx):
    if idx < 2: return False
    row = df.iloc[idx]
    return row['upper_shadow'] >= 2 * row['body'] and row['body_position'] >= 0.75 and row['prior_trend'] == 'down' and row['lower_shadow'] <= 0.25 * row['body']

def detect_shooting_star(df, idx):
    if idx < 2: return False
    row = df.iloc[idx]
    return row['upper_shadow'] >= 2 * row['body'] and row['body_position'] >= 0.75 and row['prior_trend'] == 'up' and row['lower_shadow'] <= 0.25 * row['body']

def detect_hanging_man(df, idx):
    if idx < 2: return False
    row = df.iloc[idx]
    return row['lower_shadow'] >= 2 * row['body'] and row['body_position'] <= 0.25 and row['prior_trend'] == 'up' and row['upper_shadow'] <= 0.25 * row['body']

def detect_marubozu(df, idx):
    row = df.iloc[idx]
    return row['upper_shadow_pct'] < 0.05 and row['lower_shadow_pct'] < 0.05

def detect_spinning_top(df, idx):
    row = df.iloc[idx]
    return row['body_pct'] < 0.25 and row['upper_shadow'] >= row['body'] and row['lower_shadow'] >= row['body'] and np.abs(row['upper_shadow'] - row['lower_shadow']) <= 0.3 * max(row['upper_shadow'], row['lower_shadow'])

def detect_bullish_engulfing(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    if c1['prior_trend'] != 'down' or not c2['is_bullish']: return False
    if c2['open'] >= c1['close'] or c2['close'] <= c1['open']: return False
    return (c2['close'] - c2['open']) > (c1['open'] - c1['close'])

def detect_bearish_engulfing(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    if c1['prior_trend'] != 'up' or not c2['is_bearish']: return False
    if c2['open'] <= c1['close'] or c2['close'] >= c1['open']: return False
    return (c2['open'] - c2['close']) > (c1['close'] - c1['open'])

def detect_inside_bar(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    return c2['high'] < c1['high'] and c2['low'] > c1['low']

def detect_outside_bar(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    return c2['high'] > c1['high'] and c2['low'] < c1['low']

def detect_harami(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    body1, body2 = c1['body'], c2['body']
    if body2 >= body1: return False
    if c1['is_bullish']:
        return c2['open'] > c1['open'] and c2['close'] < c1['close'] and c2['open'] < c1['close'] and c2['close'] > c1['open']
    else:
        return c2['open'] < c1['open'] and c2['close'] > c1['close'] and c2['open'] > c1['close'] and c2['close'] < c1['open']

def detect_tweezer_top(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    if c1['prior_trend'] != 'up' or not c2['is_bearish']: return False
    high_diff = np.abs(c1['high'] - c2['high'])
    return high_diff <= 0.01 * ((c1['high'] + c2['high']) / 2)

def detect_tweezer_bottom(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    if c1['prior_trend'] != 'down' or not c2['is_bullish']: return False
    low_diff = np.abs(c1['low'] - c2['low'])
    return low_diff <= 0.01 * ((c1['low'] + c2['low']) / 2)

def detect_morning_star(df, idx):
    if idx < 2: return False
    c1, c2, c3 = df.iloc[idx-2], df.iloc[idx-1], df.iloc[idx]
    if c1['prior_trend'] != 'down' or not c1['is_bearish']: return False
    avg_body = df.iloc[max(0, idx-20):idx]['body'].mean()
    if c2['body'] >= 0.5 * avg_body or c2['low'] >= c1['low']: return False
    if not c3['is_bullish']: return False
    midpoint = (c1['open'] + c1['close']) / 2
    return c3['close'] > midpoint

def detect_evening_star(df, idx):
    if idx < 2: return False
    c1, c2, c3 = df.iloc[idx-2], df.iloc[idx-1], df.iloc[idx]
    if c1['prior_trend'] != 'up' or not c1['is_bullish']: return False
    avg_body = df.iloc[max(0, idx-20):idx]['body'].mean()
    if c2['body'] >= 0.5 * avg_body or c2['high'] <= c1['high']: return False
    if not c3['is_bearish']: return False
    midpoint = (c1['open'] + c1['close']) / 2
    return c3['close'] < midpoint

def detect_three_white_soldiers(df, idx):
    if idx < 2: return False
    c1, c2, c3 = df.iloc[idx-2], df.iloc[idx-1], df.iloc[idx]
    if not (c1['is_bullish'] and c2['is_bullish'] and c3['is_bullish']): return False
    if not (c2['close'] > c1['close'] and c3['close'] > c2['close']): return False
    if not (c2['open'] > c1['open'] and c2['open'] < c1['close']): return False
    if not (c3['open'] > c2['open'] and c3['open'] < c2['close']): return False
    avg_body = df.iloc[max(0, idx-20):idx]['body'].mean()
    return c1['body'] > 0.5 * avg_body and c2['body'] > 0.5 * avg_body and c3['body'] > 0.5 * avg_body

def detect_three_black_crows(df, idx):
    if idx < 2: return False
    c1, c2, c3 = df.iloc[idx-2], df.iloc[idx-1], df.iloc[idx]
    if not (c1['is_bearish'] and c2['is_bearish'] and c3['is_bearish']): return False
    if not (c2['close'] < c1['close'] and c3['close'] < c2['close']): return False
    if not (c2['open'] < c1['open'] and c2['open'] > c1['close']): return False
    if not (c3['open'] < c2['open'] and c3['open'] > c2['close']): return False
    avg_body = df.iloc[max(0, idx-20):idx]['body'].mean()
    return c1['body'] > 0.5 * avg_body and c2['body'] > 0.5 * avg_body and c3['body'] > 0.5 * avg_body

def detect_patterns(df):
    df = calculate_candle_properties(df)
    df = calculate_rolling_stats(df)
    results = {name: [] for name in PATTERN_DETECTORS.keys()}
    for idx in range(len(df)):
        for name, func_name in PATTERN_DETECTORS.items():
            try:
                detector = globals()[func_name]
                if detector(df, idx):
                    results[name].append(idx)
            except Exception as e:
                logger.warning(f"Error detecting {name} at index {idx}: {e}")
    return results

def load_ohlc_data(data_dir, ticker, start_date, end_date):
    parquet_path = Path(data_dir) / f"{ticker}.parquet"
    if not parquet_path.exists(): return pd.DataFrame()
    try:
        df = pd.read_parquet(parquet_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
        df = df[mask].sort_values('timestamp').reset_index(drop=True)
        df['ticker'] = ticker
        return df
    except Exception as e:
        logger.error(f"Error loading {ticker}: {e}")
        return pd.DataFrame()

def process_ticker(ticker, data_dir, start_date, end_date, conn):
    df = load_ohlc_data(data_dir, ticker, start_date, end_date)
    if df.empty: return 0, 0
    patterns = detect_patterns(df)
    events, outcomes = [], []
    for name, indices in patterns.items():
        for idx in indices:
            row = df.iloc[idx]
            events.append({
                'ticker': ticker, 'timestamp': row['timestamp'], 'timeframe': 'daily',
                'candle_name': name, 'direction': DIRECTION_MAP[name], 'strength': 'standard',
                'context': {}, 'o': row['open'], 'h': row['high'], 'l': row['low'],
                'c': row['close'], 'v': row['volume']
            })
            returns = {}
            for lookahead in [1, 3, 6, 12, 24]:
                future_idx = idx + lookahead
                if future_idx < len(df):
                    returns[f'return_{lookahead}'] = (df.iloc[future_idx]['close'] - row['close']) / row['close']
                else: returns[f'return_{lookahead}'] = None
            if idx + 1 < len(df):
                next_row = df.iloc[idx+1]
                returns['return_eod'] = (next_row['close'] - row['close']) / row['close']
                returns['mfe'] = (next_row['high'] - row['close']) / row['close']
                returns['mae'] = (next_row['low'] - row['close']) / row['close']
            else: returns.update({'return_eod': None, 'mfe': None, 'mae': None})
            outcomes.append({
                'ticker': ticker, 'timestamp': row['timestamp'], 'candle_name': name,
                **returns, 'hit_target': None, 'hit_stop': None,
                'regime': 'neutral', 'vix_proxy': None, 'vwap_position': 'at',
                'prior_trend': 'neutral', 'volume_context': 'normal', 'daily_context': 'normal'
            })
    if events:
        data = [(e['ticker'], e['timestamp'], e['timeframe'], e['candle_name'], e['direction'], e['strength'], e['context'], e['o'], e['h'], e['l'], e['c'], e['v']) for e in events]
        with conn.cursor() as cursor:
            execute_batch(cursor, "INSERT INTO candlestick_events (ticker, timestamp, timeframe, candle_name, direction, strength, context, o, h, l, c, v) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", data)
        conn.commit()
    if outcomes:
        data = [(o['ticker'], o['timestamp'], o['candle_name'], o.get('event_id'), o.get('return_1'), o.get('return_3'), o.get('return_6'), o.get('return_12'), o.get('return_24'), o.get('return_eod'), o.get('mfe'), o.get('mae'), o.get('hit_target'), o.get('hit_stop'), o.get('regime'), o.get('vix_proxy'), o.get('vwap_position'), o.get('prior_trend'), o.get('volume_context'), o.get('daily_context')) for o in outcomes]
        with conn.cursor() as cursor:
            execute_batch(cursor, "INSERT INTO candlestick_outcomes (ticker, timestamp, candle_name, event_id, return_1, return_3, return_6, return_12, return_24, return_eod, mfe, mae, hit_target, hit_stop, regime, vix_proxy, vwap_position, prior_trend, volume_context, daily_context) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", data)
        conn.commit()
    return len(events), len(outcomes)

def main():
    parser = argparse.ArgumentParser(description='Atlas Candlestick Backtest')
    parser.add_argument('--universe', required=True, help='Path to universe CSV')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--data_dir', default='data/parquet')
    parser.add_argument('--db_url', default=os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost:5432/atlas_research'))
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()

    universe = pd.read_csv(args.universe)
    if 'ticker' not in universe.columns:
        universe = universe.rename(columns={universe.columns[0]: 'ticker'})
    tickers = universe['ticker'].tolist()[:args.limit] if args.limit else universe['ticker'].tolist()

    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d')

    total_events = total_outcomes = 0
    with get_db_connection(args.db_url) as conn:
        for i, ticker in enumerate(tickers):
            logger.info(f"[{i+1}/{len(tickers)}] {ticker}")
            try:
                e, o = process_ticker(ticker, args.data_dir, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), conn)
                total_events += e; total_outcomes += o
            except Exception as ex:
                logger.error(f"Error: {ticker} - {ex}")
    logger.info(f"SUMMARY: {len(tickers)} tickers, {total_events} events, {total_outcomes} outcomes")

if __name__ == '__main__':
    main()