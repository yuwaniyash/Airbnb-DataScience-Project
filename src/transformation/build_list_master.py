import pandas as pd
import numpy as np
from datetime import datetime
from src.utils.config import CITY
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger("build_list_master")


# Load the base listings table - this is our starting point, one row per listing
def load_base_listings(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM listings_detailed_clean", engine)
    logger.info(f"Loaded base listings: {df.shape}")
    return df


# Aggregate all reviews down to one row per listing (count, first date, last date)
def build_review_stats(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT listing_id, date FROM reviews_detailed_clean", engine)
    stats = df.groupby("listing_id").agg(
        review_count_scraped=("date", "count"),
        first_review_scraped=("date", "min"),
        last_review_scraped=("date", "max"),
    ).reset_index()
    logger.info(f"Built review stats for {len(stats)} listings")
    return stats


# Aggregate 365 days of calendar data down to one row per listing (occupancy rate)
def build_calendar_stats(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT listing_id, available FROM calendar_clean", engine)
    stats = df.groupby("listing_id").agg(
        days_tracked=("available", "count"),
        days_booked=("available", lambda x: (x == False).sum()),
    ).reset_index()
    stats["occupancy_rate_calc"] = (stats["days_booked"] / stats["days_tracked"]).round(4)
    logger.info(f"Built calendar stats for {len(stats)} listings")
    return stats


# Estimate yearly revenue = booked days x nightly price
def add_revenue_estimate(df: pd.DataFrame) -> pd.DataFrame:
    df["revenue_estimate_calc"] = (df["days_booked"] * df["price_clean"]).round(2)
    return df


# Compute median price, listing count, and avg rating per neighbourhood, join back onto listings
def add_neighbourhood_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("neighbourhood_cleansed").agg(
        neighbourhood_median_price=("price_clean", "median"),
        neighbourhood_listing_count=("id", "count"),
        neighbourhood_avg_rating=("review_scores_rating", "mean"),
    ).reset_index()
    agg["neighbourhood_median_price"] = agg["neighbourhood_median_price"].round(2)
    agg["neighbourhood_avg_rating"] = agg["neighbourhood_avg_rating"].round(2)
    df = df.merge(agg, on="neighbourhood_cleansed", how="left")
    logger.info(f"Added neighbourhood aggregates for {len(agg)} neighbourhoods")
    return df


# Combine years + months columns into one decimal number for how long the host has been active
def add_host_tenure(df: pd.DataFrame) -> pd.DataFrame:
    years = pd.to_numeric(df["hosts_time_as_host_years"], errors="coerce").fillna(0)
    months = pd.to_numeric(df["hosts_time_as_host_months"], errors="coerce").fillna(0)
    df["host_tenure_years"] = (years + months / 12).round(2)
    return df


# Average reviews per month = total reviews / months between first and last review
def add_review_frequency(df: pd.DataFrame) -> pd.DataFrame:
    first = pd.to_datetime(df["first_review"], errors="coerce")
    last = pd.to_datetime(df["last_review"], errors="coerce")
    months_active = ((last - first).dt.days / 30.44).replace(0, np.nan)
    reviews = pd.to_numeric(df["number_of_reviews"], errors="coerce")
    df["review_frequency"] = (reviews / months_active).round(3)
    df["review_frequency"] = df["review_frequency"].replace([np.inf, -np.inf], np.nan)
    return df


# Price per bedroom = nightly price / number of bedrooms (skip zero-bedroom studios)
def add_price_per_bedroom(df: pd.DataFrame) -> pd.DataFrame:
    bedrooms = pd.to_numeric(df["bedrooms"], errors="coerce")
    price = pd.to_numeric(df["price_clean"], errors="coerce")
    ratio = price / bedrooms.replace(0, np.nan)
    df["price_per_bedroom"] = ratio.round(2)
    return df


# Run every step in order and write the final result to Postgres as listings_master
def main():
    engine = get_engine()
    logger.info("Starting build_list_master run...")

    listings = load_base_listings(engine)

    # Join review stats onto listings, then drop the extra listing_id column from the merge
    review_stats = build_review_stats(engine)
    listings = listings.merge(review_stats, left_on="id", right_on="listing_id", how="left")
    listings = listings.drop(columns=["listing_id"])

    # Join calendar stats onto listings, then drop the extra listing_id column from the merge
    calendar_stats = build_calendar_stats(engine)
    listings = listings.merge(calendar_stats, left_on="id", right_on="listing_id", how="left")
    listings = listings.drop(columns=["listing_id"])

    listings = add_revenue_estimate(listings)
    listings = add_neighbourhood_aggregates(listings)
    listings = add_host_tenure(listings)
    listings = add_review_frequency(listings)
    listings = add_price_per_bedroom(listings)

    listings["built_at"] = datetime.now()

    listings.to_sql("listings_master", engine, if_exists="replace", index=False)
    logger.info(f"Written {len(listings)} rows to listings_master ({listings.shape[1]} columns)")

    print(f"\nlistings_master: {listings.shape[0]} rows, {listings.shape[1]} columns")
    print(f"Missing occupancy data: {listings['occupancy_rate_calc'].isna().sum()} listings")
    print(f"Missing review data: {listings['review_count_scraped'].isna().sum()} listings")

    logger.info("build_list_master run complete.")


if __name__ == "__main__":
    main()