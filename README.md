# SchoolPath Dallas — School Data Engineering & Analytics

A reproducible Python data pipeline that combines five public education datasets
into a cleaned 60-school Dallas dataset and an interactive Streamlit dashboard.
Built to support special-education recruitment and school comparison.

- Builds a fully documented, re-runnable pipeline from raw public-agency downloads
- Combines TEA AskTED, TAPR, Accountability, ArcGIS, and CRDC into one joined dataset
- Produces a cleaned 60-school Dallas dataset (60 rows × 79 columns) with zero imputation
- Delivers an interactive Streamlit dashboard covering school characteristics, special education, attendance, culture, and safety indicators

---

## Live Dashboard

**https://schoolpath-dallas.streamlit.app/**

Five pages: Overview · School Explorer · Special Education · Attendance & Culture · School Detail

---

## Deliverables

| File | Description |
|------|-------------|
| [`data/processed/dallas_school_insights.csv`](data/processed/dallas_school_insights.csv) | Final dataset — 60 rows × 79 columns |
| [`data/processed/data_dictionary.csv`](data/processed/data_dictionary.csv) | Column-by-column reference: display name, definition, source, year, coverage %, null/suppression notes, and caveats |
| [`data/processed/source_coverage_report.csv`](data/processed/source_coverage_report.csv) | Join match rate per source |
| [`data/processed/README_DATASET.md`](data/processed/README_DATASET.md) | Dataset-level README for non-technical recipients |
| [Live dashboard](https://schoolpath-dallas.streamlit.app/) | Interactive Streamlit app (Supabase-backed with Parquet fallback) |

---

## Data Sources

| Source | Year | What It Contributes | Join Key |
|--------|------|---------------------|----------|
| TEA AskTED | 2025 (Oct snapshot) | School identity, enrollment, address, grade range, magnet flag | `campus_id` (9-digit TEA ID) |
| TEA TAPR | 2024–25 | SpEd membership/enrollment counts & %, attendance rates, chronic absence rates, teacher experience distribution | `campus_id` |
| TEA Campus Accountability Summary | 2025 | Letter rating (A–F), numeric score, grade configuration | `campus_id` |
| CRDC (Civil Rights Data Collection) | 2021–22 | IDEA discipline (ISS, OOS, expulsion), restraint/seclusion, disability harassment, law enforcement referrals, campus safety offenses | `nces_school_id` = CRDC `COMBOKEY` |
| TEA ArcGIS Schools Layer | 2024–25 | Latitude/longitude for mapping | `campus_id` |

**Match rates:** AskTED 100% · TAPR 100% · Accountability 100% · ArcGIS 100% · CRDC 96.7% (58 of 60)

---

## Pipeline Phases

| Phase | Scripts | Output |
|-------|---------|--------|
| 1 — AskTED Roster | `ingest_askted.py` · `build_cohort.py` | 60-school Dallas cohort with identity and enrollment fields |
| 2 — TAPR | `ingest_tapr.py` · `build_tapr.py` | SpEd, attendance, and staff metrics joined |
| 3 — CRDC | `ingest_crdc.py` · `build_crdc.py` | Federal disability discipline and safety data joined |
| 4 — Accountability & Coordinates | `ingest_accountability.py` · `ingest_arcgis.py` · `build_enriched.py` | Rating (A–F), numeric score, lat/lon joined |
| 5 — Final Cleanup | `build_final.py` | 151 → 79 columns; 12 embedded quality checks; CSV/Parquet export |
| 6 — Supabase Load | `load_supabase.py` | 60 rows upserted to `public.schools`; RLS SELECT-only policies |
| 7 — Dashboard | `dashboard/app.py` | Streamlit 5-page app; Supabase → Parquet fallback |
| 8 — Polish | — | Friendly column labels, KPI cards, st.navigation(), source badge |

### Cohort selection

Schools are selected from AskTED using the following sequential filters:

| Step | Rule |
|------|------|
| 1 | Physical city = DALLAS |
| 2 | Status = Active |
| 3 | District type ∈ {INDEPENDENT, CHARTER} — private schools excluded |
| 4 | Instruction type excludes DAEP and JJAEP |
| 5 | IDEA enrollment > 0 (TAPR 2025) |
| 6 | Deterministic stratified cap to 60, proportional by school level × charter/ISD (`random_state=42`) |

---

## Null and Suppression Handling

| Source | Sentinel / Rule | Pipeline action |
|--------|-----------------|-----------------|
| AskTED | Enrollment = −1 (not reported) | → `null` |
| TAPR | −1 (small denominator), −2 (invalid), −3 (complementary suppression), blank | → `null` |
| CRDC | −9 (not applicable / not reported) | → `null` |
| CRDC | 0 (zero events reported) | Preserved as `0.0` — real zero, not suppressed |

**Nulls are never replaced with zero, a district mean, or any other imputation.** The `data_dictionary.csv` `null_suppression_notes` column documents the exact rule for each field.

---

## Testing and Validation

```bash
pytest tests/
```

**378 tests pass** across eight test modules:

| Module | Tests | What it covers |
|--------|------:|----------------|
| `test_phase1.py` | 25 | AskTED ingestion, cohort exclusion funnel, output schema |
| `test_phase2.py` | 36 | TAPR join coverage, suppression code handling, field values |
| `test_phase3.py` | 57 | CRDC join, −9 sentinel conversion, zero preservation |
| `test_phase4.py` | 74 | Accountability join, ArcGIS coordinate range checks |
| `test_phase5.py` | 61 | Final column set, 12 data quality checks, data dictionary schema |
| `test_phase6.py` | 40 | Migration DDL correctness, RLS policies, Supabase loader logic |
| `test_phase7.py` | 36 | Dashboard loading, Parquet fallback, null handling in filters |
| `test_phase8.py` | 49 | KPI calculations, display column lists, attendance thresholds |

The 12 embedded quality checks (run inside `build_final.py`) assert:

- Exactly 60 rows; no duplicate campus IDs or NCES IDs
- Required identity fields fully populated
- All percentage columns in [0, 100]; all counts non-negative
- No suppression sentinels (−1/−2/−3/−9) remaining in output
- Accountability ratings only A/B/C/D/F/"Not Rated" or null
- Coordinates within the Dallas bounding box [32.5–33.2 lat, −97.2–−96.4 lon]
- CRDC column coverage ≥ 90%

---

## Local Setup

### Install

```bash
pip install -r requirements.txt   # Python 3.11+
```

### Rebuild the pipeline (raw source files already present)

```bash
python scripts/build_cohort.py
python scripts/build_tapr.py
python scripts/build_crdc.py
python scripts/build_enriched.py
python scripts/build_final.py
pytest tests/
```

### Re-download all raw sources (requires internet; CRDC is ~832 MB)

```bash
python scripts/ingest_askted.py
python scripts/ingest_tapr.py
python scripts/ingest_crdc.py
python scripts/ingest_accountability.py
python scripts/ingest_arcgis.py
```

Add `--force` to any ingest script to re-download even if the file already exists.

### Load to Supabase

Copy `.env.example` to `.env` and fill in your credentials, then:

```bash
python scripts/load_supabase.py
```

### Run the dashboard locally

```bash
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

Set optional environment variables to enable live Supabase reads:

```bash
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
```

Without these, the dashboard falls back to `data/processed/dallas_school_insights.parquet` automatically. A sidebar badge indicates which source is active.

---

## Repository Structure

```
.
├── data/
│   ├── raw/                            # Downloaded source files (git-ignored)
│   │   └── *_metadata.json             # Provenance records (URL, SHA-256, row count; committed)
│   └── processed/
│       ├── dallas_school_insights.csv      # Final dataset (60 × 79)
│       ├── dallas_school_insights.parquet  # Typed nullable numerics
│       ├── data_dictionary.csv             # Column reference
│       ├── source_coverage_report.csv      # Join match rates
│       └── README_DATASET.md               # Dataset README for non-technical recipients
├── dashboard/
│   ├── app.py                          # Entry point (st.navigation)
│   ├── data_loader.py                  # Supabase → Parquet fallback loader
│   ├── components.py                   # Reusable Plotly / Streamlit helpers
│   └── pages/
│       ├── 00_overview.py              # KPI summary cards
│       ├── 01_school_explorer.py       # Map + filterable table
│       ├── 02_special_education.py     # SpEd metrics and CRDC discipline
│       ├── 03_culture_safety.py        # Attendance, chronic absence, safety offenses
│       └── 04_school_detail.py         # All fields for a single school
├── migrations/                         # Supabase DDL (schema + RLS)
├── scripts/
│   ├── ingest_askted.py
│   ├── ingest_tapr.py
│   ├── ingest_crdc.py
│   ├── ingest_accountability.py
│   ├── ingest_arcgis.py
│   ├── build_cohort.py
│   ├── build_tapr.py
│   ├── build_crdc.py
│   ├── build_enriched.py
│   ├── build_final.py
│   └── load_supabase.py
├── tests/
│   └── test_phase1.py … test_phase8.py  # 378 tests total
├── research/                           # Source links and field notes
├── requirements.txt
└── .env.example
```

---

## Known Limitations

1. **CRDC data year lag.** Civil-rights discipline and safety data are from 2021–22 — three years before the accountability and attendance data (2024–25). Use CRDC metrics as structural indicators, not current-year snapshots. Do not compare CRDC counts directly with current TAPR rates.

2. **Two schools have no CRDC match.** `BIOMEDICAL PREPARATORY AT UT SOUTHWESTERN` (campus `057905371`) and `IDEA A W BROWN COLLEGE PREPARATORY` (campus `108807209`) did not match on NCES school ID. All CRDC columns are null for these two rows.

3. **No climate survey data.** Student/staff satisfaction scores and PEARS incident reports were not available for this cohort. The Culture & Safety dashboard page uses attendance, chronic absence, and discipline counts as proxy indicators only.

4. **Attendance columns reflect 2023–24.** `tapr_att_*_2024` and `tapr_chronic_abs_*_2024` are distributed in the 2024–25 TAPR release but measure the 2023–24 school year. Column names embed the measure year to avoid confusion.

5. **"Not Rated" is not missing data.** TEA assigns "Not Rated" to new schools and certain exempt campuses. A null accountability rating means the campus was absent from the 2025 accountability file entirely.

6. **ArcGIS coordinates are approximate.** Lat/lon values come from a 2024–25 geocoder snapshot derived from AskTED addresses. Suitable for display mapping; not survey-grade.

7. **No imputation.** Missing values are never filled with district averages, state medians, or model predictions. All nulls are genuine absences of reported data.

---

*Source data are public records from the Texas Education Agency (TEA) and the U.S. Department of Education.*
