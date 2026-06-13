"""
Phase 2 – Step 1: Download the three 2024-25 TAPR campus-level CSV files.

Each download is a POST to the TEA SAS broker with dataset-specific form
parameters.  Raw CSVs are saved to data/raw/; per-file metadata JSON records
URL, POST params, timestamp, SHA-256, byte size, column list, and approximate
row count.

Skip logic:
  - If the raw file already exists and --force is not set, skip the network
    request entirely.
  - If --force is set, download; if the new content hash matches the stored
    hash, log "SAME" and do not overwrite the file.
"""

import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

TAPR_BROKER = "https://rptsvr1.tea.texas.gov/cgi/sas/broker"
TAPR_RELEASE_YEAR = 2025

_ROOT = Path(__file__).parent.parent
RAW_DIR = _ROOT / "data" / "raw"

_COMMON_PARAMS: list[tuple[str, str]] = [
    ("_service", "marykay"),
    ("_program", "perfrept.perfmast.sas"),
    ("_debug", "0"),
    ("tapr", "all_c"),
    ("ccyy", "2025"),
    ("sumlev", "C"),
    ("level", "Campus"),
    ("id", ""),
    ("prgopt", "reports/tapr/dd/dd_tapr_step_7.sas"),
    ("datafmt", "csv"),
]

TAPR_SOURCES: list[dict] = [
    {
        "name": "student",
        "official_filename": "2025 Campus Student Information.csv",
        "raw_filename": "tapr_student_2025.csv",
        "source_year": 2025,
        "measure_year": 2025,
        "extra_params": [
            ("dsname", "STUD"),
            ("key", "ETALL"),
            ("key", "NTALL"),
            ("key", "ETBIL"),
            ("key", "ETVOC"),
            ("key", "ETVHS"),
            ("key", "ETGIF"),
            ("key", "ETSPE"),
            ("key", "NTBIL"),
            ("key", "NTVOC"),
            ("key", "NTVHS"),
            ("key", "NTGIF"),
            ("key", "NTSPE"),
        ],
    },
    {
        "name": "attendance",
        "official_filename": "2025 Campus Attendance Absenteeism Dropout.csv",
        "raw_filename": "tapr_attendance_2025.csv",
        "source_year": 2025,
        "measure_year": 2024,
        "extra_params": [
            ("dsname", "DROP_ATT"),
            ("key", "AT24"),
            ("key", "CA24"),
            ("var_type", "N"),
            ("var_type", "D"),
            ("var_type", "R"),
        ],
    },
    {
        "name": "staff",
        "official_filename": "2025 Campus Staff Information.csv",
        "raw_filename": "tapr_staff_2025.csv",
        "source_year": 2025,
        "measure_year": 2025,
        "extra_params": [
            ("dsname", "STAF"),
            ("key", "ST00F"),
            ("key", "ST01F"),
            ("key", "ST06F"),
            ("key", "ST11F"),
            ("key", "ST21F"),
            ("key", "ST30F"),
            ("key", "STKID"),
            ("key", "SHEXP"),
            ("key", "SHTEN"),
            ("key", "SLEXP"),
            ("key", "SLTEN"),
            ("key", "STEXP"),
            ("key", "STTEN"),
            ("key", "STTOS"),
            ("key", "SUTOS"),
            ("key", "SSTOS"),
            ("key", "STURN"),
            ("key", "PSCTOSA"),
        ],
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _schema_summary(content: bytes) -> dict:
    """Extract column names and estimated data-row count from CSV bytes."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))

    all_rows: list[list[str]] = []
    for i, row in enumerate(reader):
        all_rows.append(row)
        if i >= 2:          # only need the first few rows for column detection
            break

    # Detect machine header row: first row whose first field is "CAMPUS"
    header_idx = 0
    for i, row in enumerate(all_rows):
        if row and row[0].strip().strip('"') == "CAMPUS":
            header_idx = i
            break

    columns = [c.strip() for c in all_rows[header_idx]] if all_rows else []
    estimated_data_rows = max(0, text.count("\n") - header_idx - 1)

    return {
        "columns": columns,
        "data_row_count_estimated": estimated_data_rows,
        "header_row_index": header_idx,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Per-source fetch
# ──────────────────────────────────────────────────────────────────────────────


def fetch_tapr_source(source: dict, force: bool = False) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = RAW_DIR / source["raw_filename"]
    meta_path = RAW_DIR / source["raw_filename"].replace(".csv", "_metadata.json")
    params = _COMMON_PARAMS + source["extra_params"]

    if raw_path.exists() and not force:
        print(f"  SKIP  {source['raw_filename']}  (already exists; --force to re-download)")
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        return {"skipped": True, "raw_file": str(raw_path)}

    retrieved_utc = datetime.now(timezone.utc).isoformat()
    print(f"  POST  {TAPR_BROKER}  [{source['name']}] ...")

    resp = requests.post(TAPR_BROKER, data=params, timeout=180)
    resp.raise_for_status()

    content = resp.content
    new_sha256 = _sha256_of(content)

    # Hash-based dedup: don't overwrite if byte-for-byte identical to existing file
    if raw_path.exists():
        existing_sha256 = _sha256_of(raw_path.read_bytes())
        if existing_sha256 == new_sha256:
            print(f"  SAME  content unchanged (sha256={new_sha256[:12]}…); skipping write")
            if meta_path.exists():
                return json.loads(meta_path.read_text())

    raw_path.write_bytes(content)

    schema = _schema_summary(content)
    metadata = {
        "source_name": source["name"],
        "official_filename": source["official_filename"],
        "raw_filename": source["raw_filename"],
        "source_url": TAPR_BROKER,
        "http_method": "POST",
        "post_params": params,
        "retrieved_utc": retrieved_utc,
        "http_status": resp.status_code,
        "content_type": resp.headers.get("Content-Type", ""),
        "sha256": new_sha256,
        "byte_size": len(content),
        "source_year": source["source_year"],
        "measure_year": source["measure_year"],
        "schema_summary": schema,
        "raw_file": str(raw_path),
    }
    meta_path.write_text(json.dumps(metadata, indent=2))

    print(
        f"  OK    {source['raw_filename']}"
        f"  rows~{schema['data_row_count_estimated']}"
        f"  sha256={new_sha256[:12]}…"
    )
    return metadata


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────────────


def ingest_tapr(force: bool = False) -> list[dict]:
    print(f"\nTAPR ingestion — release year {TAPR_RELEASE_YEAR}")
    print(f"Broker: {TAPR_BROKER}\n")

    all_meta: list[dict] = []
    for source in TAPR_SOURCES:
        meta = fetch_tapr_source(source, force=force)
        all_meta.append(meta)

    print(f"\nDone. {len(all_meta)} TAPR sources processed.")
    return all_meta


if __name__ == "__main__":
    force = "--force" in sys.argv
    try:
        ingest_tapr(force=force)
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        sys.exit(1)
