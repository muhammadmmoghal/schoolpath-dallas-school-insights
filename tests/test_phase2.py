"""
Phase 2 test suite.

Unit tests (no file I/O):
  - normalize_campus_id: apostrophe stripped; wrong length → None.
  - normalize_measure: sentinel codes → (None, code); blanks → (None, 'blank');
    valid floats preserved.

Integration tests (read output files from build_tapr.py):
  - campus_id values are exactly 9 digits.
  - No duplicate campus_id rows in cohort_tapr.csv.
  - tapr_source_year is populated (non-null) for every row.
  - Percentage/rate columns are between 0 and 100 (when not null).
  - No sentinel codes (-1, -2, -3) appear as numeric values in measure columns.
  - Cohort row count is exactly 60 (left join preserves all cohort schools).
  - All campus_ids from cohort_ids.csv are present in cohort_tapr.csv.
  - Join report exists and reports cohort_school_count == 60.

Integration tests skip automatically when output files are missing.
Run: pytest tests/
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_tapr import (
    ATTENDANCE_FIELDS,
    PCT_COLUMNS,
    STAFF_FIELDS,
    STUDENT_FIELDS,
    normalize_campus_id,
    normalize_measure,
)

_ROOT = Path(__file__).parent.parent
COHORT_IDS = _ROOT / "data" / "processed" / "cohort_ids.csv"
COHORT_TAPR = _ROOT / "data" / "processed" / "cohort_tapr.csv"
JOIN_REPORT = _ROOT / "data" / "processed" / "tapr_join_report.json"
DATA_DICT = _ROOT / "data" / "processed" / "data_dictionary.json"

_ALL_MEASURE_COLS = list(STUDENT_FIELDS.values()) + list(ATTENDANCE_FIELDS.values()) + list(STAFF_FIELDS.values())
_SENTINEL_FLOATS = {-1.0, -2.0, -3.0}


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def cohort_ids_df():
    if not COHORT_IDS.exists():
        pytest.skip(f"cohort_ids.csv not found; run build_cohort.py first")
    return pd.read_csv(COHORT_IDS, dtype=str)


@pytest.fixture(scope="module")
def tapr_df():
    if not COHORT_TAPR.exists():
        pytest.skip(f"cohort_tapr.csv not found; run build_tapr.py first")
    return pd.read_csv(COHORT_TAPR, dtype=str)


@pytest.fixture(scope="module")
def tapr_df_numeric():
    """cohort_tapr.csv with measure columns coerced to float."""
    if not COHORT_TAPR.exists():
        pytest.skip(f"cohort_tapr.csv not found; run build_tapr.py first")
    df = pd.read_csv(COHORT_TAPR, dtype=str)
    for col in _ALL_MEASURE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@pytest.fixture(scope="module")
def join_report():
    if not JOIN_REPORT.exists():
        pytest.skip(f"tapr_join_report.json not found; run build_tapr.py first")
    return json.loads(JOIN_REPORT.read_text())


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — normalize_campus_id
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizeCampusId:
    def test_strips_leading_apostrophe(self):
        assert normalize_campus_id("'057905001") == "057905001"

    def test_already_clean_nine_digits(self):
        assert normalize_campus_id("057905001") == "057905001"

    def test_eight_digits_returns_none(self):
        assert normalize_campus_id("05790500") is None

    def test_ten_digits_returns_none(self):
        assert normalize_campus_id("0579050011") is None

    def test_non_digit_returns_none(self):
        assert normalize_campus_id("05790500X") is None

    def test_blank_returns_none(self):
        assert normalize_campus_id("") is None

    def test_none_returns_none(self):
        assert normalize_campus_id(None) is None

    def test_leading_spaces_stripped(self):
        assert normalize_campus_id("  057905001  ") == "057905001"


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — normalize_measure
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizeMeasure:
    def test_valid_float(self):
        val, code = normalize_measure("92.8")
        assert val == pytest.approx(92.8)
        assert code is None

    def test_valid_integer_string(self):
        val, code = normalize_measure("220")
        assert val == pytest.approx(220.0)
        assert code is None

    def test_sentinel_minus_one(self):
        val, code = normalize_measure("-1")
        assert val is None
        assert code == "-1"

    def test_sentinel_minus_two(self):
        val, code = normalize_measure("-2")
        assert val is None
        assert code == "-2"

    def test_sentinel_minus_three(self):
        val, code = normalize_measure("-3")
        assert val is None
        assert code == "-3"

    def test_blank_string(self):
        val, code = normalize_measure("")
        assert val is None
        assert code == "blank"

    def test_none_input(self):
        val, code = normalize_measure(None)
        assert val is None
        assert code is None

    def test_nan_string(self):
        val, code = normalize_measure("nan")
        assert val is None
        assert code == "blank"

    def test_zero_is_valid(self):
        val, code = normalize_measure("0")
        assert val == pytest.approx(0.0)
        assert code is None

    def test_whitespace_blank(self):
        val, code = normalize_measure("   ")
        assert val is None
        assert code == "blank"


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — campus IDs
# ──────────────────────────────────────────────────────────────────────────────


class TestCampusIds:
    def test_all_campus_ids_are_nine_digits(self, tapr_df):
        bad = tapr_df["campus_id"].dropna().apply(
            lambda v: not (str(v).isdigit() and len(str(v)) == 9)
        )
        assert not bad.any(), (
            f"{bad.sum()} campus_id values are not 9-digit strings: "
            f"{tapr_df.loc[bad, 'campus_id'].tolist()[:5]}"
        )

    def test_no_duplicate_campus_ids(self, tapr_df):
        dupes = tapr_df["campus_id"].duplicated()
        assert not dupes.any(), (
            f"{dupes.sum()} duplicate campus_id values: "
            f"{tapr_df.loc[dupes, 'campus_id'].tolist()[:5]}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — source year
# ──────────────────────────────────────────────────────────────────────────────


class TestSourceYear:
    def test_tapr_source_year_column_exists(self, tapr_df):
        assert "tapr_source_year" in tapr_df.columns, (
            "tapr_source_year column missing from cohort_tapr.csv"
        )

    def test_tapr_source_year_populated_for_all_rows(self, tapr_df):
        null_count = tapr_df["tapr_source_year"].isna().sum()
        assert null_count == 0, (
            f"{null_count} rows have null tapr_source_year"
        )

    def test_tapr_source_year_is_2025(self, tapr_df):
        bad = tapr_df["tapr_source_year"].astype(str).str.strip().ne("2025")
        assert not bad.any(), (
            f"{bad.sum()} rows have tapr_source_year != 2025"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — sentinel suppression
# ──────────────────────────────────────────────────────────────────────────────


class TestSuppressionHandling:
    def test_sentinel_codes_not_present_as_values(self, tapr_df_numeric):
        """No measure column should contain -1, -2, or -3 as a numeric value."""
        for col in _ALL_MEASURE_COLS:
            if col not in tapr_df_numeric.columns:
                continue
            col_vals = tapr_df_numeric[col].dropna()
            sentinel_rows = col_vals[col_vals.isin(_SENTINEL_FLOATS)]
            assert sentinel_rows.empty, (
                f"Column {col!r} still contains sentinel code values: "
                f"{sentinel_rows.tolist()[:5]}"
            )

    def test_suppression_codes_column_exists(self, tapr_df):
        assert "tapr_suppression_codes" in tapr_df.columns

    def test_suppression_codes_are_valid_json_or_null(self, tapr_df):
        for val in tapr_df["tapr_suppression_codes"].dropna():
            try:
                parsed = json.loads(val)
                assert isinstance(parsed, dict), f"Expected dict, got {type(parsed)}"
            except json.JSONDecodeError:
                pytest.fail(f"tapr_suppression_codes is not valid JSON: {val!r}")


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — percentage range validation
# ──────────────────────────────────────────────────────────────────────────────


class TestPercentageRanges:
    def test_pct_columns_between_0_and_100(self, tapr_df_numeric):
        for col in PCT_COLUMNS:
            if col not in tapr_df_numeric.columns:
                continue
            col_vals = tapr_df_numeric[col].dropna()
            out_of_range = col_vals[(col_vals < 0) | (col_vals > 100)]
            assert out_of_range.empty, (
                f"Column {col!r} has values outside [0, 100]: "
                f"{out_of_range.tolist()[:5]}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — cohort preservation
# ──────────────────────────────────────────────────────────────────────────────


class TestCohortPreservation:
    def test_row_count_is_60(self, tapr_df):
        assert len(tapr_df) == 60, (
            f"Expected 60 rows (original cohort size), got {len(tapr_df)}"
        )

    def test_no_cohort_schools_dropped(self, cohort_ids_df, tapr_df):
        """Every campus_id from cohort_ids.csv must appear in cohort_tapr.csv."""
        cohort_ids = set(cohort_ids_df["campus_id"].dropna())
        tapr_ids = set(tapr_df["campus_id"].dropna())
        missing = cohort_ids - tapr_ids
        assert not missing, (
            f"{len(missing)} cohort campus IDs missing from cohort_tapr.csv: "
            f"{sorted(missing)[:5]}"
        )

    def test_cohort_campus_ids_match_exactly(self, cohort_ids_df, tapr_df):
        """No extra campus_ids appear in cohort_tapr.csv beyond the original cohort."""
        cohort_ids = set(cohort_ids_df["campus_id"].dropna())
        tapr_ids = set(tapr_df["campus_id"].dropna())
        extra = tapr_ids - cohort_ids
        assert not extra, (
            f"{len(extra)} extra campus IDs in cohort_tapr.csv not in cohort_ids.csv: "
            f"{sorted(extra)[:5]}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — join coverage (via join report)
# ──────────────────────────────────────────────────────────────────────────────


class TestJoinReport:
    def test_join_report_cohort_count_is_60(self, join_report):
        assert join_report["cohort_school_count"] == 60, (
            f"Join report cohort_school_count is {join_report['cohort_school_count']}, expected 60"
        )

    def test_join_coverage_reasonable(self, join_report):
        """At least 80% of cohort schools should have some TAPR data."""
        matched = join_report["tapr_matched"]
        total = join_report["cohort_school_count"]
        pct = 100 * matched / total if total else 0
        assert pct >= 80, (
            f"Only {matched}/{total} cohort schools matched TAPR ({pct:.1f}%). "
            "Expected at least 80% coverage."
        )

    def test_join_report_has_null_counts(self, join_report):
        assert "null_counts_per_output_column" in join_report
        assert isinstance(join_report["null_counts_per_output_column"], dict)


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — data dictionary
# ──────────────────────────────────────────────────────────────────────────────


class TestDataDictionary:
    def test_data_dictionary_exists(self):
        if not DATA_DICT.exists():
            pytest.skip("data_dictionary.json not found; run build_tapr.py first")
        assert DATA_DICT.exists()

    def test_data_dictionary_is_valid_json(self):
        if not DATA_DICT.exists():
            pytest.skip("data_dictionary.json not found")
        dd = json.loads(DATA_DICT.read_text())
        assert isinstance(dd, dict)
        assert "fields" in dd

    def test_all_output_columns_documented(self):
        if not DATA_DICT.exists():
            pytest.skip("data_dictionary.json not found")
        dd = json.loads(DATA_DICT.read_text())
        documented = {entry["column"] for entry in dd["fields"]}
        expected = set(_ALL_MEASURE_COLS) | {"tapr_source_year", "tapr_matched", "tapr_suppression_codes"}
        missing = expected - documented
        assert not missing, (
            f"Columns missing from data_dictionary.json: {sorted(missing)}"
        )
