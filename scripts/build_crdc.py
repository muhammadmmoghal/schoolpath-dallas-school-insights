"""
Phase 3 – Step 2: Parse CRDC school files, normalize, and join to the cohort.

Reads extracted CRDC CSVs from data/raw/crdc_2021_22/SCH/.
Filters to cohort schools by COMBOKEY (= nces_school_id).
Converts the -9 sentinel to null; preserves 0 as a real zero.
Left-joins all CRDC sources to the TAPR-enriched cohort by nces_school_id.

Derived M+F totals are computed for student-count fields when both components
are non-null; they are clearly labeled *_total_* and documented as derived.

Outputs:
  data/processed/cohort_crdc.csv          – 60-row cohort with TAPR + CRDC fields
  data/processed/cohort_crdc.parquet      – same, typed nullable numerics
  data/processed/crdc_join_report.json    – join coverage and null summary
  data/processed/data_dictionary.json     – CRDC entries appended to TAPR entries
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

_ROOT = Path(__file__).parent.parent
CRDC_SCH_DIR = _ROOT / "data" / "raw" / "crdc_2021_22" / "SCH"
PROCESSED_DIR = _ROOT / "data" / "processed"
COHORT_TAPR = PROCESSED_DIR / "cohort_tapr.csv"
DD_PATH = PROCESSED_DIR / "data_dictionary.json"

CRDC_COLLECTION_YEAR = "2021-22"
_CRDC_SENTINEL = "-9"
_CHUNK_SIZE = 50_000

# ──────────────────────────────────────────────────────────────────────────────
# Field maps: raw CRDC column → output column name
# ──────────────────────────────────────────────────────────────────────────────

ENROLLMENT_FIELDS: dict[str, str] = {
    "TOT_ENR_M":       "crdc_tot_enr_m_2122",
    "TOT_ENR_F":       "crdc_tot_enr_f_2122",
    "TOT_ENR_X":       "crdc_tot_enr_x_2122",
    "SCH_ENR_IDEA_M":  "crdc_idea_enr_m_2122",
    "SCH_ENR_IDEA_F":  "crdc_idea_enr_f_2122",
    "SCH_ENR_IDEA_X":  "crdc_idea_enr_x_2122",
    "TOT_IDEAENR_M":   "crdc_idea_enr_alt_m_2122",
    "TOT_IDEAENR_F":   "crdc_idea_enr_alt_f_2122",
    "TOT_IDEAENR_X":   "crdc_idea_enr_alt_x_2122",
    "SCH_ENR_504_M":   "crdc_504_enr_m_2122",
    "SCH_ENR_504_F":   "crdc_504_enr_f_2122",
    "SCH_ENR_504_X":   "crdc_504_enr_x_2122",
}

SUSPENSION_FIELDS: dict[str, str] = {
    "TOT_DISCWDIS_ISS_IDEA_M":    "crdc_idea_iss_students_m_2122",
    "TOT_DISCWDIS_ISS_IDEA_F":    "crdc_idea_iss_students_f_2122",
    "SCH_DISCWDIS_ISS_504_M":     "crdc_504_iss_students_m_2122",
    "SCH_DISCWDIS_ISS_504_F":     "crdc_504_iss_students_f_2122",
    "SCH_OOSINSTANCES_WODIS":     "crdc_oos_instances_no_dis_2122",
    "SCH_OOSINSTANCES_IDEA":      "crdc_oos_instances_idea_2122",
    "SCH_OOSINSTANCES_504":       "crdc_oos_instances_504_2122",
    "TOT_DISCWDIS_SINGOOS_IDEA_M":"crdc_idea_sing_oos_m_2122",
    "TOT_DISCWDIS_SINGOOS_IDEA_F":"crdc_idea_sing_oos_f_2122",
    "TOT_DISCWDIS_MULTOOS_IDEA_M":"crdc_idea_mult_oos_m_2122",
    "TOT_DISCWDIS_MULTOOS_IDEA_F":"crdc_idea_mult_oos_f_2122",
    "SCH_DAYSMISSED_IDEA_M":      "crdc_idea_oos_days_missed_m_2122",
    "SCH_DAYSMISSED_IDEA_F":      "crdc_idea_oos_days_missed_f_2122",
}

EXPULSION_FIELDS: dict[str, str] = {
    "TOT_DISCWDIS_EXPWE_IDEA_M":  "crdc_idea_exp_with_svc_m_2122",
    "TOT_DISCWDIS_EXPWE_IDEA_F":  "crdc_idea_exp_with_svc_f_2122",
    "TOT_DISCWDIS_EXPWOE_IDEA_M": "crdc_idea_exp_no_svc_m_2122",
    "TOT_DISCWDIS_EXPWOE_IDEA_F": "crdc_idea_exp_no_svc_f_2122",
    "TOT_DISCWDIS_EXPZT_IDEA_M":  "crdc_idea_exp_zerotol_m_2122",
    "TOT_DISCWDIS_EXPZT_IDEA_F":  "crdc_idea_exp_zerotol_f_2122",
}

RESTRAINT_FIELDS: dict[str, str] = {
    "SCH_RSINSTANCES_MECH_IDEA": "crdc_rs_mech_instances_idea_2122",
    "SCH_RSINSTANCES_PHYS_IDEA": "crdc_rs_phys_instances_idea_2122",
    "SCH_RSINSTANCES_SECL_IDEA": "crdc_rs_secl_instances_idea_2122",
    "TOT_RS_IDEA_MECH_M":        "crdc_rs_mech_students_m_2122",
    "TOT_RS_IDEA_MECH_F":        "crdc_rs_mech_students_f_2122",
    "TOT_RS_IDEA_PHYS_M":        "crdc_rs_phys_students_m_2122",
    "TOT_RS_IDEA_PHYS_F":        "crdc_rs_phys_students_f_2122",
    "TOT_RS_IDEA_SECL_M":        "crdc_rs_secl_students_m_2122",
    "TOT_RS_IDEA_SECL_F":        "crdc_rs_secl_students_f_2122",
}

HARASSMENT_FIELDS: dict[str, str] = {
    "SCH_HBALLEGATIONS_DIS":        "crdc_hb_dis_allegations_2122",
    "TOT_HBREPORTED_DIS_M":         "crdc_hb_dis_reported_m_2122",
    "TOT_HBREPORTED_DIS_F":         "crdc_hb_dis_reported_f_2122",
    "SCH_HBREPORTED_DIS_IDEA_M":    "crdc_hb_dis_reported_idea_m_2122",
    "SCH_HBREPORTED_DIS_IDEA_F":    "crdc_hb_dis_reported_idea_f_2122",
    "TOT_HBDISCIPLINED_DIS_M":      "crdc_hb_dis_disciplined_m_2122",
    "TOT_HBDISCIPLINED_DIS_F":      "crdc_hb_dis_disciplined_f_2122",
    "SCH_HBDISCIPLINED_DIS_IDEA_M": "crdc_hb_dis_disciplined_idea_m_2122",
    "SCH_HBDISCIPLINED_DIS_IDEA_F": "crdc_hb_dis_disciplined_idea_f_2122",
}

REFERRAL_FIELDS: dict[str, str] = {
    "TOT_DISCWDIS_REF_IDEA_M": "crdc_idea_ref_law_m_2122",
    "TOT_DISCWDIS_REF_IDEA_F": "crdc_idea_ref_law_f_2122",
    "TOT_DISCWDIS_ARR_IDEA_M": "crdc_idea_arr_m_2122",
    "TOT_DISCWDIS_ARR_IDEA_F": "crdc_idea_arr_f_2122",
}

OFFENSE_FIELDS: dict[str, str] = {
    "SCH_OFFENSE_ATTWW":  "crdc_offense_assault_with_wpn_2122",
    "SCH_OFFENSE_ATTWOW": "crdc_offense_assault_no_wpn_2122",
    "SCH_OFFENSE_POSSWX": "crdc_offense_wpn_possession_2122",
    "SCH_OFFENSE_ROBWW":  "crdc_offense_robbery_with_wpn_2122",
    "SCH_OFFENSE_ROBWOW": "crdc_offense_robbery_no_wpn_2122",
    "SCH_OFFENSE_THRWW":  "crdc_offense_threat_with_wpn_2122",
    "SCH_OFFENSE_THRWOW": "crdc_offense_threat_no_wpn_2122",
    "SCH_FIREARM_IND":    "crdc_offense_firearm_ind_2122",
    "SCH_HOMICIDE_IND":   "crdc_offense_homicide_ind_2122",
}

# Offense indicator columns (Yes/No string, not numeric count)
_INDICATOR_CRDC_FIELDS: frozenset[str] = frozenset({"SCH_FIREARM_IND", "SCH_HOMICIDE_IND"})

# M+F derived total pairs: (m_col, f_col, total_col)
_MF_TOTAL_PAIRS: list[tuple[str, str, str]] = [
    ("crdc_tot_enr_m_2122",           "crdc_tot_enr_f_2122",           "crdc_tot_enr_total_2122"),
    ("crdc_idea_enr_m_2122",          "crdc_idea_enr_f_2122",          "crdc_idea_enr_total_2122"),
    ("crdc_idea_enr_alt_m_2122",      "crdc_idea_enr_alt_f_2122",      "crdc_idea_enr_alt_total_2122"),
    ("crdc_504_enr_m_2122",           "crdc_504_enr_f_2122",           "crdc_504_enr_total_2122"),
    ("crdc_idea_iss_students_m_2122", "crdc_idea_iss_students_f_2122", "crdc_idea_iss_students_total_2122"),
    ("crdc_idea_sing_oos_m_2122",     "crdc_idea_sing_oos_f_2122",     "crdc_idea_sing_oos_total_2122"),
    ("crdc_idea_mult_oos_m_2122",     "crdc_idea_mult_oos_f_2122",     "crdc_idea_mult_oos_total_2122"),
    ("crdc_idea_exp_with_svc_m_2122", "crdc_idea_exp_with_svc_f_2122","crdc_idea_exp_with_svc_total_2122"),
    ("crdc_idea_exp_no_svc_m_2122",   "crdc_idea_exp_no_svc_f_2122",  "crdc_idea_exp_no_svc_total_2122"),
    ("crdc_idea_exp_zerotol_m_2122",  "crdc_idea_exp_zerotol_f_2122", "crdc_idea_exp_zerotol_total_2122"),
    ("crdc_rs_mech_students_m_2122",  "crdc_rs_mech_students_f_2122", "crdc_rs_mech_students_total_2122"),
    ("crdc_rs_phys_students_m_2122",  "crdc_rs_phys_students_f_2122", "crdc_rs_phys_students_total_2122"),
    ("crdc_rs_secl_students_m_2122",  "crdc_rs_secl_students_f_2122", "crdc_rs_secl_students_total_2122"),
    ("crdc_hb_dis_reported_m_2122",   "crdc_hb_dis_reported_f_2122",  "crdc_hb_dis_reported_total_2122"),
    ("crdc_hb_dis_disciplined_m_2122","crdc_hb_dis_disciplined_f_2122","crdc_hb_dis_disciplined_total_2122"),
    ("crdc_idea_ref_law_m_2122",      "crdc_idea_ref_law_f_2122",     "crdc_idea_ref_law_total_2122"),
    ("crdc_idea_arr_m_2122",          "crdc_idea_arr_f_2122",         "crdc_idea_arr_total_2122"),
]

_CRDC_FILE_CONFIGS: list[dict] = [
    {"name": "enrollment",  "file": "Enrollment.csv",              "field_map": ENROLLMENT_FIELDS},
    {"name": "suspensions", "file": "Suspensions.csv",             "field_map": SUSPENSION_FIELDS},
    {"name": "expulsions",  "file": "Expulsions.csv",              "field_map": EXPULSION_FIELDS},
    {"name": "restraint",   "file": "Restraint and Seclusion.csv", "field_map": RESTRAINT_FIELDS},
    {"name": "harassment",  "file": "Harassment and Bullying.csv", "field_map": HARASSMENT_FIELDS},
    {"name": "referrals",   "file": "Referrals and Arrests.csv",   "field_map": REFERRAL_FIELDS},
    {"name": "offenses",    "file": "Offenses.csv",                "field_map": OFFENSE_FIELDS},
]

# All raw measure output columns (excludes derived totals and pipeline meta)
ALL_RAW_MEASURE_COLS: list[str] = (
    list(ENROLLMENT_FIELDS.values())
    + list(SUSPENSION_FIELDS.values())
    + list(EXPULSION_FIELDS.values())
    + list(RESTRAINT_FIELDS.values())
    + list(HARASSMENT_FIELDS.values())
    + list(REFERRAL_FIELDS.values())
    + list(OFFENSE_FIELDS.values())
)

# Count columns that must be >= 0 when non-null (excludes indicators)
COUNT_COLUMNS: list[str] = [
    c for c in ALL_RAW_MEASURE_COLS
    if not c.endswith("_ind_2122")
]

# ──────────────────────────────────────────────────────────────────────────────
# Normalization helpers (importable by tests)
# ──────────────────────────────────────────────────────────────────────────────


def normalize_combokey(val) -> Optional[str]:
    """Normalize CRDC COMBOKEY to a 12-character string or None."""
    if val is None:
        return None
    s = str(val).strip().lstrip("'")
    return s if (len(s) == 12 and s.isdigit()) else None


def normalize_crdc_count(val) -> tuple[Optional[float], Optional[str]]:
    """
    Return (numeric_value, sentinel_code).

    -9  -> (None, '-9')   not applicable / not reported
    ''  -> (None, 'blank')  missing
    0   -> (0.0,  None)     real zero
    n   -> (n,    None)     real count
    """
    if val is None:
        return None, None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None, "blank"
    if s == _CRDC_SENTINEL:
        return None, _CRDC_SENTINEL
    try:
        return float(s), None
    except ValueError:
        return None, f"invalid:{s}"


def normalize_crdc_indicator(val) -> Optional[str]:
    """Return 'Yes', 'No', or None (-9 or blank -> None)."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s == _CRDC_SENTINEL:
        return None
    return s


