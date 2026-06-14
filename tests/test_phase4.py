"""
Phase 4 tests — 2025 accountability ratings and ArcGIS coordinates.

Unit tests for normalization functions run without any data files.
Integration tests require data/processed/cohort_enriched.csv and are
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
_ENRICHED_CSV = _ROOT / "data" / "processed" / "cohort_enriched.csv"
_ENRICHED_PARQUET = _ROOT / "data" / "processed" / "cohort_enriched.parquet"
_ACCT_REPORT = _ROOT / "data" / "processed" / "accountability_join_report.json"
_ARCGIS_REPORT = _ROOT / "data" / "processed" / "arcgis_join_report.json"
_DD_PATH = _ROOT / "data" / "processed" / "data_dictionary.json"

_VALID_RATING_CODES = frozenset({"A", "B", "C", "D", "F", "Not Rated"})

# Dallas TX geographic bounds for coordinate sanity checks
_LAT_MIN, _LAT_MAX = 32.5, 33.2
_LON_MIN, _LON_MAX = -97.2, -96.4


def _integration_skip(reason: str = "cohort_enriched.csv not found; run build_enriched.py"):
    return pytest.mark.skipif(not _ENRICHED_CSV.exists(), reason=reason)


@pytest.fixture(scope="module")
def cohort() -> pd.DataFrame:
    return pd.read_csv(_ENRICHED_CSV, dtype={"campus_id": str})


@pytest.fixture(scope="module")
def acct_report() -> dict:
    return json.loads(_ACCT_REPORT.read_text())


@pytest.fixture(scope="module")
def arcgis_report() -> dict:
    return json.loads(_ARCGIS_REPORT.read_text())


@pytest.fixture(scope="module")
def data_dictionary() -> dict:
    return json.loads(_DD_PATH.read_text())


# ──────────────────────────────────────────────────────────────────────────────
# Unit: normalize_campus_id_acct
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizeCampusIdAcct:
    def test_valid_9digit(self):
        from scripts.build_enriched import normalize_campus_id_acct
        assert normalize_campus_id_acct("057802001") == "057802001"

    def test_strips_whitespace(self):
        from scripts.build_enriched import normalize_campus_id_acct
        assert normalize_campus_id_acct("  057802001  ") == "057802001"

    def test_strips_leading_apostrophe(self):
        from scripts.build_enriched import normalize_campus_id_acct
        assert normalize_campus_id_acct("'057802001") == "057802001"

    def test_too_short_returns_none(self):
        from scripts.build_enriched import normalize_campus_id_acct
        assert normalize_campus_id_acct("05780200") is None

    def test_too_long_returns_none(self):
        from scripts.build_enriched import normalize_campus_id_acct
        assert normalize_campus_id_acct("0578020010") is None

    def test_alpha_chars_returns_none(self):
        from scripts.build_enriched import normalize_campus_id_acct
        assert normalize_campus_id_acct("05780200A") is None

    def test_none_input_returns_none(self):
        from scripts.build_enriched import normalize_campus_id_acct
        assert normalize_campus_id_acct(None) is None

    def test_empty_string_returns_none(self):
        from scripts.build_enriched import normalize_campus_id_acct
        assert normalize_campus_id_acct("") is None


# ──────────────────────────────────────────────────────────────────────────────
# Unit: derive_accountability_status
# ──────────────────────────────────────────────────────────────────────────────


class TestDeriveAccountabilityStatus:
    def test_a_is_rated(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status("A") == "Rated"

    def test_b_is_rated(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status("B") == "Rated"

    def test_c_is_rated(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status("C") == "Rated"

    def test_d_is_rated(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status("D") == "Rated"

    def test_f_is_rated(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status("F") == "Rated"

    def test_not_rated_string_preserved(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status("Not Rated") == "Not Rated"

    def test_not_rated_is_not_null(self):
        from scripts.build_enriched import derive_accountability_status
        result = derive_accountability_status("Not Rated")
        assert result is not None

    def test_none_returns_none(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status(None) is None

    def test_float_nan_returns_none(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status(float("nan")) is None

    def test_whitespace_around_rating(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status("  A  ") == "Rated"

    def test_not_rated_with_whitespace(self):
        from scripts.build_enriched import derive_accountability_status
        assert derive_accountability_status("  Not Rated  ") == "Not Rated"


# ──────────────────────────────────────────────────────────────────────────────
# Integration: cohort shape and identity
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestCohortPreservation:
    def test_exactly_60_rows(self, cohort):
        assert len(cohort) == 60, f"Expected 60 rows, got {len(cohort)}"

    def test_no_duplicate_campus_ids(self, cohort):
        dupes = cohort["campus_id"].duplicated()
        assert not dupes.any(), (
            f"Duplicate campus_ids: {cohort.loc[dupes, 'campus_id'].tolist()}"
        )

    def test_campus_id_nine_digits(self, cohort):
        bad = cohort["campus_id"].apply(
            lambda v: not (isinstance(v, str) and v.isdigit() and len(v) == 9)
        )
        assert not bad.any(), f"Non-9-digit campus_ids: {cohort.loc[bad, 'campus_id'].tolist()}"

    def test_prior_columns_intact(self, cohort):
        for col in ["tapr_membership_all_count_2025", "crdc_tot_enr_m_2122"]:
            assert col in cohort.columns, f"Prior column missing: {col}"


# ──────────────────────────────────────────────────────────────────────────────
# Integration: accountability join
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestAccountabilityJoin:
    def test_accountability_matched_column_present(self, cohort):
        assert "accountability_matched" in cohort.columns

    def test_accountability_rating_column_present(self, cohort):
        assert "accountability_rating_2025" in cohort.columns

    def test_accountability_status_column_present(self, cohort):
        assert "accountability_status_2025" in cohort.columns

    def test_accountability_score_column_present(self, cohort):
        assert "accountability_score_2025" in cohort.columns

    def test_at_least_50pct_matched(self, cohort):
        matched = cohort["accountability_matched"].astype(str).str.lower()
        n = (matched == "true").sum() + (matched == "1").sum()
        pct = 100 * n / len(cohort)
        assert pct >= 50, f"Accountability match rate too low: {pct:.1f}%"

    def test_source_year_populated(self, cohort):
        assert "accountability_source_year" in cohort.columns
        vals = cohort["accountability_source_year"].dropna().unique().tolist()
        assert 2025 in [int(v) for v in vals], f"Source year 2025 not found: {vals}"

    def test_rating_codes_valid(self, cohort):
        for val in cohort["accountability_rating_2025"].dropna():
            s = str(val).strip()
            assert s in _VALID_RATING_CODES, f"Unexpected rating code: {s!r}"

    def test_not_rated_is_string_not_null(self, cohort):
        """Campuses with 'Not Rated' must have a non-null rating value."""
        status_col = cohort["accountability_status_2025"]
        not_rated_mask = status_col.astype(str).str.strip() == "Not Rated"
        if not not_rated_mask.any():
            return
        rating_for_not_rated = cohort.loc[not_rated_mask, "accountability_rating_2025"]
        nulls = rating_for_not_rated.isna()
        assert not nulls.any(), (
            "Schools with status 'Not Rated' have null accountability_rating_2025 "
            "(should be 'Not Rated', not null)"
        )

    def test_status_consistent_with_rating(self, cohort):
        from scripts.build_enriched import derive_accountability_status, _RATED_CODES
        for _, row in cohort.iterrows():
            rating = row.get("accountability_rating_2025")
            status = row.get("accountability_status_2025")
            expected = derive_accountability_status(rating)
            if expected is None:
                assert status is None or (isinstance(status, float) and math.isnan(status)), (
                    f"campus {row['campus_id']}: expected null status, got {status!r}"
                )
            else:
                actual = None if (status is None or (isinstance(status, float) and math.isnan(status))) else str(status).strip()
                assert actual == expected, (
                    f"campus {row['campus_id']}: rating={rating!r} → expected status {expected!r}, got {actual!r}"
                )

    def test_unmatched_have_null_rating(self, cohort):
        matched_col = cohort["accountability_matched"].astype(str).str.lower()
        unmatched = cohort[(matched_col != "true") & (matched_col != "1")]
        for val in unmatched["accountability_rating_2025"].tolist():
            assert val is None or (isinstance(val, float) and math.isnan(val)), (
                f"Unmatched school has non-null rating: {val!r}"
            )

    def test_score_numeric_or_null(self, cohort):
        col = pd.to_numeric(cohort["accountability_score_2025"], errors="coerce")
        non_null = col.dropna()
        assert (non_null >= 0).all() and (non_null <= 100).all(), (
            "accountability_score_2025 values out of [0, 100] range"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Integration: ArcGIS coordinates
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestArcGISJoin:
    def test_arcgis_matched_column_present(self, cohort):
        assert "arcgis_matched" in cohort.columns

    def test_latitude_column_present(self, cohort):
        assert "latitude" in cohort.columns

    def test_longitude_column_present(self, cohort):
        assert "longitude" in cohort.columns

    def test_geocode_source_column_present(self, cohort):
        assert "geocode_source" in cohort.columns

    def test_arcgis_source_year_present(self, cohort):
        assert "arcgis_source_year" in cohort.columns

    def test_at_least_50pct_have_coordinates(self, cohort):
        n = cohort["latitude"].notna().sum()
        pct = 100 * n / len(cohort)
        assert pct >= 50, f"Coordinate coverage too low: {pct:.1f}%"

    def test_latitude_in_dallas_bounds(self, cohort):
        lats = pd.to_numeric(cohort["latitude"], errors="coerce").dropna()
        out_of_range = lats[(lats < _LAT_MIN) | (lats > _LAT_MAX)]
        assert len(out_of_range) == 0, (
            f"{len(out_of_range)} latitudes outside Dallas bounds "
            f"[{_LAT_MIN}, {_LAT_MAX}]: {out_of_range.tolist()}"
        )

    def test_longitude_in_dallas_bounds(self, cohort):
        lons = pd.to_numeric(cohort["longitude"], errors="coerce").dropna()
        out_of_range = lons[(lons < _LON_MIN) | (lons > _LON_MAX)]
        assert len(out_of_range) == 0, (
            f"{len(out_of_range)} longitudes outside Dallas bounds "
            f"[{_LON_MIN}, {_LON_MAX}]: {out_of_range.tolist()}"
        )

    def test_unmatched_have_null_coordinates(self, cohort):
        matched_col = cohort["arcgis_matched"].astype(str).str.lower()
        unmatched = cohort[(matched_col != "true") & (matched_col != "1")]
        for col in ["latitude", "longitude"]:
            vals = pd.to_numeric(unmatched[col], errors="coerce").dropna()
            assert len(vals) == 0, (
                f"Unmatched schools have non-null {col}: {vals.tolist()}"
            )

    def test_coordinates_present_iff_matched(self, cohort):
        matched_col = cohort["arcgis_matched"].astype(str).str.lower()
        is_matched = (matched_col == "true") | (matched_col == "1")
        has_lat = cohort["latitude"].notna()
        # All matched should have latitude
        matched_without_lat = is_matched & ~has_lat
        assert not matched_without_lat.any(), (
            f"{matched_without_lat.sum()} matched schools are missing latitude"
        )

    def test_geocode_source_populated_for_matched(self, cohort):
        matched_col = cohort["arcgis_matched"].astype(str).str.lower()
        is_matched = (matched_col == "true") | (matched_col == "1")
        bad = is_matched & cohort["geocode_source"].isna()
        assert not bad.any(), f"{bad.sum()} matched schools have null geocode_source"

    def test_geocode_source_null_for_unmatched(self, cohort):
        matched_col = cohort["arcgis_matched"].astype(str).str.lower()
        is_unmatched = ~((matched_col == "true") | (matched_col == "1"))
        bad = is_unmatched & cohort["geocode_source"].notna()
        assert not bad.any(), f"{bad.sum()} unmatched schools have non-null geocode_source"


# ──────────────────────────────────────────────────────────────────────────────
# Integration: null / sentinel handling
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestNullHandling:
    def test_no_tapr_sentinel_in_rating(self, cohort):
        """TEA masking codes should not appear in the rating column."""
        bad_vals = {"-1", "-2", "-3"}
        for val in cohort["accountability_rating_2025"].dropna():
            assert str(val).strip() not in bad_vals, (
                f"TEA masking code found in rating: {val!r}"
            )

    def test_not_rated_never_null(self, cohort):
        """Every campus with accountability_status_2025='Not Rated' must also
        have accountability_rating_2025='Not Rated' (not null)."""
        status_col = cohort["accountability_status_2025"].astype(str).str.strip()
        not_rated_rows = cohort[status_col == "Not Rated"]
        if not_rated_rows.empty:
            return
        nulls = not_rated_rows["accountability_rating_2025"].isna()
        assert not nulls.any(), "'Not Rated' status paired with null rating value"

    def test_no_arcgis_sentinel_in_coordinates(self, cohort):
        """ArcGIS does not use sentinel values; coordinates must be real floats or null."""
        for col in ["latitude", "longitude"]:
            vals = pd.to_numeric(cohort[col], errors="coerce")
            assert (vals.dropna() != -9).all(), f"Sentinel -9 found in {col}"

    def test_arcgis_source_year_populated(self, cohort):
        null_count = cohort["arcgis_source_year"].isna().sum()
        assert null_count == 0, f"arcgis_source_year has {null_count} null values"

    def test_accountability_source_year_populated(self, cohort):
        null_count = cohort["accountability_source_year"].isna().sum()
        assert null_count == 0, f"accountability_source_year has {null_count} null values"


# ──────────────────────────────────────────────────────────────────────────────
# Integration: join reports
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestJoinReports:
    def test_accountability_report_exists(self):
        assert _ACCT_REPORT.exists()

    def test_arcgis_report_exists(self):
        assert _ARCGIS_REPORT.exists()

    def test_acct_cohort_count_60(self, acct_report):
        assert acct_report["cohort_school_count"] == 60

    def test_arcgis_cohort_count_60(self, arcgis_report):
        assert arcgis_report["cohort_school_count"] == 60

    def test_acct_matched_plus_unmatched_equals_total(self, acct_report):
        total = acct_report["cohort_school_count"]
        assert acct_report["accountability_matched"] + acct_report["accountability_unmatched"] == total

    def test_arcgis_matched_plus_unmatched_equals_total(self, arcgis_report):
        total = arcgis_report["cohort_school_count"]
        assert arcgis_report["arcgis_matched"] + arcgis_report["arcgis_unmatched"] == total

    def test_acct_source_year_correct(self, acct_report):
        assert acct_report["source_year"] == 2025

    def test_arcgis_source_year_correct(self, arcgis_report):
        assert arcgis_report["source_year"] == "2024-25"

    def test_acct_match_pct_at_least_50(self, acct_report):
        assert acct_report["accountability_match_pct"] >= 50, (
            f"Accountability match rate too low: {acct_report['accountability_match_pct']}%"
        )

    def test_arcgis_match_pct_at_least_50(self, arcgis_report):
        assert arcgis_report["arcgis_match_pct"] >= 50, (
            f"ArcGIS match rate too low: {arcgis_report['arcgis_match_pct']}%"
        )

    def test_acct_rating_distribution_keys_valid(self, acct_report):
        for key in acct_report.get("rating_distribution", {}).keys():
            assert key in _VALID_RATING_CODES, f"Unexpected rating in distribution: {key!r}"

    def test_coordinate_bounds_reasonable(self, arcgis_report):
        bounds = arcgis_report.get("coordinate_bounds", {})
        if bounds.get("latitude_min") is not None:
            assert _LAT_MIN <= bounds["latitude_min"] <= _LAT_MAX
        if bounds.get("latitude_max") is not None:
            assert _LAT_MIN <= bounds["latitude_max"] <= _LAT_MAX
        if bounds.get("longitude_min") is not None:
            assert _LON_MIN <= bounds["longitude_min"] <= _LON_MAX
        if bounds.get("longitude_max") is not None:
            assert _LON_MIN <= bounds["longitude_max"] <= _LON_MAX


# ──────────────────────────────────────────────────────────────────────────────
# Integration: data dictionary
# ──────────────────────────────────────────────────────────────────────────────


@_integration_skip()
class TestDataDictionary:
    def test_dd_file_exists(self):
        assert _DD_PATH.exists()

    def test_accountability_fields_documented(self, data_dictionary):
        documented = {e["column"] for e in data_dictionary["fields"]}
        required = {"accountability_rating_2025", "accountability_status_2025",
                    "accountability_score_2025", "accountability_matched",
                    "accountability_source_year"}
        missing = required - documented
        assert not missing, f"Missing from data dictionary: {missing}"

    def test_coordinate_fields_documented(self, data_dictionary):
        documented = {e["column"] for e in data_dictionary["fields"]}
        required = {"latitude", "longitude", "geocode_source",
                    "arcgis_source_year", "arcgis_matched"}
        missing = required - documented
        assert not missing, f"Missing from data dictionary: {missing}"

    def test_all_phase4_output_columns_documented(self, cohort, data_dictionary):
        documented = {e["column"] for e in data_dictionary["fields"]}
        phase4_cols = [
            c for c in cohort.columns
            if c.startswith(("accountability_", "acct_", "arcgis_"))
            or c in ("latitude", "longitude", "geocode_source")
        ]
        missing = [c for c in phase4_cols if c not in documented]
        assert not missing, f"Phase 4 output columns not in data dictionary: {missing}"

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
        assert _ENRICHED_PARQUET.exists()

    def test_parquet_row_count(self):
        df = pd.read_parquet(_ENRICHED_PARQUET)
        assert len(df) == 60, f"Expected 60 rows, got {len(df)}"

    def test_parquet_latitude_is_float(self):
        df = pd.read_parquet(_ENRICHED_PARQUET)
        if "latitude" in df.columns:
            assert pd.api.types.is_float_dtype(df["latitude"]), (
                f"latitude dtype is {df['latitude'].dtype}, expected float"
            )

    def test_parquet_longitude_is_float(self):
        df = pd.read_parquet(_ENRICHED_PARQUET)
        if "longitude" in df.columns:
            assert pd.api.types.is_float_dtype(df["longitude"]), (
                f"longitude dtype is {df['longitude'].dtype}, expected float"
            )

    def test_parquet_score_is_numeric(self):
        df = pd.read_parquet(_ENRICHED_PARQUET)
        if "accountability_score_2025" in df.columns:
            assert pd.api.types.is_numeric_dtype(df["accountability_score_2025"]), (
                f"accountability_score_2025 dtype is {df['accountability_score_2025'].dtype}, expected numeric"
            )

    def test_parquet_has_phase4_columns(self):
        df = pd.read_parquet(_ENRICHED_PARQUET)
        expected = ["accountability_rating_2025", "latitude", "longitude", "arcgis_matched"]
        for col in expected:
            assert col in df.columns, f"Parquet missing column: {col}"
