"""
Phase 5 – Final dataset cleanup, quality validation, and submission-ready exports.

Reads : data/processed/cohort_enriched.csv
Writes:
    data/processed/dallas_school_insights.csv
    data/processed/dallas_school_insights.parquet
    data/processed/data_dictionary.csv
    data/processed/data_quality_report.json
    data/processed/source_coverage_report.csv
"""

from __future__ import annotations

import json
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
ENRICHED_CSV = PROCESSED / "cohort_enriched.csv"

OUTPUT_CSV = PROCESSED / "dallas_school_insights.csv"
OUTPUT_PARQUET = PROCESSED / "dallas_school_insights.parquet"
OUTPUT_DD_CSV = PROCESSED / "data_dictionary.csv"
OUTPUT_QUALITY = PROCESSED / "data_quality_report.json"
OUTPUT_COVERAGE = PROCESSED / "source_coverage_report.csv"

# ---------------------------------------------------------------------------
# Column selection
# ---------------------------------------------------------------------------

FINAL_COLUMNS: List[str] = [
    # -- Identity (AskTED 2025) -----------------------------------------------
    "campus_id",
    "district_id",
    "nces_school_id",
    "school_name",
    "district_name",
    "district_type",
    "instruction_type",
    "charter_type",
    "school_level",
    "operator_type",
    "grade_range",
    "enrollment",
    "school_status",
    "school_site_city",
    "school_site_address",
    "school_site_zip",
    "magnet_status",
    "enrollment_source_year",
    # -- Accountability (TEA 2025) --------------------------------------------
    "accountability_rating_2025",
    "accountability_status_2025",
    "accountability_score_2025",
    "acct_grade_type_2025",
    "acct_grade_span_2025",
    "acct_grade_low_2025",
    "acct_grade_high_2025",
    "acct_alt_ed_flag_2025",
    "acct_daep_flag_2025",
    "acct_jj_flag_2025",
    "acct_alted_flag_2025",
    "acct_residential_flag_2025",
    # -- Special education - TAPR 2025 ----------------------------------------
    "tapr_membership_all_count_2025",
    "tapr_membership_sped_count_2025",
    "tapr_membership_sped_pct_2025",
    "tapr_enrollment_all_count_2025",
    "tapr_enrollment_sped_count_2025",
    "tapr_enrollment_sped_pct_2025",
    # -- Attendance and chronic absenteeism - TAPR 2025 (measures 2024) -------
    "tapr_att_all_rate_2024",
    "tapr_att_sped_rate_2024",
    "tapr_chronic_abs_all_rate_2024",
    "tapr_chronic_abs_sped_rate_2024",
    # -- Teacher experience - TAPR 2025 ----------------------------------------
    "tapr_avg_teacher_exp_years_2025",
    "tapr_avg_teacher_tenure_years_2025",
    "tapr_beginning_teacher_fte_pct_2025",
    "tapr_teacher_1to5yr_pct_2025",
    "tapr_teacher_6to10yr_pct_2025",
    "tapr_teacher_11to20yr_pct_2025",
    "tapr_teacher_21to30yr_pct_2025",
    "tapr_teacher_over30yr_pct_2025",
    # -- Disability enrollment - CRDC 2021-22 ----------------------------------
    "crdc_tot_enr_total_2122",
    "crdc_idea_enr_total_2122",
    "crdc_504_enr_total_2122",
    # -- Suspension and discipline - CRDC 2021-22 -----------------------------
    "crdc_idea_iss_students_total_2122",
    "crdc_oos_instances_no_dis_2122",
    "crdc_oos_instances_idea_2122",
    "crdc_oos_instances_504_2122",
    "crdc_idea_sing_oos_total_2122",
    "crdc_idea_mult_oos_total_2122",
    # -- Expulsions - CRDC 2021-22 --------------------------------------------
    "crdc_idea_exp_with_svc_total_2122",
    "crdc_idea_exp_no_svc_total_2122",
    "crdc_idea_exp_zerotol_total_2122",
    # -- Restraint and seclusion (instances) - CRDC 2021-22 -------------------
    "crdc_rs_mech_instances_idea_2122",
    "crdc_rs_phys_instances_idea_2122",
    "crdc_rs_secl_instances_idea_2122",
    # -- Disability-based harassment - CRDC 2021-22 ---------------------------
    "crdc_hb_dis_allegations_2122",
    "crdc_hb_dis_reported_total_2122",
    "crdc_hb_dis_disciplined_total_2122",
    # -- Law enforcement referrals and arrests - CRDC 2021-22 -----------------
    "crdc_idea_ref_law_total_2122",
    "crdc_idea_arr_total_2122",
    # -- Offenses reported - CRDC 2021-22 ------------------------------------
    "crdc_offense_assault_with_wpn_2122",
    "crdc_offense_assault_no_wpn_2122",
    "crdc_offense_wpn_possession_2122",
    "crdc_offense_robbery_with_wpn_2122",
    "crdc_offense_robbery_no_wpn_2122",
    "crdc_offense_threat_with_wpn_2122",
    "crdc_offense_threat_no_wpn_2122",
    "crdc_offense_firearm_ind_2122",
    "crdc_offense_homicide_ind_2122",
    # -- Geocoordinates - ArcGIS 2024-25 -------------------------------------
    "latitude",
    "longitude",
]

