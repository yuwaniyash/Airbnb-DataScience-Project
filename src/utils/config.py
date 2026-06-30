import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Project root - three levels up from this file (src/utils/config.py -> src/utils -> src -> root)
BASE_DIR = Path(__file__).resolve().parents[2]

# City being processed - change this (or set CITY env var) to switch cities with zero code changes
CITY = os.getenv("CITY", "vaud")

# Raw data location
RAW_DATA_DIR = BASE_DIR / "data" / "raw files" / CITY

# Database connection - matches docker-compose.yml exactly
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "user": os.getenv("DB_USER", "vaud_user"),
    "password": os.getenv("DB_PASSWORD", "vaud_pass"),
    "dbname": os.getenv("DB_NAME", "vaud_airbnb"),
}

# Metadata table name - tracks ingestion/processing/validation runs for lineage (Section 3.5)
METADATA_TABLE = "pipeline_metadata"