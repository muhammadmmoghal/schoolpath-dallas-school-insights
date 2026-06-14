"""
Phase 3 tests — CRDC 2021-22 ingestion and cohort join.

Unit tests for normalization functions run without any data files.
Integration tests require data/processed/cohort_crdc.csv and are
skipped automatically when those files are absent.
"""

import json
import math
from pathlib import Path

import pandas as pd
import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent
_CRDC_CSV = _ROOT / "data" / "processed" / "cohort_crdc.csv"
_CRDC_PARQUET = _ROOT / "data" / "processed" / "cohort_crdc.parquet"
_JOIN_REPORT = _ROOT / "data" / "processed" / "crdc_join_report.json"
_DD_PATH = _ROOT / "data" / "processed" / "data_dictionary.json"


def _integration_skip(reason: str = "cohort_crdc.csv not found; run build_crdc.py"):
    return pytest.mark.skipif(not _CRDC_CSV.exists(), reason=reason)


@pytest.fixture(scope="module")
def cohort() -> pd.DataFrame:
    return pd.read_csv(_CRDC_CSV)


@pytest.fixture(scope="module")
def join_report() -> dict:
    return json.loads(_JOIN_REPORT.read_text())


@pytest.fixture(scope="module")
def data_dictionary() -> dict:
    return json.loads(_DD_PATH.read_text())


# ──────────────────────────────────────────────────────────────────────────────
# Unit: normalize_combokey
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizeCombokey:
    from scripts.build_crdc import normalize_combokey

    def test_valid_12digit(self):
        from scripts.build_crdc import normalize_combokey
        assert normalize_combokey("481308001432") == "481308001432"

    def test_strips_leading_apostrophe(self):
        from scripts.build_crdc import normalize_combokey
        assert normalize_combokey("'481308001432") == "481308001432"

    def test_strips_whitespace(self):
        from scripts.build_crdc import normalize_combokey
        assert normalize_combokey("  481308001432  ") == "481308001432"

    def test_too_short_returns_none(self):
        from scripts.build_crdc import normalize_combokey
        assert normalize_combokey("48130800143") is None

    def test_too_long_returns_none(self):
        from scripts.build_crdc import normalize_combokey
        assert normalize_combokey("4813080014321") is None

    def test_alpha_chars_returns_none(self):
        from scripts.build_crdc import normalize_combokey
        assert normalize_combokey("4813080014AB") is None

    def test_none_input(self):
        from scripts.build_crdc import normalize_combokey
        assert normalize_combokey(None) is None

    def test_empty_string_returns_none(self):
        from scripts.build_crdc import normalize_combokey
        assert normalize_combokey("") is None


