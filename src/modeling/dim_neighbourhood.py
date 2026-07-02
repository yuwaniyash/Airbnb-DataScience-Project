import pandas as pd
from sqlalchemy import text
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)


# compute stats per neighbourhood from the listings table
def get_neighbourhood_aggregates(engine):
    query = text("""
        SELECT
            neighbourhood_cleansed AS neighbourhood_name,
            COUNT(*) AS listing_density,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_clean) AS median_price,
            AVG(review_scores_rating) AS avg_rating
        FROM listings_detailed_clean
        GROUP BY neighbourhood_cleansed
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    logger.info(f"Aggregated {len(df)} neighbourhoods from listings")
    return df


# get the neighbourhood -> group mapping from the reference table
def get_neighbourhood_hierarchy(engine):
    query = text("""
        SELECT DISTINCT
            neighbourhood AS neighbourhood_name,
            neighbourhood_group
        FROM neighbourhoods_clean
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    logger.info(f"Loaded {len(df)} neighbourhood-to-group mappings")
    return df


# merge stats with hierarchy, keep all neighbourhoods that have listings
def build_dim_neighbourhood(agg_df, hierarchy_df):
    df = agg_df.merge(hierarchy_df, on='neighbourhood_name', how='left')

    # surrogate key since neighbourhood names have no natural numeric id
    df['neighbourhood_id'] = range(1, len(df) + 1)

    df = df[['neighbourhood_id', 'neighbourhood_name', 'neighbourhood_group',
             'median_price', 'listing_density', 'avg_rating']]
    return df


# flag any neighbourhood that didn't find a matching group
def check_unmatched(df):
    unmatched = df[df['neighbourhood_group'].isna()]
    if len(unmatched) > 0:
        logger.warning(f"{len(unmatched)} neighbourhoods had no group match: "
                        f"{unmatched['neighbourhood_name'].tolist()}")
    else:
        logger.info("All neighbourhoods matched to a group successfully")


# fully derived table, safe to rebuild each run
def write_dim_neighbourhood(df, engine):
    df.to_sql('dim_neighbourhood', engine, if_exists='replace', index=False)
    logger.info(f"dim_neighbourhood written: {len(df)} rows")


if __name__ == "__main__":
    engine = get_engine()
    agg_df = get_neighbourhood_aggregates(engine)
    hierarchy_df = get_neighbourhood_hierarchy(engine)
    df = build_dim_neighbourhood(agg_df, hierarchy_df)
    check_unmatched(df)
    write_dim_neighbourhood(df, engine)