# ──────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────────────────────


def _available_cols(csv_path: Path) -> list[str]:
    """Read only the header row to get the available column names."""
    return pd.read_csv(csv_path, nrows=0, encoding="utf-8-sig").columns.tolist()


def _load_crdc_source(
    csv_path: Path,
    field_map: dict[str, str],
    cohort_nces: set[str],
    source_name: str,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """
    Stream-read one CRDC CSV, filter to cohort NCES IDs, normalize.

    Returns
    -------
    df        – DataFrame with columns: combokey + normalized output columns
    sup_codes – {combokey: {crdc_field: code}} for every sentinel/-9 value
    """
    avail = _available_cols(csv_path)
    needed_src_cols = [c for c in field_map if c in avail]
    missing_src_cols = [c for c in field_map if c not in avail]
    if missing_src_cols:
        print(
            f"  [{source_name}] WARNING: {len(missing_src_cols)} columns absent in CSV: "
            f"{missing_src_cols[:5]}",
            file=sys.stderr,
        )

    read_cols = ["COMBOKEY"] + needed_src_cols
    frames: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        csv_path,
        dtype=str,
        encoding="utf-8-sig",
        chunksize=_CHUNK_SIZE,
        usecols=read_cols,
        on_bad_lines="skip",
    ):
        subset = chunk[chunk["COMBOKEY"].isin(cohort_nces)]
        if not subset.empty:
            frames.append(subset.copy())

    if not frames:
        print(f"  [{source_name}] no cohort schools found in file", file=sys.stderr)
        empty = pd.DataFrame(columns=["combokey"] + list(field_map.values()))
        return empty, {}

    raw = pd.concat(frames, ignore_index=True)
    raw["combokey"] = raw["COMBOKEY"].apply(normalize_combokey)

    invalid = raw["combokey"].isna()
    if invalid.any():
        print(
            f"  [{source_name}] {invalid.sum()} rows with invalid COMBOKEY dropped",
            file=sys.stderr,
        )
    raw = raw[~invalid].copy()

    dupes = raw.duplicated(subset=["combokey"], keep="first")
    if dupes.any():
        print(
            f"  [{source_name}] {dupes.sum()} duplicate COMBOKEY rows dropped",
            file=sys.stderr,
        )
        raw = raw[~dupes].copy()

    out_data: dict[str, list] = {"combokey": raw["combokey"].tolist()}
    sup_codes: dict[str, dict[str, str]] = {}
    combokeys = raw["combokey"].tolist()

    for crdc_f, out_col in field_map.items():
        if crdc_f not in raw.columns:
            out_data[out_col] = [None] * len(raw)
            continue

        raw_vals = raw[crdc_f].tolist()
        if crdc_f in _INDICATOR_CRDC_FIELDS:
            out_data[out_col] = [normalize_crdc_indicator(v) for v in raw_vals]
        else:
            vals: list[Optional[float]] = []
            for combokey, rv in zip(combokeys, raw_vals):
                num, code = normalize_crdc_count(rv)
                vals.append(num)
                if code is not None:
                    if combokey not in sup_codes:
                        sup_codes[combokey] = {}
                    sup_codes[combokey][crdc_f] = code
            out_data[out_col] = vals

    return pd.DataFrame(out_data), sup_codes


