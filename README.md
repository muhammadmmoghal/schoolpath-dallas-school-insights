# SchoolPath Dallas Data Pipeline

A reproducible, source-verified dataset comparing Dallas public schools across
special-education support, culture, and safety dimensions.

**Approved sources (all phases)**
| Source | Purpose | Join key |
|---|---|---|
| AskTED site-address download | Canonical school roster | TEA campus ID (9 digits) |
| TEA TAPR 2024-25 | Student demographics, attendance, staff | TEA campus ID |
| TEA 2025 accountability | Rating context | TEA campus ID |
| CRDC 2021-22 | Historical civil-rights / discipline | NCES school ID → COMBOKEY |
| ArcGIS school layer | Coordinates only | TEA campus ID |

**Excluded fields** (not verified in source data): LRE/inclusion %, DAEP rate,
teacher turnover, teacher certification %, public climate score, PEARS incidents.

---

## Phase 1 — AskTED Roster and Dallas Cohort

Phase 1 fetches the AskTED site-address roster, applies a documented exclusion
funnel, and exports a deterministic 40–80 school cohort for Dallas.

### Prerequisites

- Python 3.11+
- Internet access (one-time fetch from TEA)

```
pip install -r requirements.txt
```

### Running Phase 1

**Step 1 — download the raw roster**

```
python scripts/ingest_askted.py
```

Saves:
- `data/raw/askted_directory.csv` — full statewide AskTED file (not committed; see .gitignore)
- `data/raw/askted_fetch_metadata.json` — provenance record (SHA-256, timestamp, row count)

**Step 2 — build the Dallas cohort**

```
python scripts/build_cohort.py
```

Saves:
- `data/processed/cohort_ids.csv` — campus_id, district_id, nces_school_id, school_name
- `data/processed/cohort_preview.csv` — all normalized fields (school level, operator type, enrollment, …)
- `data/processed/cohort_funnel.json` — step-by-step exclusion counts and cohort breakdown

**Step 3 — run tests**

```
pytest tests/
```

Integration tests skip automatically if the output files are missing.

### Cohort rules

Applied in order:

| # | Rule |
|---|---|
| 1 | `School Site City == DALLAS` (physical address, not mailing) |
| 2 | `School Status == Active` |
| 3 | `District Type` in `{INDEPENDENT, CHARTER}` — excludes private / unknown |
| 4 | Instruction type does **not** contain `DAEP`, `JJAEP`, `JUVENILE JUSTICE`, or `DISCIPLINARY ALTERNATIVE` |
| 5 | Enrollment is not null (AskTED sentinel `-1` converted to null) |
| 6 | Enrollment > 0 |
| 7 | De-duplicate on campus ID |
| 8 | If count > 60: deterministic stratified cap to 60 (proportional by school level × charter/ISD status; fixed-seed random sample within each stratum, `random_state=42`) |

### Output schema

**cohort_ids.csv**

| Column | Type | Notes |
|---|---|---|
| `campus_id` | string | 9-digit zero-padded TEA campus number |
| `district_id` | string | 6-digit zero-padded TEA district number |
| `nces_school_id` | string | 12-char NCES school ID (CRDC crosswalk) |
| `school_name` | string | |
| `district_name` | string | |

**cohort_preview.csv** — adds: `district_type`, `instruction_type`,
`charter_type`, `school_level`, `operator_type`, `grade_range`, `enrollment`,
`enrollment_source_year`, `school_status`, `school_site_city`,
`school_site_address`, `school_site_zip`, `magnet_status`.

**cohort_funnel.json** — JSON document listing every exclusion step with
before/after counts, the stratified cap allocation, and the final breakdown by
school level and charter/ISD status.

### Design decisions

- **Missing data stays null.** Unavailable or suppressed values are null, never
  zero or a district-level imputation.
- **No black-box ranking.** Each field traces to a specific source, year, and
  suppression rule.
- **Private schools excluded.** Only INDEPENDENT and CHARTER district types are
  included.
- **Source year exposed.** The enrollment column name embeds the collection year
  (e.g., "School Enrollment as of Oct 2025"); this year is also written to
  `cohort_preview.csv` as `enrollment_source_year`.

---

## Phases 2–4 (not yet implemented)

| Phase | Content |
|---|---|
| 2 | TAPR ingestion (student, attendance, staff) and left-join to cohort |
| 3 | Accountability summary and CRDC ingestion (via NCES crosswalk) |
| 4 | Supabase load (optional) and dashboard |
