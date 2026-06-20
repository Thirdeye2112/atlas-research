import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv; load_dotenv()
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    cols = c.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='research_hypotheses' ORDER BY ordinal_position"
    )).fetchall()
    print('research_hypotheses columns:')
    for r in cols:
        print(f'  {r[0]}: {r[1]}')
    n = c.execute(text('SELECT COUNT(*) FROM research_hypotheses')).scalar()
    print(f'Rows: {n}')
