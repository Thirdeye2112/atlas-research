import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
import numpy as np

from atlas_research.features import omni_proxy, momentum, trend, volume, relative_strength

np.random.seed(42)
close = np.cumprod(1 + np.random.randn(300) * 0.01) * 100
high  = close * (1 + np.abs(np.random.randn(300) * 0.005))
low   = close * (1 - np.abs(np.random.randn(300) * 0.005))
vol   = np.random.randint(1_000_000, 5_000_000, 300).astype(float)
spy   = np.cumprod(1 + np.random.randn(300) * 0.008) * 450

r_omni  = omni_proxy.compute(close, high, low)
r_mom   = momentum.compute(close)
r_trend = trend.compute(close)
r_vol   = volume.compute(close, vol)
r_rs    = relative_strength.compute(close, spy)

new_features = {
    'omni_82_distance_5d_change': r_omni.get('omni_82_distance_5d_change'),
    'omni_82_slope_10d':          r_omni.get('omni_82_slope_10d'),
    'rsi_momentum_5d':            r_mom.get('rsi_momentum_5d'),
    'distance_sma20_momentum':    r_trend.get('distance_sma20_momentum'),
    'volume_trend_5d':            r_vol.get('volume_trend_5d'),
    'rs_spy_20_momentum':         r_rs.get('rs_spy_20_momentum'),
}
for k, v in new_features.items():
    print("  %s: %s" % (k, v))

missing = [k for k, v in new_features.items() if v is None]
if missing:
    print("WARNING: None values for: %s" % missing)
else:
    print("All 6 new features computed OK")

from config.settings import ALL_FEATURES, MOMENTUM_V2_FEATURES
print("ALL_FEATURES count: %d" % len(ALL_FEATURES))
print("MOMENTUM_V2_FEATURES: %s" % MOMENTUM_V2_FEATURES)
