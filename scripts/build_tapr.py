"""
Phase 2 – Step 2: Parse TAPR campus files, normalize, and join to the Dallas cohort.

Reads raw TAPR CSVs from data/raw/ (produced by ingest_tapr.py).
Handles the two-row header format (descriptive labels + machine field names).
Converts TEA suppression codes -1/-2/-3 and blank values to null.
Left-joins all three TAPR sources to the 60-school cohort by campus_id.

Outputs:
  data/processed/cohort_tapr.csv          – joined cohort with all TAPR fields
  data/processed/cohort_tapr.parquet      – same, with typed nullable numerics
  data/processed/tapr_join_report.json    – join coverage, suppression summary
  data/processed/data_dictionary.json     – field definitions for every TAPR column
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
COHORT_PREVIEW = PROCESSED_DIR / "cohort_preview.csv"

TAPR_RELEASE_YEAR = 2025

# TEA masking sentinel codes (tapr_discovery.md §TAPR masking)
_SUPPRESSION_CODES = frozenset({"-1", "-2", "-3"})

# ──────────────────────────────────────────────────────────────────────────────
# Field maps: raw TAPR column → output column name
# ──────────────────────────────────────────────────────────────────────────────

STUDENT_FIELDS: dict[str, str] = {
    "CPETALLC": "tapr_membership_all_count_2025",
    "CPETSPEC": "tapr_membership_sped_count_2025",
    "CPETSPEP": "tapr_membership_sped_pct_2025",
    "CPNTALLC": "tapr_enrollment_all_count_2025",
    "CPNTSPEC": "tapr_enrollment_sped_count_2025",
    "CPNTSPEP": "tapr_enrollment_sped_pct_2025",
}

ATTENDANCE_FIELDS: dict[str, str] = {
    "CA0AT24N": "tapr_att_all_days_present_2024",
    "CA0AT24D": "tapr_att_all_days_membership_2024",
    "CA0AT24R": "tapr_att_all_rate_2024",
    "CS0AT24N": "tapr_att_sped_days_present_2024",
    "CS0AT24D": "tapr_att_sped_days_membership_2024",
    "CS0AT24R": "tapr_att_sped_rate_2024",
    "CA0CA24N": "tapr_chronic_abs_all_numerator_2024",
    "CA0CA24D": "tapr_chronic_abs_all_denominator_2024",
    "CA0CA24R": "tapr_chronic_abs_all_rate_2024",
    "CS0CA24N": "tapr_chronic_abs_sped_numerator_2024",
    "CS0CA24D": "tapr_chronic_abs_sped_denominator_2024",
    "CS0CA24R": "tapr_chronic_abs_sped_rate_2024",
}

STAFF_FIELDS: dict[str, str] = {
    "CPSTEXPA": "tapr_avg_teacher_exp_years_2025",
    "CPSTTENA": "tapr_avg_teacher_tenure_years_2025",
    "CPST00FC": "tapr_beginning_teacher_fte_count_2025",
    "CPST00FP": "tapr_beginning_teacher_fte_pct_2025",
    "CPST01FP": "tapr_teacher_1to5yr_pct_2025",
    "CPST06FP": "tapr_teacher_6to10yr_pct_2025",
    "CPST11FP": "tapr_teacher_11to20yr_pct_2025",
    "CPST21FP": "tapr_teacher_21to30yr_pct_2025",
    "CPST30FP": "tapr_teacher_over30yr_pct_2025",
}

# Columns that are percentage/rate values (must be 0–100 when present)
PCT_COLUMNS: frozenset[str] = frozenset({
    "tapr_membership_sped_pct_2025",
    "tapr_enrollment_sped_pct_2025",
    "tapr_att_all_rate_2024",
    "tapr_att_sped_rate_2024",
    "tapr_chronic_abs_all_rate_2024",
    "tapr_chronic_abs_sped_rate_2024",
    "tapr_beginning_teacher_fte_pct_2025",
    "tapr_teacher_1to5yr_pct_2025",
    "tapr_teacher_6to10yr_pct_2025",
    "tapr_teacher_11to20yr_pct_2025",
    "tapr_teacher_21to30yr_pct_2025",
    "tapr_teacher_over30yr_pct_2025",
})

_TAPR_FILE_CONFIGS: list[dict] = [
    {
        "name": "student",
        "raw_filename": "tapr_student_2025.csv",
        "official_filename": "2025 Campus Student Information.csv",
        "field_map": STUDENT_FIELDS,
    },
    {
        "name": "attendance",
        "raw_filename": "tapr_attendance_2025.csv",
        "official_filename": "2025 Campus Attendance Absenteeism Dropout.csv",
        "field_map": ATTENDANCE_FIELDS,
    },
    {
        "name": "staff",
        "raw_filename": "tapr_staff_2025.csv",
        "official_filename": "2025 Campus Staff Information.csv",
        "field_map": STAFF_FIELDS,
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Normalization helpers (importable by tests)
# ──────────────────────────────────────────────────────────────────────────────


def normalize_campus_id(val) -> Optional[str]:
    """Strip leading apostrophe; return a 9-digit string or None if invalid."""
    if val is None:
        return None
    s = str(val).strip().lstrip("'")
    return s if (s.isdigit() and len(s) == 9) else None


def normalize_measure(val) -> tuple[Optional[float], Optional[str]]:
    """
    Return (numeric_value, suppression_code).

    suppression_code is:
      None          – valid numeric value
      '-1'/'-2'/'-3' – TEA masking sentinel
      'blank'       – empty or missing string
    numeric_value is None whenever suppression_code is not None.
    """
    if val is None:
        return None, None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None, "blank"
    if s in _SUPPRESSION_CODES:
        return None, s
    try:
        return float(s), None
    except ValueError:
        return None, f"invalid:{s}"


# ──────────────────────────────────────────────────────────────────────────────
# File reading
# ──────────────────────────────────────────────────────────────────────────────


def _find_campus_header_row(path: Path) -> int:
    """
    Return the 0-based index of the machine-name header row.

    TAPR CSVs may have a descriptive-label row before the machine-name row.
    The machine-name row starts with the literal text CAMPUS.
    """
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            for i, line in enumerate(f):
                first = line.split(",")[0].strip().strip('"')
                if first == "CAMPUS":
                    return i
                if i >= 5:
                    break
    except OSError:
        pass
    return 0


def _parse_tapr_source(
    path: Path,
    field_map: dict[str, str],
    source_name: str,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """
    Parse one TAPR statewide campus CSV.

    Returns
    -------
    df : DataFrame
        campus_id + normalized (float / NaN) measure columns.
    sup_codes : dict
        {campus_id: {original_tapr_field: suppression_code}} for every
        suppressed or blank field-value.
    """
    header_row = _find_campus_header_row(path)
    skip = list(range(header_row)) if header_row > 0 else []

    raw = pd.read_csv(
        path,
        dtype=str,
        encoding="utf-8-sig",
        skiprows=skip,
        header=0,
        low_memory=False,
    )

    # Normalize campus IDs
    raw["campus_id"] = raw["CAMPUS"].apply(normalize_campus_id)
    invalid_mask = raw["campus_id"].isna()
    if invalid_mask.any():
        print(
            f"  [{source_name}] {invalid_mask.sum()} rows with invalid campus IDs dropped",
            file=sys.stderr,
        )
    raw = raw[~invalid_mask].copy()

    dupe_mask = raw.duplicated(subset=["campus_id"], keep="first")
    if dupe_mask.any():
        print(
            f"  [{source_name}] {dupe_mask.sum()} duplicate campus rows dropped",
            file=sys.stderr,
        )
        raw = raw[~dupe_mask].copy()

    campus_ids = raw["campus_id"].tolist()
    out_data: dict[str, list] = {"campus_id": campus_ids}
    sup_codes: dict[str, dict[str, str]] = {}

    for tapr_f, new_name in field_map.items():
        if tapr_f not in raw.columns:
            print(
                f"  [{source_name}] WARNING: column {tapr_f!r} not present in file",
                file=sys.stderr,
            )
            out_data[new_name] = [float("nan")] * len(campus_ids)
            continue

        vals: list[Optional[float]] = []
        for campus_id, raw_val in zip(campus_ids, raw[tapr_f].tolist()):
            num, code = normalize_measure(raw_val)
            vals.append(num)
            if code is not None:
                if campus_id not in sup_codes:
                    sup_codes[campus_id] = {}
                sup_codes[campus_id][tapr_f] = code

        out_data[new_name] = vals

    return pd.DataFrame(out_data), sup_codes


# ──────────────────────────────────────────────────────────────────────────────
# Data dictionary
# ──────────────────────────────────────────────────────────────────────────────


def _write_data_dictionary(path: Path) -> None:
    def _entry(
        column: str,
        tapr_field: str,
        official_filename: str,
        source_year: int,
        measure_year: int,
        description: str,
        unit: str,
        field_type: str,
        notes: Optional[str] = None,
    ) -> dict:
        e: dict = {
            "column": column,
            "source": f"TEA TAPR {source_year}",
            "source_year": source_year,
            "measure_year": measure_year,
            "tapr_field": tapr_field,
            "tapr_file": official_filename,
            "description": description,
            "type": field_type,
            "unit": unit,
            "suppression_notes": (
                "TEA masking codes: -1 (small denominator / suppressed), "
                "-2 (invalid or improbable), -3 (complementary suppression). "
                "Blank also treated as unavailable. All mapped to null. "
                "See tapr_suppression_codes for the original per-campus codes."
            ),
        }
        if notes:
            e["notes"] = notes
        return e

    _STU = "2025 Campus Student Information.csv"
    _ATT = "2025 Campus Attendance Absenteeism Dropout.csv"
    _STF = "2025 Campus Staff Information.csv"

    student_entries = [
        _entry("tapr_membership_all_count_2025", "CPETALLC", _STU, 2025, 2025,
               "Student membership count, all students", "count", "float"),
        _entry("tapr_membership_sped_count_2025", "CPETSPEC", _STU, 2025, 2025,
               "Student membership count, special education", "count", "float"),
        _entry("tapr_membership_sped_pct_2025", "CPETSPEP", _STU, 2025, 2025,
               "Student membership percent, special education",
               "percent", "float",
               "Primary special-ed share metric; denominator is CPETALLC (tapr_membership_all_count_2025)."),
        _entry("tapr_enrollment_all_count_2025", "CPNTALLC", _STU, 2025, 2025,
               "Student enrollment count, all students", "count", "float"),
        _entry("tapr_enrollment_sped_count_2025", "CPNTSPEC", _STU, 2025, 2025,
               "Student enrollment count, special education", "count", "float"),
        _entry("tapr_enrollment_sped_pct_2025", "CPNTSPEP", _STU, 2025, 2025,
               "Student enrollment percent, special education", "percent", "float"),
    ]

    attendance_entries = [
        _entry("tapr_att_all_days_present_2024", "CA0AT24N", _ATT, 2025, 2024,
               "All-student days present (numerator for attendance rate)", "days", "float",
               "Measure year is 2024, distributed in the 2024-25 TAPR release."),
        _entry("tapr_att_all_days_membership_2024", "CA0AT24D", _ATT, 2025, 2024,
               "All-student days membership (denominator for attendance rate)", "days", "float",
               "Suppressed (-1) when days membership < 900."),
        _entry("tapr_att_all_rate_2024", "CA0AT24R", _ATT, 2025, 2024,
               "All-student attendance rate", "percent", "float"),
        _entry("tapr_att_sped_days_present_2024", "CS0AT24N", _ATT, 2025, 2024,
               "Special-education days present", "days", "float"),
        _entry("tapr_att_sped_days_membership_2024", "CS0AT24D", _ATT, 2025, 2024,
               "Special-education days membership", "days", "float",
               "Suppressed (-1) when days membership < 900."),
        _entry("tapr_att_sped_rate_2024", "CS0AT24R", _ATT, 2025, 2024,
               "Special-education attendance rate", "percent", "float"),
        _entry("tapr_chronic_abs_all_numerator_2024", "CA0CA24N", _ATT, 2025, 2024,
               "All-student chronic absence numerator (students missing 10%+ of days)",
               "count", "float"),
        _entry("tapr_chronic_abs_all_denominator_2024", "CA0CA24D", _ATT, 2025, 2024,
               "All-student chronic absence denominator", "count", "float",
               "Suppressed (-1) when denominator is 1–4 students."),
        _entry("tapr_chronic_abs_all_rate_2024", "CA0CA24R", _ATT, 2025, 2024,
               "All-student chronic absence rate", "percent", "float"),
        _entry("tapr_chronic_abs_sped_numerator_2024", "CS0CA24N", _ATT, 2025, 2024,
               "Special-education chronic absence numerator", "count", "float"),
        _entry("tapr_chronic_abs_sped_denominator_2024", "CS0CA24D", _ATT, 2025, 2024,
               "Special-education chronic absence denominator", "count", "float",
               "Suppressed (-1) when denominator is 1–4 students."),
        _entry("tapr_chronic_abs_sped_rate_2024", "CS0CA24R", _ATT, 2025, 2024,
               "Special-education chronic absence rate", "percent", "float"),
    ]

    staff_entries = [
        _entry("tapr_avg_teacher_exp_years_2025", "CPSTEXPA", _STF, 2025, 2025,
               "Average years of teacher experience", "years", "float"),
        _entry("tapr_avg_teacher_tenure_years_2025", "CPSTTENA", _STF, 2025, 2025,
               "Average teacher years with this district", "years", "float",
               "District tenure only; not a teacher turnover measure."),
        _entry("tapr_beginning_teacher_fte_count_2025", "CPST00FC", _STF, 2025, 2025,
               "Beginning teacher FTE count (first-year teachers)", "FTE", "float"),
        _entry("tapr_beginning_teacher_fte_pct_2025", "CPST00FP", _STF, 2025, 2025,
               "Beginning teacher FTE percent", "percent", "float"),
        _entry("tapr_teacher_1to5yr_pct_2025", "CPST01FP", _STF, 2025, 2025,
               "Teacher FTE percent with 1–5 years experience", "percent", "float"),
        _entry("tapr_teacher_6to10yr_pct_2025", "CPST06FP", _STF, 2025, 2025,
               "Teacher FTE percent with 6–10 years experience", "percent", "float"),
        _entry("tapr_teacher_11to20yr_pct_2025", "CPST11FP", _STF, 2025, 2025,
               "Teacher FTE percent with 11–20 years experience", "percent", "float"),
        _entry("tapr_teacher_21to30yr_pct_2025", "CPST21FP", _STF, 2025, 2025,
               "Teacher FTE percent with 21–30 years experience", "percent", "float"),
        _entry("tapr_teacher_over30yr_pct_2025", "CPST30FP", _STF, 2025, 2025,
               "Teacher FTE percent with more than 30 years experience", "percent", "float"),
    ]

    meta_entries: list[dict] = [
        {
            "column": "tapr_source_year",
            "source": "TEA TAPR",
            "source_year": 2025,
            "measure_year": 2025,
            "tapr_field": None,
            "description": (
                "TAPR release year (2025 = 2024-25 TAPR). "
                "Attendance and chronic-absence fields refer to measure_year=2024; "
                "all other TAPR fields refer to measure_year=2025."
            ),
            "type": "integer",
            "unit": "year",
        },
        {
            "column": "tapr_matched",
            "source": "pipeline",
            "description": (
                "True if this campus appeared in at least one of the three TAPR "
                "statewide files; False if not found (all TAPR fields will be null)."
            ),
            "type": "boolean",
        },
        {
            "column": "tapr_suppression_codes",
            "source": "pipeline",
            "description": (
                "JSON object mapping original TAPR field name to the suppression "
                "code for any field that was masked or blank for this campus. "
                "Codes: -1 (small denominator), -2 (invalid/improbable), "
                "-3 (complementary suppression), 'blank' (empty cell). "
                "Null if no fields were suppressed."
            ),
            "type": "string (JSON)",
        },
    ]

    dd = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "tapr_release_year": TAPR_RELEASE_YEAR,
        "notes": [
            "Attendance fields (tapr_att_*, tapr_chronic_abs_*) have measure_year=2024 "
            "because TEA distributes 2024 attendance data in the 2024-25 TAPR release.",
            "TEA masking codes -1/-2/-3 and blank values are all stored as null. "
            "The tapr_suppression_codes column preserves the original per-campus codes.",
            "Teacher turnover, teacher certification, LRE/inclusion, DAEP rate, ISS, OSS, "
            "expulsion, restraint, and seclusion are excluded because they are not present "
            "in the verified 2024-25 TAPR campus files (see research/tapr_discovery.md).",
        ],
        "fields": student_entries + attendance_entries + staff_entries + meta_entries,
    }

    path.write_text(json.dumps(dd, indent=2))


# ──────────────────────────────────────────────────────────────────────────────
# Main build function
# ──────────────────────────────────────────────────────────────────────────────


def build_tapr() -> pd.DataFrame:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if not COHORT_PREVIEW.exists():
        print(
            f"ERROR: {COHORT_PREVIEW} not found. Run build_cohort.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    cohort = pd.read_csv(COHORT_PREVIEW, dtype=str)
    cohort_ids = set(cohort["campus_id"].dropna())
    print(f"Cohort: {len(cohort)} schools\n")

    # ── Parse each TAPR source ────────────────────────────────────────────────

    all_sup: dict[str, dict[str, str]] = {}
    tapr_frames: list[pd.DataFrame] = []
    tapr_campus_sets: list[set] = []

    for cfg in _TAPR_FILE_CONFIGS:
        raw_path = RAW_DIR / cfg["raw_filename"]
        if not raw_path.exists():
            print(
                f"ERROR: {raw_path} not found. Run ingest_tapr.py first.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Parsing {cfg['raw_filename']} ...")
        df, sup = _parse_tapr_source(raw_path, cfg["field_map"], cfg["name"])

        sup_count = sum(len(v) for v in sup.values())
        print(f"  {len(df):,} campus rows  |  {sup_count:,} suppressed field-values")

        # Accumulate suppression codes across all three sources
        for campus_id, codes in sup.items():
            if campus_id not in all_sup:
                all_sup[campus_id] = {}
            all_sup[campus_id].update(codes)

        tapr_campus_sets.append(set(df["campus_id"]))
        tapr_frames.append(df)

    # ── Merge the three TAPR DataFrames (outer join on campus_id) ─────────────

    tapr_wide = tapr_frames[0]
    for df in tapr_frames[1:]:
        tapr_wide = tapr_wide.merge(df, on="campus_id", how="outer")

    tapr_campus_set = set(tapr_wide["campus_id"].dropna())
    print(f"\nMerged TAPR: {len(tapr_wide):,} statewide campus rows")

    # ── Left-join cohort to TAPR ──────────────────────────────────────────────

    result = cohort.merge(tapr_wide, on="campus_id", how="left")

    # Post-join metadata columns
    result["tapr_source_year"] = TAPR_RELEASE_YEAR
    result["tapr_matched"] = result["campus_id"].isin(tapr_campus_set)
    result["tapr_suppression_codes"] = result["campus_id"].apply(
        lambda cid: json.dumps(all_sup[cid]) if cid in all_sup else None
    )

    # ── Reorder columns ───────────────────────────────────────────────────────

    cohort_cols = list(cohort.columns)
    all_measure_cols = (
        list(STUDENT_FIELDS.values())
        + list(ATTENDANCE_FIELDS.values())
        + list(STAFF_FIELDS.values())
    )
    tail_cols = ["tapr_source_year", "tapr_matched", "tapr_suppression_codes"]
    ordered = cohort_cols + [c for c in all_measure_cols if c in result.columns] + tail_cols
    result = result[[c for c in ordered if c in result.columns]].copy()

    # ── Coerce measure columns to float for parquet typing ───────────────────

    for col in all_measure_cols:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    # ── Write outputs ─────────────────────────────────────────────────────────

    csv_path = PROCESSED_DIR / "cohort_tapr.csv"
    parquet_path = PROCESSED_DIR / "cohort_tapr.parquet"
    report_path = PROCESSED_DIR / "tapr_join_report.json"
    dd_path = PROCESSED_DIR / "data_dictionary.json"

    result.to_csv(csv_path, index=False)
    result.to_parquet(parquet_path, index=False)

    _write_data_dictionary(dd_path)

    # ── Join report ───────────────────────────────────────────────────────────

    matched = int(result["tapr_matched"].sum())
    unmatched = int((~result["tapr_matched"]).sum())

    null_counts: dict[str, int] = {
        col: int(result[col].isna().sum())
        for col in all_measure_cols
        if col in result.columns
    }

    # Suppression code breakdown for matched cohort campuses
    code_totals: dict[str, int] = {}
    for campus_id, codes in all_sup.items():
        if campus_id in cohort_ids:
            for code in codes.values():
                code_totals[code] = code_totals.get(code, 0) + 1

    report: dict = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "tapr_release_year": TAPR_RELEASE_YEAR,
        "cohort_school_count": len(result),
        "tapr_matched": matched,
        "tapr_unmatched": unmatched,
        "tapr_match_pct": round(100 * matched / len(result), 1) if len(result) > 0 else 0,
        "tapr_statewide_rows_per_source": {
            cfg["name"]: len(frames)
            for cfg, frames in zip(_TAPR_FILE_CONFIGS, tapr_frames)
        },
        "tapr_statewide_merged_rows": len(tapr_wide),
        "suppression_code_totals_in_cohort": code_totals,
        "null_counts_per_output_column": null_counts,
        "unmatched_campus_ids": result.loc[~result["tapr_matched"], "campus_id"].tolist(),
        "sources": [
            {
                "name": cfg["name"],
                "official_filename": cfg["official_filename"],
                "raw_file": cfg["raw_filename"],
                "tapr_fields": list(cfg["field_map"].keys()),
                "output_columns": list(cfg["field_map"].values()),
            }
            for cfg in _TAPR_FILE_CONFIGS
        ],
    }
    report_path.write_text(json.dumps(report, indent=2))

    # ── Console summary ───────────────────────────────────────────────────────

    print(f"\n{'='*60}")
    print(f"Cohort rows    : {len(result)}")
    print(f"TAPR matched   : {matched} / {len(result)}")
    if unmatched:
        print(f"Unmatched IDs  : {result.loc[~result['tapr_matched'], 'campus_id'].tolist()}")
    print(f"\nNull counts per output column:")
    for col, n in null_counts.items():
        flag = " <- suppressed/missing" if n > 0 else ""
        print(f"  {col:<55} {n}{flag}")
    print(f"\nSuppression codes (cohort campuses): {code_totals}")
    print(f"\nOutputs:")
    for p in [csv_path, parquet_path, report_path, dd_path]:
        print(f"  {p}")

    return result


if __name__ == "__main__":
    build_tapr()
