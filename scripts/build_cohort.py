"""
Phase 1 – Step 2: Normalize AskTED data and build the Dallas public school cohort.

Normalization:
  - Strip leading apostrophe from TEA/NCES identifiers; assert digit lengths.
  - Convert blank strings → None; enrollment sentinel -1 → None.
  - Derive school_level from grade range; classify operator_type (isd / charter).

Cohort rules (applied in order):
  1. School Site City == DALLAS (physical address)
  2. School Status == Active
  3. District Type in {INDEPENDENT, CHARTER}  (excludes private/unknown)
  4. Instruction Type excludes DAEP / JJAEP keywords
  5. Enrollment not null (sentinel -1 already converted)
  6. Enrollment > 0
  7. De-duplicate on campus_id
  8. If remaining > 60: deterministic stratified cap (school_level × operator_type,
     largest-remainder allocation, random_state=42 sample within each stratum)

Outputs:
  data/processed/cohort_ids.csv       – campus_id, district_id, nces_school_id, school_name
  data/processed/cohort_preview.csv   – all normalized fields used for testing/inspection
  data/processed/cohort_funnel.json   – step-by-step exclusion counts and cohort breakdown
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

_ROOT = Path(__file__).parent.parent
RAW_FILE = _ROOT / "data" / "raw" / "askted_directory.csv"
METADATA_FILE = _ROOT / "data" / "raw" / "askted_fetch_metadata.json"
PROCESSED_DIR = _ROOT / "data" / "processed"

DALLAS_SITE_CITY = "DALLAS"
ACTIVE_STATUS = "Active"
COHORT_MIN = 40
COHORT_MAX = 60

# Substrings that mark non-comparable instruction types (upper-cased match)
EXCLUDED_INSTRUCTION_SUBSTRINGS = (
    "DAEP",
    "JJAEP",
    "JUVENILE JUSTICE",
    "DISCIPLINARY ALTERNATIVE",
)

INCLUDED_DISTRICT_TYPES = frozenset({"INDEPENDENT", "CHARTER"})

# Grade-code → integer mapping (PK=-1, KG=0, 01-12 = 1-12)
_GRADE_MAP: dict[str, int] = {"PK": -1, "KG": 0}
_GRADE_MAP.update({f"{i:02d}": i for i in range(1, 13)})
_GRADE_MAP.update({str(i): i for i in range(1, 13)})   # bare digits without leading zero

_ENROLLMENT_COL_RE = re.compile(r"^School Enrollment as of Oct \d{4}$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Normalization helpers (importable by tests)
# ---------------------------------------------------------------------------

def strip_apostrophe(value) -> Optional[str]:
    """Strip the leading apostrophe TEA uses to protect identifiers in CSV."""
    if value is None or (isinstance(value, float)):
        return None
    s = str(value).strip()
    return s.lstrip("'") if s else None


def normalize_id(value, expected_digits: int) -> Optional[str]:
    """
    Strip apostrophe and validate digit count.
    Returns None if the value is blank, non-numeric, or wrong length.
    """
    cleaned = strip_apostrophe(value)
    if not cleaned:
        return None
    if not cleaned.isdigit() or len(cleaned) != expected_digits:
        return None
    return cleaned


def blank_to_none(value) -> Optional[str]:
    """Convert pandas NaN or blank strings to None; otherwise return stripped string."""
    if value is None:
        return None
    if isinstance(value, float):  # NaN from pandas
        return None
    s = str(value).strip()
    return s if s else None


def parse_enrollment(value) -> Optional[int]:
    """
    Parse enrollment to int.
    -1 is the AskTED sentinel for unknown/missing → returns None.
    Empty / blank / non-numeric → returns None.
    0 returns 0 (genuine zero enrollment, filtered separately).
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        n = int(float(s))
    except (ValueError, TypeError):
        return None
    return None if n == -1 else n


def parse_grade(code: str) -> Optional[int]:
    return _GRADE_MAP.get(code.strip().upper())


