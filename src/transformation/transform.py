import pandas as pd
import numpy as np
from src.utils.config import CITY
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger("transform")


# Standardizing price columns
def clean_price(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(r"[\$,]", "", regex=True),
        errors="coerce"
    )


# Converting date string columns to proper datetime objects
def clean_dates(df: pd.DataFrame, date_cols: list) -> pd.DataFrame:
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


# Normalizing free-text fields
def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower()


# Title case and strip whitespace from geographic name columns
def standardize_geo(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.title()


# Rounding lat/lon to 5 decimal places for consistent coordinate precision
def standardize_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["latitude", "longitude"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(5)
    return df


# Drop columns where every single value is null
def drop_all_null_columns(df: pd.DataFrame) -> pd.DataFrame:
    before = df.shape[1]
    df = df.dropna(axis=1, how="all")
    after = df.shape[1]
    logger.info(f"Dropped {before - after} fully-null columns")
    return df


# Log how many prices could not be parsed — left as NaN (explicit null strategy)
def log_null_prices(df: pd.DataFrame, table_name: str):
    if "price_clean" in df.columns:
        null_count = df["price_clean"].isna().sum()
        logger.info(f"{table_name}: {null_count} unparseable prices left as NaN")


# Add flag_invalid column marking records that fail domain validation rules
def flag_validation_failures(df: pd.DataFrame) -> pd.DataFrame:
    df["flag_invalid"] = False

    if "price_clean" in df.columns:
        df.loc[df["price_clean"] < 0, "flag_invalid"] = True

    if "latitude" in df.columns:
        lat = pd.to_numeric(df["latitude"], errors="coerce")
        df.loc[(lat < 46.0) | (lat > 47.0), "flag_invalid"] = True

    if "longitude" in df.columns:
        lon = pd.to_numeric(df["longitude"], errors="coerce")
        df.loc[(lon < 6.0) | (lon > 7.5), "flag_invalid"] = True

    flagged = df["flag_invalid"].sum()
    logger.info(f"Flagged {flagged} records as invalid")
    return df


def transform_listings_summary(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM listings_summary", engine)
    logger.info(f"Loaded listings_summary: {df.shape}")

    df = drop_all_null_columns(df)
    df["price_clean"] = clean_price(df["price"])
    log_null_prices(df, "listings_summary")
    df = clean_dates(df, ["last_review", "host_since"])

    if "neighbourhood" in df.columns:
        df["neighbourhood"] = standardize_geo(df["neighbourhood"])
    if "neighbourhood_group" in df.columns:
        df["neighbourhood_group"] = standardize_geo(df["neighbourhood_group"])
    if "room_type" in df.columns:
        df["room_type"] = normalize_text(df["room_type"])
    if "beds" in df.columns:
        df["beds"] = df["beds"].fillna(0)

    df = standardize_coordinates(df)
    df = flag_validation_failures(df)
    df["city"] = CITY
    return df


def transform_listings_detailed(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM listings_detailed", engine)
    logger.info(f"Loaded listings_detailed: {df.shape}")

    df = drop_all_null_columns(df)
    df["price_clean"] = clean_price(df["price"])
    log_null_prices(df, "listings_detailed")
    df = clean_dates(df, ["last_review", "host_since", "first_review", "calendar_last_scraped"])

    if "neighbourhood_cleansed" in df.columns:
        df["neighbourhood_cleansed"] = standardize_geo(df["neighbourhood_cleansed"])
    if "room_type" in df.columns:
        df["room_type"] = normalize_text(df["room_type"])
    if "property_type" in df.columns:
        df["property_type"] = normalize_text(df["property_type"])
    if "bathrooms_text" in df.columns:
        df["bathrooms_text"] = normalize_text(df["bathrooms_text"])
    if "beds" in df.columns:
        df["beds"] = df["beds"].fillna(0)
    if "bedrooms" in df.columns:
        df["bedrooms"] = df["bedrooms"].fillna(0)

    df = standardize_coordinates(df)
    df = flag_validation_failures(df)
    df["city"] = CITY
    return df


def transform_calendar(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM calendar", engine)
    logger.info(f"Loaded calendar: {df.shape}")

    df = clean_dates(df, ["date"])
    if "price" in df.columns:
        df["price_clean"] = clean_price(df["price"])
        log_null_prices(df, "calendar")
    if "adjusted_price" in df.columns:
        df["adjusted_price_clean"] = clean_price(df["adjusted_price"])
    if "available" in df.columns:
        df["available"] = df["available"].map({"t": True, "f": False})

    return df


def transform_reviews_detailed(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM reviews_detailed", engine)
    logger.info(f"Loaded reviews_detailed: {df.shape}")
    df = clean_dates(df, ["date"])
    return df


def transform_reviews_summary(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM reviews_summary", engine)
    logger.info(f"Loaded reviews_summary: {df.shape}")
    df = clean_dates(df, ["date"])
    return df


def transform_neighbourhoods(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM neighbourhoods", engine)
    logger.info(f"Loaded neighbourhoods: {df.shape}")

    if "neighbourhood" in df.columns:
        df["neighbourhood"] = standardize_geo(df["neighbourhood"])
    if "neighbourhood_group" in df.columns:
        df["neighbourhood_group"] = standardize_geo(df["neighbourhood_group"])

    return df


def transform_neighbourhoods_geo(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM neighbourhoods_geo", engine)
    logger.info(f"Loaded neighbourhoods_geo: {df.shape}")
    return df


# Writing cleaned dataframe to Postgres, replacing the table if it already exists
def write_table(df: pd.DataFrame, table_name: str, engine):
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    logger.info(f"Written {len(df)} rows to {table_name}")


def main():
    engine = get_engine()
    logger.info("Starting transformation run...")

    write_table(transform_listings_summary(engine), "listings_summary_clean", engine)
    write_table(transform_listings_detailed(engine), "listings_detailed_clean", engine)
    write_table(transform_calendar(engine), "calendar_clean", engine)
    write_table(transform_reviews_detailed(engine), "reviews_detailed_clean", engine)
    write_table(transform_reviews_summary(engine), "reviews_summary_clean", engine)
    write_table(transform_neighbourhoods(engine), "neighbourhoods_clean", engine)
    write_table(transform_neighbourhoods_geo(engine), "neighbourhoods_geo_clean", engine)

    logger.info("Transformation run complete.")


if __name__ == "__main__":
    main()
