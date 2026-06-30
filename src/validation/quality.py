import pandas as pd
from thefuzz import fuzz
from src.utils.config import BASE_DIR
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger("quality")

OUTPUT_DIR = BASE_DIR / "data" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def detect_duplicates(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT id, name, latitude, longitude FROM listings_detailed", engine)
    
    # Deterministic: exact same id appearing more than once
    exact_dupes = df[df.duplicated(subset=["id"], keep=False)].copy()
    exact_dupes["duplicate_type"] = "exact"
    logger.info(f"Exact duplicates found: {len(exact_dupes)}")

    # Fuzzy: same lat/lon but slightly different name
    fuzzy_dupes = []
    df_sample = df.dropna(subset=["name", "latitude", "longitude"])
    seen = set()

    for i, row in df_sample.iterrows():
        if i in seen:
            continue
        same_location = df_sample[
            (abs(df_sample["latitude"] - row["latitude"]) < 0.001) &
            (abs(df_sample["longitude"] - row["longitude"]) < 0.001) &
            (df_sample.index != i)
        ]
        for j, other in same_location.iterrows():
            if j in seen:
                continue
            score = fuzz.ratio(str(row["name"]), str(other["name"]))
            if score >= 85:
                fuzzy_dupes.append({
                    "id_1": row["id"],
                    "id_2": other["id"],
                    "name_1": row["name"],
                    "name_2": other["name"],
                    "similarity_score": score,
                    "duplicate_type": "fuzzy"
                })
                seen.add(j)
        seen.add(i)

    fuzzy_df = pd.DataFrame(fuzzy_dupes)
    logger.info(f"Fuzzy duplicates found: {len(fuzzy_df)}")
    return exact_dupes, fuzzy_df


def detect_outliers(engine) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT id, price, availability_365, number_of_reviews FROM listings_summary",
        engine
    )

    results = []
    for col in ["price", "availability_365", "number_of_reviews"]:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_count = ((series < lower) | (series > upper)).sum()
        results.append({
            "column": col,
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "lower_bound": round(lower, 2),
            "upper_bound": round(upper, 2),
            "outlier_count": int(outlier_count),
            "outlier_rate_%": round((outlier_count / len(series)) * 100, 2),
        })

    return pd.DataFrame(results)


def validate_domain(engine) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT id, price, latitude, longitude, minimum_nights FROM listings_summary",
        engine
    )

    violations = []

    # Price must not be negative
    price_series = pd.to_numeric(df["price"].astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce")
    neg_price = (price_series < 0).sum()
    violations.append({"rule": "price >= 0", "violations": int(neg_price)})

    # Latitude must be between 46.0 and 47.0 for Vaud
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    bad_lat = ((lat < 46.0) | (lat > 47.0)).sum()
    violations.append({"rule": "latitude in [46.0, 47.0]", "violations": int(bad_lat)})

    # Longitude must be between 6.0 and 7.5 for Vaud
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    bad_lon = ((lon < 6.0) | (lon > 7.5)).sum()
    violations.append({"rule": "longitude in [6.0, 7.5]", "violations": int(bad_lon)})

    # Minimum nights must be positive
    min_nights = pd.to_numeric(df["minimum_nights"], errors="coerce")
    bad_nights = (min_nights <= 0).sum()
    violations.append({"rule": "minimum_nights > 0", "violations": int(bad_nights)})

    return pd.DataFrame(violations)


def main():
    engine = get_engine()
    logger.info("Starting quality checks...")

    # Duplicates
    exact_dupes, fuzzy_dupes = detect_duplicates(engine)
    exact_dupes.to_csv(OUTPUT_DIR / "duplicates_exact.csv", index=False)
    fuzzy_dupes.to_csv(OUTPUT_DIR / "duplicates_fuzzy.csv", index=False)

    # Outliers
    outliers = detect_outliers(engine)
    outliers.to_csv(OUTPUT_DIR / "outliers_report.csv", index=False)

    # Domain validation
    domain = validate_domain(engine)
    domain.to_csv(OUTPUT_DIR / "domain_violations.csv", index=False)

    print("\n--- OUTLIER DETECTION ---")
    print(outliers.to_string(index=False))

    print("\n--- DOMAIN VALIDATION ---")
    print(domain.to_string(index=False))

    print(f"\n--- DUPLICATES ---")
    print(f"Exact duplicates: {len(exact_dupes)}")
    print(f"Fuzzy duplicates: {len(fuzzy_dupes)}")

    logger.info("Quality checks complete.")


if __name__ == "__main__":
    main()