# Columns that exist in cohort_enriched but are intentionally excluded, with reason.
DROPPED_LOG: Dict[str, str] = {
    # Pipeline-internal flags / constants (documented in data dictionary)
    "tapr_matched": "internal pipeline flag",
    "tapr_suppression_codes": "internal suppression metadata; not useful to evaluators",
    "tapr_source_year": "constant 2025; documented in data dictionary source_year column",
    "crdc_matched": "internal pipeline flag",
    "crdc_suppression_codes": "internal suppression metadata; not useful to evaluators",
    "crdc_collection_year": "constant 2021-22; documented in data dictionary",
    "accountability_matched": "internal pipeline flag",
    "accountability_source_year": "constant 2025; documented in data dictionary",
    "arcgis_matched": "internal pipeline flag",
    "geocode_source": "constant TEA ArcGIS Schools 2024-25; documented in data dictionary",
    "arcgis_source_year": "constant 2024-25; documented in data dictionary",
    # Accountability - redundant or all-null
    "acct_charter_flag_2025": "duplicated by district_type and charter_type",
    "acct_alt_ed_type_2025": "all-null (60/60 null for cohort schools)",
    # TAPR numerators/denominators (rates kept)
    "tapr_att_all_days_present_2024": "numerator; tapr_att_all_rate_2024 kept",
    "tapr_att_all_days_membership_2024": "denominator; rate kept",
    "tapr_att_sped_days_present_2024": "numerator; tapr_att_sped_rate_2024 kept",
    "tapr_att_sped_days_membership_2024": "denominator; rate kept",
    "tapr_chronic_abs_all_numerator_2024": "numerator; tapr_chronic_abs_all_rate_2024 kept",
    "tapr_chronic_abs_all_denominator_2024": "denominator; rate kept",
    "tapr_chronic_abs_sped_numerator_2024": "numerator; tapr_chronic_abs_sped_rate_2024 kept",
    "tapr_chronic_abs_sped_denominator_2024": "denominator; rate kept",
    "tapr_beginning_teacher_fte_count_2025": "count; tapr_beginning_teacher_fte_pct_2025 kept",
    # CRDC - all-null (TX does not report non-binary gender counts)
    "crdc_tot_enr_x_2122": "all-null; TX schools do not report non-binary gender",
    "crdc_idea_enr_x_2122": "all-null",
    "crdc_idea_enr_alt_x_2122": "all-null",
    "crdc_504_enr_x_2122": "all-null",
    # CRDC - mechanical/seclusion student counts all-null; physical students too sparse
    "crdc_rs_mech_students_m_2122": "all-null for cohort",
    "crdc_rs_mech_students_f_2122": "all-null for cohort",
    "crdc_rs_mech_students_total_2122": "all-null for cohort",
    "crdc_rs_secl_students_m_2122": "all-null for cohort",
    "crdc_rs_secl_students_f_2122": "all-null for cohort",
    "crdc_rs_secl_students_total_2122": "all-null for cohort",
    "crdc_rs_phys_students_m_2122": "only 4/60 schools have data; too sparse",
    "crdc_rs_phys_students_f_2122": "only 4/60 schools have data; too sparse",
    "crdc_rs_phys_students_total_2122": "only 4/60 schools have data; too sparse",
    # CRDC - M/F breakdowns (combined totals kept)
    "crdc_tot_enr_m_2122": "M breakdown; crdc_tot_enr_total_2122 kept",
    "crdc_tot_enr_f_2122": "F breakdown; total kept",
    "crdc_idea_enr_m_2122": "M breakdown; crdc_idea_enr_total_2122 kept",
    "crdc_idea_enr_f_2122": "F breakdown; total kept",
    "crdc_idea_enr_alt_m_2122": "duplicate of primary IDEA enrollment M; M breakdown",
    "crdc_idea_enr_alt_f_2122": "duplicate of primary IDEA enrollment F; F breakdown",
    "crdc_idea_enr_alt_total_2122": "duplicate of crdc_idea_enr_total_2122 for cohort",
    "crdc_504_enr_m_2122": "M breakdown; crdc_504_enr_total_2122 kept",
    "crdc_504_enr_f_2122": "F breakdown; total kept",
    "crdc_idea_iss_students_m_2122": "M breakdown; crdc_idea_iss_students_total_2122 kept",
    "crdc_idea_iss_students_f_2122": "F breakdown; total kept",
    "crdc_504_iss_students_m_2122": "M breakdown; no total available in pipeline",
    "crdc_504_iss_students_f_2122": "F breakdown; no total available in pipeline",
    "crdc_idea_sing_oos_m_2122": "M breakdown; crdc_idea_sing_oos_total_2122 kept",
    "crdc_idea_sing_oos_f_2122": "F breakdown; total kept",
    "crdc_idea_mult_oos_m_2122": "M breakdown; crdc_idea_mult_oos_total_2122 kept",
    "crdc_idea_mult_oos_f_2122": "F breakdown; total kept",
    "crdc_idea_oos_days_missed_m_2122": "M only; no combined total in pipeline",
    "crdc_idea_oos_days_missed_f_2122": "F only; no combined total in pipeline",
    "crdc_idea_exp_with_svc_m_2122": "M breakdown; crdc_idea_exp_with_svc_total_2122 kept",
    "crdc_idea_exp_with_svc_f_2122": "F breakdown; total kept",
    "crdc_idea_exp_no_svc_m_2122": "M breakdown; crdc_idea_exp_no_svc_total_2122 kept",
    "crdc_idea_exp_no_svc_f_2122": "F breakdown; total kept",
    "crdc_idea_exp_zerotol_m_2122": "M breakdown; crdc_idea_exp_zerotol_total_2122 kept",
    "crdc_idea_exp_zerotol_f_2122": "F breakdown; total kept",
    "crdc_hb_dis_reported_m_2122": "M breakdown; crdc_hb_dis_reported_total_2122 kept",
    "crdc_hb_dis_reported_f_2122": "F breakdown; total kept",
    "crdc_hb_dis_reported_idea_m_2122": "IDEA M breakdown; no IDEA total in pipeline",
    "crdc_hb_dis_reported_idea_f_2122": "IDEA F breakdown",
    "crdc_hb_dis_disciplined_m_2122": "M breakdown; crdc_hb_dis_disciplined_total_2122 kept",
    "crdc_hb_dis_disciplined_f_2122": "F breakdown; total kept",
    "crdc_hb_dis_disciplined_idea_m_2122": "IDEA M breakdown",
    "crdc_hb_dis_disciplined_idea_f_2122": "IDEA F breakdown",
    "crdc_idea_ref_law_m_2122": "M breakdown; crdc_idea_ref_law_total_2122 kept",
    "crdc_idea_ref_law_f_2122": "F breakdown; total kept",
    "crdc_idea_arr_m_2122": "M breakdown; crdc_idea_arr_total_2122 kept",
    "crdc_idea_arr_f_2122": "F breakdown; total kept",
}

