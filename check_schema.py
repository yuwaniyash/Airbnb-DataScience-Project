"""
Quick schema dump for Supabase.
Prints every table + its columns (with types) so we can build the
Streamlit dashboard against the *real* schema instead of guessing.

Run:
    python check_schema.py

Paste the full output back.
"""

import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()  # reads .env if present

DB_URL = os.getenv("SUPABASE_DATABASE_URL")

if not DB_URL:
    raise SystemExit(
        "SUPABASE_DATABASE_URL not found. Either set it in .env or run:\n"
        '  $env:SUPABASE_DATABASE_URL="postgresql://...@...supabase.com:5432/postgres"\n'
        "in this terminal session before running this script."
    )

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# 1. List all tables in public schema, with row counts
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")
tables = [r[0] for r in cur.fetchall()]

print("=" * 70)
print(f"Found {len(tables)} tables in public schema")
print("=" * 70)

for t in tables:
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
    """, (t,))
    cols = cur.fetchall()

    cur.execute(f'SELECT COUNT(*) FROM "{t}";')
    row_count = cur.fetchone()[0]

    print(f"\n--- {t} ({row_count} rows) ---")
    for col_name, data_type, nullable in cols:
        print(f"  {col_name:35s} {data_type:20s} {'NULL' if nullable=='YES' else 'NOT NULL'}")

# 2. Peek at 1 sample row per table so we see real values (helps with filter options)
print("\n" + "=" * 70)
print("SAMPLE ROWS (first row of each table)")
print("=" * 70)
for t in tables:
    cur.execute(f'SELECT * FROM "{t}" LIMIT 1;')
    row = cur.fetchone()
    colnames = [desc[0] for desc in cur.description]
    print(f"\n--- {t} ---")
    if row:
        for cname, val in zip(colnames, row):
            print(f"  {cname}: {val}")
    else:
        print("  (empty)")

cur.close()
conn.close()
print("\nDone.")
