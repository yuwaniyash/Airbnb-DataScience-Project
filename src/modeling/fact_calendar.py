import pandas as pd
from sqlalchemy import text
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)


#pull calendar rows and convert the date into the same YYYYMMDD format used as the primary key in dim_date, so the join will work
def get_calendar_data(engine):

    query = text("""
        SELECT
            listing_id AS listing_key,
            TO_CHAR(date, 'YYYYMMDD')::int AS date_id,
            available AS is_available,
            minimum_nights,
            maximum_nights
        FROM calendar_clean
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    logger.info(f"Pulled {len(df)} calendar rows")
    return df


#confirm every listing_key actually exists in dim_listing,and every date_id actually exists in dim_date
#a broken FK here means a row would silently fail to join later
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



# calendar_key is just a simple row counter, since there's no natural unique id for a single listing+date combination
def add_surrogate_key(df):
    df = df.reset_index(drop=True)
    df['calendar_key'] = df.index + 1
    return df


# fully derived table, safe to rebuild each run
def write_fact_calendar(df, engine):
    cols = ['calendar_key', 'listing_key', 'date_id', 'is_available',
            'minimum_nights', 'maximum_nights']
    df = df[cols]
    df.to_sql('fact_calendar', engine, if_exists='replace', index=False)
    logger.info(f"fact_calendar written: {len(df)} rows")


if __name__ == "__main__":
    engine = get_engine()
    df = get_calendar_data(engine)
    check_fk_integrity(df, engine)
    df = add_surrogate_key(df)
    write_fact_calendar(df, engine)