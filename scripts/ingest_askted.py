"""
Phase 1 – Step 1: Fetch the AskTED site-address roster.

Saves:
  data/raw/askted_directory.csv        – full statewide CSV from TEA
  data/raw/askted_fetch_metadata.json  – provenance: URL, timestamp, SHA-256,
                                         byte size, row/column counts, update-date range
"""

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ASKTED_URL = "https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadSite.aspx"

_ROOT = Path(__file__).parent.parent
RAW_DIR = _ROOT / "data" / "raw"
RAW_FILE = RAW_DIR / "askted_directory.csv"
METADATA_FILE = RAW_DIR / "askted_fetch_metadata.json"


def fetch_askted() -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    retrieved_utc = datetime.now(timezone.utc).isoformat()
    print(f"Fetching {ASKTED_URL} ...")

    resp = requests.get(ASKTED_URL, timeout=120)
    resp.raise_for_status()

    content = resp.content
    sha256 = hashlib.sha256(content).hexdigest()

    RAW_FILE.write_bytes(content)

    # Parse only for metadata; keep original bytes in the raw file
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(text.splitlines())
    rows = list(reader)
    columns = list(reader.fieldnames or [])

    update_dates = sorted(
        r.get("Update Date", "").strip()
        for r in rows
        if r.get("Update Date", "").strip()
    )

    metadata = {
        "source_url": ASKTED_URL,
        "retrieved_utc": retrieved_utc,
        "http_status": resp.status_code,
        "content_type": resp.headers.get("Content-Type", ""),
        "content_disposition": resp.headers.get("Content-Disposition", ""),
        "sha256": sha256,
        "byte_size": len(content),
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
        "update_date_min": update_dates[0] if update_dates else None,
        "update_date_max": update_dates[-1] if update_dates else None,
        "raw_file": str(RAW_FILE),
    }

    METADATA_FILE.write_text(json.dumps(metadata, indent=2))

    print(f"Rows:     {len(rows)}")
    print(f"Columns:  {len(columns)}")
    print(f"SHA-256:  {sha256}")
    print(f"Raw CSV:  {RAW_FILE}")
    print(f"Metadata: {METADATA_FILE}")

    return metadata


if __name__ == "__main__":
    try:
        fetch_askted()
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        sys.exit(1)
