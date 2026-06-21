# Atlas Candlestick Knowledge Layer v1
# Backtest Script - Pattern Detection & Outcome Analysis
# Updated: Support for loading OHLCV from raw_bars PostgreSQL table

import argparse, os, sys, logging, json, re
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from psycopg2.extensions import register_adapter, AsIs
from dotenv import load_dotenv

# psycopg2 cannot adapt numpy scalar types (numpy.int64/float64/bool_) that
# leak in from pandas/raw_bars columns, so OHLCV values raise
# "can't adapt type 'numpy.int64'" on insert.  Register adapters that unwrap
# them to native Python scalars (NaN -> SQL NULL).
def _adapt_numpy_int(v):
    return AsIs(int(v))

def _adapt_numpy_float(v):
    return AsIs('NULL') if np.isnan(v) else AsIs(repr(float(v)))

def _adapt_numpy_bool(v):
    return AsIs('TRUE' if bool(v) else 'FALSE')

for _t in (np.int8, np.int16, np.int32, np.int64,
           np.uint8, np.uint16, np.uint32, np.uint64):
    register_adapter(_t, _adapt_numpy_int)
for _t in (np.float16, np.float32, np.float64):
    register_adapter(_t, _adapt_numpy_float)
register_adapter(np.bool_, _adapt_numpy_bool)

# Load environment variables from .env
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('candlestick_backtest.log'), logging.StreamHandler()]
)
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
    """Get database connection with error handling."""
    try:
        conn = psycopg2.connect(db_url)
        logger.info(f"Connected to database: {db_url.split('@')[0]}@...")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)


def calculate_candle_properties(df):
    """Calculate candle body, range, shadows, and positions."""
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
    """Calculate rolling statistics for trend detection."""
    df = df.copy()
    df['avg_range_20'] = df['range'].rolling(window=window).mean()
    df['avg_body_20'] = df['body'].rolling(window=window).mean()
    vol_col = 'volume' if 'volume' in df.columns else ('v' if 'v' in df.columns else None)
    if vol_col:
        df['avg_volume_20'] = df[vol_col].rolling(window=window).mean()
    df['prior_trend'] = 'neutral'
    if len(df) >= 3:
        closes = df['close'].values
        diffs = np.diff(closes)
        up_trend = np.array([False] * len(closes))
        down_trend = np.array([False] * len(closes))
        for i in range(2, len(closes)):
            if diffs[i-2] > 0 and diffs[i-1] > 0:
                up_trend[i] = True
            if diffs[i-2] < 0 and diffs[i-1] < 0:
                down_trend[i] = True
        df.loc[up_trend, 'prior_trend'] = 'up'
        df.loc[down_trend, 'prior_trend'] = 'down'
    return df


# =============================================================================
# Pattern Detectors (19 patterns)
# =============================================================================

def detect_doji(df, idx):
    row = df.iloc[idx]
    return row.get('body_pct', 0) < 0.05 and row.get('upper_shadow', 0) >= 2 * row.get('body', 0) and row.get('lower_shadow', 0) >= 2 * row.get('body', 0)


def detect_long_legged_doji(df, idx):
    row = df.iloc[idx]
    return (row.get('body_pct', 0) < 0.05 and 
            row.get('upper_shadow', 0) >= 3 * row.get('body', 0) and 
            row.get('lower_shadow', 0) >= 3 * row.get('body', 0) and
            row.get('range', 0) >= 1.5 * row.get('avg_range_20', row.get('range', 0)))


def detect_hammer(df, idx):
    if idx < 2: return False
    row = df.iloc[idx]
    return (row.get('lower_shadow', 0) >= 2 * row.get('body', 0) and 
            row.get('body_position', 0) <= 0.25 and 
            row.get('prior_trend', '') == 'down' and 
            row.get('upper_shadow', 0) <= 0.25 * row.get('body', 0))


def detect_inverted_hammer(df, idx):
    if idx < 2: return False
    row = df.iloc[idx]
    return (row.get('upper_shadow', 0) >= 2 * row.get('body', 0) and 
            row.get('body_position', 0) >= 0.75 and 
            row.get('prior_trend', '') == 'down' and 
            row.get('lower_shadow', 0) <= 0.25 * row.get('body', 0))


