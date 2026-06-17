# Atlas Candlestick Knowledge Layer v1
# Backtest Script - Pattern Detection & Outcome Analysis
# Updated: Support for Atlas date-partitioned parquet exports (feature_matrix_YYYY-MM-DD.parquet)

import argparse, os, sys, logging
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

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
    df['avg_volume_20'] = df['volume'].rolling(window=window).mean() if 'volume' in df.columns else df['v'].rolling(window=window).mean()
    df['prior_trend'] = 'neutral'
    if len(df) >= 3:
        df.loc[df['close'].rolling(3).apply(lambda x: all(x.diff().dropna() > 0), raw=False), 'prior_trend'] = 'up'
        df.loc[df['close'].rolling(3).apply(lambda x: all(x.diff().dropna() < 0), raw=False), 'prior_trend'] = 'down'
    return df