# ──────────────────────────────────────────────────────────────────────────────
# Unit: normalize_crdc_count
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizeCrdcCount:
    def test_real_integer(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("42")
        assert val == 42.0
        assert code is None

    def test_zero_is_real(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("0")
        assert val == 0.0
        assert code is None

    def test_sentinel_minus9(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("-9")
        assert val is None
        assert code == "-9"

    def test_blank_string(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("")
        assert val is None
        assert code == "blank"

    def test_whitespace_only(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("   ")
        assert val is None
        assert code == "blank"

    def test_none_input(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count(None)
        assert val is None
        assert code is None

    def test_float_string(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("3.5")
        assert val == 3.5
        assert code is None

    def test_non_numeric_returns_invalid_code(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("N/A")
        assert val is None
        assert code is not None and "invalid" in code

    def test_negative_non_sentinel(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("-3")
        assert val == -3.0
        assert code is None

    def test_large_count(self):
        from scripts.build_crdc import normalize_crdc_count
        val, code = normalize_crdc_count("2500")
        assert val == 2500.0
        assert code is None


# ──────────────────────────────────────────────────────────────────────────────
# Unit: normalize_crdc_indicator
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizeCrdcIndicator:
    def test_yes(self):
        from scripts.build_crdc import normalize_crdc_indicator
        assert normalize_crdc_indicator("Yes") == "Yes"

    def test_no(self):
        from scripts.build_crdc import normalize_crdc_indicator
        assert normalize_crdc_indicator("No") == "No"

    def test_sentinel_minus9_returns_none(self):
        from scripts.build_crdc import normalize_crdc_indicator
        assert normalize_crdc_indicator("-9") is None

    def test_blank_returns_none(self):
        from scripts.build_crdc import normalize_crdc_indicator
        assert normalize_crdc_indicator("") is None

    def test_none_input(self):
        from scripts.build_crdc import normalize_crdc_indicator
        assert normalize_crdc_indicator(None) is None


# ──────────────────────────────────────────────────────────────────────────────
# Integration: cohort shape and identity
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestCohortPreservation:
    def test_exactly_60_rows(self, cohort):
        assert len(cohort) == 60, f"Expected 60 rows, got {len(cohort)}"

    def test_nces_school_id_present(self, cohort):
        assert "nces_school_id" in cohort.columns

    def test_no_duplicate_nces_ids(self, cohort):
        dupes = cohort["nces_school_id"].duplicated()
        assert not dupes.any(), f"Duplicate nces_school_ids: {cohort.loc[dupes,'nces_school_id'].tolist()}"

    def test_campus_id_present(self, cohort):
        assert "campus_id" in cohort.columns

    def test_tapr_columns_intact(self, cohort):
        tapr_cols = [c for c in cohort.columns if c.startswith("tapr_")]
        assert len(tapr_cols) >= 27, f"Expected >= 27 TAPR columns, found {len(tapr_cols)}"


# ──────────────────────────────────────────────────────────────────────────────
# Integration: CRDC field presence
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestCrdcFieldPresence:
    def test_crdc_columns_present(self, cohort):
        crdc_cols = [c for c in cohort.columns if c.startswith("crdc_")]
        assert len(crdc_cols) >= 50, f"Expected >= 50 CRDC columns, found {len(crdc_cols)}"

    def test_pipeline_meta_columns_present(self, cohort):
        for col in ["crdc_collection_year", "crdc_matched", "crdc_suppression_codes"]:
            assert col in cohort.columns, f"Missing pipeline column: {col}"

    def test_collection_year_value(self, cohort):
        vals = cohort["crdc_collection_year"].dropna().unique().tolist()
        assert vals == ["2021-22"], f"Unexpected collection year: {vals}"

    def test_derived_total_columns_present(self, cohort):
        expected_totals = [
            "crdc_tot_enr_total_2122",
            "crdc_idea_enr_total_2122",
            "crdc_504_enr_total_2122",
            "crdc_idea_iss_students_total_2122",
            "crdc_idea_sing_oos_total_2122",
            "crdc_idea_mult_oos_total_2122",
            "crdc_idea_exp_with_svc_total_2122",
            "crdc_idea_exp_no_svc_total_2122",
            "crdc_idea_exp_zerotol_total_2122",
            "crdc_rs_mech_students_total_2122",
            "crdc_rs_phys_students_total_2122",
            "crdc_rs_secl_students_total_2122",
            "crdc_hb_dis_reported_total_2122",
            "crdc_hb_dis_disciplined_total_2122",
            "crdc_idea_ref_law_total_2122",
            "crdc_idea_arr_total_2122",
        ]
        for col in expected_totals:
            assert col in cohort.columns, f"Missing derived total column: {col}"

    def test_indicator_columns_present(self, cohort):
        assert "crdc_offense_firearm_ind_2122" in cohort.columns
        assert "crdc_offense_homicide_ind_2122" in cohort.columns


# ──────────────────────────────────────────────────────────────────────────────
# Integration: sentinel / null handling
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestSentinelHandling:
    def test_no_minus9_in_count_columns(self, cohort):
        from scripts.build_crdc import COUNT_COLUMNS
        for col in COUNT_COLUMNS:
            if col not in cohort.columns:
                continue
            numeric = pd.to_numeric(cohort[col], errors="coerce")
            bad = (numeric == -9).sum()
            assert bad == 0, f"{col} contains {bad} raw -9 values (should be null)"

    def test_count_columns_non_negative(self, cohort):
        from scripts.build_crdc import COUNT_COLUMNS
        for col in COUNT_COLUMNS:
            if col not in cohort.columns:
                continue
            numeric = pd.to_numeric(cohort[col], errors="coerce")
            negative = (numeric < 0).sum()
            assert negative == 0, f"{col} contains {negative} negative values"

    def test_indicator_columns_valid_values(self, cohort):
        for col in ["crdc_offense_firearm_ind_2122", "crdc_offense_homicide_ind_2122"]:
            if col not in cohort.columns:
                continue
            valid = {"Yes", "No", float("nan"), None}
            for val in cohort[col].tolist():
                is_nan = isinstance(val, float) and math.isnan(val)
                assert val in valid or is_nan or val is None, (
                    f"{col} contains unexpected value: {val!r}"
                )

    def test_suppression_codes_valid_json(self, cohort):
        for idx, val in cohort["crdc_suppression_codes"].items():
            if val is None or (isinstance(val, float) and math.isnan(val)):
                continue
            try:
                parsed = json.loads(val)
            except (json.JSONDecodeError, TypeError) as exc:
                pytest.fail(f"Row {idx} crdc_suppression_codes not valid JSON: {exc}")
            assert isinstance(parsed, dict), f"Row {idx} suppression codes is not a dict"
            for code in parsed.values():
                assert code in {"-9", "blank"} or code.startswith("invalid:"), (
                    f"Unexpected suppression code value: {code!r}"
                )

    def test_no_sentinel_in_suppression_codes_dict(self, cohort):
        for idx, val in cohort["crdc_suppression_codes"].items():
            if val is None or (isinstance(val, float) and math.isnan(val)):
                continue
            parsed = json.loads(val)
            for raw_col, code in parsed.items():
                assert code != "0", (
                    f"Row {idx}: suppression code for {raw_col} is '0' (should not be suppressed)"
                )


# ──────────────────────────────────────────────────────────────────────────────
# Integration: derived total consistency
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestDerivedTotals:
    _PAIRS = [
        ("crdc_tot_enr_m_2122",           "crdc_tot_enr_f_2122",           "crdc_tot_enr_total_2122"),
        ("crdc_idea_enr_m_2122",          "crdc_idea_enr_f_2122",          "crdc_idea_enr_total_2122"),
        ("crdc_idea_iss_students_m_2122", "crdc_idea_iss_students_f_2122", "crdc_idea_iss_students_total_2122"),
        ("crdc_idea_ref_law_m_2122",      "crdc_idea_ref_law_f_2122",      "crdc_idea_ref_law_total_2122"),
    ]

    def test_total_equals_mf_sum_when_both_non_null(self, cohort):
        for m_col, f_col, total_col in self._PAIRS:
            if not all(c in cohort.columns for c in [m_col, f_col, total_col]):
                continue
            m = pd.to_numeric(cohort[m_col], errors="coerce")
            f = pd.to_numeric(cohort[f_col], errors="coerce")
            t = pd.to_numeric(cohort[total_col], errors="coerce")
            both_non_null = m.notna() & f.notna()
            if not both_non_null.any():
                continue
            expected = (m + f)[both_non_null]
            actual = t[both_non_null]
            mismatches = (expected - actual).abs() > 0.01
            assert not mismatches.any(), (
                f"{total_col}: {mismatches.sum()} rows where total != M+F"
            )

    def test_total_is_null_when_either_component_null(self, cohort):
        m_col, f_col, total_col = (
            "crdc_tot_enr_m_2122",
            "crdc_tot_enr_f_2122",
            "crdc_tot_enr_total_2122",
        )
        if not all(c in cohort.columns for c in [m_col, f_col, total_col]):
            return
        m = pd.to_numeric(cohort[m_col], errors="coerce")
        f = pd.to_numeric(cohort[f_col], errors="coerce")
        t = pd.to_numeric(cohort[total_col], errors="coerce")
        either_null = m.isna() | f.isna()
        if not either_null.any():
            return
        assert t[either_null].isna().all(), (
            "Total should be null when either M or F component is null"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Integration: join report
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestJoinReport:
    def test_report_file_exists(self):
        assert _JOIN_REPORT.exists()

    def test_cohort_school_count_60(self, join_report):
        assert join_report["cohort_school_count"] == 60

    def test_collection_year_correct(self, join_report):
        assert join_report["crdc_collection_year"] == "2021-22"

    def test_match_pct_at_least_80(self, join_report):
        assert join_report["crdc_match_pct"] >= 80.0, (
            f"CRDC match coverage too low: {join_report['crdc_match_pct']}%"
        )

    def test_matched_plus_unmatched_equals_total(self, join_report):
        total = join_report["cohort_school_count"]
        matched = join_report["crdc_matched"]
        unmatched = join_report["crdc_unmatched"]
        assert matched + unmatched == total

    def test_sources_present(self, join_report):
        source_names = {s["name"] for s in join_report.get("sources", [])}
        expected = {"enrollment", "suspensions", "expulsions", "restraint",
                    "harassment", "referrals", "offenses"}
        assert expected == source_names, f"Missing sources: {expected - source_names}"


# ──────────────────────────────────────────────────────────────────────────────
# Integration: crdc_matched column
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestMatchedColumn:
    def test_matched_is_boolean_compatible(self, cohort):
        vals = set(str(v).lower() for v in cohort["crdc_matched"].dropna().unique())
        assert vals.issubset({"true", "false", "1", "0"}), (
            f"crdc_matched has unexpected values: {vals}"
        )

    def test_at_least_one_matched(self, cohort):
        matched_col = cohort["crdc_matched"].astype(str).str.lower()
        n_matched = (matched_col == "true").sum() + (matched_col == "1").sum()
        assert n_matched > 0, "No schools matched in CRDC"

    def test_unmatched_have_null_crdc_fields(self, cohort):
        matched_col = cohort["crdc_matched"].astype(str).str.lower()
        unmatched = cohort[(matched_col != "true") & (matched_col != "1")]
        check_cols = [c for c in ["crdc_tot_enr_m_2122", "crdc_idea_enr_m_2122"]
                      if c in cohort.columns]
        for col in check_cols:
            vals = unmatched[col].dropna()
            assert len(vals) == 0, (
                f"Unmatched schools have non-null {col}: {vals.tolist()}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Integration: data dictionary
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestDataDictionary:
    def test_dd_file_exists(self):
        assert _DD_PATH.exists()

    def test_crdc_fields_documented(self, data_dictionary):
        crdc_entries = [e for e in data_dictionary["fields"] if str(e.get("column","")).startswith("crdc_")]
        assert len(crdc_entries) >= 50, (
            f"Expected >= 50 CRDC entries in data dictionary, found {len(crdc_entries)}"
        )

    def test_pipeline_meta_columns_documented(self, data_dictionary):
        documented = {e["column"] for e in data_dictionary["fields"]}
        for col in ["crdc_collection_year", "crdc_matched", "crdc_suppression_codes"]:
            assert col in documented, f"Data dictionary missing: {col}"

    def test_all_output_columns_documented(self, cohort, data_dictionary):
        documented = {e["column"] for e in data_dictionary["fields"]}
        crdc_cols = [c for c in cohort.columns if c.startswith("crdc_")]
        missing = [c for c in crdc_cols if c not in documented]
        assert not missing, f"CRDC columns not in data dictionary: {missing}"

    def test_no_duplicate_entries(self, data_dictionary):
        columns = [e["column"] for e in data_dictionary["fields"]]
        seen: set[str] = set()
        dupes: list[str] = []
        for col in columns:
            if col in seen:
                dupes.append(col)
            seen.add(col)
        assert not dupes, f"Duplicate data dictionary entries: {dupes}"


# ──────────────────────────────────────────────────────────────────────────────
# Integration: parquet file
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestParquetFile:
    def test_parquet_exists(self):
        assert _CRDC_PARQUET.exists()

    def test_parquet_row_count(self):
        df = pd.read_parquet(_CRDC_PARQUET)
        assert len(df) == 60

    def test_parquet_has_crdc_columns(self):
        df = pd.read_parquet(_CRDC_PARQUET)
        crdc_cols = [c for c in df.columns if c.startswith("crdc_")]
        assert len(crdc_cols) >= 50
