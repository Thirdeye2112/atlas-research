"""
Apply a SQL migration file using SQLAlchemy (no psql needed).
Usage: python apply_migration.py db/migrations/003_transcript_intelligence.sql
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from atlas_research.db.connection import get_connection
from sqlalchemy import text

migration_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join('db', 'migrations', '003_transcript_intelligence.sql')

sql = open(migration_file, encoding='utf-8').read()

# Split into individual statements; handle DO $$ blocks specially
import re

# Collect statements: split on semicolons but not inside $$ blocks
statements = []
current = []
in_dollar_block = False
for line in sql.splitlines():
    stripped = line.strip()
    if stripped.startswith('--'):
        continue
    if '$$' in line:
        in_dollar_block = not in_dollar_block
    current.append(line)
    if not in_dollar_block and stripped.endswith(';'):
        stmt = '\n'.join(current).strip().rstrip(';')
        if stmt:
            statements.append(stmt)
        current = []

print(f"Applying {len(statements)} statements from {migration_file}...")

with get_connection() as conn:
    for i, stmt in enumerate(statements):
        try:
            conn.execute(text(stmt))
            print(f"  [{i+1}/{len(statements)}] OK")
        except Exception as e:
            msg = str(e).split('\n')[0][:120]
            print(f"  [{i+1}/{len(statements)}] WARN: {msg}")
    conn.commit()

print("Migration complete.")