def detect_shooting_star(df, idx):
    if idx < 2: return False
    row = df.iloc[idx]
    return (row.get('upper_shadow', 0) >= 2 * row.get('body', 0) and 
            row.get('body_position', 0) >= 0.75 and 
            row.get('prior_trend', '') == 'up' and 
            row.get('lower_shadow', 0) <= 0.25 * row.get('body', 0))


def detect_hanging_man(df, idx):
    if idx < 2: return False
    row = df.iloc[idx]
    return (row.get('lower_shadow', 0) >= 2 * row.get('body', 0) and 
            row.get('body_position', 0) <= 0.25 and 
            row.get('prior_trend', '') == 'up' and 
            row.get('upper_shadow', 0) <= 0.25 * row.get('body', 0))


def detect_marubozu(df, idx):
    row = df.iloc[idx]
    return row.get('upper_shadow_pct', 0) < 0.05 and row.get('lower_shadow_pct', 0) < 0.05


def detect_spinning_top(df, idx):
    row = df.iloc[idx]
    upper = row.get('upper_shadow', 0)
    lower = row.get('lower_shadow', 0)
    body = row.get('body', 0)
    return (row.get('body_pct', 0) < 0.25 and 
            upper >= body and 
            lower >= body and 
            np.abs(upper - lower) <= 0.3 * max(upper, lower))