# ---------------------------------------------------------------------------
# Identity column data dictionary definitions (not in data_dictionary.json)
# ---------------------------------------------------------------------------

_IDENTITY_DD: Dict[str, Tuple] = {
    # (data_type, definition, source, source_year, raw_cleaned_or_derived, caveat)
    "campus_id": (
        "string", "Nine-digit TEA campus ID (zero-padded). Primary join key across all TEA sources.",
        "TEA AskTED", "2025", "cleaned",
        "Leading apostrophe stripped from AskTED source value.",
    ),
    "district_id": (
        "string", "Six-digit TEA district ID (zero-padded).",
        "TEA AskTED", "2025", "cleaned", "",
    ),
    "nces_school_id": (
        "string", "12-digit NCES school ID. Used to join CRDC data (equals COMBOKEY in CRDC files).",
        "TEA AskTED", "2025", "cleaned",
        "2 of 60 cohort schools had no CRDC match on this key.",
    ),
    "school_name": (
        "string", "Campus name as listed in AskTED.",
        "TEA AskTED", "2025", "cleaned", "",
    ),
    "district_name": (
        "string", "District or charter operator name.",
        "TEA AskTED", "2025", "cleaned", "",
    ),
    "district_type": (
        "string", "District classification: INDEPENDENT or CHARTER.",
        "TEA AskTED", "2025", "cleaned",
        "Private schools excluded from cohort.",
    ),
    "instruction_type": (
        "string", "Instruction type: REGULAR INSTRUCTIONAL or ALTERNATIVE INSTRUCTIONAL.",
        "TEA AskTED", "2025", "cleaned",
        "DAEP and JJAEP campuses excluded from cohort.",
    ),
    "charter_type": (
        "string", "Charter classification (OPEN ENROLLMENT CHARTER for charter campuses; null for ISDs).",
        "TEA AskTED", "2025", "cleaned",
        "Null for non-charter campuses.",
    ),
    "school_level": (
        "string", "Derived school level: elementary, middle, high, or mixed.",
        "TEA AskTED (derived)", "2025", "derived",
        "Derived from grade_range using TEA grade spans.",
    ),
    "operator_type": (
        "string", "Operator classification: charter or isd.",
        "TEA AskTED (derived)", "2025", "derived",
        "Derived from district_type.",
    ),
    "grade_range": (
        "string", "Grades served (e.g. KG-12, 09-12).",
        "TEA AskTED", "2025", "cleaned", "",
    ),
    "enrollment": (
        "float", "Student enrollment count as of October 2025.",
        "TEA AskTED", "2025", "cleaned",
        "AskTED sentinel -1 converted to null.",
    ),
    "school_status": (
        "string", "School operational status (Active for all rows in cohort).",
        "TEA AskTED", "2025", "cleaned",
        "All rows Active; inactive and under-construction schools excluded from cohort.",
    ),
    "school_site_city": (
        "string", "Physical site city (DALLAS for all rows; cohort filtered on this field).",
        "TEA AskTED", "2025", "cleaned",
        "All rows DALLAS.",
    ),
    "school_site_address": (
        "string", "Physical site street address.",
        "TEA AskTED", "2025", "cleaned", "",
    ),
    "school_site_zip": (
        "string", "Physical site ZIP code.",
        "TEA AskTED", "2025", "cleaned", "",
    ),
    "magnet_status": (
        "string", "Magnet school flag from AskTED (Y or N).",
        "TEA AskTED", "2025", "cleaned", "",
    ),
    "enrollment_source_year": (
        "integer", "Collection year of the enrollment field (2025 = October 2025 snapshot).",
        "TEA AskTED", "2025", "cleaned", "",
    ),
}