def parse_grade_range(raw) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Returns (normalized_range_string, low_grade_int, high_grade_int).
    Strips the leading apostrophe, then splits on '-'.
    """
    cleaned = strip_apostrophe(raw)
    if not cleaned:
        return None, None, None
    parts = cleaned.split("-", 1)
    if len(parts) != 2:
        return cleaned, None, None
    low = parse_grade(parts[0])
    high = parse_grade(parts[1])
    return cleaned, low, high


def infer_school_level(low: Optional[int], high: Optional[int]) -> str:
    """
    Classify school level from numeric grade bounds.

    elementary : high <= 6
    middle     : high in [7–9] and low >= 5
    high       : high >= 10 and low >= 7
    mixed      : PK/K through senior grades (low <= 0 and high >= 10)
                 or spans that don't fit the above buckets
    unknown    : either bound is None
    """
    if low is None or high is None:
        return "unknown"
    if low <= 0 and high >= 10:
        return "mixed"
    if high <= 6:
        return "elementary"
    if low >= 5 and high <= 9:
        return "middle"
    if high >= 10 and low >= 7:
        return "high"
    return "mixed"


def is_excluded_instruction_type(value) -> bool:
    if not value:
        return False
    upper = str(value).upper().strip()
    return any(sub in upper for sub in EXCLUDED_INSTRUCTION_SUBSTRINGS)


# ---------------------------------------------------------------------------
# Stratified cap
# ---------------------------------------------------------------------------

def apply_stratified_cap(df: pd.DataFrame, target: int) -> pd.DataFrame:
    """
    Deterministically reduce df to `target` rows.

    Strata: (school_level, operator_type).
    Allocation: proportional with largest-remainder rounding.
    Selection within each stratum: sort by campus_id ascending (lexicographic on
    zero-padded 9-digit strings is equivalent to numeric order).
    """
    groups = df.groupby(["school_level", "operator_type"], sort=True)
    total = len(df)

    raw_alloc: dict = {key: (size / total) * target for key, size in groups.size().items()}
    alloc: dict = {k: int(v) for k, v in raw_alloc.items()}

    remainder = target - sum(alloc.values())
    by_fraction = sorted(raw_alloc.keys(), key=lambda k: -(raw_alloc[k] - int(raw_alloc[k])))
    for k in by_fraction[:remainder]:
        alloc[k] += 1

    selected = []
    for key, group in groups:
        n = alloc.get(key, 0)
        n_take = min(n, len(group))
        selected.append(group.sample(n=n_take, random_state=42))

    return pd.concat(selected).sort_values("campus_id").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def _find_enrollment_col(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        if _ENROLLMENT_COL_RE.match(col) and "District" not in col:
            return col
    return None


def build_cohort() -> pd.DataFrame:
    if not RAW_FILE.exists():
        print(f"ERROR: {RAW_FILE} not found. Run scripts/ingest_askted.py first.", file=sys.stderr)
        sys.exit(1)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    fetch_meta: dict = {}
    if METADATA_FILE.exists():
        fetch_meta = json.loads(METADATA_FILE.read_text())

    # --- Load ---
    df = pd.read_csv(RAW_FILE, dtype=str, encoding="utf-8-sig", low_memory=False)
    funnel = [{"step": "raw_rows", "count": len(df)}]

    # --- Enrollment column (name encodes year) ---
    enroll_col = _find_enrollment_col(df)
    if enroll_col is None:
        print("WARNING: enrollment column not found by pattern; falling back to literal name.", file=sys.stderr)
        enroll_col = "School Enrollment as of Oct 2025"

    year_match = re.search(r"(\d{4})", enroll_col)
    enrollment_source_year = int(year_match.group(1)) if year_match else None

    # --- Normalize IDs ---
    df["campus_id"]    = df["School Number"].apply(lambda x: normalize_id(x, 9))
    df["district_id"]  = df["District Number"].apply(lambda x: normalize_id(x, 6))
    df["nces_school_id"] = df["NCES School ID"].apply(strip_apostrophe)

    bad_campus = df["campus_id"].isna().sum()
    bad_district = df["district_id"].isna().sum()
    if bad_campus:
        print(f"WARNING: {bad_campus} rows with invalid/missing campus IDs (dropped at normalization).")
    if bad_district:
        print(f"WARNING: {bad_district} rows with invalid/missing district IDs.")

    # Derived district prefix must match supplied district_id
    df["_district_prefix"] = df["campus_id"].str[:6]
    mismatch = (
        df["campus_id"].notna()
        & df["district_id"].notna()
        & (df["_district_prefix"] != df["district_id"])
    ).sum()
    if mismatch:
        print(f"WARNING: {mismatch} rows where first 6 digits of campus_id != district_id.")

    # --- Normalize text fields to None-or-stripped-string ---
    text_cols = [
        "School Name", "District Name", "District Type", "Instruction Type",
        "Charter Type", "School Site City", "School Status", "Grade Range",
        "Magnet Status", "Residential Facility", "AEA",
        "School Site Street Address", "School Site Zip",
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].apply(blank_to_none)

    # --- Enrollment ---
    if enroll_col in df.columns:
        df["enrollment"] = df[enroll_col].apply(parse_enrollment)
    else:
        df["enrollment"] = None

    # --- Grade range + school level ---
    parsed = df["Grade Range"].apply(lambda x: pd.Series(parse_grade_range(x)))
    parsed.columns = ["grade_range", "grade_low_num", "grade_high_num"]
    df = pd.concat([df, parsed], axis=1)
    df["school_level"] = df.apply(
        lambda r: infer_school_level(r["grade_low_num"], r["grade_high_num"]), axis=1
    )

    # --- Operator type ---
    df["operator_type"] = df["District Type"].apply(
        lambda x: "charter" if x == "CHARTER" else ("isd" if x == "INDEPENDENT" else "other")
    )

    # ================================================================
    # Cohort filtering — each step appends to funnel
    # ================================================================

    # 1. Physical site city == DALLAS
    mask = df["School Site City"].fillna("").str.upper() == DALLAS_SITE_CITY
    df = df[mask].copy()
    funnel.append({"step": "dallas_site_city", "count": len(df),
                   "filter": f"School Site City == {DALLAS_SITE_CITY}"})

    # 2. Active status
    mask = df["School Status"] == ACTIVE_STATUS
    df = df[mask].copy()
    funnel.append({"step": "active_status", "count": len(df),
                   "filter": "School Status == Active"})

    # 3. Public only (INDEPENDENT or CHARTER district types)
    mask = df["operator_type"].isin({"isd", "charter"})
    excl = (~mask).sum()
    df = df[mask].copy()
    if excl:
        funnel.append({"step": "exclude_non_public", "count": len(df),
                       "excluded": int(excl), "filter": "District Type in {INDEPENDENT, CHARTER}"})

    # 4. Exclude DAEP / JJAEP instruction types
    mask = ~df["Instruction Type"].apply(is_excluded_instruction_type)
    excl = (~mask).sum()
    df = df[mask].copy()
    funnel.append({"step": "exclude_daep_jjaep", "count": len(df),
                   "excluded": int(excl), "filter": "Instruction Type excludes DAEP/JJAEP keywords"})

    # 5. Exclude unknown enrollment (sentinel -1 → None)
    mask = df["enrollment"].notna()
    excl = (~mask).sum()
    df = df[mask].copy()
    funnel.append({"step": "exclude_unknown_enrollment", "count": len(df),
                   "excluded": int(excl), "filter": "Enrollment not null (sentinel -1 converted)"})

    # 6. Exclude zero enrollment
    mask = df["enrollment"].astype(float) > 0
    excl = (~mask).sum()
    df = df[mask].copy()
    funnel.append({"step": "exclude_zero_enrollment", "count": len(df),
                   "excluded": int(excl), "filter": "Enrollment > 0"})

    # 7. De-duplicate campus IDs (defensive; should not occur)
    dupes = df.duplicated(subset=["campus_id"], keep="first").sum()
    if dupes:
        print(f"WARNING: {dupes} duplicate campus_id rows dropped.")
        df = df[~df.duplicated(subset=["campus_id"], keep="first")].copy()
    funnel.append({"step": "after_dedup", "count": len(df)})

    pre_cap = len(df)
    cap_applied = False

    # 8. Stratified cap if above COHORT_MAX
    if pre_cap > COHORT_MAX:
        cap_applied = True
        df = apply_stratified_cap(df, COHORT_MAX)
        funnel.append({
            "step": "stratified_cap",
            "count": len(df),
            "excluded": pre_cap - len(df),
            "filter": (
                f"Proportional cap to {COHORT_MAX} by school_level × operator_type; "
                "largest-remainder allocation; random_state=42 sample within each stratum"
            ),
        })

    funnel.append({"step": "final_cohort", "count": len(df)})

    if len(df) < COHORT_MIN:
        print(f"WARNING: cohort size {len(df)} is below minimum {COHORT_MIN}.", file=sys.stderr)

    # --- Cohort breakdown ---
    breakdown = (
        df.groupby(["school_level", "operator_type"])
        .size()
        .reset_index(name="count")
        .assign(count=lambda x: x["count"].astype(int))
        .to_dict(orient="records")
    )

    # --- Funnel document ---
    funnel_doc = {
        "source": "AskTED direct site-address download",
        "source_url": fetch_meta.get("source_url", ASKTED_URL if "ASKTED_URL" in dir() else ""),
        "retrieved_utc": fetch_meta.get("retrieved_utc"),
        "sha256": fetch_meta.get("sha256"),
        "raw_row_count": fetch_meta.get("row_count"),
        "enrollment_source_year": enrollment_source_year,
        "cap_applied": cap_applied,
        "funnel": funnel,
        "cohort_breakdown": breakdown,
    }

    funnel_path = PROCESSED_DIR / "cohort_funnel.json"
    funnel_path.write_text(json.dumps(funnel_doc, indent=2))

    # --- cohort_ids.csv ---
    ids_df = df[["campus_id", "district_id", "nces_school_id", "School Name", "District Name"]].copy()
    ids_df = ids_df.rename(columns={"School Name": "school_name", "District Name": "district_name"})
    ids_path = PROCESSED_DIR / "cohort_ids.csv"
    ids_df.to_csv(ids_path, index=False)

    # --- cohort_preview.csv ---
    preview_map = {
        "campus_id":             "campus_id",
        "district_id":           "district_id",
        "nces_school_id":        "nces_school_id",
        "School Name":           "school_name",
        "District Name":         "district_name",
        "District Type":         "district_type",
        "Instruction Type":      "instruction_type",
        "Charter Type":          "charter_type",
        "school_level":          "school_level",
        "operator_type":         "operator_type",
        "grade_range":           "grade_range",
        "enrollment":            "enrollment",
        "School Status":         "school_status",
        "School Site City":      "school_site_city",
        "School Site Street Address": "school_site_address",
        "School Site Zip":       "school_site_zip",
        "Magnet Status":         "magnet_status",
    }
    keep = [c for c in preview_map if c in df.columns]
    preview_df = df[keep].rename(columns=preview_map).copy()
    preview_df["enrollment_source_year"] = enrollment_source_year
    preview_path = PROCESSED_DIR / "cohort_preview.csv"
    preview_df.to_csv(preview_path, index=False)

    # --- Console summary ---
    print(f"\n{'='*60}")
    print(f"Final cohort size : {len(df)}")
    print(f"Stratified cap    : {cap_applied}")
    print(f"\nBreakdown (school_level × operator_type):")
    for row in breakdown:
        print(f"  {row['school_level']:12s}  {row['operator_type']:8s}  {row['count']}")
    print(f"\nFunnel:")
    for step in funnel:
        excl_str = f"  (excluded {step['excluded']})" if step.get("excluded") else ""
        print(f"  {step['step']:<36} {step['count']}{excl_str}")
    print(f"\nOutputs:")
    print(f"  {ids_path}")
    print(f"  {preview_path}")
    print(f"  {funnel_path}")

    return df


if __name__ == "__main__":
    build_cohort()
