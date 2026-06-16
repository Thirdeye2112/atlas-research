import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from sqlalchemy import create_engine, text

engine = create_engine(os.environ['DATABASE_URL'])
migrations = [
    'db/migrations/0035_signal_combination_scores.sql',
    'db/migrations/0036_predictions_meta_columns.sql',
]
root = os.path.join(os.path.dirname(__file__), '..')
for f in migrations:
    print(f"\n-- {f}")
    sql = open(os.path.join(root, f)).read()
    # Execute each file in its own transaction, one statement at a time
    stmts = [s.strip() for s in sql.split(';') if s.strip()]
    for s in stmts:
        # Strip leading comment lines to check if there's real SQL
        lines = [ln for ln in s.splitlines() if not ln.strip().startswith('--')]
        real = '\n'.join(lines).strip()
        if not real:
            continue
        # Execute the original statement (with comments, postgres handles them)
        try:
            with engine.begin() as conn:
                conn.execute(text(s))
            preview = real[:70].replace('\n', ' ')
            print(f"  OK: {preview}")
        except Exception as e:
            print(f"  ERR ({real[:50]}): {e}")
print("\nDone.")