# ---------------------------------------------------------------------------
# Quality-check helpers
# ---------------------------------------------------------------------------

_VALID_RATINGS = {"A", "B", "C", "D", "F", "Not Rated"}
_PCT_COLS = [
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
]
_COUNT_COLS = [
    "enrollment",
    "tapr_membership_all_count_2025",
    "tapr_membership_sped_count_2025",
    "tapr_enrollment_all_count_2025",
    "tapr_enrollment_sped_count_2025",
    "crdc_tot_enr_total_2122",
    "crdc_idea_enr_total_2122",
    "crdc_504_enr_total_2122",
    "crdc_idea_iss_students_total_2122",
    "crdc_oos_instances_no_dis_2122",
    "crdc_oos_instances_idea_2122",
    "crdc_oos_instances_504_2122",
    "crdc_idea_sing_oos_total_2122",
    "crdc_idea_mult_oos_total_2122",
    "crdc_idea_exp_with_svc_total_2122",
    "crdc_idea_exp_no_svc_total_2122",
    "crdc_idea_exp_zerotol_total_2122",
    "crdc_rs_mech_instances_idea_2122",
    "crdc_rs_phys_instances_idea_2122",
    "crdc_rs_secl_instances_idea_2122",
    "crdc_hb_dis_allegations_2122",
    "crdc_hb_dis_reported_total_2122",
    "crdc_hb_dis_disciplined_total_2122",
    "crdc_idea_ref_law_total_2122",
    "crdc_idea_arr_total_2122",
    "crdc_offense_assault_with_wpn_2122",
    "crdc_offense_assault_no_wpn_2122",
    "crdc_offense_wpn_possession_2122",
    "crdc_offense_robbery_with_wpn_2122",
    "crdc_offense_robbery_no_wpn_2122",
    "crdc_offense_threat_with_wpn_2122",
    "crdc_offense_threat_no_wpn_2122",
]
_REQUIRED_IDENTITY = [
    "campus_id", "school_name", "district_name",
    "school_site_address", "enrollment",
]
_SENTINEL_STRINGS = {"-1", "-2", "-3", "-9"}
_SENTINEL_NUMS = {-1, -2, -3, -9}


