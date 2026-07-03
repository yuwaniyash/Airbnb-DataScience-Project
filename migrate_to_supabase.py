import os
import pandas as pd
from sqlalchemy import create_engine, text
from src.utils.logger import get_logger

logger = get_logger("migrate_to_supabase")

LOCAL_DB_URL = os.environ["LOCAL_DATABASE_URL"]        # your existing local Postgres
SUPABASE_DB_URL = os.environ["SUPABASE_DATABASE_URL"]  # from Supabase: Project Settings > Database > Connection string (URI, use the pooler one for scripts)

TABLES_TO_COPY = [
    "dim_date",
    "dim_neighbourhood",
    "dim_listing",
    "fact_calendar",
    "fact_reviews",
    "listings_master",
]

def get_engines():
    local_engine = create_engine(LOCAL_DB_URL)
    supabase_engine = create_engine(SUPABASE_DB_URL)
    return local_engine, supabase_engine


def copy_table(table_name, local_engine, supabase_engine, chunksize=5000):
    logger.info(f"Copying {table_name}...")
    df = pd.read_sql(f"SELECT * FROM {table_name}", local_engine)
    df.to_sql(table_name, supabase_engine, if_exists="replace", index=False, chunksize=chunksize, method="multi")
    logger.info(f"{table_name}: {len(df)} rows copied")
    return len(df)


# fact_reviews strips out comment text, but NLP needs it — pull a dedicated
# reviews_text table with just what's needed: listing_key, date_id, comments
def copy_reviews_text(local_engine, supabase_engine, chunksize=5000):
    logger.info("Copying review text (for NLP)...")
    query = text("""
        SELECT
            id AS review_key,
            listing_id AS listing_key,
            TO_CHAR(date, 'YYYYMMDD')::int AS date_id,
            comments
        FROM reviews_detailed_clean
        WHERE comments IS NOT NULL
    """)
    with local_engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df.to_sql("reviews_text", supabase_engine, if_exists="replace", index=False, chunksize=chunksize, method="multi")
    logger.info(f"reviews_text: {len(df)} rows copied")
    return len(df)


def verify_row_counts(local_engine, supabase_engine, tables):
    logger.info("Verifying row counts match...")
    mismatches = []
    for t in tables:
        local_count = pd.read_sql(f"SELECT COUNT(*) AS c FROM {t}", local_engine).iloc[0]["c"]
        supa_count = pd.read_sql(f"SELECT COUNT(*) AS c FROM {t}", supabase_engine).iloc[0]["c"]
        status = "OK" if local_count == supa_count else "MISMATCH"
        if status == "MISMATCH":
            mismatches.append(t)
        logger.info(f"  {t}: local={local_count} supabase={supa_count} [{status}]")
    if mismatches:
        logger.warning(f"Row count mismatches in: {mismatches}")
    else:
        logger.info("All row counts match.")


def main():
    local_engine, supabase_engine = get_engines()

    for table in TABLES_TO_COPY:
        copy_table(table, local_engine, supabase_engine)

    reviews_text_count = copy_reviews_text(local_engine, supabase_engine)

    verify_row_counts(local_engine, supabase_engine, TABLES_TO_COPY)

    # reviews_text only exists on Supabase (it's derived, not a 1:1 copy of a local table),
    # so just confirm the row count landed correctly rather than comparing against local
    supa_reviews_text_count = pd.read_sql("SELECT COUNT(*) AS c FROM reviews_text", supabase_engine).iloc[0]["c"]
    status = "OK" if supa_reviews_text_count == reviews_text_count else "MISMATCH"
    logger.info(f"  reviews_text: expected={reviews_text_count} supabase={supa_reviews_text_count} [{status}]")

    logger.info("Migration complete.")


if __name__ == "__main__":
    main()
