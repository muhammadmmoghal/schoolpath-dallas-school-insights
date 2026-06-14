"""
Phase 5 tests — final dataset quality validation.

All integration tests are skipped when dallas_school_insights.csv is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
INSIGHTS_CSV = PROCESSED / "dallas_school_insights.csv"
INSIGHTS_PARQUET = PROCESSED / "dallas_school_insights.parquet"
DATA_DICT_CSV = PROCESSED / "data_dictionary.csv"
QUALITY_JSON = PROCESSED / "data_quality_report.json"
COVERAGE_CSV = PROCESSED / "source_coverage_report.csv"

SKIP_INTEGRATION = not INSIGHTS_CSV.exists()
SKIP_MSG = "dallas_school_insights.csv not found; run scripts/build_final.py"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def df():
    return pd.read_csv(
        INSIGHTS_CSV,
        dtype={"campus_id": str, "district_id": str, "nces_school_id": str},
    )


@pytest.fixture(scope="module")
def quality_report():
    with open(QUALITY_JSON, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def data_dict():
    return pd.read_csv(DATA_DICT_CSV)


@pytest.fixture(scope="module")
def coverage():
    return pd.read_csv(COVERAGE_CSV)


# ---------------------------------------------------------------------------
# Category 1: Shape and uniqueness
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestShapeAndUniqueness:
    def test_exactly_60_rows(self, df):
        assert len(df) == 60, f"Expected 60 rows, got {len(df)}"

    def test_no_duplicate_campus_ids(self, df):
        assert not df["campus_id"].duplicated().any()

    def test_no_duplicate_nces_ids(self, df):
        nces = df["nces_school_id"].dropna()
        assert not nces.duplicated().any()

    def test_campus_id_nine_digits(self, df):
        valid = df["campus_id"].apply(lambda v: isinstance(v, str) and v.isdigit() and len(v) == 9)
        assert valid.all(), f"Non-9-digit campus_ids: {df.loc[~valid, 'campus_id'].tolist()}"

    def test_column_count_matches_expected(self, df):
        # 79 final columns defined in build_final.FINAL_COLUMNS
        assert df.shape[1] == 79, f"Expected 79 columns, got {df.shape[1]}"


# ---------------------------------------------------------------------------
# Category 2: Required identity fields
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestRequiredIdentityFields:
    def test_campus_id_fully_populated(self, df):
        assert df["campus_id"].notna().all()

    def test_school_name_fully_populated(self, df):
        assert df["school_name"].notna().all()

    def test_district_name_fully_populated(self, df):
        assert df["district_name"].notna().all()

    def test_address_fully_populated(self, df):
        assert df["school_site_address"].notna().all()

    def test_enrollment_fully_populated(self, df):
        assert df["enrollment"].notna().all()

    def test_all_schools_in_dallas(self, df):
        assert (df["school_site_city"] == "DALLAS").all()

    def test_all_schools_active(self, df):
        assert (df["school_status"] == "Active").all()


# ---------------------------------------------------------------------------
# Category 3: Accountability data quality
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestAccountabilityQuality:
    _VALID_RATINGS = {"A", "B", "C", "D", "F", "Not Rated"}

    def test_accountability_rating_fully_populated(self, df):
        assert df["accountability_rating_2025"].notna().all()

    def test_accountability_rating_valid_codes(self, df):
        ratings = df["accountability_rating_2025"].dropna()
        invalid = ratings[~ratings.isin(self._VALID_RATINGS)]
        assert invalid.empty, f"Invalid ratings: {invalid.unique().tolist()}"

    def test_not_rated_is_string_not_null(self, df):
        not_rated = df[df["accountability_rating_2025"] == "Not Rated"]
        if not not_rated.empty:
            assert not_rated["accountability_status_2025"].eq("Not Rated").all()

    def test_rated_schools_have_status_rated(self, df):
        rated_mask = df["accountability_rating_2025"].isin({"A", "B", "C", "D", "F"})
        rated = df[rated_mask]
        assert (rated["accountability_status_2025"] == "Rated").all()

    def test_score_is_numeric_when_present(self, df):
        import pandas.api.types as pat
        assert pat.is_numeric_dtype(df["accountability_score_2025"]) or \
               pd.to_numeric(df["accountability_score_2025"], errors="coerce").notna().any()

    def test_acct_alt_ed_type_dropped(self, df):
        assert "acct_alt_ed_type_2025" not in df.columns, \
            "acct_alt_ed_type_2025 must be dropped (all-null column)"

    def test_acct_charter_flag_dropped(self, df):
        assert "acct_charter_flag_2025" not in df.columns, \
            "acct_charter_flag_2025 must be dropped (duplicated by district_type)"


# ---------------------------------------------------------------------------
# Category 4: Valid coordinate range
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestCoordinateQuality:
    def test_latitude_fully_populated(self, df):
        assert df["latitude"].notna().all()

    def test_longitude_fully_populated(self, df):
        assert df["longitude"].notna().all()

    def test_latitude_in_dallas_range(self, df):
        lat = pd.to_numeric(df["latitude"], errors="coerce")
        assert ((lat >= 32.5) & (lat <= 33.2)).all(), \
            f"Out-of-range latitudes: {lat[(lat < 32.5) | (lat > 33.2)].tolist()}"

    def test_longitude_in_dallas_range(self, df):
        lon = pd.to_numeric(df["longitude"], errors="coerce")
        assert ((lon >= -97.2) & (lon <= -96.4)).all(), \
            f"Out-of-range longitudes: {lon[(lon < -97.2) | (lon > -96.4)].tolist()}"


# ---------------------------------------------------------------------------
# Category 5: Valid percentages and counts
# ---------------------------------------------------------------------------

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


@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestValidRanges:
    @pytest.mark.parametrize("col", _PCT_COLS)
    def test_percentage_in_0_100(self, df, col):
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        assert ((s >= 0) & (s <= 100)).all(), \
            f"{col}: out-of-range values: {s[(s < 0) | (s > 100)].tolist()}"

    def test_enrollment_nonnegative(self, df):
        s = pd.to_numeric(df["enrollment"], errors="coerce").dropna()
        assert (s >= 0).all()

    def test_crdc_counts_nonnegative(self, df):
        crdc_count_cols = [c for c in df.columns if c.startswith("crdc_") and "_pct_" not in c]
        for col in crdc_count_cols:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            neg = s[s < 0]
            assert neg.empty, f"{col}: negative values found: {neg.tolist()}"


# ---------------------------------------------------------------------------
# Category 6: No suppression sentinels remain
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestNoSentinels:
    _SENTINEL_STR = {"-1", "-2", "-3", "-9"}
    _SENTINEL_NUM = {-1, -2, -3, -9}
    # Identity columns are strings; skip sentinel check on them
    _IDENTITY_COLS = {
        "campus_id", "district_id", "nces_school_id", "school_name",
        "district_name", "district_type", "instruction_type", "charter_type",
        "school_level", "operator_type", "grade_range", "school_status",
        "school_site_city", "school_site_address", "school_site_zip",
        "magnet_status",
    }

    def test_no_sentinel_strings_in_analytical_cols(self, df):
        hits: dict = {}
        for col in df.columns:
            if col in self._IDENTITY_COLS:
                continue
            s = df[col]
            if pd.api.types.is_object_dtype(s):
                n = int(s.isin(self._SENTINEL_STR).sum())
                if n:
                    hits[col] = n
        assert not hits, f"Sentinel strings found: {hits}"

    def test_no_sentinel_numbers_in_numeric_cols(self, df):
        hits: dict = {}
        for col in df.columns:
            if col in self._IDENTITY_COLS:
                continue
            s = df[col]
            if pd.api.types.is_numeric_dtype(s):
                n = int(s.isin(self._SENTINEL_NUM).sum())
                if n:
                    hits[col] = n
        assert not hits, f"Sentinel numbers found: {hits}"


# ---------------------------------------------------------------------------
# Category 7: No all-null analytical columns
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestNoAllNullAnalytical:
    _IDENTITY_COLS = set(_PCT_COLS) | {
        "campus_id", "district_id", "nces_school_id", "school_name",
        "district_name", "district_type", "instruction_type", "charter_type",
        "school_level", "operator_type", "grade_range", "enrollment",
        "school_status", "school_site_city", "school_site_address",
        "school_site_zip", "magnet_status", "enrollment_source_year",
    }

    def test_no_analytical_column_is_all_null(self, df):
        analytical = [c for c in df.columns if c not in self._IDENTITY_COLS]
        all_null = [c for c in analytical if df[c].isna().all()]
        assert not all_null, f"All-null analytical columns: {all_null}"


# ---------------------------------------------------------------------------
# Category 8: Data dictionary
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestDataDictionary:
    _REQUIRED_COLS = {
        "column_name", "data_type", "definition", "source", "source_year",
        "raw_cleaned_or_derived", "coverage_percent", "caveat",
    }

    def test_data_dictionary_exists(self):
        assert DATA_DICT_CSV.exists()

    def test_data_dictionary_has_required_schema(self, data_dict):
        assert self._REQUIRED_COLS.issubset(set(data_dict.columns)), \
            f"Missing columns: {self._REQUIRED_COLS - set(data_dict.columns)}"

    def test_all_final_columns_documented(self, df, data_dict):
        documented = set(data_dict["column_name"])
        for col in df.columns:
            assert col in documented, f"{col} not in data_dictionary.csv"

    def test_no_duplicate_dictionary_entries(self, data_dict):
        dupes = data_dict["column_name"].duplicated().sum()
        assert dupes == 0, f"{dupes} duplicate column_name entries in data dictionary"

    def test_all_entries_have_definitions(self, data_dict):
        empty = data_dict[data_dict["definition"].isna() | (data_dict["definition"] == "")]
        assert empty.empty, f"Missing definitions for: {empty['column_name'].tolist()}"

    def test_coverage_percent_in_range(self, data_dict):
        cov = pd.to_numeric(data_dict["coverage_percent"], errors="coerce")
        assert ((cov >= 0) & (cov <= 100)).all()

    def test_source_year_populated(self, data_dict):
        empty = data_dict[data_dict["source_year"].isna() | (data_dict["source_year"].astype(str) == "")]
        assert empty.empty, f"source_year missing for: {empty['column_name'].tolist()}"


# ---------------------------------------------------------------------------
# Category 9: Source coverage report
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestSourceCoverageReport:
    _EXPECTED_SOURCES = {
        "TEA AskTED",
        "TAPR",
        "CRDC",
        "TEA 2025 Campus Accountability Summary",
        "TEA ArcGIS Schools 2024-25",
    }

    def test_coverage_report_exists(self):
        assert COVERAGE_CSV.exists()

    def test_coverage_report_has_all_sources(self, coverage):
        found = set(coverage["source"])
        assert self._EXPECTED_SOURCES.issubset(found), \
            f"Missing sources: {self._EXPECTED_SOURCES - found}"

    def test_schools_total_is_60(self, coverage):
        assert (coverage["schools_total"] == 60).all()

    def test_match_pct_in_range(self, coverage):
        pct = pd.to_numeric(coverage["match_pct"], errors="coerce")
        assert ((pct >= 0) & (pct <= 100)).all()

    def test_crdc_match_below_100(self, coverage):
        crdc = coverage[coverage["source"] == "CRDC"]
        if not crdc.empty:
            pct = float(crdc["match_pct"].iloc[0])
            assert pct < 100.0, "Expected CRDC match < 100% (2 unmatched schools)"

    def test_non_crdc_sources_100pct(self, coverage):
        non_crdc = coverage[coverage["source"] != "CRDC"]
        low = non_crdc[pd.to_numeric(non_crdc["match_pct"], errors="coerce") < 100.0]
        assert low.empty, f"Unexpected <100% match: {low[['source', 'match_pct']].to_dict('records')}"


# ---------------------------------------------------------------------------
# Category 10: Quality report
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestQualityReport:
    def test_quality_report_exists(self):
        assert QUALITY_JSON.exists()

    def test_all_checks_passed(self, quality_report):
        if not quality_report.get("all_checks_passed"):
            failed = [
                c["name"] for c in quality_report.get("checks", []) if not c["passed"]
            ]
            pytest.fail(f"Quality checks failed: {failed}")

    def test_report_has_expected_fields(self, quality_report):
        for key in ("generated_utc", "total_checks", "checks_passed", "checks_failed", "checks"):
            assert key in quality_report, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Category 11: Parquet file
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_MSG)
class TestParquetFile:
    def test_parquet_exists(self):
        assert INSIGHTS_PARQUET.exists()

    def test_parquet_row_count(self):
        import pyarrow.parquet as pq
        table = pq.read_table(INSIGHTS_PARQUET)
        assert table.num_rows == 60

    def test_parquet_column_count(self):
        import pyarrow.parquet as pq
        table = pq.read_table(INSIGHTS_PARQUET)
        assert table.num_columns == 79

    def test_parquet_lat_lon_float(self):
        import pyarrow.parquet as pq
        import pyarrow as pa
        table = pq.read_table(INSIGHTS_PARQUET)
        schema = table.schema
        for col in ("latitude", "longitude"):
            idx = schema.get_field_index(col)
            assert idx >= 0, f"{col} missing from parquet"
            assert pa.types.is_floating(schema.field(col).type), \
                f"{col} is not float in parquet: {schema.field(col).type}"

    def test_parquet_campus_id_is_string(self):
        import pyarrow.parquet as pq
        import pyarrow as pa
        table = pq.read_table(INSIGHTS_PARQUET)
        schema = table.schema
        idx = schema.get_field_index("campus_id")
        assert idx >= 0
        assert pa.types.is_string(schema.field("campus_id").type) or \
               pa.types.is_large_string(schema.field("campus_id").type)
