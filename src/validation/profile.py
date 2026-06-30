import pandas as pd
from src.utils.config import BASE_DIR
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger("profile")

TABLES = [
    "listings_summary",
    "listings_detailed",
    "reviews_summary",
    "reviews_detailed",
    "calendar",
    "neighbourhoods",
    "neighbourhoods_geo",
]

OUTPUT_DIR = BASE_DIR / "data" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def profile_table(table_name: str, engine) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
    row_count = len(df)
    logger.info(f"Profiling {table_name} ({row_count} rows, {len(df.columns)} columns)")

    records = []
    for col in df.columns:
        null_count = df[col].isna().sum()
        null_rate = round((null_count / row_count) * 100, 2) if row_count > 0 else 0
        cardinality = df[col].nunique()
        records.append({
            "table": table_name,
            "column": col,
            "dtype": str(df[col].dtype),
            "row_count": row_count,
            "null_count": int(null_count),
            "null_rate_%": null_rate,
            "unique_values": int(cardinality),
        })

    return pd.DataFrame(records)


def main():
    engine = get_engine()
    logger.info("Starting profiling run...")

    all_profiles = []
    for table in TABLES:
        try:
            profile_df = profile_table(table, engine)
            all_profiles.append(profile_df)
        except Exception as e:
            logger.error(f"Failed to profile {table}: {e}")

    if not all_profiles:
        logger.error("No tables were profiled successfully.")
        return

    combined = pd.concat(all_profiles, ignore_index=True)

    csv_path = OUTPUT_DIR / "profiling_report.csv"
    html_path = OUTPUT_DIR / "profiling_report.html"

    combined.to_csv(csv_path, index=False)
    combined.to_html(html_path, index=False, border=1)

    logger.info(f"Saved: {csv_path}")
    logger.info(f"Saved: {html_path}")

    print("\n--- COMPLETENESS SUMMARY (avg null rate per table) ---")
    summary = (
        combined.groupby("table")["null_rate_%"]
        .mean()
        .reset_index()
        .rename(columns={"null_rate_%": "avg_null_rate_%"})
        .sort_values("avg_null_rate_%", ascending=False)
    )
    print(summary.to_string(index=False))

    print("\n--- TOP 20 MOST INCOMPLETE COLUMNS ---")
    top_missing = (
        combined[combined["null_rate_%"] > 0]
        .sort_values("null_rate_%", ascending=False)
        .head(20)[["table", "column", "null_rate_%", "unique_values"]]
    )
    print(top_missing.to_string(index=False))

    logger.info("Profiling run complete.")


if __name__ == "__main__":
    main()