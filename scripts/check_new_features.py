import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from atlas_research.db.connection import get_connection
from sqlalchemy import text

with get_connection() as c:
    rows = c.execute(text(
        "SELECT feature_name, COUNT(*) as cnt "
        "FROM feature_snapshots "
        "WHERE feature_name IN ("
        "'omni_82_distance_5d_change','omni_82_slope_10d',"
        "'rsi_momentum_5d','distance_sma20_momentum',"
        "'volume_trend_5d','rs_spy_20_momentum'"
        ") GROUP BY feature_name ORDER BY feature_name"
    )).fetchall()
    for row in rows:
        print("%s: %d" % (row[0], row[1]))
    total = c.execute(text("SELECT COUNT(*) FROM feature_snapshots")).scalar()
    print("total rows: %d" % total)
