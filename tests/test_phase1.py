"""
Phase 1 test suite.

Unit tests (no file I/O):
  - parse_enrollment: sentinel -1 → None; blanks → None; real values preserved.
  - normalize_id: apostrophe stripped; wrong length → None; non-digit → None.

Integration tests (read output files produced by build_cohort.py):
  - campus IDs are exactly 9 digits.
  - district IDs are exactly 6 digits.
  - campus IDs are unique.
  - school_status column is all "Active".
  - school_site_city is all "DALLAS".
  - instruction_type contains no DAEP / JJAEP rows.
  - cohort size is between 40 and 80 (inclusive).

Run with: pytest tests/
Integration tests skip automatically if output files are missing.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_cohort import (
    COHORT_MAX,
    COHORT_MIN,
    EXCLUDED_INSTRUCTION_SUBSTRINGS,
    normalize_id,
    parse_enrollment,
)

_ROOT = Path(__file__).parent.parent
COHORT_IDS = _ROOT / "data" / "processed" / "cohort_ids.csv"
COHORT_PREVIEW = _ROOT / "data" / "processed" / "cohort_preview.csv"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ids_df():
    if not COHORT_IDS.exists():
        pytest.skip(f"cohort_ids.csv not found at {COHORT_IDS}; run build_cohort.py first")
    return pd.read_csv(COHORT_IDS, dtype=str)


@pytest.fixture(scope="module")
def preview_df():
    if not COHORT_PREVIEW.exists():
        pytest.skip(f"cohort_preview.csv not found at {COHORT_PREVIEW}; run build_cohort.py first")
    return pd.read_csv(COHORT_PREVIEW, dtype=str)


# ---------------------------------------------------------------------------
# Unit tests — normalization functions
# ---------------------------------------------------------------------------

class TestParseEnrollment:
    def test_sentinel_minus_one_returns_none(self):
        assert parse_enrollment("-1") is None

    def test_sentinel_minus_one_float_string(self):
        assert parse_enrollment("-1.0") is None

    def test_sentinel_int_minus_one(self):
        assert parse_enrollment(-1) is None

    def test_blank_string_returns_none(self):
        assert parse_enrollment("") is None

    def test_none_returns_none(self):
        assert parse_enrollment(None) is None

    def test_zero_returns_zero(self):
        assert parse_enrollment("0") == 0

    def test_positive_integer(self):
        assert parse_enrollment("500") == 500

    def test_positive_float_string_truncates(self):
        assert parse_enrollment("734.0") == 734

    def test_non_numeric_returns_none(self):
        assert parse_enrollment("N/A") is None


class TestNormalizeId:
    def test_strips_leading_apostrophe_campus(self):
        assert normalize_id("'057802001", 9) == "057802001"

    def test_strips_leading_apostrophe_district(self):
        assert normalize_id("'057802", 6) == "057802"

    def test_already_clean_campus(self):
        assert normalize_id("043910052", 9) == "043910052"

    def test_wrong_length_returns_none(self):
        assert normalize_id("'05780200", 9) is None    # 8 digits

    def test_non_digit_returns_none(self):
        assert normalize_id("'05780200X", 9) is None

    def test_blank_returns_none(self):
        assert normalize_id("", 9) is None

    def test_none_returns_none(self):
        assert normalize_id(None, 9) is None


# ---------------------------------------------------------------------------
# Integration tests — output files
# ---------------------------------------------------------------------------

class TestCampusIds:
    def test_nine_digit_campus_ids(self, ids_df):
        bad = ids_df["campus_id"].dropna().apply(
            lambda v: not (v.isdigit() and len(v) == 9)
        )
        assert not bad.any(), (
            f"{bad.sum()} campus_id values are not exactly 9 digits: "
            f"{ids_df.loc[bad, 'campus_id'].tolist()[:5]}"
        )

    def test_six_digit_district_ids(self, ids_df):
        bad = ids_df["district_id"].dropna().apply(
            lambda v: not (v.isdigit() and len(v) == 6)
        )
        assert not bad.any(), (
            f"{bad.sum()} district_id values are not exactly 6 digits: "
            f"{ids_df.loc[bad, 'district_id'].tolist()[:5]}"
        )

    def test_unique_campus_ids(self, ids_df):
        dupes = ids_df["campus_id"].duplicated()
        assert not dupes.any(), (
            f"{dupes.sum()} duplicate campus_id values: "
            f"{ids_df.loc[dupes, 'campus_id'].tolist()[:5]}"
        )


class TestCohortRules:
    def test_active_status_only(self, preview_df):
        non_active = preview_df["school_status"].dropna()[
            preview_df["school_status"].dropna() != "Active"
        ]
        assert len(non_active) == 0, (
            f"{len(non_active)} rows with non-Active status: {non_active.unique().tolist()}"
        )

    def test_dallas_site_city(self, preview_df):
        non_dallas = preview_df["school_site_city"].dropna()[
            preview_df["school_site_city"].str.upper() != "DALLAS"
        ]
        assert len(non_dallas) == 0, (
            f"{len(non_dallas)} rows with site city != DALLAS: {non_dallas.unique().tolist()}"
        )

    def test_excluded_instruction_types_absent(self, preview_df):
        def _is_excluded(val):
            if pd.isna(val) or not val:
                return False
            upper = str(val).upper()
            return any(sub in upper for sub in EXCLUDED_INSTRUCTION_SUBSTRINGS)

        bad = preview_df["instruction_type"].apply(_is_excluded)
        assert not bad.any(), (
            f"{bad.sum()} rows with excluded instruction types: "
            f"{preview_df.loc[bad, 'instruction_type'].unique().tolist()}"
        )

    def test_enrollment_sentinel_not_present(self, preview_df):
        sentinel_rows = preview_df["enrollment"].astype(str).str.strip() == "-1"
        assert not sentinel_rows.any(), (
            f"{sentinel_rows.sum()} rows still have enrollment == -1 (sentinel not converted)"
        )

    def test_district_prefix_matches_campus_prefix(self, ids_df):
        valid = ids_df.dropna(subset=["campus_id", "district_id"])
        mismatches = valid[valid["campus_id"].str[:6] != valid["district_id"]]
        assert len(mismatches) == 0, (
            f"{len(mismatches)} rows where campus_id prefix != district_id"
        )


class TestCohortSize:
    def test_cohort_size_in_range(self, ids_df):
        n = len(ids_df)
        assert COHORT_MIN <= n <= COHORT_MAX, (
            f"Cohort size {n} is outside the required range [{COHORT_MIN}, {COHORT_MAX}]"
        )
