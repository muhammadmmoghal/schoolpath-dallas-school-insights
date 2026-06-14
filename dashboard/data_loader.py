"""
Data loader for the SchoolPath Dallas dashboard.

Tries Supabase first; falls back to the local Parquet file when credentials
are absent or when the network call fails.  Callers receive a plain
pandas DataFrame and a string describing the active source.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
PARQUET = ROOT / "data" / "processed" / "dallas_school_insights.parquet"

FRIENDLY_SOURCE_LABELS: dict[str, str] = {
    "Supabase (live)": "Supabase database",
    "Local Parquet (fallback)": "Local processed dataset",
}


def friendly_source_label(internal_label: str) -> str:
    """Return the user-visible source label for a given internal source string."""
    return FRIENDLY_SOURCE_LABELS.get(internal_label, internal_label)


REQUIRED_COLUMNS = [
    "campus_id",
    "school_name",
    "district_name",
    "school_level",
    "operator_type",
    "enrollment",
    "accountability_rating_2025",
    "latitude",
    "longitude",
]


def _load_parquet() -> pd.DataFrame:
    if not PARQUET.exists():
        raise FileNotFoundError(
            f"Local fallback not found: {PARQUET}\n"
            "Run scripts/build_final.py to generate it."
        )
    return pd.read_parquet(PARQUET)


def _load_supabase() -> pd.DataFrame:
    """
    Fetch all rows from public.schools via the Supabase Python client.
    Raises if credentials are missing or the call fails.
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_ANON_KEY not set")

    from supabase import create_client  # noqa: PLC0415

    client = create_client(url, key)
    response = client.table("schools").select("*").execute()
    if not response.data:
        raise RuntimeError("Supabase returned no data")
    return pd.DataFrame(response.data)


def load_data() -> tuple[pd.DataFrame, str]:
    """
    Return (df, source_label).

    Tries Supabase first; falls back to local Parquet on any error.
    source_label is one of:
      "Supabase (live)"
      "Local Parquet (fallback)"
    """
    try:
        df = _load_supabase()
        source = "Supabase (live)"
    except Exception:
        df = _load_parquet()
        source = "Local Parquet (fallback)"

    _validate(df)
    return df, source


def _validate(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Loaded data is missing required columns: {missing}")
    if len(df) == 0:
        raise ValueError("Loaded data contains no rows")
