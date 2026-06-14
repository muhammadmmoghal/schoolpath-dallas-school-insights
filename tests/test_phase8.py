"""
Phase 8 tests — recruiter-facing dashboard polish and analytical insights.

All tests are local (no network, no Supabase connection required).

Covers:
  1. New dashboard files exist
  2. Friendly source label mapping
  3. KPI calculations on real data
  4. Title-case labels (LEVEL_LABELS, OPERATOR_LABELS)
  5. fmt_value helper — zero distinct from null
  6. Explorer default table columns present in data
  7. Attendance threshold filter
  8. Attendance disparity column computable
  9. Schools above 20% SpEd inferable
  10. CRDC coverage count
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

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


# ── Category 1: Dashboard files exist ─────────────────────────────────────────

class TestPhase8FilesExist:
    def test_overview_page_exists(self):
        assert (DASHBOARD / "pages" / "00_overview.py").exists()

    def test_app_py_still_exists(self):
        assert (DASHBOARD / "app.py").exists()

    def test_all_original_page_files_still_exist(self):
        for fname in [
            "01_school_explorer.py",
            "02_special_education.py",
            "03_culture_safety.py",
            "04_school_detail.py",
        ]:
            assert (DASHBOARD / "pages" / fname).exists(), f"Missing: {fname}"

    def test_components_has_level_labels(self):
        from components import LEVEL_LABELS
        assert isinstance(LEVEL_LABELS, dict)
        assert len(LEVEL_LABELS) >= 4

    def test_components_has_operator_labels(self):
        from components import OPERATOR_LABELS
        assert isinstance(OPERATOR_LABELS, dict)
        assert len(OPERATOR_LABELS) >= 2

    def test_data_loader_has_friendly_source_labels(self):
        from data_loader import FRIENDLY_SOURCE_LABELS
        assert isinstance(FRIENDLY_SOURCE_LABELS, dict)


# ── Category 2: Friendly source labels ────────────────────────────────────────

class TestFriendlySourceLabels:
    def test_local_parquet_maps_to_friendly(self):
        from data_loader import FRIENDLY_SOURCE_LABELS
        assert FRIENDLY_SOURCE_LABELS["Local Parquet (fallback)"] == "Local processed dataset"

    def test_supabase_maps_to_friendly(self):
        from data_loader import FRIENDLY_SOURCE_LABELS
        assert FRIENDLY_SOURCE_LABELS["Supabase (live)"] == "Supabase database"

    def test_friendly_source_label_function_exists(self):
        from data_loader import friendly_source_label
        assert callable(friendly_source_label)

    def test_friendly_source_label_returns_string(self):
        from data_loader import friendly_source_label
        result = friendly_source_label("Local Parquet (fallback)")
        assert isinstance(result, str)
        assert result == "Local processed dataset"

    def test_friendly_label_fallback_for_unknown(self):
        from data_loader import friendly_source_label
        unknown = "Some Unknown Source"
        assert friendly_source_label(unknown) == unknown

    def test_internal_load_data_labels_unchanged(self):
        """Phase 7 test compatibility: internal labels from load_data() are not changed."""
        from data_loader import load_data
        with patch("data_loader._load_supabase", side_effect=RuntimeError("fail")):
            _, src = load_data()
        assert src == "Local Parquet (fallback)"


# ── Category 3: Title-case labels ─────────────────────────────────────────────

class TestTitleCaseLabels:
    def test_all_level_labels_start_uppercase(self):
        from components import LEVEL_LABELS
        for raw, display in LEVEL_LABELS.items():
            assert display[0].isupper(), f"Level label {display!r} should start with uppercase"

    def test_all_operator_labels_start_uppercase(self):
        from components import OPERATOR_LABELS
        for raw, display in OPERATOR_LABELS.items():
            assert display[0].isupper(), f"Operator label {display!r} should start with uppercase"

    def test_isd_label(self):
        from components import OPERATOR_LABELS
        assert OPERATOR_LABELS.get("isd") == "Independent School District"

    def test_charter_label(self):
        from components import OPERATOR_LABELS
        assert OPERATOR_LABELS.get("charter") == "Charter School"

    def test_elementary_label(self):
        from components import LEVEL_LABELS
        assert LEVEL_LABELS.get("elementary") == "Elementary"

    def test_middle_label(self):
        from components import LEVEL_LABELS
        assert LEVEL_LABELS.get("middle") == "Middle"

    def test_high_label(self):
        from components import LEVEL_LABELS
        assert LEVEL_LABELS.get("high") == "High School"

    def test_mixed_label(self):
        from components import LEVEL_LABELS
        assert LEVEL_LABELS.get("mixed") == "Multi-Level"

    def test_no_raw_snake_case_in_operator_labels(self):
        from components import OPERATOR_LABELS
        for display_label in OPERATOR_LABELS.values():
            assert "_" not in display_label, f"Label {display_label!r} contains underscore"

    def test_no_raw_snake_case_in_level_labels(self):
        from components import LEVEL_LABELS
        for display_label in LEVEL_LABELS.values():
            assert "_" not in display_label, f"Label {display_label!r} contains underscore"


# ── Category 4: fmt_value helper ──────────────────────────────────────────────

class TestFmtValue:
    def test_none_returns_dash(self):
        from components import fmt_value
        assert fmt_value(None) == "—"

    def test_nan_returns_dash(self):
        from components import fmt_value
        import math
        assert fmt_value(float("nan")) == "—"

    def test_zero_returns_zero_not_dash(self):
        from components import fmt_value
        assert fmt_value(0) != "—"
        assert fmt_value(0.0) != "—"

    def test_zero_explicitly_preserved(self):
        from components import fmt_value
        assert "0" in fmt_value(0)

    def test_pct_format(self):
        from components import fmt_value
        assert fmt_value(12.5, "pct") == "12.5%"

    def test_count_format(self):
        from components import fmt_value
        assert fmt_value(1234, "count") == "1,234"

    def test_float1_format(self):
        from components import fmt_value
        assert fmt_value(7.3456, "float1") == "7.3"

    def test_pandas_na_returns_dash(self):
        from components import fmt_value
        assert fmt_value(pd.NA) == "—"

    def test_zero_different_from_null(self):
        from components import fmt_value
        assert fmt_value(0.0) != fmt_value(None)


# ── Category 5: KPI calculations on real data ─────────────────────────────────

class TestKPICalculations:
    @_SKIP_NO_PARQUET
    def test_total_schools_is_60(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        assert len(df) == 60

    @_SKIP_NO_PARQUET
    def test_median_enrollment_positive(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        assert df["enrollment"].median() > 0

    @_SKIP_NO_PARQUET
    def test_ab_percentage_in_range(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        n_ab = int(df["accountability_rating_2025"].isin(["A", "B"]).sum())
        pct = n_ab / len(df) * 100
        assert 0 <= pct <= 100

    @_SKIP_NO_PARQUET
    def test_median_sped_pct_positive(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        med = df["tapr_membership_sped_pct_2025"].median()
        assert pd.notna(med) and med > 0

    @_SKIP_NO_PARQUET
    def test_median_attendance_in_realistic_range(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        med = df["tapr_att_all_rate_2024"].median()
        assert pd.notna(med) and 80 <= med <= 100

    @_SKIP_NO_PARQUET
    def test_schools_above_20pct_sped_in_range(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        n = int((df["tapr_membership_sped_pct_2025"] > 20).sum())
        assert 0 <= n <= 60

    @_SKIP_NO_PARQUET
    def test_crdc_coverage_at_least_58(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        n_crdc = int(df["crdc_idea_enr_total_2122"].notna().sum())
        assert n_crdc >= 58

    @_SKIP_NO_PARQUET
    def test_isd_charter_split_sums_to_60(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        n_isd = int((df["operator_type"] == "isd").sum())
        n_charter = int((df["operator_type"] == "charter").sum())
        assert n_isd + n_charter == 60


# ── Category 6: Explorer default table columns present ────────────────────────

class TestExplorerDefaultColumns:
    DEFAULT_TABLE_COLS = [
        "school_name",
        "district_name",
        "school_level",
        "operator_type",
        "enrollment",
        "accountability_rating_2025",
        "accountability_score_2025",
        "tapr_membership_sped_pct_2025",
        "tapr_att_all_rate_2024",
        "tapr_chronic_abs_all_rate_2024",
    ]

    @_SKIP_NO_PARQUET
    def test_all_default_columns_in_dataset(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        for col in self.DEFAULT_TABLE_COLS:
            assert col in df.columns, f"Default table column missing from data: {col}"

    def test_default_column_count(self):
        assert len(self.DEFAULT_TABLE_COLS) == 10


# ── Category 7: Attendance threshold filter ────────────────────────────────────

class TestAttendanceThreshold:
    @_SKIP_NO_PARQUET
    def test_schools_below_95pct_count_valid(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        n = int((df["tapr_att_all_rate_2024"] < 95).sum())
        assert 0 <= n <= 60

    @_SKIP_NO_PARQUET
    def test_threshold_filter_is_monotone(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        att = df["tapr_att_all_rate_2024"]
        n_below_95 = int((att < 95).sum())
        n_below_90 = int((att < 90).sum())
        assert n_below_90 <= n_below_95

    @_SKIP_NO_PARQUET
    def test_threshold_result_does_not_include_nulls_as_above(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        att = df["tapr_att_all_rate_2024"]
        n_below = int((att < 95).sum())
        n_null = int(att.isna().sum())
        # nulls should not be counted as above threshold (pandas < comparison returns False for NaN)
        assert n_below + n_null <= 60


# ── Category 8: Attendance disparity ──────────────────────────────────────────

class TestAttendanceDisparity:
    @_SKIP_NO_PARQUET
    def test_disparity_can_be_computed(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        gap = df["tapr_att_all_rate_2024"] - df["tapr_att_sped_rate_2024"]
        assert gap.dropna().shape[0] > 0

    @_SKIP_NO_PARQUET
    def test_disparity_values_are_numeric(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        gap = (df["tapr_att_all_rate_2024"] - df["tapr_att_sped_rate_2024"]).dropna()
        assert gap.dtype.kind == "f"

    @_SKIP_NO_PARQUET
    def test_disparity_median_plausible(self):
        from data_loader import _load_parquet
        df = _load_parquet()
        gap = (df["tapr_att_all_rate_2024"] - df["tapr_att_sped_rate_2024"]).dropna()
        med = gap.median()
        assert -10 <= med <= 10  # gap should be within ±10 percentage points


# ── Category 9: Source badge compatibility ─────────────────────────────────────

class TestSourceBadgeCompatibility:
    def test_source_badge_function_exists(self):
        from components import source_badge
        assert callable(source_badge)

    def test_friendly_label_function_in_data_loader(self):
        from data_loader import friendly_source_label
        assert friendly_source_label("Supabase (live)") == "Supabase database"
        assert friendly_source_label("Local Parquet (fallback)") == "Local processed dataset"