# ──────────────────────────────────────────────────────────────────────────────
# Data dictionary update
# ──────────────────────────────────────────────────────────────────────────────


def _append_crdc_to_data_dictionary(dd_path: Path) -> None:
    """Load existing data_dictionary.json, remove stale CRDC entries, append new ones."""
    if dd_path.exists():
        dd = json.loads(dd_path.read_text())
    else:
        dd = {"schema_version": 1, "fields": []}

    # Remove existing CRDC entries so re-runs are idempotent
    dd["fields"] = [e for e in dd["fields"] if not str(e.get("column", "")).startswith("crdc_")]

    def _entry(column, crdc_field, source_file, description, unit, field_type, notes=None):
        e = {
            "column": column,
            "source": f"CRDC {CRDC_COLLECTION_YEAR}",
            "collection_year": CRDC_COLLECTION_YEAR,
            "crdc_field": crdc_field,
            "crdc_file": source_file,
            "description": description,
            "type": field_type,
            "unit": unit,
            "sentinel_notes": (
                "CRDC sentinel -9 = not applicable / not reported; mapped to null. "
                "0 is a real zero (not suppressed). CRDC 2021-22 FAQ states no "
                "data-quality suppression was applied; raw district-reported values "
                "may contain zeros that reflect reporting practice, not absence of events."
            ),
        }
        if notes:
            e["notes"] = notes
        return e

    def _derived(column, description, components):
        return {
            "column": column,
            "source": "derived",
            "collection_year": CRDC_COLLECTION_YEAR,
            "crdc_field": None,
            "description": description,
            "type": "float",
            "unit": "count",
            "notes": (
                f"Derived: sum of {components[0]} and {components[1]}. "
                "Null if either component is null."
            ),
        }

    _ENR = "SCH/Enrollment.csv"
    _SUS = "SCH/Suspensions.csv"
    _EXP = "SCH/Expulsions.csv"
    _RST = "SCH/Restraint and Seclusion.csv"
    _HBL = "SCH/Harassment and Bullying.csv"
    _REF = "SCH/Referrals and Arrests.csv"
    _OFF = "SCH/Offenses.csv"

    new_entries = [
        # ── Enrollment ───────────────────────────────────────────────────────
        _entry("crdc_tot_enr_m_2122",          "TOT_ENR_M",       _ENR, "Total enrollment, male",       "count", "float"),
        _entry("crdc_tot_enr_f_2122",          "TOT_ENR_F",       _ENR, "Total enrollment, female",     "count", "float"),
        _entry("crdc_tot_enr_x_2122",          "TOT_ENR_X",       _ENR, "Total enrollment, non-binary/unknown gender", "count", "float", "Typically -9 (null) for Texas schools."),
        _entry("crdc_idea_enr_m_2122",         "SCH_ENR_IDEA_M",  _ENR, "IDEA enrollment, male",        "count", "float"),
        _entry("crdc_idea_enr_f_2122",         "SCH_ENR_IDEA_F",  _ENR, "IDEA enrollment, female",      "count", "float"),
        _entry("crdc_idea_enr_x_2122",         "SCH_ENR_IDEA_X",  _ENR, "IDEA enrollment, non-binary/unknown gender", "count", "float", "Typically -9 (null)."),
        _entry("crdc_idea_enr_alt_m_2122",     "TOT_IDEAENR_M",   _ENR, "Alternate total IDEA enrollment, male (may differ from SCH_ENR_IDEA_M)", "count", "float"),
        _entry("crdc_idea_enr_alt_f_2122",     "TOT_IDEAENR_F",   _ENR, "Alternate total IDEA enrollment, female", "count", "float"),
        _entry("crdc_idea_enr_alt_x_2122",     "TOT_IDEAENR_X",   _ENR, "Alternate total IDEA enrollment, non-binary/unknown", "count", "float", "Typically -9 (null)."),
        _entry("crdc_504_enr_m_2122",          "SCH_ENR_504_M",   _ENR, "Section 504 enrollment, male",    "count", "float"),
        _entry("crdc_504_enr_f_2122",          "SCH_ENR_504_F",   _ENR, "Section 504 enrollment, female",  "count", "float"),
        _entry("crdc_504_enr_x_2122",          "SCH_ENR_504_X",   _ENR, "Section 504 enrollment, non-binary/unknown", "count", "float", "Typically -9 (null)."),
        _derived("crdc_tot_enr_total_2122",    "Total enrollment (M+F derived)", ["crdc_tot_enr_m_2122",  "crdc_tot_enr_f_2122"]),
        _derived("crdc_idea_enr_total_2122",   "IDEA enrollment total (M+F derived)", ["crdc_idea_enr_m_2122","crdc_idea_enr_f_2122"]),
        _derived("crdc_idea_enr_alt_total_2122","Alternate IDEA enrollment total (M+F derived)",["crdc_idea_enr_alt_m_2122","crdc_idea_enr_alt_f_2122"]),
        _derived("crdc_504_enr_total_2122",    "Section 504 enrollment total (M+F derived)", ["crdc_504_enr_m_2122","crdc_504_enr_f_2122"]),
        # ── Suspensions ──────────────────────────────────────────────────────
        _entry("crdc_idea_iss_students_m_2122",  "TOT_DISCWDIS_ISS_IDEA_M",    _SUS, "IDEA students receiving ISS, male",   "count", "float"),
        _entry("crdc_idea_iss_students_f_2122",  "TOT_DISCWDIS_ISS_IDEA_F",    _SUS, "IDEA students receiving ISS, female", "count", "float"),
        _entry("crdc_504_iss_students_m_2122",   "SCH_DISCWDIS_ISS_504_M",     _SUS, "504 students receiving ISS, male",    "count", "float"),
        _entry("crdc_504_iss_students_f_2122",   "SCH_DISCWDIS_ISS_504_F",     _SUS, "504 students receiving ISS, female",  "count", "float"),
        _entry("crdc_oos_instances_no_dis_2122", "SCH_OOSINSTANCES_WODIS",      _SUS, "OOS suspension instances, students without disabilities", "count", "float"),
        _entry("crdc_oos_instances_idea_2122",   "SCH_OOSINSTANCES_IDEA",       _SUS, "OOS suspension instances, IDEA students", "count", "float"),
        _entry("crdc_oos_instances_504_2122",    "SCH_OOSINSTANCES_504",        _SUS, "OOS suspension instances, 504 students", "count", "float"),
        _entry("crdc_idea_sing_oos_m_2122",  "TOT_DISCWDIS_SINGOOS_IDEA_M", _SUS, "IDEA students receiving single OOS suspension, male",   "count", "float"),
        _entry("crdc_idea_sing_oos_f_2122",  "TOT_DISCWDIS_SINGOOS_IDEA_F", _SUS, "IDEA students receiving single OOS suspension, female", "count", "float"),
        _entry("crdc_idea_mult_oos_m_2122",  "TOT_DISCWDIS_MULTOOS_IDEA_M", _SUS, "IDEA students receiving multiple OOS suspensions, male",   "count", "float"),
        _entry("crdc_idea_mult_oos_f_2122",  "TOT_DISCWDIS_MULTOOS_IDEA_F", _SUS, "IDEA students receiving multiple OOS suspensions, female", "count", "float"),
        _entry("crdc_idea_oos_days_missed_m_2122","SCH_DAYSMISSED_IDEA_M",    _SUS, "IDEA student days missed due to OOS suspension, male",   "days", "float"),
        _entry("crdc_idea_oos_days_missed_f_2122","SCH_DAYSMISSED_IDEA_F",    _SUS, "IDEA student days missed due to OOS suspension, female", "days", "float"),
        _derived("crdc_idea_iss_students_total_2122","IDEA students receiving ISS (M+F)",["crdc_idea_iss_students_m_2122","crdc_idea_iss_students_f_2122"]),
        _derived("crdc_idea_sing_oos_total_2122","IDEA students with single OOS (M+F)",["crdc_idea_sing_oos_m_2122","crdc_idea_sing_oos_f_2122"]),
        _derived("crdc_idea_mult_oos_total_2122","IDEA students with multiple OOS (M+F)",["crdc_idea_mult_oos_m_2122","crdc_idea_mult_oos_f_2122"]),
        # ── Expulsions ───────────────────────────────────────────────────────
        _entry("crdc_idea_exp_with_svc_m_2122", "TOT_DISCWDIS_EXPWE_IDEA_M",  _EXP, "IDEA expulsions with educational services, male",    "count", "float"),
        _entry("crdc_idea_exp_with_svc_f_2122", "TOT_DISCWDIS_EXPWE_IDEA_F",  _EXP, "IDEA expulsions with educational services, female",  "count", "float"),
        _entry("crdc_idea_exp_no_svc_m_2122",   "TOT_DISCWDIS_EXPWOE_IDEA_M", _EXP, "IDEA expulsions without educational services, male",  "count", "float"),
        _entry("crdc_idea_exp_no_svc_f_2122",   "TOT_DISCWDIS_EXPWOE_IDEA_F", _EXP, "IDEA expulsions without educational services, female","count", "float"),
        _entry("crdc_idea_exp_zerotol_m_2122",  "TOT_DISCWDIS_EXPZT_IDEA_M",  _EXP, "IDEA zero-tolerance expulsions, male",    "count", "float"),
        _entry("crdc_idea_exp_zerotol_f_2122",  "TOT_DISCWDIS_EXPZT_IDEA_F",  _EXP, "IDEA zero-tolerance expulsions, female",  "count", "float"),
        _derived("crdc_idea_exp_with_svc_total_2122","IDEA expulsions with services (M+F)",["crdc_idea_exp_with_svc_m_2122","crdc_idea_exp_with_svc_f_2122"]),
        _derived("crdc_idea_exp_no_svc_total_2122","IDEA expulsions without services (M+F)",["crdc_idea_exp_no_svc_m_2122","crdc_idea_exp_no_svc_f_2122"]),
        _derived("crdc_idea_exp_zerotol_total_2122","IDEA zero-tolerance expulsions (M+F)",["crdc_idea_exp_zerotol_m_2122","crdc_idea_exp_zerotol_f_2122"]),
        # ── Restraint and Seclusion ──────────────────────────────────────────
        _entry("crdc_rs_mech_instances_idea_2122","SCH_RSINSTANCES_MECH_IDEA","_RST","IDEA mechanical restraint instances","count","float"),
        _entry("crdc_rs_phys_instances_idea_2122","SCH_RSINSTANCES_PHYS_IDEA","_RST","IDEA physical restraint instances","count","float"),
        _entry("crdc_rs_secl_instances_idea_2122","SCH_RSINSTANCES_SECL_IDEA","_RST","IDEA seclusion instances","count","float"),
        _entry("crdc_rs_mech_students_m_2122",   "TOT_RS_IDEA_MECH_M",       _RST, "IDEA students subjected to mechanical restraint, male",   "count","float"),
        _entry("crdc_rs_mech_students_f_2122",   "TOT_RS_IDEA_MECH_F",       _RST, "IDEA students subjected to mechanical restraint, female", "count","float"),
        _entry("crdc_rs_phys_students_m_2122",   "TOT_RS_IDEA_PHYS_M",       _RST, "IDEA students subjected to physical restraint, male",   "count","float"),
        _entry("crdc_rs_phys_students_f_2122",   "TOT_RS_IDEA_PHYS_F",       _RST, "IDEA students subjected to physical restraint, female", "count","float"),
        _entry("crdc_rs_secl_students_m_2122",   "TOT_RS_IDEA_SECL_M",       _RST, "IDEA students subjected to seclusion, male",   "count","float"),
        _entry("crdc_rs_secl_students_f_2122",   "TOT_RS_IDEA_SECL_F",       _RST, "IDEA students subjected to seclusion, female", "count","float"),
        _derived("crdc_rs_mech_students_total_2122","IDEA students in mechanical restraint (M+F)",["crdc_rs_mech_students_m_2122","crdc_rs_mech_students_f_2122"]),
        _derived("crdc_rs_phys_students_total_2122","IDEA students in physical restraint (M+F)",["crdc_rs_phys_students_m_2122","crdc_rs_phys_students_f_2122"]),
        _derived("crdc_rs_secl_students_total_2122","IDEA students in seclusion (M+F)",["crdc_rs_secl_students_m_2122","crdc_rs_secl_students_f_2122"]),
        # ── Harassment and Bullying ──────────────────────────────────────────
        _entry("crdc_hb_dis_allegations_2122",         "SCH_HBALLEGATIONS_DIS",        _HBL,"Allegations of harassment/bullying based on disability","count","float"),
        _entry("crdc_hb_dis_reported_m_2122",          "TOT_HBREPORTED_DIS_M",         _HBL,"Students reported harassed/bullied for disability, male",  "count","float"),
        _entry("crdc_hb_dis_reported_f_2122",          "TOT_HBREPORTED_DIS_F",         _HBL,"Students reported harassed/bullied for disability, female","count","float"),
        _entry("crdc_hb_dis_reported_idea_m_2122",     "SCH_HBREPORTED_DIS_IDEA_M",    _HBL,"IDEA students reported harassed/bullied, male",   "count","float"),
        _entry("crdc_hb_dis_reported_idea_f_2122",     "SCH_HBREPORTED_DIS_IDEA_F",    _HBL,"IDEA students reported harassed/bullied, female", "count","float"),
        _entry("crdc_hb_dis_disciplined_m_2122",       "TOT_HBDISCIPLINED_DIS_M",      _HBL,"Students disciplined for disability-based harassment, male",  "count","float"),
        _entry("crdc_hb_dis_disciplined_f_2122",       "TOT_HBDISCIPLINED_DIS_F",      _HBL,"Students disciplined for disability-based harassment, female","count","float"),
        _entry("crdc_hb_dis_disciplined_idea_m_2122",  "SCH_HBDISCIPLINED_DIS_IDEA_M", _HBL,"IDEA students disciplined for harassment, male",   "count","float"),
        _entry("crdc_hb_dis_disciplined_idea_f_2122",  "SCH_HBDISCIPLINED_DIS_IDEA_F", _HBL,"IDEA students disciplined for harassment, female", "count","float"),
        _derived("crdc_hb_dis_reported_total_2122","Students reported harassed for disability (M+F)",["crdc_hb_dis_reported_m_2122","crdc_hb_dis_reported_f_2122"]),
        _derived("crdc_hb_dis_disciplined_total_2122","Students disciplined for disability harassment (M+F)",["crdc_hb_dis_disciplined_m_2122","crdc_hb_dis_disciplined_f_2122"]),
        # ── Referrals and Arrests ────────────────────────────────────────────
        _entry("crdc_idea_ref_law_m_2122","TOT_DISCWDIS_REF_IDEA_M",_REF,"IDEA students referred to law enforcement, male",   "count","float"),
        _entry("crdc_idea_ref_law_f_2122","TOT_DISCWDIS_REF_IDEA_F",_REF,"IDEA students referred to law enforcement, female", "count","float"),
        _entry("crdc_idea_arr_m_2122",    "TOT_DISCWDIS_ARR_IDEA_M",_REF,"IDEA students arrested (school-related), male",   "count","float"),
        _entry("crdc_idea_arr_f_2122",    "TOT_DISCWDIS_ARR_IDEA_F",_REF,"IDEA students arrested (school-related), female", "count","float"),
        _derived("crdc_idea_ref_law_total_2122","IDEA students referred to law enforcement (M+F)",["crdc_idea_ref_law_m_2122","crdc_idea_ref_law_f_2122"]),
        _derived("crdc_idea_arr_total_2122","IDEA students arrested (M+F)",["crdc_idea_arr_m_2122","crdc_idea_arr_f_2122"]),
        # ── Offenses ─────────────────────────────────────────────────────────
        _entry("crdc_offense_assault_with_wpn_2122","SCH_OFFENSE_ATTWW",  _OFF,"Assault with weapon incidents",          "count","float"),
        _entry("crdc_offense_assault_no_wpn_2122",  "SCH_OFFENSE_ATTWOW", _OFF,"Assault without weapon incidents",        "count","float"),
        _entry("crdc_offense_wpn_possession_2122",  "SCH_OFFENSE_POSSWX", _OFF,"Weapon possession incidents",              "count","float"),
        _entry("crdc_offense_robbery_with_wpn_2122","SCH_OFFENSE_ROBWW",  _OFF,"Robbery with weapon incidents",            "count","float"),
        _entry("crdc_offense_robbery_no_wpn_2122",  "SCH_OFFENSE_ROBWOW", _OFF,"Robbery without weapon incidents",         "count","float"),
        _entry("crdc_offense_threat_with_wpn_2122", "SCH_OFFENSE_THRWW",  _OFF,"Threat with weapon incidents",             "count","float"),
        _entry("crdc_offense_threat_no_wpn_2122",   "SCH_OFFENSE_THRWOW", _OFF,"Threat without weapon incidents",          "count","float"),
        _entry("crdc_offense_firearm_ind_2122",      "SCH_FIREARM_IND",   _OFF,"Firearm involved indicator (Yes/No)",      "indicator","string"),
        _entry("crdc_offense_homicide_ind_2122",     "SCH_HOMICIDE_IND",  _OFF,"Homicide indicator (Yes/No)",               "indicator","string"),
        # ── Pipeline metadata ────────────────────────────────────────────────
        {
            "column": "crdc_collection_year",
            "source": "pipeline",
            "description": (
                "CRDC collection year (2021-22). Data are historical; "
                "they reflect conditions from the 2021-22 school year, "
                "not the current year. Do not compare CRDC counts directly "
                "with current-year TAPR rates."
            ),
            "type": "string",
        },
        {
            "column": "crdc_matched",
            "source": "pipeline",
            "description": (
                "True if this campus NCES school ID (nces_school_id) matched "
                "a COMBOKEY in the CRDC 2021-22 school files. "
                "False if the school was not found (all CRDC fields null)."
            ),
            "type": "boolean",
        },
        {
            "column": "crdc_suppression_codes",
            "source": "pipeline",
            "description": (
                "JSON object mapping original CRDC field name to '-9' "
                "for any field whose value was -9 (not applicable / not reported). "
                "Null if no fields were suppressed for this campus."
            ),
            "type": "string (JSON)",
        },
    ]

    dd["fields"].extend(new_entries)
    dd["generated_utc"] = datetime.now(timezone.utc).isoformat()
    dd.setdefault("notes", []).append(
        f"CRDC {CRDC_COLLECTION_YEAR} fields added. Data are historical (2021-22). "
        "Sentinel -9 = not applicable; 0 = real zero. "
        "No data-quality suppression was applied by ED for 2021-22."
    )
    dd_path.write_text(json.dumps(dd, indent=2))