def detect_bullish_engulfing(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    if c1.get('prior_trend', '') != 'down' or not c2.get('is_bullish', False): return False
    if c2['open'] >= c1['close'] or c2['close'] <= c1['open']: return False
    return (c2['close'] - c2['open']) > (c1['open'] - c1['close'])


def detect_bearish_engulfing(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    if c1.get('prior_trend', '') != 'up' or not c2.get('is_bearish', False): return False
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
    body1 = c1.get('body', 0)
    body2 = c2.get('body', 0)
    if body2 >= body1: return False
    if c1.get('is_bullish', False):
        return c2['open'] > c1['open'] and c2['close'] < c1['close'] and c2['open'] < c1['close'] and c2['close'] > c1['open']
    else:
        return c2['open'] < c1['open'] and c2['close'] > c1['close'] and c2['open'] > c1['close'] and c2['close'] < c1['open']


def detect_tweezer_top(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    if c1.get('prior_trend', '') != 'up' or not c2.get('is_bearish', False): return False
    high_diff = np.abs(c1['high'] - c2['high'])
    avg_high = (c1['high'] + c2['high']) / 2
    return high_diff <= 0.01 * avg_high


def detect_tweezer_bottom(df, idx):
    if idx < 1: return False
    c1, c2 = df.iloc[idx-1], df.iloc[idx]
    if c1.get('prior_trend', '') != 'down' or not c2.get('is_bullish', False): return False
    low_diff = np.abs(c1['low'] - c2['low'])
    avg_low = (c1['low'] + c2['low']) / 2
    return low_diff <= 0.01 * avg_low


def detect_morning_star(df, idx):
    if idx < 2: return False
    c1, c2, c3 = df.iloc[idx-2], df.iloc[idx-1], df.iloc[idx]
    if c1.get('prior_trend', '') != 'down' or not c1.get('is_bearish', False): return False
    avg_body = df.iloc[max(0, idx-20):idx]['body'].mean()
    if pd.isna(avg_body) or c2.get('body', 0) >= 0.5 * avg_body or c2['low'] >= c1['low']: return False
    if not c3.get('is_bullish', False): return False
    midpoint = (c1['open'] + c1['close']) / 2
    return c3['close'] > midpoint


def detect_evening_star(df, idx):
    if idx < 2: return False
    c1, c2, c3 = df.iloc[idx-2], df.iloc[idx-1], df.iloc[idx]
    if c1.get('prior_trend', '') != 'up' or not c1.get('is_bullish', False): return False
    avg_body = df.iloc[max(0, idx-20):idx]['body'].mean()
    if pd.isna(avg_body) or c2.get('body', 0) >= 0.5 * avg_body or c2['high'] <= c1['high']: return False
    if not c3.get('is_bearish', False): return False
    midpoint = (c1['open'] + c1['close']) / 2
    return c3['close'] < midpoint


def detect_three_white_soldiers(df, idx):
    if idx < 2: return False
    c1, c2, c3 = df.iloc[idx-2], df.iloc[idx-1], df.iloc[idx]
    if not (c1.get('is_bullish', False) and c2.get('is_bullish', False) and c3.get('is_bullish', False)): return False
    if not (c2['close'] > c1['close'] and c3['close'] > c2['close']): return False
    if not (c2['open'] > c1['open'] and c2['open'] < c1['close']): return False
    if not (c3['open'] > c2['open'] and c3['open'] < c2['close']): return False
    avg_body = df.iloc[max(0, idx-20):idx]['body'].mean()
    if pd.isna(avg_body): return False
    return c1.get('body', 0) > 0.5 * avg_body and c2.get('body', 0) > 0.5 * avg_body and c3.get('body', 0) > 0.5 * avg_body


def detect_three_black_crows(df, idx):
    if idx < 2: return False
    c1, c2, c3 = df.iloc[idx-2], df.iloc[idx-1], df.iloc[idx]
    if not (c1.get('is_bearish', False) and c2.get('is_bearish', False) and c3.get('is_bearish', False)): return False
    if not (c2['close'] < c1['close'] and c3['close'] < c2['close']): return False
    if not (c2['open'] < c1['open'] and c2['open'] > c1['close']): return False
    if not (c3['open'] < c2['open'] and c3['open'] > c2['close']): return False
    avg_body = df.iloc[max(0, idx-20):idx]['body'].mean()
    if pd.isna(avg_body): return False
    return c1.get('body', 0) > 0.5 * avg_body and c2.get('body', 0) > 0.5 * avg_body and c3.get('body', 0) > 0.5 * avg_body


# =============================================================================
# Data Loading Functions
# =============================================================================

def load_from_parquet(data_dir, universe_tickers, start_date, end_date):
    """
    Load OHLCV data from date-partitioned parquet files.
    Returns dict: {ticker: DataFrame} with OHLCV data filtered by date range.
    """
    data_dir = Path(data_dir)
    all_files = list(data_dir.glob('*.parquet'))
    
    if not all_files:
        logger.warning(f"No parquet files found in {data_dir}")
        return {}
    
    logger.info(f"Found {len(all_files)} parquet files in {data_dir}")
    
    # Load all files
    all_dfs = []
    total_rows = 0
    for file_path in sorted(all_files):
        try:
            df = pd.read_parquet(file_path)
            all_dfs.append(df)
            total_rows += len(df)
            logger.info(f"  Loaded {file_path.name}: {len(df)} rows")
        except Exception as e:
            logger.error(f"  Error loading {file_path}: {e}")
    
    if not all_dfs:
        logger.error("No valid data loaded from any parquet file")
        return {}
    
    combined_df = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"Total rows loaded from parquet: {total_rows}")
    
    # Check for required OHLCV columns
    required_cols = {'open', 'high', 'low', 'close'}
    available_cols = set(combined_df.columns)
    missing_ohlc = required_cols - available_cols
    
    if missing_ohlc:
        logger.warning(f"Parquet files missing OHLC columns: {missing_ohlc}")
        return {}
    
    # Filter by universe
    universe_set = set(universe_tickers)
    if 'ticker' in combined_df.columns:
        combined_df = combined_df[combined_df['ticker'].isin(universe_set)]
        logger.info(f"Rows after universe filter: {len(combined_df)}")
    else:
        logger.error("No 'ticker' column found in parquet files")
        return {}
    
    # Convert timestamp
    timestamp_cols = [c for c in ['timestamp', 'date', 'Date', 'datetime'] if c in combined_df.columns]
    if timestamp_cols:
        combined_df['timestamp'] = pd.to_datetime(combined_df[timestamp_cols[0]])
    else:
        logger.error("No timestamp column found in parquet files")
        return {}
    
    # Filter by date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    combined_df = combined_df[(combined_df['timestamp'] >= start_dt) & (combined_df['timestamp'] <= end_dt)]
    logger.info(f"Rows after date filter ({start_date} to {end_date}): {len(combined_df)}")
    
    # Group by ticker
    ticker_data = {}
    for ticker in universe_tickers:
        ticker_df = combined_df[combined_df['ticker'] == ticker].copy()
        if len(ticker_df) > 0:
            ticker_df = ticker_df.sort_values('timestamp').reset_index(drop=True)
            ticker_data[ticker] = ticker_df
            first_date = ticker_df['timestamp'].iloc[0].strftime('%Y-%m-%d')
            last_date = ticker_df['timestamp'].iloc[-1].strftime('%Y-%m-%d')
            logger.info(f"  Ticker {ticker}: {len(ticker_df)} rows (date range: {first_date} to {last_date})")
        else:
            logger.warning(f"  Ticker {ticker}: NO DATA FOUND")
    
    # Report missing tickers
    found_tickers = set(ticker_data.keys())
    missing_tickers = universe_set - found_tickers
    if missing_tickers:
        logger.warning(f"Missing data for {len(missing_tickers)} tickers: {sorted(list(missing_tickers)[:10])}")
        if len(missing_tickers) > 10:
            logger.warning(f"  ... and {len(missing_tickers) - 10} more")
    
    return ticker_data


def load_from_raw_bars(conn, universe_tickers, start_date, end_date):
    """
    Load OHLCV data directly from raw_bars PostgreSQL table.
    Returns dict: {ticker: DataFrame} with OHLCV data filtered by date range.
    """
    logger.info("Loading OHLCV data from raw_bars table")
    
    # Build the query
    universe_str = ", ".join([f"'{t}'" for t in universe_tickers])
    
    query = f"""
        SELECT 
            ticker,
            date as timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM raw_bars
        WHERE ticker IN ({universe_str})
        AND date >= %s
        AND date <= %s
        ORDER BY ticker, date
    """
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (start_date, end_date))
            rows = cursor.fetchall()
            
        if not rows:
            logger.warning("No OHLCV data found in raw_bars for the specified criteria")
            return {}
        
        # Convert to DataFrame
        columns = ['ticker', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
        df = pd.DataFrame(rows, columns=columns)
        logger.info(f"Total rows loaded from raw_bars: {len(df)}")
        
        # Group by ticker in a single pass (O(n)).  The previous implementation
        # filtered df[df['ticker']==t] once per ticker — O(tickers x rows), which
        # is hours of work for the full ~6k-ticker universe.
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        ticker_data = {}
        verbose = len(universe_tickers) <= 50  # quiet per-ticker logging at scale
        for ticker, ticker_df in df.groupby('ticker', sort=False):
            ticker_df = ticker_df.sort_values('timestamp').reset_index(drop=True)
            ticker_data[ticker] = ticker_df
            if verbose:
                first_date = ticker_df['timestamp'].iloc[0].strftime('%Y-%m-%d')
                last_date = ticker_df['timestamp'].iloc[-1].strftime('%Y-%m-%d')
                logger.info(f"  Ticker {ticker}: {len(ticker_df)} rows (date range: {first_date} to {last_date})")

        # Report missing tickers
        found_tickers = set(ticker_data.keys())
        missing_tickers = set(universe_tickers) - found_tickers
        if missing_tickers:
            logger.warning(f"Missing data for {len(missing_tickers)} tickers: {sorted(list(missing_tickers)[:10])}")
            if len(missing_tickers) > 10:
                logger.warning(f"  ... and {len(missing_tickers) - 10} more")

        return ticker_data
        
    except Exception as e:
        logger.error(f"Error loading from raw_bars: {e}")
        return {}


def load_ohlcv_data(source, data_dir, conn, universe_tickers, start_date, end_date):
    """
    Load OHLCV data from the specified source.
    Falls back to raw_bars if parquet files don't have OHLC columns.
    """
    if source == 'raw_bars':
        logger.info("Source: raw_bars (PostgreSQL table)")
        return load_from_raw_bars(conn, universe_tickers, start_date, end_date)
    
    # Try parquet first
    logger.info("Source: parquet (trying parquet files first)")
    ticker_data = load_from_parquet(data_dir, universe_tickers, start_date, end_date)
    
    # If parquet files don't have OHLC, fallback to raw_bars
    if not ticker_data:
        logger.info("Parquet files missing OHLC columns, falling back to raw_bars")
        ticker_data = load_from_raw_bars(conn, universe_tickers, start_date, end_date)
    
    return ticker_data


# =============================================================================
# Context & Processing Functions
# =============================================================================

def calculate_context(df, idx):
    """Calculate context for a pattern occurrence."""
    if idx < 20:
        return {
            'regime': 'neutral',
            'vix_proxy': None,
            'vwap_position': 'at',
            'prior_trend': df.iloc[idx].get('prior_trend', 'neutral'),
            'volume_context': 'normal',
            'daily_context': 'normal'
        }
    
    lookback = df.iloc[max(0, idx-20):idx]
    
    # Regime classification
    total_return = (lookback['close'].iloc[-1] - lookback['close'].iloc[0]) / lookback['close'].iloc[0]
    regime = 'bullish' if total_return > 0.05 else ('bearish' if total_return < -0.05 else 'sideways')
    
    # VIX proxy (volatility)
    returns = lookback['close'].pct_change().dropna()
    vix_proxy = returns.std() * np.sqrt(252) if len(returns) > 0 else None
    
    # VWAP position
    avg_price = lookback['close'].mean()
    current_price = df.iloc[idx]['close']
    vwap_position = 'above' if current_price > avg_price else ('below' if current_price < avg_price else 'at')
    
    # Prior trend
    prior_trend = df.iloc[idx].get('prior_trend', 'neutral')
    
    # Volume context
    vol_col = 'volume' if 'volume' in df.columns else ('v' if 'v' in df.columns else None)
    if vol_col:
        avg_volume = lookback[vol_col].mean()
        current_volume = df.iloc[idx].get(vol_col, 0)
        if current_volume > 1.5 * avg_volume:
            volume_context = 'high'
        elif current_volume < 0.5 * avg_volume:
            volume_context = 'low'
        else:
            volume_context = 'normal'
    else:
        volume_context = 'normal'
    
    return {
        'regime': regime,
        'vix_proxy': vix_proxy,
        'vwap_position': vwap_position,
        'prior_trend': prior_trend,
        'volume_context': volume_context,
        'daily_context': 'normal'
    }


def detect_patterns(df):
    """Detect all 19 candlestick patterns in the dataframe."""
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


def process_ticker_data(ticker, df, conn):
    """Process a single ticker's dataframe to detect patterns and compute outcomes."""
    if df.empty or len(df) < 3:
        logger.warning(f"  Insufficient data for {ticker} ({len(df)} rows)")
        return 0, 0
    
    # Ensure required OHLCV columns exist
    required_cols = ['timestamp', 'open', 'high', 'low', 'close']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"  Missing columns in {ticker}: {missing_cols}")
        return 0, 0
    
    # Detect patterns
    patterns = detect_patterns(df)
    events, outcomes = [], []
    
    for name, indices in patterns.items():
        for idx in indices:
            row = df.iloc[idx]
            
            # Build event record
            events.append({
                'ticker': ticker,
                'timestamp': row['timestamp'],
                'timeframe': 'daily',
                'candle_name': name,
                'direction': DIRECTION_MAP[name],
                'strength': 'standard',
                'context': {},
                'o': row['open'],
                'h': row['high'],
                'l': row['low'],
                'c': row['close'],
                'v': row.get('volume', row.get('v', 0))
            })
            
            # Calculate forward returns
            returns = {}
            for lookahead in [1, 3, 6, 12, 24]:
                future_idx = idx + lookahead
                if future_idx < len(df):
                    returns[f'return_{lookahead}'] = (df.iloc[future_idx]['close'] - row['close']) / row['close']
                else:
                    returns[f'return_{lookahead}'] = None
            
            # Return to next close (EOD)
            if idx + 1 < len(df):
                next_row = df.iloc[idx+1]
                returns['return_eod'] = (next_row['close'] - row['close']) / row['close']
                returns['mfe'] = (next_row['high'] - row['close']) / row['close']
                returns['mae'] = (next_row['low'] - row['close']) / row['close']
            else:
                returns.update({'return_eod': None, 'mfe': None, 'mae': None})
            
            # Context information
            context = calculate_context(df, idx)
            
            # Determine hit target/stop based on direction
            if DIRECTION_MAP[name] == 'bullish':
                hit_target = returns.get('return_1', 0) > 0.01 if returns.get('return_1') is not None else None
                hit_stop = returns.get('return_1', 0) < -0.01 if returns.get('return_1') is not None else None
            elif DIRECTION_MAP[name] == 'bearish':
                hit_target = returns.get('return_1', 0) < -0.01 if returns.get('return_1') is not None else None
                hit_stop = returns.get('return_1', 0) > 0.01 if returns.get('return_1') is not None else None
            else:
                hit_target = None
                hit_stop = None
            
            outcomes.append({
                'ticker': ticker,
                'timestamp': row['timestamp'],
                'candle_name': name,
                **returns,
                'hit_target': hit_target,
                'hit_stop': hit_stop,
                **context
            })
    
    # Save events to database
    if events:
        event_data = [(
            e['ticker'], e['timestamp'], e['timeframe'], e['candle_name'],
            e['direction'], e['strength'], json.dumps(e['context']),
            e['o'], e['h'], e['l'], e['c'], e['v']
        ) for e in events]
        
        with conn.cursor() as cursor:
            execute_batch(cursor, """
                INSERT INTO candlestick_events 
                (ticker, timestamp, timeframe, candle_name, direction, strength, context, o, h, l, c, v)
                VALUES (%s, %s, %s, %s, %s, %s, %s::json, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, timestamp, timeframe, candle_name) DO NOTHING
            """, event_data)
        conn.commit()
        logger.info(f"  Saved {len(events)} events for {ticker}")
    
    # Get event IDs for outcomes
    event_ids = {}
    if events:
        for event in events:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM candlestick_events 
                    WHERE ticker = %s AND timestamp = %s AND candle_name = %s 
                    ORDER BY created_at DESC LIMIT 1
                """, (event['ticker'], event['timestamp'], event['candle_name']))
                result = cursor.fetchone()
                if result:
                    event_ids[(event['ticker'], event['timestamp'], event['candle_name'])] = result[0]
    
    # Save outcomes to database
    if outcomes:
        outcome_data = [(
            o['ticker'], o['timestamp'], o['candle_name'],
            event_ids.get((o['ticker'], o['timestamp'], o['candle_name'])),
            o.get('return_1'), o.get('return_3'), o.get('return_6'),
            o.get('return_12'), o.get('return_24'), o.get('return_eod'),
            o.get('mfe'), o.get('mae'), o.get('hit_target'), o.get('hit_stop'),
            # regime/vwap_position/prior_trend/volume_context/daily_context are
            # varchar and vix_proxy is double precision in candlestick_outcomes —
            # these are scalar values (not dicts), so insert them directly.
            o.get('regime'), o.get('vix_proxy'), o.get('vwap_position'),
            o.get('prior_trend'), o.get('volume_context'), o.get('daily_context')
        ) for o in outcomes]
        
        with conn.cursor() as cursor:
            execute_batch(cursor, """
                INSERT INTO candlestick_outcomes 
                (ticker, timestamp, candle_name, event_id, return_1, return_3, return_6,
                 return_12, return_24, return_eod, mfe, mae, hit_target, hit_stop,
                 regime, vix_proxy, vwap_position, prior_trend, volume_context, daily_context)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, outcome_data)
        conn.commit()
        logger.info(f"  Saved {len(outcomes)} outcomes for {ticker}")
    
    return len(events), len(outcomes)


