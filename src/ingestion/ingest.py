import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

import pandas as pd
from sqlalchemy import create_engine, text

from src.utils.config import RAW_DATA_DIR, DB_CONFIG, CITY, METADATA_TABLE
from src.utils.logger import get_logger

logger = get_logger("ingest")

TABLE_MAP = {
    "listings.csv": "listings_summary",
    "listings.csv.gz": "listings_detailed",
    "reviews.csv": "reviews_summary",
    "reviews.csv.gz": "reviews_detailed",
    "calendar.csv.gz": "calendar",
    "neighbourhoods.csv": "neighbourhoods",
    "neighbourhoods.geojson": "neighbourhoods_geo",
}


def get_engine():
    url = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    return create_engine(url)


def retry(func, *args, attempts=3, delay=2, **kwargs):
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            logger.warning(f"Attempt {attempt}/{attempts} failed: {e}")
            time.sleep(delay)
    logger.error(f"All {attempts} attempts failed.")
    raise last_err


def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_metadata_table(engine):
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {METADATA_TABLE} (
                id SERIAL PRIMARY KEY,
                city TEXT NOT NULL,
                source_file TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                target_table TEXT NOT NULL,
                row_count INTEGER,
                status TEXT,
                ingested_at TIMESTAMP DEFAULT NOW()
            );
        """))


def already_ingested(engine, source_file: str, hash_value: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(
            text(f"""
                SELECT 1 FROM {METADATA_TABLE}
                WHERE source_file = :f AND file_hash = :h AND status = 'success'
                LIMIT 1
            """),
            {"f": source_file, "h": hash_value},
        ).fetchone()
    return result is not None


def record_ingestion(engine, source_file, hash_value, target_table, row_count, status):
    with engine.begin() as conn:
        conn.execute(
            text(f"""
                INSERT INTO {METADATA_TABLE}
                    (city, source_file, file_hash, target_table, row_count, status)
                VALUES (:city, :f, :h, :t, :r, :s)
            """),
            {"city": CITY, "f": source_file, "h": hash_value,
             "t": target_table, "r": row_count, "s": status},
        )


def load_tabular(path: Path, table_name: str, engine):
    compression = "gzip" if path.suffix == ".gz" else None
    df = pd.read_csv(path, compression=compression, low_memory=False)
    df["city"] = CITY
    df["source_file"] = path.name
    df["ingested_at"] = datetime.utcnow()
    df.to_sql(table_name, engine, if_exists="append", index=False)
    return len(df)


def load_geojson(path: Path, table_name: str, engine):
    with open(path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    features = geo.get("features", [])
    rows = []
    for feat in features:
        rows.append({
            "properties": json.dumps(feat.get("properties", {})),
            "geometry": json.dumps(feat.get("geometry", {})),
            "city": CITY,
            "source_file": path.name,
            "ingested_at": datetime.utcnow(),
        })
    df = pd.DataFrame(rows)
    df.to_sql(table_name, engine, if_exists="append", index=False)
    return len(df)


def ingest_file(path: Path, engine):
    table_name = TABLE_MAP.get(path.name)

    if table_name is None:
        logger.warning(f"No table mapping for {path.name}, skipping.")
        return

    hash_value = file_hash(path)

    if already_ingested(engine, path.name, hash_value):
        logger.info(f"Skipping {path.name} — already ingested, unchanged.")
        return

    try:
        if path.suffix == ".geojson":
            row_count = retry(load_geojson, path, table_name, engine)
        else:
            row_count = retry(load_tabular, path, table_name, engine)
        record_ingestion(engine, path.name, hash_value, table_name, row_count, "success")
        logger.info(f"Ingested {path.name} -> {table_name} ({row_count} rows)")
    except Exception as e:
        record_ingestion(engine, path.name, hash_value, table_name, 0, "failed")
        logger.error(f"Failed to ingest {path.name}: {e}")


def main():
    logger.info(f"Starting ingestion for city='{CITY}' from {RAW_DATA_DIR}")
    engine = get_engine()
    ensure_metadata_table(engine)

    files = sorted(RAW_DATA_DIR.glob("*"))
    if not files:
        logger.warning(f"No files found in {RAW_DATA_DIR}")
        return

    for path in files:
        if path.is_file():
            ingest_file(path, engine)

    logger.info("Ingestion run complete.")


if __name__ == "__main__":
    main()
