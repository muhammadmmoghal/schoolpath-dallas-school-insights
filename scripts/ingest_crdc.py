"""
Phase 3 – Step 1: Download and extract the 2021-22 CRDC school-level ZIP archive.

The full ZIP is 832 MB.  It is streamed to data/raw/crdc_2021_22.zip, then the
seven needed CSV members are extracted to data/raw/crdc_2021_22/SCH/.

Per-member metadata JSON files record COMBOKEY row counts, column lists, SHA-256,
and extraction size so the build step can verify completeness without re-reading
large files.

Skip logic
----------
If all seven extracted CSVs already exist and --force is not set, skip the
network request.  If --force is set, re-download; if the ZIP's SHA-256 matches
the stored hash the ZIP is not re-extracted (content unchanged).
"""

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

CRDC_ZIP_URL = "https://civilrightsdata.ed.gov/assets/ocr/docs/2021-22-crdc-data.zip"
CRDC_COLLECTION_YEAR = "2021-22"

_ROOT = Path(__file__).parent.parent
RAW_DIR = _ROOT / "data" / "raw"
CRDC_DIR = RAW_DIR / "crdc_2021_22"
ZIP_PATH = RAW_DIR / "crdc_2021_22.zip"
ZIP_META_PATH = RAW_DIR / "crdc_2021_22_zip_metadata.json"

# Exact ZIP member paths for the seven files this pipeline uses
CRDC_MEMBERS: list[str] = [
    "SCH/Enrollment.csv",
    "SCH/Suspensions.csv",
    "SCH/Expulsions.csv",
    "SCH/Restraint and Seclusion.csv",
    "SCH/Harassment and Bullying.csv",
    "SCH/Referrals and Arrests.csv",
    "SCH/Offenses.csv",
]

_CHUNK = 4 * 1024 * 1024   # 4 MB streaming chunk


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _extracted_paths() -> list[Path]:
    return [CRDC_DIR / member for member in CRDC_MEMBERS]


def _all_extracted() -> bool:
    return all(p.exists() for p in _extracted_paths())


