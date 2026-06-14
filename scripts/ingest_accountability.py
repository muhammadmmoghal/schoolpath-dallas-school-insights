"""
Phase 4 – Step 1a: Download the 2025 TEA campus accountability summary CSV.

Endpoint (GET, no authentication):
  https://rptsvr1.tea.texas.gov/cgi/sas/broker/
  with query parameters from tapr_discovery.md §2025 Campus Accountability Ratings

Saves:
  data/raw/accountability_2025.csv             – full statewide CSV (git-ignored)
  data/raw/accountability_2025_metadata.json   – provenance record (committed)
"""

import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ACCT_URL = (
    "https://rptsvr1.tea.texas.gov/cgi/sas/broker/"
    "?_service=marykay"
    "&_program=perfrept.perfmast.sas"
    "&_debug=0"
    "&ccyy=2025"
    "&dsname=RATE"
    "&sumlev=C"
    "&key=RATE"
    "&key=GRD"
    "&key=FLAG"
    "&datafmt=C"
    "&prgopt=reports%2Facct%2Fdd%2Fdd_get_data.sas"
)

ACCT_SOURCE_YEAR = 2025
OFFICIAL_FILENAME = "2025 Campus Accountability Summary.csv"
PUBLIC_PAGE = (
    "https://tea.texas.gov/school-and-district-leaders/accountability/"
    "academic-accountability/performance-reporting/"
    "2025-accountability-rating-system"
)

_ROOT = Path(__file__).parent.parent
RAW_DIR = _ROOT / "data" / "raw"
RAW_CSV = RAW_DIR / "accountability_2025.csv"
META_PATH = RAW_DIR / "accountability_2025_metadata.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _schema_summary(content: bytes) -> dict:
    """Extract column names and estimated row count from the CSV bytes."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))

    rows: list[list[str]] = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= 3:
            break

    # Find the machine-name header row (starts with CAMPUS)
    header_idx = 0
    for i, row in enumerate(rows):
        if row and row[0].strip().strip('"') == "CAMPUS":
            header_idx = i
            break

    columns = [c.strip() for c in rows[header_idx]] if rows else []
    estimated_data_rows = max(0, text.count("\n") - header_idx - 1)
    return {
        "columns": columns,
        "column_count": len(columns),
        "header_row_index": header_idx,
        "data_row_count_estimated": estimated_data_rows,
    }


def ingest_accountability(force: bool = False) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if RAW_CSV.exists() and not force:
        print(f"SKIP  {RAW_CSV.name}  (already exists; --force to re-download)")
        return RAW_CSV

    print(f"GET  {ACCT_URL[:80]}…")
    retrieved_utc = datetime.now(timezone.utc).isoformat()

    resp = requests.get(ACCT_URL, timeout=120)
    resp.raise_for_status()

    content = resp.content
    sha256 = _sha256_bytes(content)

    if force and RAW_CSV.exists():
        if _sha256_file(RAW_CSV) == sha256:
            print(f"SAME  content unchanged (sha256={sha256[:12]}…); file not rewritten")
            return RAW_CSV

    RAW_CSV.write_bytes(content)

    schema = _schema_summary(content)

    meta = {
        "source": "TEA 2025 Campus Accountability Summary",
        "official_filename": OFFICIAL_FILENAME,
        "public_page": PUBLIC_PAGE,
        "url": ACCT_URL,
        "source_year": ACCT_SOURCE_YEAR,
        "method": "GET",
        "http_status": resp.status_code,
        "content_type": resp.headers.get("Content-Type", ""),
        "retrieved_utc": retrieved_utc,
        "sha256": sha256,
        "byte_size": len(content),
        "row_count": schema["data_row_count_estimated"],
        "schema_summary": schema,
    }
    META_PATH.write_text(json.dumps(meta, indent=2))

    print(
        f"OK    {RAW_CSV.name}"
        f"  rows~{schema['data_row_count_estimated']}"
        f"  cols={schema['column_count']}"
        f"  sha256={sha256[:12]}…"
    )
    print(f"      metadata -> {META_PATH.name}")
    return RAW_CSV


if __name__ == "__main__":
    force = "--force" in sys.argv
    try:
        ingest_accountability(force=force)
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        sys.exit(1)
