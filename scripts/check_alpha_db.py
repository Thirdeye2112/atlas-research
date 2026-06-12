from sqlalchemy import create_engine, text
e = create_engine('postgresql://postgres:Postnat74%3F@localhost:5432/atlas_alpha')
with e.connect() as c:
    row = c.execute(text('SELECT id, data FROM ohlcv_cache LIMIT 1')).fetchone()
    data = row[1]
    print('ohlcv_cache.id sample:', row[0])
    print('data type:', type(data))
    if isinstance(data, list) and data:
        print('data[0]:', data[0])
    elif isinstance(data, dict):
        print('data keys:', list(data.keys())[:5])
    # ohlcv_history
    row2 = c.execute(text('SELECT * FROM ohlcv_history LIMIT 1')).fetchone()
    if row2:
        print('ohlcv_history cols:', list(row2._mapping.keys()))
        print('ohlcv_history row:', {k: v for k, v in list(row2._mapping.items())[:5]})
    else:
        print('ohlcv_history: empty')
    # quote_cache
    row3 = c.execute(text('SELECT * FROM quote_cache LIMIT 1')).fetchone()
    if row3:
        print('quote_cache cols:', list(row3._mapping.keys()))