def _member_metadata(member: str, extracted_path: Path) -> dict:
    """Count header + data rows and read column list from an extracted CSV."""
    columns: list[str] = []
    row_count = 0
    try:
        with open(extracted_path, "r", encoding="utf-8-sig", errors="replace") as f:
            for i, line in enumerate(f):
                if i == 0:
                    columns = [c.strip() for c in line.split(",")]
                else:
                    row_count += 1
    except OSError:
        pass
    return {
        "zip_member": member,
        "extracted_path": str(extracted_path),
        "extracted_size_bytes": extracted_path.stat().st_size if extracted_path.exists() else 0,
        "sha256": _sha256_file(extracted_path) if extracted_path.exists() else None,
        "column_count": len(columns),
        "columns": columns,
        "data_row_count": row_count,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Download
# ──────────────────────────────────────────────────────────────────────────────


def _download_zip(force_overwrite: bool = False) -> str:
    """
    Stream the CRDC ZIP to disk.  Returns the SHA-256 of the downloaded file.
    If the file already exists and force_overwrite is False, return the stored hash.
    """
    if ZIP_PATH.exists() and not force_overwrite:
        print(f"  ZIP   {ZIP_PATH.name} already exists; skipping download")
        if ZIP_META_PATH.exists():
            return json.loads(ZIP_META_PATH.read_text()).get("sha256", "")
        return _sha256_file(ZIP_PATH)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"  GET   {CRDC_ZIP_URL}")
    print(f"  Dest  {ZIP_PATH}")
    print(f"  NOTE  The CRDC archive is 832 MB — this may take several minutes.")

    h = hashlib.sha256()
    downloaded = 0
    last_report = 0

    retrieved_utc = datetime.now(timezone.utc).isoformat()
    with requests.get(CRDC_ZIP_URL, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        with open(ZIP_PATH, "wb") as out:
            for chunk in resp.iter_content(chunk_size=_CHUNK):
                out.write(chunk)
                h.update(chunk)
                downloaded += len(chunk)
                mb = downloaded // (1024 * 1024)
                if mb - last_report >= 50:
                    total_mb = total // (1024 * 1024) if total else "?"
                    print(f"  ...   {mb} / {total_mb} MB", flush=True)
                    last_report = mb

    sha256 = h.hexdigest()
    print(f"  OK    {downloaded:,} bytes  sha256={sha256[:12]}...")

    meta = {
        "source_url": CRDC_ZIP_URL,
        "retrieved_utc": retrieved_utc,
        "sha256": sha256,
        "byte_size": downloaded,
        "collection_year": CRDC_COLLECTION_YEAR,
        "zip_file": str(ZIP_PATH),
    }
    ZIP_META_PATH.write_text(json.dumps(meta, indent=2))
    return sha256


# ──────────────────────────────────────────────────────────────────────────────
# Extraction
# ──────────────────────────────────────────────────────────────────────────────


def _extract_members(force: bool = False) -> list[dict]:
    """Extract the seven needed CSV members from the ZIP.  Returns per-member metadata."""
    CRDC_DIR.mkdir(parents=True, exist_ok=True)
    (CRDC_DIR / "SCH").mkdir(exist_ok=True)

    all_meta: list[dict] = []
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        available = set(zf.namelist())
        for member in CRDC_MEMBERS:
            extracted_path = CRDC_DIR / member

            if extracted_path.exists() and not force:
                print(f"  SKIP  {member}  (already extracted)")
                meta = _member_metadata(member, extracted_path)
                meta["action"] = "skipped"
                all_meta.append(meta)
                continue

            if member not in available:
                print(f"  WARN  {member!r} not found in ZIP", file=sys.stderr)
                all_meta.append({"zip_member": member, "error": "not_in_zip"})
                continue

            print(f"  EXTR  {member} ...", end=" ", flush=True)
            zf.extract(member, path=CRDC_DIR)
            print(f"OK ({extracted_path.stat().st_size // (1024*1024)} MB)")

            meta = _member_metadata(member, extracted_path)
            meta["action"] = "extracted"
            all_meta.append(meta)

    return all_meta


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────────────


def ingest_crdc(force: bool = False) -> list[dict]:
    print(f"\nCRDC ingestion — collection year {CRDC_COLLECTION_YEAR}")
    print(f"Source: {CRDC_ZIP_URL}\n")

    # Step 1: download ZIP
    existing_sha256 = ""
    if ZIP_PATH.exists() and ZIP_META_PATH.exists():
        existing_sha256 = json.loads(ZIP_META_PATH.read_text()).get("sha256", "")

    zip_sha256 = _download_zip(force_overwrite=force and not _all_extracted())

    # Step 2: skip extraction if content unchanged and files present
    if _all_extracted() and zip_sha256 == existing_sha256 and not force:
        print("\n  All extracted files present and ZIP hash unchanged; skipping extraction.")
        # Still return per-file metadata
        return [_member_metadata(m, CRDC_DIR / m) for m in CRDC_MEMBERS]

    # Step 3: extract
    print(f"\nExtracting members from {ZIP_PATH.name} ...")
    member_meta = _extract_members(force=force)

    # Step 4: write combined metadata
    combined_meta_path = RAW_DIR / "crdc_2021_22_members_metadata.json"
    combined = {
        "collection_year": CRDC_COLLECTION_YEAR,
        "zip_url": CRDC_ZIP_URL,
        "zip_sha256": zip_sha256,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "members": member_meta,
    }
    combined_meta_path.write_text(json.dumps(combined, indent=2))

    print(f"\nDone. Metadata: {combined_meta_path}")
    return member_meta


if __name__ == "__main__":
    force = "--force" in sys.argv
    try:
        ingest_crdc(force=force)
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)
