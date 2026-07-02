import pandas as pd
from sqlalchemy import text
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)

# find the earliest and latest dates across both fact source tables
def get_date_range(engine):
    query = text("""
        SELECT MIN(date) AS min_date, MAX(date) AS max_date
        FROM (
            SELECT date FROM calendar_clean
            UNION
            SELECT date FROM reviews_detailed_clean
        ) combined
    """)
    with engine.connect() as conn:
        result = conn.execute(query).fetchone()
    logger.info(f"Date range found: {result.min_date} to {result.max_date}")
    return result.min_date, result.max_date


# generate one row per day, no gaps
def build_dim_date(min_date, max_date):
    dates = pd.date_range(start=min_date, end=max_date, freq='D')
    df = pd.DataFrame({'full_date': dates})
    return df

# surrogate key in YYYYMMDD format, e.g. 20250714
def add_date_attributes(df):
    df['date_id'] = df['full_date'].dt.strftime('%Y%m%d').astype(int)

    df['day'] = df['full_date'].dt.day
    df['month'] = df['full_date'].dt.month
    df['month_name'] = df['full_date'].dt.strftime('%B')
    df['quarter'] = df['full_date'].dt.quarter
    df['year'] = df['full_date'].dt.year
    df['day_of_week'] = df['full_date'].dt.strftime('%A')

    # Monday=0 ... Sunday=6, so 5 and 6 are the weekend
    df['is_weekend'] = df['full_date'].dt.dayofweek >= 5

    return df

# dim_date is fully derived, safe to rebuild from scratch each run
def write_dim_date(df, engine):
    df.to_sql('dim_date', engine, if_exists='replace', index=False)
    logger.info(f"dim_date written: {len(df)} rows")


if __name__ == "__main__":
    engine = get_engine()
    min_date, max_date = get_date_range(engine)
    df = build_dim_date(min_date, max_date)
    df = add_date_attributes(df)
    write_dim_date(df, engine)