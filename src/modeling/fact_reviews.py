import pandas as pd
from sqlalchemy import text
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)


# pull review rows, convert date to YYYYMMDD to match dim_date's key,and measure comment length instead of storing the full text here
def get_reviews_data(engine):
    
    query = text("""
        SELECT
            id AS review_key,
            listing_id AS listing_key,
            TO_CHAR(date, 'YYYYMMDD')::int AS date_id,
            reviewer_id,
            LENGTH(comments) AS comment_length
        FROM reviews_detailed_clean
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    logger.info(f"Pulled {len(df)} review rows")
    return df


# same FK check pattern as fact_calendar: confirm every listing_key and date_id actually exists in the dimension tables before writing
def check_fk_integrity(df, engine):
    
    with engine.connect() as conn:
        valid_listings = pd.read_sql("SELECT listing_key FROM dim_listing", conn)
        valid_dates = pd.read_sql("SELECT date_id FROM dim_date", conn)

    bad_listings = ~df['listing_key'].isin(valid_listings['listing_key'])
    bad_dates = ~df['date_id'].isin(valid_dates['date_id'])

    if bad_listings.sum() > 0:
        logger.warning(f"{bad_listings.sum()} rows have a listing_key not in dim_listing")
    else:
        logger.info("All listing_key values found in dim_listing")

    if bad_dates.sum() > 0:
        logger.warning(f"{bad_dates.sum()} rows have a date_id not in dim_date")
    else:
        logger.info("All date_id values found in dim_date")


# fully derived table, safe to rebuild each run
def write_fact_reviews(df, engine):
    df.to_sql('fact_reviews', engine, if_exists='replace', index=False)
    logger.info(f"fact_reviews written: {len(df)} rows")


if __name__ == "__main__":
    engine = get_engine()
    df = get_reviews_data(engine)
    check_fk_integrity(df, engine)
    write_fact_reviews(df, engine)