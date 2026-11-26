"""Simple SQLite3 database helper for Chicago Crime Analytics."""

import os
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "chicago_crime.db"
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"
COMMUNITY_CSV = BASE_DIR / "data" / "processed" / "chicago_city_community_cleaned.csv"
CRIME_CSV = BASE_DIR / "data" / "processed" / "chicago_crime_analysis_ready.csv"


def get_db_path() -> str:
    """Return the active SQLite database path."""
    return os.environ.get("CHICAGO_DB_PATH", str(DEFAULT_DB_PATH))


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with dictionary-style rows."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create tables/views if missing and seed from cleaned CSVs if empty."""
    conn = get_connection(db_path)
    try:
        if SCHEMA_PATH.exists():
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        community_count = conn.execute("SELECT COUNT(*) FROM community").fetchone()[0]
        if community_count == 0 and COMMUNITY_CSV.exists():
            df_comm = pd.read_csv(COMMUNITY_CSV)
            df_comm.to_sql("community", conn, if_exists="append", index=False)

        crime_count = conn.execute("SELECT COUNT(*) FROM crime").fetchone()[0]
        if crime_count == 0 and CRIME_CSV.exists():
            df_crime = pd.read_csv(CRIME_CSV)
            df_crime.to_sql("crime", conn, if_exists="append", index=False)

        conn.commit()
    finally:
        conn.close()
