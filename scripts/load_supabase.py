"""
Load dallas_school_insights.parquet into Supabase public.schools.

Usage
-----
    python scripts/load_supabase.py

Required environment variables
-------------------------------
    SUPABASE_URL         https://<project-ref>.supabase.co
    SUPABASE_SERVICE_KEY service_role JWT  (NOT the anon key)

Optional
--------
    DOTENV_PATH   path to a .env file (default: .env in the project root)

The script:
  1. Reads data/processed/dallas_school_insights.parquet
  2. Deletes all existing rows from public.schools
  3. Inserts all 60 rows in chunks
  4. Validates that exactly 60 rows are present after load
  5. Appends one record to public.pipeline_runs

The local Parquet file is always the source of truth; Supabase is the
downstream read replica used by the dashboard.
"""
from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── optional .env support ─────────────────────────────────────────────────────

try:
    from dotenv import load_dotenv as _load_dotenv
    _env_path = os.environ.get("DOTENV_PATH", Path(__file__).parent.parent / ".env")
    _load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv is optional; set env vars directly if not installed

# ── constants ─────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
PARQUET = ROOT / "data" / "processed" / "dallas_school_insights.parquet"
EXPECTED_ROWS = 60
_CHUNK_SIZE = 500

# ── helpers ───────────────────────────────────────────────────────────────────


def _require_env(key: str) -> str:
    """Return the value of an environment variable or raise RuntimeError."""
    val = os.environ.get(key, "").strip()
    if not val:
        raise RuntimeError(
            f"Required environment variable not set: {key}\n"
            "Copy .env.example to .env and fill in your Supabase credentials."
        )
    return val


def _nan_to_none(row: dict) -> dict:
    """
    Replace NaN / pd.NA with None so the dict is JSON-serialisable.
    Also converts numpy scalar types to Python natives.
    """
    import numpy as np

    result: dict = {}
    for k, v in row.items():
        # pd.NA (pandas nullable extension types)
        try:
            import pandas as pd
            if v is pd.NA:
                result[k] = None
                continue
        except ImportError:
            pass

        if v is None:
            result[k] = None
        elif isinstance(v, float) and math.isnan(v):
            result[k] = None
        elif isinstance(v, np.floating):
            f = float(v)
            result[k] = None if math.isnan(f) else f
        elif isinstance(v, np.integer):
            result[k] = int(v)
        elif isinstance(v, np.bool_):
            result[k] = bool(v)
        else:
            result[k] = v

    return result


# ── main load function ────────────────────────────────────────────────────────


def load(parquet_path: Path = PARQUET) -> dict:
    """
    Truncate-and-reload public.schools from *parquet_path*.

    Returns a dict with keys ``loaded``, ``expected``, ``ok``.
    Raises RuntimeError on missing credentials or row-count mismatch.
    """
    import pandas as pd
    from supabase import create_client

    url = _require_env("SUPABASE_URL")
    key = _require_env("SUPABASE_SERVICE_KEY")
    client = create_client(url, key)

    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Parquet file not found: {parquet_path}\n"
            "Run scripts/build_final.py first."
        )

    df = pd.read_parquet(parquet_path)

    # ── 1. Delete existing rows ───────────────────────────────────────────────
    # campus_id is always a non-empty 9-digit string, so this matches all rows.
    client.table("schools").delete().neq("campus_id", "").execute()

    # ── 2. Insert in chunks ───────────────────────────────────────────────────
    rows = [_nan_to_none(r) for r in df.to_dict(orient="records")]
    for i in range(0, len(rows), _CHUNK_SIZE):
        client.table("schools").insert(rows[i : i + _CHUNK_SIZE]).execute()

    # ── 3. Validate row count ─────────────────────────────────────────────────
    response = client.table("schools").select("campus_id").execute()
    loaded = len(response.data)
    if loaded != EXPECTED_ROWS:
        raise RuntimeError(
            f"Row count mismatch after load: expected {EXPECTED_ROWS}, got {loaded}"
        )

    # ── 4. Audit record ───────────────────────────────────────────────────────
    client.table("pipeline_runs").insert(
        {
            "source_file": str(parquet_path.resolve()),
            "row_count": loaded,
            "notes": (
                f"Phase 6 load — {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
            ),
        }
    ).execute()

    return {"loaded": loaded, "expected": EXPECTED_ROWS, "ok": True}


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        result = load()
        print(
            f"Load complete: {result['loaded']} / {result['expected']} rows loaded."
        )
        sys.exit(0)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