# ──────────────────────────────────────────────────────────────────────────────
# Main build function
# ──────────────────────────────────────────────────────────────────────────────


def build_crdc() -> pd.DataFrame:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if not COHORT_TAPR.exists():
        print(f"ERROR: {COHORT_TAPR} not found. Run build_tapr.py first.", file=sys.stderr)
        sys.exit(1)

    cohort = pd.read_csv(COHORT_TAPR, dtype=str)
    cohort_nces = set(cohort["nces_school_id"].dropna())
    print(f"Cohort: {len(cohort)} schools  |  {len(cohort_nces)} unique NCES IDs\n")

    # ── Parse each CRDC source file ──────────────────────────────────────────

    all_sup: dict[str, dict[str, str]] = {}
    crdc_frames: list[pd.DataFrame] = []

    for cfg in _CRDC_FILE_CONFIGS:
        csv_path = CRDC_SCH_DIR / cfg["file"]
        if not csv_path.exists():
            print(
                f"ERROR: {csv_path} not found. Run ingest_crdc.py first.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Parsing {cfg['file']} ...")
        df, sup = _load_crdc_source(csv_path, cfg["field_map"], cohort_nces, cfg["name"])
        sup_count = sum(len(v) for v in sup.values())
        print(f"  {len(df)} matching rows  |  {sup_count} -9/-sentinel values")

        for combokey, codes in sup.items():
            if combokey not in all_sup:
                all_sup[combokey] = {}
            all_sup[combokey].update(codes)

        crdc_frames.append(df)

    # ── Merge all CRDC frames (outer join by combokey) ───────────────────────

    crdc_wide = crdc_frames[0]
    for df in crdc_frames[1:]:
        crdc_wide = crdc_wide.merge(df, on="combokey", how="outer")

    crdc_combokey_set = set(crdc_wide["combokey"].dropna())
    print(f"\nMerged CRDC: {len(crdc_wide)} schools in cohort subset")

    # ── Left-join cohort to CRDC on nces_school_id = combokey ───────────────

    result = cohort.merge(
        crdc_wide.rename(columns={"combokey": "nces_school_id"}),
        on="nces_school_id",
        how="left",
    )

    # ── Coerce count columns to float ─────────────────────────────────────────

    for col in COUNT_COLUMNS:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    # ── Derived M+F totals ────────────────────────────────────────────────────

    for m_col, f_col, total_col in _MF_TOTAL_PAIRS:
        if m_col in result.columns and f_col in result.columns:
            result[total_col] = (
                pd.to_numeric(result[m_col], errors="coerce")
                + pd.to_numeric(result[f_col], errors="coerce")
            )

    # ── Pipeline metadata columns ─────────────────────────────────────────────

    result["crdc_collection_year"] = CRDC_COLLECTION_YEAR
    result["crdc_matched"] = result["nces_school_id"].isin(crdc_combokey_set)
    result["crdc_suppression_codes"] = result["nces_school_id"].apply(
        lambda k: json.dumps(all_sup[k]) if k in all_sup else None
    )

    # ── Reorder columns ───────────────────────────────────────────────────────

    tapr_cols = list(cohort.columns)
    derived_total_cols = [t for _, _, t in _MF_TOTAL_PAIRS]
    crdc_measure_cols = ALL_RAW_MEASURE_COLS + derived_total_cols
    tail_cols = ["crdc_collection_year", "crdc_matched", "crdc_suppression_codes"]
    ordered = tapr_cols + [c for c in crdc_measure_cols if c in result.columns] + tail_cols
    result = result[[c for c in ordered if c in result.columns]].copy()

    # ── Write outputs ─────────────────────────────────────────────────────────

    csv_path = PROCESSED_DIR / "cohort_crdc.csv"
    parquet_path = PROCESSED_DIR / "cohort_crdc.parquet"
    report_path = PROCESSED_DIR / "crdc_join_report.json"

    result.to_csv(csv_path, index=False)
    result.to_parquet(parquet_path, index=False)

    _append_crdc_to_data_dictionary(DD_PATH)

    # ── Join report ───────────────────────────────────────────────────────────

    matched = int(result["crdc_matched"].sum())
    unmatched = int((~result["crdc_matched"]).sum())

    null_counts: dict[str, int] = {}
    for col in crdc_measure_cols:
        if col in result.columns:
            null_counts[col] = int(result[col].isna().sum())

    sentinel_totals: dict[str, int] = {}
    for combokey, codes in all_sup.items():
        if combokey in cohort_nces:
            for code in codes.values():
                sentinel_totals[code] = sentinel_totals.get(code, 0) + 1

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "crdc_collection_year": CRDC_COLLECTION_YEAR,
        "cohort_school_count": len(result),
        "crdc_matched": matched,
        "crdc_unmatched": unmatched,
        "crdc_match_pct": round(100 * matched / len(result), 1) if len(result) > 0 else 0,
        "sentinel_code_totals_in_cohort": sentinel_totals,
        "null_counts_per_output_column": null_counts,
        "unmatched_nces_ids": result.loc[~result["crdc_matched"], "nces_school_id"].tolist(),
        "sources": [
            {
                "name": cfg["name"],
                "file": cfg["file"],
                "crdc_fields": list(cfg["field_map"].keys()),
                "output_columns": list(cfg["field_map"].values()),
            }
            for cfg in _CRDC_FILE_CONFIGS
        ],
    }
    report_path.write_text(json.dumps(report, indent=2))

    # ── Console summary ───────────────────────────────────────────────────────

    print(f"\n{'='*60}")
    print(f"Cohort rows    : {len(result)}")
    print(f"CRDC matched   : {matched} / {len(result)}  ({report['crdc_match_pct']}%)")
    if unmatched:
        print(f"Unmatched IDs  : {result.loc[~result['crdc_matched'], 'nces_school_id'].tolist()}")
    print(f"\nSentinel codes : {sentinel_totals}")
    print(f"\nNull counts (top columns with nulls):")
    for col, n in sorted(null_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {col:<60} {n}")
    if sum(1 for n in null_counts.values() if n > 0) > 10:
        print(f"  ... ({sum(1 for n in null_counts.values() if n > 0)} columns have nulls)")
    print(f"\nOutputs:")
    for p in [csv_path, parquet_path, report_path, DD_PATH]:
        print(f"  {p}")

    return result


if __name__ == "__main__":
    build_crdc()
