"""
Phase 4 – Step 1b: Query the TEA ArcGIS FeatureServer for cohort school coordinates.

Source (verified in research/source_discovery.md):
  Layer: Schools 2024-25
  Item ID: 80c162b9008a40d681c127874722670f
  URL: https://services2.arcgis.com/5MVN2jsqIrNZD4tP/arcgis/rest/services/
       Schools_2024_to_2025/FeatureServer/0

Queries only the 60 cohort campus IDs (not the full statewide layer).
ArcGIS layer stores USER_School_Number with a leading apostrophe (TEA convention);
the SQL WHERE clause escapes this with doubled single-quotes.

Saves:
  data/raw/arcgis_schools_raw.json          – feature collection (git-ignored)
  data/raw/arcgis_schools_metadata.json     – provenance record (committed)
"""

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ARCGIS_LAYER_URL = (
    "https://services2.arcgis.com/5MVN2jsqIrNZD4tP/arcgis/rest"
    "/services/Schools_2024_to_2025/FeatureServer/0"
)
ARCGIS_QUERY_URL = ARCGIS_LAYER_URL + "/query"
ARCGIS_ITEM_ID = "80c162b9008a40d681c127874722670f"
ARCGIS_SOURCE_YEAR = "2024-25"
ARCGIS_ITEM_MODIFIED = "2026-01-15"

# Fields to retrieve (geometry also requested via returnGeometry=true)
_OUT_FIELDS = "USER_School_Number,USER_School_Name,USER_School_Site_City,School_Type"

_BATCH_SIZE = 50          # well under the 2000-record max; 2 batches for 60 schools
_BATCH_DELAY_S = 1.0      # courtesy pause between batch requests

_ROOT = Path(__file__).parent.parent
RAW_DIR = _ROOT / "data" / "raw"
PROCESSED_DIR = _ROOT / "data" / "processed"
COHORT_CSV = PROCESSED_DIR / "cohort_crdc.csv"
RAW_JSON = RAW_DIR / "arcgis_schools_raw.json"
META_PATH = RAW_DIR / "arcgis_schools_metadata.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_school_number(val) -> str:
    """Strip leading apostrophe and whitespace from a TEA campus number."""
    return str(val).strip().lstrip("'") if val is not None else ""


def _build_where_clause(campus_ids: list[str]) -> str:
    """
    Build an ArcGIS SQL WHERE clause to match campus IDs.

    USER_School_Number values in the layer have a leading apostrophe (TEA
    convention, e.g. '057802001). In ArcGIS SQL, a literal single-quote inside
    a string literal is escaped by doubling it, so:

        WHERE USER_School_Number IN ('''057802001', '''057803004')

    matches the stored values '057802001 and '057803004.

    Verified filter pattern from source_discovery.md:
        USER_District_Number='''057905'  → 248 Dallas ISD rows
    """
    escaped = [f"'''{cid}'" for cid in campus_ids]
    return f"USER_School_Number IN ({', '.join(escaped)})"


def _query_batch(campus_ids: list[str]) -> list[dict]:
    """Execute one ArcGIS query and return the feature list."""
    params = {
        "where": _build_where_clause(campus_ids),
        "outFields": _OUT_FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    resp = requests.get(ARCGIS_QUERY_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(
            f"ArcGIS API error {data['error'].get('code','?')}: "
            f"{data['error'].get('message','')}"
        )
    return data.get("features", [])


def ingest_arcgis(force: bool = False) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if RAW_JSON.exists() and not force:
        print(f"SKIP  {RAW_JSON.name}  (already exists; --force to re-download)")
        return RAW_JSON

    if not COHORT_CSV.exists():
        print(f"ERROR: {COHORT_CSV} not found. Run build_crdc.py first.", file=sys.stderr)
        sys.exit(1)

    import pandas as pd
    cohort = pd.read_csv(COHORT_CSV, usecols=["campus_id"], dtype=str)
    campus_ids = cohort["campus_id"].dropna().str.strip().tolist()
    print(f"Cohort campus IDs: {len(campus_ids)}")

    retrieved_utc = datetime.now(timezone.utc).isoformat()
    all_features: list[dict] = []
    n_batches = (len(campus_ids) + _BATCH_SIZE - 1) // _BATCH_SIZE

    for i in range(0, len(campus_ids), _BATCH_SIZE):
        batch = campus_ids[i : i + _BATCH_SIZE]
        batch_num = i // _BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{n_batches}: {len(batch)} IDs …", end=" ", flush=True)
        features = _query_batch(batch)
        print(f"{len(features)} features")
        all_features.extend(features)
        if i + _BATCH_SIZE < len(campus_ids):
            time.sleep(_BATCH_DELAY_S)

    # Deduplicate by normalized USER_School_Number
    seen: set[str] = set()
    deduped: list[dict] = []
    for feat in all_features:
        sn = _normalize_school_number(feat["attributes"].get("USER_School_Number", ""))
        if sn and sn not in seen:
            seen.add(sn)
            deduped.append(feat)

    result_obj = {
        "item_id": ARCGIS_ITEM_ID,
        "layer_url": ARCGIS_LAYER_URL,
        "source_year": ARCGIS_SOURCE_YEAR,
        "item_modified": ARCGIS_ITEM_MODIFIED,
        "retrieved_utc": retrieved_utc,
        "campus_ids_requested": len(campus_ids),
        "features_returned": len(deduped),
        "features": deduped,
    }
    raw_bytes = json.dumps(result_obj, indent=2).encode("utf-8")
    sha256 = _sha256_bytes(raw_bytes)

    RAW_JSON.write_bytes(raw_bytes)

    meta = {
        "source": "TEA ArcGIS Schools 2024-25",
        "item_id": ARCGIS_ITEM_ID,
        "layer_url": ARCGIS_LAYER_URL,
        "query_url": ARCGIS_QUERY_URL,
        "item_modified": ARCGIS_ITEM_MODIFIED,
        "source_year": ARCGIS_SOURCE_YEAR,
        "method": "GET",
        "out_fields": _OUT_FIELDS,
        "geometry_included": True,
        "spatial_reference": 4326,
        "retrieved_utc": retrieved_utc,
        "sha256": sha256,
        "byte_size": len(raw_bytes),
        "campus_ids_requested": len(campus_ids),
        "features_returned": len(deduped),
        "schema_summary": {
            "geometry_type": "esriGeometryPoint",
            "coordinate_fields": ["geometry.y → latitude", "geometry.x → longitude"],
            "attribute_fields": _OUT_FIELDS.split(","),
            "coordinate_system": "WGS84 (EPSG:4326)",
            "caveat": (
                "Coordinates are from a 2024-25 ArcGIS snapshot derived from AskTED. "
                "Point locations are geocoder output and may differ from the exact "
                "building footprint. Use for display only."
            ),
        },
    }
    META_PATH.write_text(json.dumps(meta, indent=2))

    print(
        f"OK    {RAW_JSON.name}"
        f"  features={len(deduped)}/{len(campus_ids)}"
        f"  sha256={sha256[:12]}…"
    )
    print(f"      metadata -> {META_PATH.name}")
    return RAW_JSON


if __name__ == "__main__":
    force = "--force" in sys.argv
    try:
        ingest_arcgis(force=force)
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)
    except (requests.RequestException, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
