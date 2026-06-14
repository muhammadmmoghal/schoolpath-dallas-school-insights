"""
Phase 4 – Step 2: Join accountability ratings and ArcGIS coordinates to the cohort.

Reads:
  data/processed/cohort_crdc.csv             – Phase 3 output (60 rows)
  data/raw/accountability_2025.csv           – TEA statewide accountability
  data/raw/arcgis_schools_raw.json           – ArcGIS feature collection

Outputs:
  data/processed/cohort_enriched.csv         – 60-row cohort with all Phase 4 fields
  data/processed/cohort_enriched.parquet     – same, typed nullable numerics
  data/processed/accountability_join_report.json
  data/processed/arcgis_join_report.json
  data/processed/data_dictionary.json        – Phase 4 entries appended
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

_ROOT = Path(__file__).parent.parent
RAW_DIR = _ROOT / "data" / "raw"
PROCESSED_DIR = _ROOT / "data" / "processed"

COHORT_CRDC = PROCESSED_DIR / "cohort_crdc.csv"
ACCT_CSV = RAW_DIR / "accountability_2025.csv"
ARCGIS_JSON = RAW_DIR / "arcgis_schools_raw.json"
DD_PATH = PROCESSED_DIR / "data_dictionary.json"

ACCT_SOURCE_YEAR = 2025
ARCGIS_SOURCE_YEAR = "2024-25"

_RATED_CODES: frozenset[str] = frozenset({"A", "B", "C", "D", "F"})
_NOT_RATED = "Not Rated"

# ──────────────────────────────────────────────────────────────────────────────
# Field maps
# ──────────────────────────────────────────────────────────────────────────────

# Required fields that must exist in the accountability CSV
_REQUIRED_ACCT: dict[str, str] = {
    "C_RATING": "accountability_rating_2025",
    "CDALLS":   "accountability_score_2025",
}

# Optional fields: included only when present in the downloaded CSV
_OPTIONAL_ACCT: dict[str, str] = {
    "GRDTYPE":    "acct_grade_type_2025",
    "GRDSPAN":    "acct_grade_span_2025",
    "GRDLOW":     "acct_grade_low_2025",
    "GRDHIGH":    "acct_grade_high_2025",
    "CFLCHART":   "acct_charter_flag_2025",
    "CFLAEC":     "acct_alt_ed_flag_2025",
    "CFLAEATYPE": "acct_alt_ed_type_2025",
    "CFLDAEP":    "acct_daep_flag_2025",
    "CFLJJ":      "acct_jj_flag_2025",
    "CFLALTED":   "acct_alted_flag_2025",
    "CFLRTF":     "acct_residential_flag_2025",
}

# ──────────────────────────────────────────────────────────────────────────────
# Normalization helpers (importable by tests)
# ──────────────────────────────────────────────────────────────────────────────


def normalize_campus_id_acct(val) -> Optional[str]:
    """Strip whitespace; return a 9-digit string or None if invalid.

    Accountability CSV uses plain 9-digit IDs (no leading apostrophe).
    """
    if val is None:
        return None
    s = str(val).strip().lstrip("'")
    return s if (s.isdigit() and len(s) == 9) else None


def derive_accountability_status(rating: Optional[str]) -> Optional[str]:
    """
    Map a C_RATING value to a status string.

    "Rated"     – campus received a letter grade (A/B/C/D/F)
    "Not Rated" – campus is in the file but explicitly rated "Not Rated"
    None        – campus is not in the accountability file (missing)
    """
    if rating is None or (isinstance(rating, float)):
        return None
    r = str(rating).strip()
    if r in _RATED_CODES:
        return "Rated"
    if r == _NOT_RATED:
        return _NOT_RATED
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Accountability parsing
# ──────────────────────────────────────────────────────────────────────────────


def _find_campus_header_row(path: Path) -> int:
    """Return the 0-based index of the row whose first field is CAMPUS."""
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for i, line in enumerate(fh):
            first = line.split(",")[0].strip().strip('"')
            if first == "CAMPUS":
                return i
            if i >= 5:
                break
    return 0


def _load_accountability(cohort_ids: set[str]) -> pd.DataFrame:
    """
    Read the statewide accountability CSV, filter to cohort campus IDs,
    and normalize fields to output column names.

    Returns a DataFrame with 'campus_id' plus all mapped output columns.
    """
    if not ACCT_CSV.exists():
        print(f"ERROR: {ACCT_CSV} not found. Run ingest_accountability.py first.", file=sys.stderr)
        sys.exit(1)

    header_row = _find_campus_header_row(ACCT_CSV)
    skip = list(range(header_row)) if header_row > 0 else []

    raw = pd.read_csv(
        ACCT_CSV,
        dtype=str,
        encoding="utf-8-sig",
        skiprows=skip,
        header=0,
        low_memory=False,
    )

    # Normalize campus ID
    raw["campus_id"] = raw["CAMPUS"].apply(normalize_campus_id_acct)
    invalid = raw["campus_id"].isna()
    if invalid.any():
        print(f"  [accountability] {invalid.sum()} rows with invalid CAMPUS dropped", file=sys.stderr)
    raw = raw[~invalid].copy()

    # Filter to cohort
    subset = raw[raw["campus_id"].isin(cohort_ids)].copy()
    dupes = subset.duplicated(subset=["campus_id"], keep="first")
    if dupes.any():
        print(f"  [accountability] {dupes.sum()} duplicate campus_id rows dropped", file=sys.stderr)
        subset = subset[~dupes].copy()

    # Build output DataFrame
    out: dict[str, list] = {"campus_id": subset["campus_id"].tolist()}

    for src_col, out_col in _REQUIRED_ACCT.items():
        if src_col not in subset.columns:
            print(f"  [accountability] WARNING: required column {src_col!r} absent", file=sys.stderr)
            out[out_col] = [None] * len(subset)
        else:
            out[out_col] = subset[src_col].where(subset[src_col].notna(), None).tolist()

    for src_col, out_col in _OPTIONAL_ACCT.items():
        if src_col in subset.columns:
            out[out_col] = subset[src_col].where(subset[src_col].notna(), None).tolist()

    df = pd.DataFrame(out)

    # CDALLS → nullable numeric
    if "accountability_score_2025" in df.columns:
        df["accountability_score_2025"] = pd.to_numeric(
            df["accountability_score_2025"], errors="coerce"
        )

    # Coerce empty strings to None for string columns
    str_cols = [c for c in df.columns if c not in ("campus_id", "accountability_score_2025")]
    for col in str_cols:
        df[col] = df[col].apply(lambda v: None if (v is not None and str(v).strip() == "") else v)

    return df


# ──────────────────────────────────────────────────────────────────────────────
# ArcGIS parsing
# ──────────────────────────────────────────────────────────────────────────────


def _load_arcgis(cohort_ids: set[str]) -> pd.DataFrame:
    """
    Read the raw ArcGIS JSON, extract campus_id, latitude, longitude.

    Returns a DataFrame with 'campus_id', 'latitude', 'longitude'.
    """
    if not ARCGIS_JSON.exists():
        print(f"ERROR: {ARCGIS_JSON} not found. Run ingest_arcgis.py first.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(ARCGIS_JSON.read_text())
    features = data.get("features", [])

    rows: list[dict] = []
    for feat in features:
        attrs = feat.get("attributes", {})
        raw_sn = attrs.get("USER_School_Number", "")
        campus_id = str(raw_sn).strip().lstrip("'") if raw_sn else ""
        if not (campus_id.isdigit() and len(campus_id) == 9):
            continue
        if campus_id not in cohort_ids:
            continue

        geom = feat.get("geometry")
        lat = float(geom["y"]) if geom and geom.get("y") is not None else None
        lon = float(geom["x"]) if geom and geom.get("x") is not None else None

        rows.append({"campus_id": campus_id, "latitude": lat, "longitude": lon})

    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["campus_id", "latitude", "longitude"]
    )

    dupes = df.duplicated(subset=["campus_id"], keep="first")
    if dupes.any():
        print(f"  [arcgis] {dupes.sum()} duplicate campus_id rows dropped", file=sys.stderr)
        df = df[~dupes].copy()

    return df


# ──────────────────────────────────────────────────────────────────────────────
# Data dictionary update
# ──────────────────────────────────────────────────────────────────────────────


def _update_data_dictionary(dd_path: Path, acct_optional_present: list[str]) -> None:
    """Append Phase 4 accountability and ArcGIS entries to the data dictionary."""
    if dd_path.exists():
        dd = json.loads(dd_path.read_text())
    else:
        dd = {"schema_version": 1, "fields": []}

    # Remove any stale Phase 4 entries so re-runs are idempotent
    p4_prefixes = (
        "accountability_", "acct_", "latitude", "longitude",
        "geocode_source", "arcgis_",
    )
    dd["fields"] = [
        e for e in dd["fields"]
        if not any(str(e.get("column", "")).startswith(p) for p in p4_prefixes)
    ]

    _ACCT_SOURCE = f"TEA {ACCT_SOURCE_YEAR} Campus Accountability Summary"

    def _acct(column, src_field, description, field_type, unit, notes=None):
        e = {
            "column": column,
            "source": _ACCT_SOURCE,
            "source_year": ACCT_SOURCE_YEAR,
            "measure_year": ACCT_SOURCE_YEAR,
            "acct_field": src_field,
            "acct_file": "2025 Campus Accountability Summary.csv",
            "description": description,
            "type": field_type,
            "unit": unit,
        }
        if notes:
            e["notes"] = notes
        return e

    new_entries = [
        # ── Core accountability ───────────────────────────────────────────────
        _acct(
            "accountability_rating_2025", "C_RATING",
            "Overall campus accountability rating",
            "string", "category",
            "Values: A, B, C, D, F, 'Not Rated'. Null if campus not in file. "
            "'Not Rated' is a real TEA designation (new schools, DAEP campuses, etc.); "
            "it is NOT equivalent to missing data.",
        ),
        {
            "column": "accountability_status_2025",
            "source": "derived",
            "source_year": ACCT_SOURCE_YEAR,
            "description": (
                "Derived accountability status. 'Rated' when C_RATING is A/B/C/D/F; "
                "'Not Rated' when C_RATING is 'Not Rated'; null when campus is not in "
                "the 2025 accountability file."
            ),
            "type": "string",
            "unit": "category",
        },
        _acct(
            "accountability_score_2025", "CDALLS",
            "Overall campus numeric accountability score",
            "float", "score (0–100)",
            "Null for 'Not Rated' campuses and for unmatched campuses.",
        ),
    ]

    # Optional flag and grade fields
    optional_field_meta = {
        "acct_grade_type_2025":   ("GRDTYPE",    "Grade-configuration type code (S=single, E=elementary, etc.)", "string", "code"),
        "acct_grade_span_2025":   ("GRDSPAN",    "Grade span label (e.g. '09 - 12')", "string", "label"),
        "acct_grade_low_2025":    ("GRDLOW",     "Lowest grade served", "string", "grade"),
        "acct_grade_high_2025":   ("GRDHIGH",    "Highest grade served", "string", "grade"),
        "acct_charter_flag_2025": ("CFLCHART",   "Charter campus flag (Y/N)", "string", "flag"),
        "acct_alt_ed_flag_2025":  ("CFLAEC",     "Alternative education campus flag (Y/N)", "string", "flag"),
        "acct_alt_ed_type_2025":  ("CFLAEATYPE", "Alternative education campus type", "string", "category"),
        "acct_daep_flag_2025":    ("CFLDAEP",    "DAEP campus flag (Y/N)", "string", "flag"),
        "acct_jj_flag_2025":      ("CFLJJ",      "Juvenile Justice campus flag (Y/N)", "string", "flag"),
        "acct_alted_flag_2025":   ("CFLALTED",   "Other alternative education flag (Y/N)", "string", "flag"),
        "acct_residential_flag_2025": ("CFLRTF", "Residential Treatment Facility flag (Y/N)", "string", "flag"),
    }
    for col in acct_optional_present:
        if col in optional_field_meta:
            src_f, desc, ftype, unit = optional_field_meta[col]
            new_entries.append(_acct(col, src_f, desc, ftype, unit))

    new_entries += [
        # ── Accountability pipeline metadata ──────────────────────────────────
        {
            "column": "accountability_source_year",
            "source": "pipeline",
            "description": f"TEA accountability release year ({ACCT_SOURCE_YEAR}) for all rows.",
            "type": "integer",
        },
        {
            "column": "accountability_matched",
            "source": "pipeline",
            "description": (
                "True if this campus_id matched a CAMPUS row in the 2025 TEA "
                "campus accountability file. False if the campus is not in that file "
                "(all accountability fields null)."
            ),
            "type": "boolean",
        },
        # ── ArcGIS coordinates ────────────────────────────────────────────────
        {
            "column": "latitude",
            "source": "TEA ArcGIS Schools 2024-25",
            "source_year": ARCGIS_SOURCE_YEAR,
            "arcgis_item_id": "80c162b9008a40d681c127874722670f",
            "description": "Campus latitude (WGS84 decimal degrees, from ArcGIS point geometry).",
            "type": "float",
            "unit": "decimal degrees",
            "notes": (
                "Geocoder output from a 2024-25 ArcGIS snapshot derived from AskTED. "
                "For display and approximate mapping only. "
                "Dallas schools expected in range [32.5, 33.2]."
            ),
        },
        {
            "column": "longitude",
            "source": "TEA ArcGIS Schools 2024-25",
            "source_year": ARCGIS_SOURCE_YEAR,
            "arcgis_item_id": "80c162b9008a40d681c127874722670f",
            "description": "Campus longitude (WGS84 decimal degrees, from ArcGIS point geometry).",
            "type": "float",
            "unit": "decimal degrees",
            "notes": (
                "Geocoder output from a 2024-25 ArcGIS snapshot derived from AskTED. "
                "For display and approximate mapping only. "
                "Dallas schools expected in range [-97.2, -96.4]."
            ),
        },
        {
            "column": "geocode_source",
            "source": "pipeline",
            "description": (
                "Source of the latitude/longitude coordinates. "
                "'TEA ArcGIS Schools 2024-25' for matched campuses; null if unmatched."
            ),
            "type": "string",
        },
        {
            "column": "arcgis_source_year",
            "source": "pipeline",
            "description": f"ArcGIS layer school year ({ARCGIS_SOURCE_YEAR}) for all rows.",
            "type": "string",
        },
        {
            "column": "arcgis_matched",
            "source": "pipeline",
            "description": (
                "True if this campus_id matched a feature in the ArcGIS Schools 2024-25 "
                "layer. False if the campus has no ArcGIS feature (latitude/longitude null)."
            ),
            "type": "boolean",
        },
    ]

    dd["fields"].extend(new_entries)
    dd["generated_utc"] = datetime.now(timezone.utc).isoformat()
    dd.setdefault("notes", []).append(
        f"Phase 4 ({ACCT_SOURCE_YEAR} accountability + ArcGIS {ARCGIS_SOURCE_YEAR} coordinates) "
        "fields added."
    )
    dd_path.write_text(json.dumps(dd, indent=2))


# ──────────────────────────────────────────────────────────────────────────────
# Main build function
# ──────────────────────────────────────────────────────────────────────────────


def build_enriched() -> pd.DataFrame:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if not COHORT_CRDC.exists():
        print(f"ERROR: {COHORT_CRDC} not found. Run build_crdc.py first.", file=sys.stderr)
        sys.exit(1)

    cohort = pd.read_csv(COHORT_CRDC, dtype=str)
    cohort_ids: set[str] = set(cohort["campus_id"].dropna().str.strip())
    print(f"Cohort: {len(cohort)} rows  |  {len(cohort_ids)} campus IDs\n")

    # ── Accountability ────────────────────────────────────────────────────────

    print("Loading accountability …")
    acct_df = _load_accountability(cohort_ids)
    acct_matched_ids: set[str] = set(acct_df["campus_id"])
    print(f"  Matched {len(acct_matched_ids)} of {len(cohort_ids)} cohort schools")

    # Detect which optional columns were actually produced
    all_optional_out = set(_OPTIONAL_ACCT.values())
    acct_optional_present = [c for c in acct_df.columns if c in all_optional_out]
    print(f"  Optional flag columns present: {len(acct_optional_present)}")

    # ── ArcGIS ───────────────────────────────────────────────────────────────

    print("\nLoading ArcGIS coordinates …")
    arcgis_df = _load_arcgis(cohort_ids)
    arcgis_matched_ids: set[str] = set(arcgis_df["campus_id"])
    print(f"  Matched {len(arcgis_matched_ids)} of {len(cohort_ids)} cohort schools")

    # ── Join ──────────────────────────────────────────────────────────────────

    result = cohort.merge(acct_df, on="campus_id", how="left")
    result = result.merge(arcgis_df, on="campus_id", how="left")

    # Derive accountability_status_2025
    result["accountability_status_2025"] = result["accountability_rating_2025"].apply(
        derive_accountability_status
    )

    # Pipeline metadata
    result["accountability_source_year"] = ACCT_SOURCE_YEAR
    result["accountability_matched"] = result["campus_id"].isin(acct_matched_ids)

    result["geocode_source"] = result["campus_id"].apply(
        lambda cid: "TEA ArcGIS Schools 2024-25" if cid in arcgis_matched_ids else None
    )
    result["arcgis_source_year"] = ARCGIS_SOURCE_YEAR
    result["arcgis_matched"] = result["campus_id"].isin(arcgis_matched_ids)

    # Coerce coordinate columns to float
    for col in ["latitude", "longitude"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    # ── Column ordering ───────────────────────────────────────────────────────

    crdc_cols = list(cohort.columns)
    acct_measure_cols = (
        ["accountability_rating_2025", "accountability_status_2025", "accountability_score_2025"]
        + acct_optional_present
        + ["accountability_source_year", "accountability_matched"]
    )
    arcgis_cols = ["latitude", "longitude", "geocode_source", "arcgis_source_year", "arcgis_matched"]

    ordered = crdc_cols + acct_measure_cols + arcgis_cols
    result = result[[c for c in ordered if c in result.columns]].copy()

    # ── Write outputs ─────────────────────────────────────────────────────────

    csv_out = PROCESSED_DIR / "cohort_enriched.csv"
    parquet_out = PROCESSED_DIR / "cohort_enriched.parquet"
    acct_report_out = PROCESSED_DIR / "accountability_join_report.json"
    arcgis_report_out = PROCESSED_DIR / "arcgis_join_report.json"

    result.to_csv(csv_out, index=False)
    result.to_parquet(parquet_out, index=False)

    # ── Accountability join report ─────────────────────────────────────────────

    rating_dist: dict[str, int] = {}
    if "accountability_rating_2025" in result.columns:
        for v in result["accountability_rating_2025"].dropna():
            rating_dist[str(v)] = rating_dist.get(str(v), 0) + 1

    acct_null_counts: dict[str, int] = {}
    for col in acct_measure_cols:
        if col in result.columns:
            acct_null_counts[col] = int(result[col].isna().sum())

    acct_report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_year": ACCT_SOURCE_YEAR,
        "official_filename": "2025 Campus Accountability Summary.csv",
        "cohort_school_count": len(result),
        "accountability_matched": int(result["accountability_matched"].sum()),
        "accountability_unmatched": int((~result["accountability_matched"]).sum()),
        "accountability_match_pct": round(
            100 * int(result["accountability_matched"].sum()) / len(result), 1
        ) if len(result) > 0 else 0,
        "rating_distribution": rating_dist,
        "not_rated_count": rating_dist.get(_NOT_RATED, 0),
        "optional_columns_present": acct_optional_present,
        "null_counts_per_output_column": acct_null_counts,
        "unmatched_campus_ids": result.loc[
            ~result["accountability_matched"], "campus_id"
        ].tolist(),
    }
    acct_report_out.write_text(json.dumps(acct_report, indent=2))

    # ── ArcGIS join report ─────────────────────────────────────────────────────

    matched_with_coords = result["arcgis_matched"] & result["latitude"].notna()
    lat_vals = result.loc[result["latitude"].notna(), "latitude"]
    lon_vals = result.loc[result["longitude"].notna(), "longitude"]

    arcgis_report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": "TEA ArcGIS Schools 2024-25",
        "item_id": "80c162b9008a40d681c127874722670f",
        "source_year": ARCGIS_SOURCE_YEAR,
        "cohort_school_count": len(result),
        "arcgis_matched": int(result["arcgis_matched"].sum()),
        "arcgis_unmatched": int((~result["arcgis_matched"]).sum()),
        "arcgis_match_pct": round(
            100 * int(result["arcgis_matched"].sum()) / len(result), 1
        ) if len(result) > 0 else 0,
        "schools_with_coordinates": int(matched_with_coords.sum()),
        "coordinate_bounds": {
            "latitude_min": float(lat_vals.min()) if not lat_vals.empty else None,
            "latitude_max": float(lat_vals.max()) if not lat_vals.empty else None,
            "longitude_min": float(lon_vals.min()) if not lon_vals.empty else None,
            "longitude_max": float(lon_vals.max()) if not lon_vals.empty else None,
        },
        "null_counts": {
            "latitude": int(result["latitude"].isna().sum()),
            "longitude": int(result["longitude"].isna().sum()),
        },
        "unmatched_campus_ids": result.loc[
            ~result["arcgis_matched"], "campus_id"
        ].tolist(),
    }
    arcgis_report_out.write_text(json.dumps(arcgis_report, indent=2))

    # ── Data dictionary ───────────────────────────────────────────────────────

    _update_data_dictionary(DD_PATH, acct_optional_present)

    # ── Console summary ───────────────────────────────────────────────────────

    print(f"\n{'='*60}")
    print(f"Cohort rows         : {len(result)}")
    print(f"\nAccountability join : {acct_report['accountability_matched']}/{len(result)}"
          f"  ({acct_report['accountability_match_pct']}%)")
    print(f"  Rating distribution: {rating_dist}")
    print(f"  Not Rated count    : {acct_report['not_rated_count']}")

    print(f"\nArcGIS join         : {arcgis_report['arcgis_matched']}/{len(result)}"
          f"  ({arcgis_report['arcgis_match_pct']}%)")
    if not lat_vals.empty:
        print(f"  Latitude range     : [{lat_vals.min():.4f}, {lat_vals.max():.4f}]")
        print(f"  Longitude range    : [{lon_vals.min():.4f}, {lon_vals.max():.4f}]")

    print(f"\nNull counts (accountability):")
    for col, n in acct_null_counts.items():
        if n > 0:
            print(f"  {col:<45} {n}")

    print(f"\nOutputs:")
    for p in [csv_out, parquet_out, acct_report_out, arcgis_report_out, DD_PATH]:
        print(f"  {p}")

    return result


if __name__ == "__main__":
    build_enriched()
