import pandas as pd
from sqlalchemy import text
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)


# pull listing attributes, joined to dim_neighbourhood to get the FK
def get_listings(engine):
    query = text("""
        SELECT
            l.id AS listing_key,
            l.host_id,
            l.host_name,
            l.host_is_superhost,
            l.hosts_time_as_host_years AS host_tenure_years,
            l.property_type,
            l.room_type,
            l.accommodates,
            l.bedrooms,
            l.beds,
            l.price_clean AS price_base,
            l.review_scores_rating AS rating_overall,
            n.neighbourhood_id
        FROM listings_detailed_clean l
        LEFT JOIN dim_neighbourhood n
            ON l.neighbourhood_cleansed = n.neighbourhood_name
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    logger.info(f"Pulled {len(df)} listings with neighbourhood FK attached")
    return df


# explicit flag instead of relying on implicit nulls in price_base
def add_price_flag(df):
    df['has_price'] = df['price_base'].notna()
    return df

# flag any listing that didn't get matched to a neighbourhood
def check_unmatched(df):
    unmatched = df[df['neighbourhood_id'].isna()]
    if len(unmatched) > 0:
        logger.warning(f"{len(unmatched)} listings have no neighbourhood match")
    else:
        logger.info("All listings matched to a neighbourhood successfully")


# fully derived table, safe to rebuild each run
def write_dim_listing(df, engine):
    df.to_sql('dim_listing', engine, if_exists='replace', index=False)
    logger.info(f"dim_listing written: {len(df)} rows")


if __name__ == "__main__":
    engine = get_engine()
    df = get_listings(engine)
    df = add_price_flag(df)
    check_unmatched(df)
    write_dim_listing(df, engine)