def _run_quality_checks(df: pd.DataFrame) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def _add(name: str, passed: bool, **kw) -> None:
        checks.append({"name": name, "passed": bool(passed), **kw})

    # 1. Row count
    _add("row_count_equals_60", len(df) == 60, value=int(len(df)))

    # 2. No duplicate campus_ids
    dup_ids = int(df["campus_id"].duplicated().sum())
    _add("no_duplicate_campus_ids", dup_ids == 0, duplicate_count=dup_ids)

    # 3. No duplicate NCES IDs (for populated rows)
    nces_pop = df["nces_school_id"].dropna()
    dup_nces = int(nces_pop.duplicated().sum())
    _add("no_duplicate_nces_ids", dup_nces == 0, duplicate_count=dup_nces)

    # 4. Required identity fields populated
    missing_counts: Dict[str, int] = {}
    for col in _REQUIRED_IDENTITY:
        if col in df.columns:
            missing_counts[col] = int(df[col].isna().sum())
    id_ok = all(v == 0 for v in missing_counts.values())
    _add("required_identity_fields_populated", id_ok, missing_counts=missing_counts)

    # 5. Valid percentages in [0, 100]
    pct_issues: Dict[str, int] = {}
    for col in _PCT_COLS:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        out = int(((s < 0) | (s > 100)).sum())
        if out:
            pct_issues[col] = out
    _add("valid_percentages_in_range_0_100", len(pct_issues) == 0, violations=pct_issues)

    # 6. Valid counts >= 0
    count_issues: Dict[str, int] = {}
    for col in _COUNT_COLS:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        neg = int((s < 0).sum())
        if neg:
            count_issues[col] = neg
    _add("valid_counts_nonnegative", len(count_issues) == 0, violations=count_issues)

    # 7. Valid accountability rating codes
    if "accountability_rating_2025" in df.columns:
        present = df["accountability_rating_2025"].dropna()
        bad = present[~present.isin(_VALID_RATINGS)].unique().tolist()
        _add("valid_accountability_rating_codes", len(bad) == 0, invalid_values=bad)
    else:
        _add("valid_accountability_rating_codes", False, invalid_values=["column missing"])

    # 8. Valid Dallas coordinates
    if "latitude" in df.columns and "longitude" in df.columns:
        lat = pd.to_numeric(df["latitude"], errors="coerce")
        lon = pd.to_numeric(df["longitude"], errors="coerce")
        bad_lat = int(((lat < 32.5) | (lat > 33.2)).sum())
        bad_lon = int(((lon < -97.2) | (lon > -96.4)).sum())
        _add(
            "valid_dallas_coordinates",
            bad_lat == 0 and bad_lon == 0,
            out_of_range_lat=bad_lat,
            out_of_range_lon=bad_lon,
        )
    else:
        _add("valid_dallas_coordinates", False, out_of_range_lat=-1, out_of_range_lon=-1)

    # 9. No suppression sentinels remaining
    sentinel_hits: Dict[str, int] = {}
    analytical_cols = [c for c in FINAL_COLUMNS if c not in _IDENTITY_DD and c in df.columns]
    for col in analytical_cols:
        s = df[col]
        if pd.api.types.is_object_dtype(s):
            hits = int(s.isin(_SENTINEL_STRINGS).sum())
        else:
            hits = int(pd.to_numeric(s, errors="coerce").isin(_SENTINEL_NUMS).sum())
        if hits:
            sentinel_hits[col] = hits
    _add("no_suppression_sentinels", len(sentinel_hits) == 0, sentinel_counts=sentinel_hits)

    # 10. No all-null analytical columns
    all_null_cols = [
        c for c in analytical_cols if df[c].isna().all()
    ]
    _add("no_all_null_analytical_columns", len(all_null_cols) == 0, all_null_columns=all_null_cols)

    # 11. Accountability score in plausible range when present
    if "accountability_score_2025" in df.columns:
        score = pd.to_numeric(df["accountability_score_2025"], errors="coerce").dropna()
        bad_score = int(((score < 0) | (score > 100)).sum())
        _add("accountability_score_in_range", bad_score == 0, out_of_range=bad_score)
    else:
        _add("accountability_score_in_range", False, out_of_range=-1)

    # 12. CRDC match coverage >= 90%
    crdc_cols = [c for c in df.columns if c.startswith("crdc_")]
    if crdc_cols:
        null_counts = df[crdc_cols].isna().sum()
        worst_coverage = float(round(100 * (1 - null_counts.max() / len(df)), 1))
        _add("crdc_coverage_at_least_90pct", worst_coverage >= 90.0, worst_coverage_pct=worst_coverage)
    else:
        _add("crdc_coverage_at_least_90pct", False, worst_coverage_pct=0)

    n_passed = sum(1 for c in checks if c["passed"])
    return {
        "generated_utc": datetime.now(tz=timezone.utc).isoformat(),
        "total_checks": len(checks),
        "checks_passed": n_passed,
        "checks_failed": len(checks) - n_passed,
        "all_checks_passed": n_passed == len(checks),
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# Data dictionary CSV
# ---------------------------------------------------------------------------

def _build_data_dictionary(df: pd.DataFrame) -> pd.DataFrame:
    dd_json_path = PROCESSED / "data_dictionary.json"
    dd_json: Dict[str, Any] = {}
    if dd_json_path.exists():
        with open(dd_json_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        dd_json = {f["column"]: f for f in raw.get("fields", [])}

    rows: List[Dict[str, Any]] = []

    for col in FINAL_COLUMNS:
        # Coverage from actual data
        cov = round(100.0 * df[col].notna().sum() / len(df), 1) if col in df.columns else 0.0

        if col in _IDENTITY_DD:
            dt, defn, src, src_yr, r_c_d, caveat = _IDENTITY_DD[col]
            rows.append(
                {
                    "column_name": col,
                    "data_type": dt,
                    "definition": defn,
                    "source": src,
                    "source_year": src_yr,
                    "raw_cleaned_or_derived": r_c_d,
                    "coverage_percent": cov,
                    "caveat": caveat,
                }
            )
            continue

        entry = dd_json.get(col)
        if entry is None:
            rows.append(
                {
                    "column_name": col,
                    "data_type": "unknown",
                    "definition": "",
                    "source": "",
                    "source_year": "",
                    "raw_cleaned_or_derived": "",
                    "coverage_percent": cov,
                    "caveat": "NOT FOUND in data_dictionary.json",
                }
            )
            continue

        # Map JSON schema to CSV schema
        src = entry.get("source", "")
        raw_yr = entry.get("source_year") or entry.get("measure_year")
        if raw_yr:
            src_yr = str(raw_yr)
        elif col.endswith("_2122"):
            src_yr = "2021-22"
        elif col.endswith("_2025") or col.endswith("_2024"):
            src_yr = col[-4:]
        else:
            src_yr = ""
        defn = entry.get("description", "")
        dtype = entry.get("type", "")

        # raw_cleaned_or_derived
        if src in ("derived", "pipeline"):
            r_c_d = "derived"
        elif any(
            k in entry
            for k in ("suppression_notes", "sentinel_notes", "crdc_field")
        ):
            r_c_d = "cleaned"
        else:
            r_c_d = "cleaned"

        caveat_parts = []
        for key in ("notes", "suppression_notes", "sentinel_notes"):
            v = entry.get(key)
            if v:
                caveat_parts.append(str(v))
        caveat = " | ".join(caveat_parts)

        rows.append(
            {
                "column_name": col,
                "data_type": dtype,
                "definition": defn,
                "source": src,
                "source_year": src_yr,
                "raw_cleaned_or_derived": r_c_d,
                "coverage_percent": cov,
                "caveat": caveat,
            }
        )

    return pd.DataFrame(rows, columns=[
        "column_name", "data_type", "definition", "source", "source_year",
        "raw_cleaned_or_derived", "coverage_percent", "caveat",
    ])


# ---------------------------------------------------------------------------
# Source coverage report
# ---------------------------------------------------------------------------

def _build_source_coverage(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)

    def _load_report(name: str) -> Dict[str, Any]:
        p = PROCESSED / name
        if p.exists():
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        return {}

    acct = _load_report("accountability_join_report.json")
    arcgis = _load_report("arcgis_join_report.json")
    crdc = _load_report("crdc_join_report.json")
    tapr = _load_report("tapr_join_report.json")

    def _pct(matched: int, tot: int) -> float:
        return round(100.0 * matched / tot, 1) if tot else 0.0

    records = [
        {
            "source": "TEA AskTED",
            "source_year": "2025",
            "primary_join_key": "campus_id",
            "schools_matched": total,
            "schools_total": total,
            "match_pct": 100.0,
            "notes": "Canonical roster; all cohort schools by definition.",
        },
        {
            "source": "TAPR",
            "source_year": str(tapr.get("source_year", "2025")),
            "primary_join_key": "campus_id",
            "schools_matched": int(tapr.get("tapr_matched", total)),
            "schools_total": total,
            "match_pct": _pct(int(tapr.get("tapr_matched", total)), total),
            "notes": tapr.get("notes", ""),
        },
        {
            "source": "CRDC",
            "source_year": "2021-22",
            "primary_join_key": "nces_school_id (= COMBOKEY)",
            "schools_matched": int(crdc.get("crdc_matched", 58)),
            "schools_total": total,
            "match_pct": _pct(int(crdc.get("crdc_matched", 58)), total),
            "notes": "2 cohort schools had no CRDC match on NCES school ID.",
        },
        {
            "source": "TEA 2025 Campus Accountability Summary",
            "source_year": str(acct.get("source_year", "2025")),
            "primary_join_key": "campus_id",
            "schools_matched": int(acct.get("accountability_matched", total)),
            "schools_total": total,
            "match_pct": _pct(int(acct.get("accountability_matched", total)), total),
            "notes": acct.get("notes", ""),
        },
        {
            "source": "TEA ArcGIS Schools 2024-25",
            "source_year": str(arcgis.get("source_year", "2024-25")),
            "primary_join_key": "campus_id",
            "schools_matched": int(arcgis.get("arcgis_matched", total)),
            "schools_total": total,
            "match_pct": _pct(int(arcgis.get("arcgis_matched", total)), total),
            "notes": "Coordinates for display only; geocoder output from ArcGIS snapshot.",
        },
    ]

    return pd.DataFrame(
        records,
        columns=[
            "source", "source_year", "primary_join_key",
            "schools_matched", "schools_total", "match_pct", "notes",
        ],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not ENRICHED_CSV.exists():
        sys.exit(
            f"ERROR: {ENRICHED_CSV} not found. Run build_enriched.py first."
        )

    print(f"Reading {ENRICHED_CSV} ...")
    df_enriched = pd.read_csv(
        ENRICHED_CSV,
        dtype={"campus_id": str, "district_id": str, "nces_school_id": str},
    )
    print(f"  -> {df_enriched.shape[0]} rows x {df_enriched.shape[1]} columns")

    # Validate all expected FINAL_COLUMNS are present
    missing_cols = [c for c in FINAL_COLUMNS if c not in df_enriched.columns]
    if missing_cols:
        sys.exit(f"ERROR: columns missing from enriched CSV: {missing_cols}")

    # Validate no undocumented drop (warn only)
    all_cols = set(df_enriched.columns)
    kept = set(FINAL_COLUMNS)
    dropped_in_script = all_cols - kept
    undocumented = dropped_in_script - set(DROPPED_LOG.keys())
    if undocumented:
        print(f"WARNING: {len(undocumented)} columns dropped without a log entry:")
        for c in sorted(undocumented):
            print(f"  {c}")

    # Select final columns
    df = df_enriched[FINAL_COLUMNS].copy()
    print(f"\nFinal dataset shape: {df.shape[0]} rows x {df.shape[1]} columns")

    # -- Quality checks -------------------------------------------------------
    print("\nRunning quality checks ...")
    quality = _run_quality_checks(df)
    for chk in quality["checks"]:
        status = "PASS" if chk["passed"] else "FAIL"
        print(f"  [{status}] {chk['name']}")

    if quality["all_checks_passed"]:
        print(f"\nAll {quality['total_checks']} checks passed.")
    else:
        print(
            f"\n{quality['checks_failed']} of {quality['total_checks']} checks FAILED."
        )

    # -- Write outputs --------------------------------------------------------
    PROCESSED.mkdir(parents=True, exist_ok=True)

    print(f"\nWriting {OUTPUT_CSV} ...")
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Writing {OUTPUT_PARQUET} ...")
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, OUTPUT_PARQUET)

    print(f"Writing {OUTPUT_QUALITY} ...")
    with open(OUTPUT_QUALITY, "w", encoding="utf-8") as fh:
        json.dump(quality, fh, indent=2)

    print(f"Writing {OUTPUT_DD_CSV} ...")
    dd_df = _build_data_dictionary(df)
    dd_df.to_csv(OUTPUT_DD_CSV, index=False)
    missing_def = dd_df[dd_df["definition"] == ""]["column_name"].tolist()
    if missing_def:
        print(f"  WARNING: {len(missing_def)} columns have no definition: {missing_def}")

    print(f"Writing {OUTPUT_COVERAGE} ...")
    cov_df = _build_source_coverage(df)
    cov_df.to_csv(OUTPUT_COVERAGE, index=False)

    # -- Summary --------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Phase 5 complete.")
    print(f"  Final dataset : {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"  Columns kept  : {len(FINAL_COLUMNS)}")
    print(f"  Columns dropped from enriched: {len(DROPPED_LOG)}")
    print(f"  Quality checks: {quality['checks_passed']}/{quality['total_checks']} passed")
    print(f"\nOutputs:")
    for p in [OUTPUT_CSV, OUTPUT_PARQUET, OUTPUT_DD_CSV, OUTPUT_QUALITY, OUTPUT_COVERAGE]:
        size = p.stat().st_size if p.exists() else 0
        print(f"  {p.relative_to(ROOT)}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
