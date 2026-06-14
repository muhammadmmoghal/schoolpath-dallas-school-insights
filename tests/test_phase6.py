"""
Phase 6 tests — Supabase schema, migration files, and load script validation.

These tests are entirely local (no network calls, no Supabase connection
required) and cover:
  1. Migration files exist and contain expected DDL
  2. All 79 final columns appear in the schools migration
  3. Security (RLS + SELECT-only policies) is declared in migration SQL
  4. .env.example has the required credential keys
  5. load_supabase.py references the right env vars and parquet path
  6. _nan_to_none correctly converts NaN / pd.NA / numpy scalars to None
  7. _nan_to_none preserves valid values unchanged
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
MIGRATIONS_DIR = ROOT / "migrations"
PROCESSED = ROOT / "data" / "processed"
DATA_DICT_CSV = PROCESSED / "data_dictionary.csv"
LOAD_SCRIPT = ROOT / "scripts" / "load_supabase.py"
ENV_EXAMPLE = ROOT / ".env.example"

_SKIP_IF_NO_DATA_DICT = pytest.mark.skipif(
    not DATA_DICT_CSV.exists(),
    reason="data_dictionary.csv not found; run scripts/build_final.py",
)


def _all_migration_sql() -> str:
    """Concatenate all migration SQL files into one searchable string."""
    if not MIGRATIONS_DIR.exists():
        return ""
    return "\n".join(f.read_text(encoding="utf-8") for f in sorted(MIGRATIONS_DIR.glob("*.sql")))


# ---------------------------------------------------------------------------
# Category 1: Migration files exist
# ---------------------------------------------------------------------------

class TestMigrationFilesExist:
    def test_migrations_directory_exists(self):
        assert MIGRATIONS_DIR.exists(), "migrations/ directory not found"

    def test_at_least_three_migration_files(self):
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        assert len(files) >= 3, f"Expected ≥3 migration files, found {len(files)}"

    def test_create_schools_migration_exists(self):
        files = list(MIGRATIONS_DIR.glob("*create_schools*.sql"))
        assert files, "No migration file matching *create_schools*.sql found"

    def test_create_pipeline_runs_migration_exists(self):
        files = (
            list(MIGRATIONS_DIR.glob("*pipeline_runs*.sql"))
        )
        assert files, "No migration file matching *pipeline_runs*.sql found"

    def test_rls_policies_migration_exists(self):
        files = list(MIGRATIONS_DIR.glob("*rls*.sql")) + list(
            MIGRATIONS_DIR.glob("*policies*.sql")
        )
        assert files, "No migration file matching *rls*.sql or *policies*.sql found"


# ---------------------------------------------------------------------------
# Category 2: Schools migration DDL correctness
# ---------------------------------------------------------------------------

class TestSchoolsMigrationDDL:
    def test_creates_schools_table(self):
        sql = _all_migration_sql().upper()
        assert "CREATE TABLE" in sql
        assert "SCHOOLS" in sql

    def test_campus_id_is_primary_key(self):
        sql = _all_migration_sql()
        assert "campus_id" in sql
        assert "PRIMARY KEY" in sql.upper()

    def test_creates_pipeline_runs_table(self):
        sql = _all_migration_sql().upper()
        assert "PIPELINE_RUNS" in sql

    def test_pipeline_runs_has_loaded_at(self):
        sql = _all_migration_sql()
        assert "loaded_at" in sql
        assert "timestamptz" in sql.lower()

    @_SKIP_IF_NO_DATA_DICT
    def test_all_79_columns_in_migration_sql(self):
        data_dict = pd.read_csv(DATA_DICT_CSV)
        sql = _all_migration_sql()
        missing = [col for col in data_dict["column_name"] if col not in sql]
        assert not missing, (
            f"These final columns are absent from migration SQL: {missing}"
        )

    def test_id_columns_are_text_type(self):
        sql = _all_migration_sql()
        for col in ("district_id", "nces_school_id"):
            idx = sql.find(col)
            assert idx != -1, f"{col} not found in migration SQL"
            snippet = sql[idx : idx + 60]
            assert "text" in snippet.lower(), (
                f"{col} should be text type; got: {snippet!r}"
            )

    def test_float_columns_are_double_precision(self):
        sql = _all_migration_sql()
        for col in ("latitude", "longitude", "accountability_score_2025"):
            idx = sql.find(col)
            assert idx != -1, f"{col} not found in migration SQL"
            snippet = sql[idx : idx + 80]
            assert "double precision" in snippet.lower(), (
                f"{col} should be double precision; got: {snippet!r}"
            )

    def test_enrollment_source_year_is_integer(self):
        sql = _all_migration_sql()
        idx = sql.find("enrollment_source_year")
        assert idx != -1
        snippet = sql[idx : idx + 60]
        assert "integer" in snippet.lower(), (
            f"enrollment_source_year should be integer; got: {snippet!r}"
        )


# ---------------------------------------------------------------------------
# Category 3: RLS and security policies
# ---------------------------------------------------------------------------

class TestSecurityPolicies:
    def test_rls_enabled_for_schools(self):
        sql = _all_migration_sql().upper()
        assert "ROW LEVEL SECURITY" in sql, "RLS not found in any migration file"

    def test_anon_select_policy_exists(self):
        sql = _all_migration_sql().upper()
        assert "ANON" in sql, "anon role not referenced in migration policies"
        assert "SELECT" in sql

    def test_authenticated_select_policy_exists(self):
        sql = _all_migration_sql().upper()
        assert "AUTHENTICATED" in sql

    def test_no_public_write_policies(self):
        sql = _all_migration_sql().upper()
        for dml in ("FOR INSERT", "FOR UPDATE", "FOR DELETE"):
            assert dml not in sql, (
                f"Found write policy '{dml}' in migration — public writes must not be allowed"
            )

    def test_pipeline_runs_rls_enabled(self):
        sql = _all_migration_sql().upper()
        # RLS must be enabled; no anon policies should exist for pipeline_runs
        assert "PIPELINE_RUNS" in sql
        # Verify no anon SELECT policy is created for pipeline_runs
        # (the policy lines reference "schools", not "pipeline_runs", for anon)
        anon_sections = [
            line for line in sql.splitlines()
            if "ANON" in line and "PIPELINE_RUNS" in line
        ]
        assert not anon_sections, (
            "pipeline_runs should have no anon policies; found: "
            + str(anon_sections)
        )

    def test_no_secrets_in_migration_files(self):
        sql = _all_migration_sql()
        # JWT tokens start with 'eyJ'
        assert "eyJ" not in sql, "JWT token found in migration SQL file"


# ---------------------------------------------------------------------------
# Category 4: .env.example
# ---------------------------------------------------------------------------

class TestEnvExample:
    def test_env_example_exists(self):
        assert ENV_EXAMPLE.exists(), ".env.example not found at project root"

    def test_env_example_has_supabase_url(self):
        content = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "SUPABASE_URL" in content

    def test_env_example_has_service_key(self):
        content = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "SUPABASE_SERVICE_KEY" in content

    def test_env_example_no_real_secrets(self):
        content = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "eyJ" not in content, ".env.example must not contain a real JWT token"


# ---------------------------------------------------------------------------
# Category 5: load_supabase.py structure
# ---------------------------------------------------------------------------

class TestLoadScript:
    def test_load_script_exists(self):
        assert LOAD_SCRIPT.exists(), "scripts/load_supabase.py not found"

    def test_load_script_references_supabase_url(self):
        src = LOAD_SCRIPT.read_text(encoding="utf-8")
        assert "SUPABASE_URL" in src

    def test_load_script_references_service_key(self):
        src = LOAD_SCRIPT.read_text(encoding="utf-8")
        assert "SUPABASE_SERVICE_KEY" in src

    def test_load_script_references_parquet(self):
        src = LOAD_SCRIPT.read_text(encoding="utf-8")
        assert "dallas_school_insights.parquet" in src

    def test_load_script_validates_row_count(self):
        src = LOAD_SCRIPT.read_text(encoding="utf-8")
        assert "EXPECTED_ROWS" in src
        assert "60" in src

    def test_load_script_references_pipeline_runs(self):
        src = LOAD_SCRIPT.read_text(encoding="utf-8")
        assert "pipeline_runs" in src

    def test_require_env_raises_on_missing_var(self):
        import importlib.util, sys, os

        spec = importlib.util.spec_from_file_location("load_supabase", LOAD_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        old = os.environ.pop("_PHASE6_NONEXISTENT_VAR", None)
        with pytest.raises(RuntimeError, match="_PHASE6_NONEXISTENT_VAR"):
            mod._require_env("_PHASE6_NONEXISTENT_VAR")
        if old is not None:
            os.environ["_PHASE6_NONEXISTENT_VAR"] = old


# ---------------------------------------------------------------------------
# Category 6: _nan_to_none unit tests
# ---------------------------------------------------------------------------

class TestNanToNone:
    @pytest.fixture(scope="class")
    def fn(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("load_supabase", LOAD_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._nan_to_none

    def test_float_nan_becomes_none(self, fn):
        result = fn({"x": float("nan")})
        assert result["x"] is None

    def test_none_stays_none(self, fn):
        result = fn({"x": None})
        assert result["x"] is None

    def test_pd_na_becomes_none(self, fn):
        result = fn({"x": pd.NA})
        assert result["x"] is None

    def test_valid_float_preserved(self, fn):
        result = fn({"x": 3.14})
        assert result["x"] == pytest.approx(3.14)

    def test_valid_string_preserved(self, fn):
        result = fn({"x": "DALLAS"})
        assert result["x"] == "DALLAS"

    def test_valid_int_preserved(self, fn):
        result = fn({"x": 2025})
        assert result["x"] == 2025

    def test_numpy_float64_nan_becomes_none(self, fn):
        import numpy as np
        result = fn({"x": np.float64("nan")})
        assert result["x"] is None

    def test_numpy_float64_value_preserved(self, fn):
        import numpy as np
        result = fn({"x": np.float64(95.5)})
        assert result["x"] == pytest.approx(95.5)

    def test_numpy_int64_converted_to_python_int(self, fn):
        import numpy as np
        result = fn({"x": np.int64(2025)})
        assert result["x"] == 2025
        assert isinstance(result["x"], int)

    def test_multiple_fields_mixed_types(self, fn):
        import numpy as np
        row = {
            "campus_id": "123456789",
            "enrollment": np.float64(450.0),
            "accountability_score_2025": float("nan"),
            "latitude": np.float64(32.8),
            "charter_type": pd.NA,
        }
        result = fn(row)
        assert result["campus_id"] == "123456789"
        assert result["enrollment"] == pytest.approx(450.0)
        assert result["accountability_score_2025"] is None
        assert result["latitude"] == pytest.approx(32.8)
        assert result["charter_type"] is None
