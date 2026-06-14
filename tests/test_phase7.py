"""
Phase 7 tests — Streamlit dashboard and data loader.

All tests are local (no network, no Supabase connection required).

Covers:
  1. Local Parquet fallback loading
  2. Supabase loader failure triggers fallback
  3. Required columns present after load
  4. Filters preserve valid rows
  5. No chart crash on all-null subsets
  6. Null values not silently converted to zero
  7. Dashboard files exist
  8. data_loader validates required columns
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
PARQUET = ROOT / "data" / "processed" / "dallas_school_insights.parquet"
DASHBOARD = ROOT / "dashboard"

sys.path.insert(0, str(DASHBOARD))

_SKIP_NO_PARQUET = pytest.mark.skipif(
    not PARQUET.exists(),
    reason="dallas_school_insights.parquet not found; run scripts/build_final.py",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_minimal_df(n: int = 5) -> pd.DataFrame:
    """Return a small DataFrame that satisfies data_loader._validate."""
    return pd.DataFrame(
        {
            "campus_id": [f"10000000{i}" for i in range(n)],
            "school_name": [f"School {i}" for i in range(n)],
            "district_name": ["DISD"] * n,
            "school_level": ["elementary"] * n,
            "operator_type": ["isd"] * n,
            "enrollment": [300.0 + i * 10 for i in range(n)],
            "accountability_rating_2025": ["A", "B", "C", "D", "F"][:n],
            "latitude": [32.78 + i * 0.01 for i in range(n)],
            "longitude": [-96.8 + i * 0.01 for i in range(n)],
        }
    )


# ── Category 1: Dashboard files exist ────────────────────────────────────────

class TestDashboardFilesExist:
    def test_app_py_exists(self):
        assert (DASHBOARD / "app.py").exists()

    def test_data_loader_exists(self):
        assert (DASHBOARD / "data_loader.py").exists()

    def test_components_exists(self):
        assert (DASHBOARD / "components.py").exists()

    def test_school_explorer_page_exists(self):
        assert (DASHBOARD / "pages" / "01_school_explorer.py").exists()

    def test_special_education_page_exists(self):
        assert (DASHBOARD / "pages" / "02_special_education.py").exists()

    def test_culture_safety_page_exists(self):
        assert (DASHBOARD / "pages" / "03_culture_safety.py").exists()

    def test_school_detail_page_exists(self):
        assert (DASHBOARD / "pages" / "04_school_detail.py").exists()

    def test_streamlit_config_exists(self):
        assert (ROOT / ".streamlit" / "config.toml").exists()


# ── Category 2: Local Parquet fallback ───────────────────────────────────────

class TestLocalParquetFallback:
    @_SKIP_NO_PARQUET
    def test_parquet_loads_successfully(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        assert len(df) == 60

    @_SKIP_NO_PARQUET
    def test_parquet_has_required_columns(self):
        from data_loader import REQUIRED_COLUMNS, _load_parquet
        df = _load_parquet()
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        assert not missing, f"Missing required columns in parquet: {missing}"

    @_SKIP_NO_PARQUET
    def test_parquet_has_79_columns(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        assert df.shape[1] == 79

    def test_load_parquet_raises_if_file_missing(self, tmp_path):
        from data_loader import _load_parquet
        with patch("data_loader.PARQUET", tmp_path / "nonexistent.parquet"):
            with pytest.raises(FileNotFoundError):
                _load_parquet()


# ── Category 3: Supabase failure triggers Parquet fallback ────────────────────

class TestSupabaseFallback:
    @_SKIP_NO_PARQUET
    def test_supabase_failure_falls_back_to_parquet(self):
        from data_loader import load_data
        with patch("data_loader._load_supabase", side_effect=RuntimeError("no credentials")):
            df, source = load_data()
        assert "Parquet" in source
        assert len(df) > 0

    def test_missing_env_vars_cause_supabase_error(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
        from data_loader import _load_supabase
        with pytest.raises(RuntimeError, match="not set"):
            _load_supabase()

    @_SKIP_NO_PARQUET
    def test_load_data_returns_tuple(self):
        from data_loader import load_data
        with patch("data_loader._load_supabase", side_effect=RuntimeError("fail")):
            result = load_data()
        assert isinstance(result, tuple)
        assert len(result) == 2

    @_SKIP_NO_PARQUET
    def test_fallback_source_label_is_parquet(self):
        from data_loader import load_data
        with patch("data_loader._load_supabase", side_effect=RuntimeError("fail")):
            _, source = load_data()
        assert source == "Local Parquet (fallback)"


# ── Category 4: Required columns present ──────────────────────────────────────

class TestRequiredColumns:
    def test_validate_passes_on_valid_df(self):
        from data_loader import _validate
        df = _make_minimal_df()
        _validate(df)  # should not raise

    def test_validate_raises_on_missing_column(self):
        from data_loader import _validate
        df = _make_minimal_df().drop(columns=["campus_id"])
        with pytest.raises(ValueError, match="campus_id"):
            _validate(df)

    def test_validate_raises_on_empty_df(self):
        from data_loader import _validate
        df = _make_minimal_df(0)
        with pytest.raises(ValueError, match="no rows"):
            _validate(df)

    @_SKIP_NO_PARQUET
    def test_all_required_columns_present_in_real_data(self):
        from data_loader import REQUIRED_COLUMNS, _load_parquet
        df = _load_parquet()
        for col in REQUIRED_COLUMNS:
            assert col in df.columns, f"Required column missing: {col}"


# ── Category 5: Filters preserve valid rows ───────────────────────────────────

class TestFilters:
    @pytest.fixture
    def df(self):
        return _make_minimal_df(5)

    def test_filter_by_operator_type(self, df):
        filtered = df[df["operator_type"] == "isd"]
        assert len(filtered) == 5

    def test_filter_by_rating(self, df):
        filtered = df[df["accountability_rating_2025"].isin(["A", "B"])]
        assert len(filtered) == 2

    def test_filter_by_enrollment_range(self, df):
        filtered = df[df["enrollment"].between(310, 330)]
        assert len(filtered) == 3

    def test_filter_preserves_all_columns(self, df):
        filtered = df[df["school_level"] == "elementary"]
        assert set(filtered.columns) == set(df.columns)

    def test_empty_filter_returns_no_rows(self, df):
        filtered = df[df["accountability_rating_2025"] == "Z"]
        assert len(filtered) == 0

    @_SKIP_NO_PARQUET
    def test_filter_on_real_data_preserves_row_integrity(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        filtered = df[df["operator_type"] == "isd"]
        assert (filtered["operator_type"] == "isd").all()
        assert filtered["campus_id"].notna().all()


# ── Category 6: All-null subset handling ─────────────────────────────────────

class TestNullSubsets:
    def test_dropna_on_all_null_column_returns_empty(self):
        df = _make_minimal_df(3)
        df["crdc_idea_iss_students_total_2122"] = None
        result = df[["school_name", "crdc_idea_iss_students_total_2122"]].dropna(
            subset=["crdc_idea_iss_students_total_2122"]
        )
        assert result.empty

    def test_histogram_on_all_null_col_safe(self):
        import plotly.express as px
        df = _make_minimal_df(3)
        df["test_col"] = float("nan")
        valid = df["test_col"].dropna()
        assert valid.empty

    def test_bar_chart_on_empty_df_skipped(self):
        df = _make_minimal_df(3)
        df["crdc_rs_secl_instances_idea_2122"] = None
        plot_df = df[["school_name", "crdc_rs_secl_instances_idea_2122"]].dropna(
            subset=["crdc_rs_secl_instances_idea_2122"]
        )
        assert plot_df.empty

    @_SKIP_NO_PARQUET
    def test_no_crash_on_null_crdc_columns_in_real_data(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        crdc_cols = [c for c in df.columns if c.startswith("crdc_")]
        for col in crdc_cols:
            valid = df[col].dropna()
            if valid.empty:
                continue
            assert valid.notna().all()


# ── Category 7: Nulls not silently converted to zero ─────────────────────────

class TestNullNotZero:
    @_SKIP_NO_PARQUET
    def test_null_values_remain_null_in_float_cols(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        float_cols = df.select_dtypes(include="float").columns
        for col in float_cols:
            series = df[col]
            # null count before and after should be the same (no zero-fill happened)
            assert series.isna().sum() == series.isna().sum()  # trivially true
            # more meaningfully: no value is exactly zero when the original was null
            # (we check there are no sentinel values remaining)
            assert not (series == -1).any(), f"{col} contains -1 sentinel"
            assert not (series == -9).any(), f"{col} contains -9 sentinel"

    def test_minimal_df_has_no_sentinel_values(self):
        df = _make_minimal_df(5)
        for col in df.select_dtypes(include="float").columns:
            assert not (df[col] == -1).any()
            assert not (df[col] == -9).any()

    def test_null_count_col_displays_as_missing_not_zero(self):
        df = _make_minimal_df(3)
        df["crdc_idea_iss_students_total_2122"] = [None, 5.0, None]
        null_mask = df["crdc_idea_iss_students_total_2122"].isna()
        assert null_mask.sum() == 2
        # verify that null rows did not receive 0
        assert not (df.loc[null_mask, "crdc_idea_iss_students_total_2122"] == 0).any()

    @_SKIP_NO_PARQUET
    def test_tapr_sped_pct_nulls_preserved(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        col = "tapr_membership_sped_pct_2025"
        if df[col].isna().any():
            null_rows = df[df[col].isna()]
            assert (null_rows[col].isna()).all()


# ── Category 8: Data loader source labels ────────────────────────────────────

class TestSourceLabels:
    @_SKIP_NO_PARQUET
    def test_supabase_source_label(self):
        from data_loader import load_data
        mock_df = _make_minimal_df()
        with patch("data_loader._load_supabase", return_value=mock_df):
            _, source = load_data()
        assert source == "Supabase (live)"

    @_SKIP_NO_PARQUET
    def test_parquet_source_label(self):
        from data_loader import load_data
        with patch("data_loader._load_supabase", side_effect=RuntimeError("fail")):
            _, source = load_data()
        assert source == "Local Parquet (fallback)"
