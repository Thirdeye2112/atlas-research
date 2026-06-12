from sqlalchemy import create_engine, text
import os; from dotenv import load_dotenv; from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")
e = create_engine(os.environ["DATABASE_URL"])
with e.connect() as c:
    r = c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='schema_migrations'")).fetchall()
    print("schema_migrations cols:", [x[0] for x in r])
    rows = c.execute(text("SELECT * FROM schema_migrations ORDER BY 1 DESC LIMIT 5")).fetchall()
    print("Last 5 rows:", [dict(x._mapping) for x in rows])