# =============================================================================
# Keep-awake (Windows) — prevent idle system sleep during long runs.
# Auto-reverts when the process exits.  Display may still sleep; a manual
# sleep / lid-close still suspends the machine.
# =============================================================================

def prevent_system_sleep():
    """Best-effort: stop Windows from idle-sleeping while this process runs."""
    if not sys.platform.startswith('win'):
        return
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        logger.info("Keep-awake enabled (system idle-sleep suppressed for this run)")
    except Exception as e:
        logger.warning(f"Could not set keep-awake: {e}")


# =============================================================================
# Universe discovery / resume helpers
# =============================================================================

def get_all_db_tickers(conn, start_date, end_date):
    """Return every distinct ticker in raw_bars within the date range."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT ticker FROM raw_bars
            WHERE date >= %s AND date <= %s
            ORDER BY ticker
        """, (start_date, end_date))
        return [r[0] for r in cursor.fetchall()]


def get_processed_tickers(conn):
    """Tickers that already have rows in candlestick_events (for --resume)."""
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT ticker FROM candlestick_events")
            return {r[0] for r in cursor.fetchall()}
    except Exception:
        conn.rollback()
        return set()


# =============================================================================
# Main Function
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Atlas Candlestick Knowledge Layer - Backtest Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backtest_candlestick_outcomes.py --universe config/universe_500.csv --start 2020-01-01 --end 2026-06-17 --source raw_bars
  python backtest_candlestick_outcomes.py --universe config/universe_500.csv --start 2020-01-01 --end 2026-06-17 --limit 10
        """
    )
    parser.add_argument('--universe', type=str, default=None,
                        help='Path to universe CSV file (omit when using --all-db)')
    parser.add_argument('--all-db', action='store_true',
                        help='Backtest every distinct ticker in raw_bars within the date range')
    parser.add_argument('--batch-size', type=int, default=200,
                        help='Tickers loaded+processed per batch in --all-db mode (default: 200)')
    parser.add_argument('--resume', action='store_true',
                        help='Skip tickers already present in candlestick_events')
    parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--data_dir', type=str, default='exports/parquet', 
                        help='Directory with parquet files (default: exports/parquet)')
    parser.add_argument('--source', type=str, default='parquet', 
                        choices=['parquet', 'raw_bars'],
                        help='Data source: "parquet" or "raw_bars" (default: parquet)')
    parser.add_argument('--db_url', type=str, default=None, 
                        help='Database URL (default: DATABASE_URL env var or localhost atlas_research)')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of tickers to process')
    
    args = parser.parse_args()

    if not args.all_db and not args.universe:
        logger.error("Provide --universe <csv> or --all-db")
        sys.exit(1)

    # Long runs (esp. --all-db) should not be killed by idle sleep.
    if args.all_db:
        prevent_system_sleep()

    # Determine database URL
    db_url = args.db_url or os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL not set. Check your .env and that load_dotenv() ran.")
        sys.exit(1)
    masked = re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", db_url)
    logger.info(f"Database: {masked}")
    logger.info(f"Date range: {args.start} to {args.end}  |  Source: {args.source}")

    with get_db_connection(db_url) as conn:
        # ── Resolve the ticker universe ──────────────────────────────────────
        if args.all_db:
            universe_tickers = get_all_db_tickers(conn, args.start, args.end)
            logger.info(f"--all-db: {len(universe_tickers)} distinct tickers in raw_bars")
        else:
            try:
                universe = pd.read_csv(args.universe)
                if 'ticker' not in universe.columns:
                    universe = universe.rename(columns={universe.columns[0]: 'ticker'})
                universe_tickers = universe['ticker'].tolist()
            except Exception as e:
                logger.error(f"Error loading universe file: {e}")
                sys.exit(1)

        if args.resume:
            done = get_processed_tickers(conn)
            before = len(universe_tickers)
            universe_tickers = [t for t in universe_tickers if t not in done]
            logger.info(f"--resume: skipping {before - len(universe_tickers)} already-processed tickers")

        if args.limit:
            universe_tickers = universe_tickers[:args.limit]

        if not universe_tickers:
            logger.info("No tickers left to process.")
            return

        logger.info(f"Processing {len(universe_tickers)} tickers "
                    f"in batches of {args.batch_size}")

        # ── Batched load + process (bounds memory; resilient per ticker) ─────
        total_events = total_outcomes = 0
        tickers_with_data = processed = errored = 0
        n = len(universe_tickers)

        for b0 in range(0, n, args.batch_size):
            batch = universe_tickers[b0:b0 + args.batch_size]
            ticker_data = load_ohlcv_data(
                source=args.source, data_dir=args.data_dir, conn=conn,
                universe_tickers=batch, start_date=args.start, end_date=args.end,
            )
            for j, ticker in enumerate(batch):
                idx = b0 + j + 1
                if ticker not in ticker_data:
                    continue
                tickers_with_data += 1
                try:
                    events, outcomes = process_ticker_data(ticker, ticker_data[ticker], conn)
                    total_events += events
                    total_outcomes += outcomes
                    processed += 1
                except Exception as ex:
                    # One bad ticker must not abort the whole run — roll back the
                    # failed transaction so the connection stays usable.
                    conn.rollback()
                    errored += 1
                    logger.error(f"  [{idx}/{n}] Error processing {ticker}: {ex}")
            logger.info(f"  progress: {min(b0 + args.batch_size, n)}/{n} tickers "
                        f"| events={total_events} outcomes={total_outcomes} errors={errored}")

        logger.info("=" * 60)
        logger.info("BACKTEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Source used: {args.source}")
        logger.info(f"Tickers requested: {n}")
        logger.info(f"Tickers with data: {tickers_with_data}")
        logger.info(f"Tickers processed OK: {processed}  |  errored: {errored}")
        logger.info(f"Total events detected: {total_events}")
        logger.info(f"Total outcomes calculated: {total_outcomes}")
        if processed > 0:
            logger.info(f"Average events per ticker: {total_events / processed:.2f}")
        logger.info("=" * 60)


if __name__ == '__main__':
    main()

