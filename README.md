# SchoolPath Dallas Data Pipeline

A reproducible, source-verified dataset comparing Dallas public schools across
special-education support, culture, and safety dimensions.

## Final Dataset — `data/processed/dallas_school_insights.csv`

**60 rows x 79 columns** — one row per Dallas public school.

| Dimension | Detail |
|---|---|
| Row count | 60 schools |
| Column count | 79 |
| Source coverage | AskTED 100%, TAPR 100%, Accountability 100%, ArcGIS 100%, CRDC 96.7% (58/60) |
| CRDC data year | 2021-22 (historical) |
| Accountability year | 2025 |
| TAPR year | 2025 (attendance measures are 2024) |
| Quality checks | 12/12 pass (see `data/processed/data_quality_report.json`) |

**Rebuild the entire pipeline from existing raw files**

```
python scripts/build_cohort.py
python scripts/build_tapr.py
python scripts/build_crdc.py
python scripts/build_enriched.py
python scripts/build_final.py
pytest tests/
```

To re-download all raw sources first (requires internet):

```
python scripts/ingest_askted.py
python scripts/ingest_tapr.py
python scripts/ingest_crdc.py
python scripts/ingest_accountability.py
python scripts/ingest_arcgis.py
```

**Key caveats**

- Null values mean "not reported / suppressed / not applicable". They are never
  treated as zero.
- CRDC discipline and enrollment data are from 2021-22 and should not be compared
  directly with current-year TAPR rates.
- Accountability "Not Rated" is a real TEA designation, not missing data.
- ArcGIS coordinates are geocoder output for display only.
- 2 of 60 schools (NCES IDs 481623022813 and 480021123204) have no CRDC match;
  all CRDC columns are null for those two rows.
- `acct_alt_ed_type_2025` was dropped (all-null for the cohort). See
  `data/processed/data_dictionary.csv` for the full drop log.

---

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

---

## Phase 2 — TAPR Ingestion and Cohort Join

Phase 2 downloads three 2024-25 TAPR campus-level files from the TEA SAS
broker, normalizes suppression codes, and left-joins all measures to the
60-school cohort.

### Prerequisites

Python 3.11+ and the packages in `requirements.txt` (includes `pyarrow` for
Parquet output):

```
pip install -r requirements.txt
```

### Running Phase 2

**Step 1 — download raw TAPR files**

```
python scripts/ingest_tapr.py
```

Saves to `data/raw/` (CSV files are git-ignored; metadata JSON files are committed):
- `tapr_student_2025.csv` + `tapr_student_2025_metadata.json`
- `tapr_attendance_2025.csv` + `tapr_attendance_2025_metadata.json`
- `tapr_staff_2025.csv` + `tapr_staff_2025_metadata.json`

Re-run with `--force` to re-download. If the downloaded content is byte-for-byte
identical to the existing file (same SHA-256), the file is not rewritten.

**Step 2 — parse, normalize, and join**

```
python scripts/build_tapr.py
```

Saves:
- `data/processed/cohort_tapr.csv` — 60-row cohort with all TAPR fields
- `data/processed/cohort_tapr.parquet` — same, with typed nullable numerics
- `data/processed/tapr_join_report.json` — join coverage and suppression summary
- `data/processed/data_dictionary.json` — field definitions for all TAPR columns

**Step 3 — run tests**

```
pytest tests/
```

All 61 Phase 1 + Phase 2 tests pass.

### TAPR source year

| File | Official filename | Source year | Measure year |
|---|---|---|---|
| Student information | `2025 Campus Student Information.csv` | 2025 | 2025 |
| Attendance and absenteeism | `2025 Campus Attendance Absenteeism Dropout.csv` | 2025 | **2024** |
| Staff information | `2025 Campus Staff Information.csv` | 2025 | 2025 |

The attendance and chronic-absence fields refer to the **2024** school year
even though they are distributed in the 2024-25 TAPR release. Column names
embed the measure year (e.g., `tapr_att_all_rate_2024`). The `tapr_source_year`
column records the TAPR release year (2025) for every row.

### Fields added by Phase 2

**Student (measure year 2025)**

| Output column | TAPR field | Description |
|---|---|---|
| `tapr_membership_all_count_2025` | `CPETALLC` | Membership count, all students |
| `tapr_membership_sped_count_2025` | `CPETSPEC` | Membership count, special education |
| `tapr_membership_sped_pct_2025` | `CPETSPEP` | Membership %, special education |
| `tapr_enrollment_all_count_2025` | `CPNTALLC` | Enrollment count, all students |
| `tapr_enrollment_sped_count_2025` | `CPNTSPEC` | Enrollment count, special education |
| `tapr_enrollment_sped_pct_2025` | `CPNTSPEP` | Enrollment %, special education |

**Attendance and chronic absenteeism (measure year 2024)**

| Output column | TAPR field | Description |
|---|---|---|
| `tapr_att_all_days_present_2024` | `CA0AT24N` | All-student days present |
| `tapr_att_all_days_membership_2024` | `CA0AT24D` | All-student days membership |
| `tapr_att_all_rate_2024` | `CA0AT24R` | All-student attendance rate (%) |
| `tapr_att_sped_days_present_2024` | `CS0AT24N` | Special-ed days present |
| `tapr_att_sped_days_membership_2024` | `CS0AT24D` | Special-ed days membership |
| `tapr_att_sped_rate_2024` | `CS0AT24R` | Special-ed attendance rate (%) |
| `tapr_chronic_abs_all_numerator_2024` | `CA0CA24N` | All-student chronic-absence numerator |
| `tapr_chronic_abs_all_denominator_2024` | `CA0CA24D` | All-student chronic-absence denominator |
| `tapr_chronic_abs_all_rate_2024` | `CA0CA24R` | All-student chronic-absence rate (%) |
| `tapr_chronic_abs_sped_numerator_2024` | `CS0CA24N` | Special-ed chronic-absence numerator |
| `tapr_chronic_abs_sped_denominator_2024` | `CS0CA24D` | Special-ed chronic-absence denominator |
| `tapr_chronic_abs_sped_rate_2024` | `CS0CA24R` | Special-ed chronic-absence rate (%) |

**Staff (measure year 2025)**

| Output column | TAPR field | Description |
|---|---|---|
| `tapr_avg_teacher_exp_years_2025` | `CPSTEXPA` | Average teacher years of experience |
| `tapr_avg_teacher_tenure_years_2025` | `CPSTTENA` | Average teacher years with this district |
| `tapr_beginning_teacher_fte_count_2025` | `CPST00FC` | Beginning teacher FTE count |
| `tapr_beginning_teacher_fte_pct_2025` | `CPST00FP` | Beginning teacher FTE % |
| `tapr_teacher_1to5yr_pct_2025` | `CPST01FP` | Teacher FTE % with 1–5 years experience |
| `tapr_teacher_6to10yr_pct_2025` | `CPST06FP` | Teacher FTE % with 6–10 years |
| `tapr_teacher_11to20yr_pct_2025` | `CPST11FP` | Teacher FTE % with 11–20 years |
| `tapr_teacher_21to30yr_pct_2025` | `CPST21FP` | Teacher FTE % with 21–30 years |
| `tapr_teacher_over30yr_pct_2025` | `CPST30FP` | Teacher FTE % with >30 years |

**Pipeline metadata columns**

| Column | Description |
|---|---|
| `tapr_source_year` | TAPR release year (2025 for all rows) |
| `tapr_matched` | True if campus appeared in the TAPR statewide files |
| `tapr_suppression_codes` | JSON: original TAPR field name → suppression code, for any suppressed value |

### Suppression and coverage limitations

TEA masking codes observed in the cohort:

| Code | Meaning | Cohort occurrences |
|---|---|---|
| `-1` | Small denominator (attendance < 900 days; chronic-absence denom 1–4) | 6 |
| `blank` | Unavailable / not applicable | 24 |

All sentinel codes and blank values are stored as **null** in the output.
The `tapr_suppression_codes` column records which fields were suppressed for
each campus and with which code.

**Excluded fields** (not present in the verified TAPR campus files):
teacher turnover, teacher certification %, LRE/inclusion %, DAEP rate,
ISS/OSS rates, expulsion rate, restraint rate, seclusion rate.

**Join coverage**: 60 of 60 cohort schools matched the TAPR statewide file
(100%). The 97% active-campus coverage figure from research refers to the
full 362-campus AskTED Dallas city roster; the cohort's 60 schools are
a subset of that.

---

## Phase 3 — CRDC 2021-22 Ingestion and Cohort Join

Phase 3 downloads the 2021-22 Civil Rights Data Collection (CRDC) national ZIP
archive, extracts the seven school-level CSV files this pipeline uses, and
left-joins disability-related discipline, enrollment, restraint, harassment,
referral, and offense counts to the 60-school cohort.

### Prerequisites

Python 3.11+ and the packages in `requirements.txt`.  
The CRDC archive is **~832 MB** and is downloaded once; extracted CSVs and the
ZIP are git-ignored (`data/raw/crdc_2021_22/`, `data/raw/*.zip`).

### Running Phase 3

**Step 1 — download and extract the CRDC archive**

```
python scripts/ingest_crdc.py
```

Streams the 832 MB ZIP to `data/raw/crdc_2021_22.zip`, then extracts seven CSV
members to `data/raw/crdc_2021_22/SCH/`. If all seven CSVs are already present
and the ZIP hash is unchanged, the step is skipped.

Re-download and re-extract: `python scripts/ingest_crdc.py --force`

Saves (committed):
- `data/raw/crdc_2021_22_zip_metadata.json` — ZIP provenance (URL, SHA-256, size, date)
- `data/raw/crdc_2021_22_members_metadata.json` — per-CSV column list, row count, SHA-256

**Step 2 — parse, normalize, and join**

```
python scripts/build_crdc.py
```

Reads the seven CRDC CSVs, filters to cohort NCES IDs (`COMBOKEY`), converts
the `-9` sentinel to null (preserving `0` as a real zero), merges all sources,
and left-joins to the TAPR-enriched cohort.

Saves:
- `data/processed/cohort_crdc.csv` — 60-row cohort with TAPR + CRDC fields
- `data/processed/cohort_crdc.parquet` — same, with typed nullable numerics
- `data/processed/crdc_join_report.json` — match coverage, sentinel totals, null counts
- `data/processed/data_dictionary.json` — CRDC entries appended to existing TAPR entries

**Step 3 — run tests**

```
pytest tests/
```

All 118 Phase 1 + Phase 2 + Phase 3 tests pass.

### CRDC source year

| File | Content | Measure year |
|---|---|---|
| `SCH/Enrollment.csv` | Total, IDEA, Section 504 enrollment by gender | 2021-22 |
| `SCH/Suspensions.csv` | ISS, OOS suspension counts and days missed | 2021-22 |
| `SCH/Expulsions.csv` | Expulsions with/without services, zero-tolerance | 2021-22 |
| `SCH/Restraint and Seclusion.csv` | Mechanical, physical, seclusion instances and students | 2021-22 |
| `SCH/Harassment and Bullying.csv` | Disability-based harassment allegations, reported, disciplined | 2021-22 |
| `SCH/Referrals and Arrests.csv` | Law enforcement referrals and school-related arrests | 2021-22 |
| `SCH/Offenses.csv` | Weapon/assault/robbery/homicide incidents and indicators | 2021-22 |

CRDC data are historical (2021-22 school year). Do not compare CRDC counts
directly with current-year TAPR rates.

### Fields added by Phase 3

All output column names follow the pattern `crdc_<measure>_<gender>_2122`
(raw counts) or `crdc_<measure>_total_2122` (M+F derived sums). Indicator
columns end in `_ind_2122` and hold `"Yes"`, `"No"`, or null.

**Enrollment**

| Output column | CRDC field | Description |
|---|---|---|
| `crdc_tot_enr_m_2122` / `_f_2122` / `_total_2122` | `TOT_ENR_M/F` | Total enrollment by gender / M+F total |
| `crdc_idea_enr_m_2122` / `_f_2122` / `_total_2122` | `SCH_ENR_IDEA_M/F` | IDEA enrollment |
| `crdc_504_enr_m_2122` / `_f_2122` / `_total_2122` | `SCH_ENR_504_M/F` | Section 504 enrollment |

**Suspensions**

| Output column | Description |
|---|---|
| `crdc_idea_iss_students_m/f/total_2122` | IDEA students receiving in-school suspension |
| `crdc_oos_instances_no_dis/idea/504_2122` | Out-of-school suspension instances by disability status |
| `crdc_idea_sing/mult_oos_m/f/total_2122` | IDEA students with single / multiple OOS suspensions |
| `crdc_idea_oos_days_missed_m/f_2122` | Days missed due to OOS suspension, IDEA students |

**Expulsions, Restraint, Harassment, Referrals, Offenses** — see
`data/processed/data_dictionary.json` for full field list.

**Pipeline metadata columns**

| Column | Description |
|---|---|
| `crdc_collection_year` | `"2021-22"` for every row |
| `crdc_matched` | `True` if NCES school ID matched a CRDC `COMBOKEY` |
| `crdc_suppression_codes` | JSON object: raw CRDC field name → `"-9"` for suppressed fields |

### Sentinel and suppression notes

| Code | CRDC meaning | Pipeline handling |
|---|---|---|
| `-9` | Not applicable / not reported | → `null`; recorded in `crdc_suppression_codes` |
| `0` | Real zero (no events) | Preserved as `0.0` |

CRDC 2021-22 does not apply data-quality suppression (no small-cell masking).
Raw district-reported zeros reflect actual reporting, not absence of events.

### Coverage

60 of 60 cohort schools returned by the left join; 58 of 60 matched the CRDC
file (96.7%). The 2 unmatched schools have null for all CRDC fields and
`crdc_matched = False`.

---

## Phase 4 — Accountability Ratings and Coordinates

Phase 4 joins two additional verified sources to the 60-school cohort:

1. **TEA 2025 campus accountability ratings** (letter grades A–F and "Not Rated")
2. **TEA ArcGIS Schools 2024-25** (geocoded latitude/longitude)

### Prerequisites

Python 3.11+ and the packages in `requirements.txt`. Internet access for
the one-time data fetch.

### Running Phase 4

**Step 1 — download raw sources**

```
python scripts/ingest_accountability.py
python scripts/ingest_arcgis.py
```

Saves to `data/raw/` (CSV and JSON files are git-ignored; `*_metadata.json`
files are committed):
- `accountability_2025.csv` + `accountability_2025_metadata.json`
- `arcgis_schools_raw.json` + `arcgis_schools_metadata.json`

Re-download with `--force`.

**Step 2 — join and build enriched cohort**

```
python scripts/build_enriched.py
```

Saves:
- `data/processed/cohort_enriched.csv`
- `data/processed/cohort_enriched.parquet`
- `data/processed/accountability_join_report.json`
- `data/processed/arcgis_join_report.json`
- `data/processed/data_dictionary.json` — Phase 4 entries appended

**Step 3 — run tests**

```
pytest tests/
```

All Phase 1–4 tests pass.

### Fields added by Phase 4

**Accountability (source: TEA 2025 Campus Accountability Summary)**

| Output column | Source field | Description |
|---|---|---|
| `accountability_rating_2025` | `C_RATING` | Overall rating: A / B / C / D / F / "Not Rated" |
| `accountability_status_2025` | derived | "Rated" (A–F) / "Not Rated" / null (unmatched) |
| `accountability_score_2025` | `CDALLS` | Numeric score (nullable float) |
| `acct_grade_type_2025` | `GRDTYPE` | Grade-configuration type code |
| `acct_grade_span_2025` | `GRDSPAN` | Grade span label |
| `acct_grade_low_2025` | `GRDLOW` | Lowest grade served |
| `acct_grade_high_2025` | `GRDHIGH` | Highest grade served |
| `acct_charter_flag_2025` | `CFLCHART` | Charter campus flag (Y/N) |
| `acct_alt_ed_flag_2025` | `CFLAEC` | Alternative education flag (Y/N) |
| `acct_alt_ed_type_2025` | `CFLAEATYPE` | Alt-ed type (if present in download) |
| `acct_daep_flag_2025` | `CFLDAEP` | DAEP flag (if present) |
| `acct_jj_flag_2025` | `CFLJJ` | Juvenile Justice flag (if present) |
| `acct_alted_flag_2025` | `CFLALTED` | Other alt-ed flag (if present) |
| `acct_residential_flag_2025` | `CFLRTF` | Residential Treatment Facility flag (if present) |
| `accountability_source_year` | pipeline | 2025 (constant) |
| `accountability_matched` | pipeline | True if campus matched the statewide file |

**Coordinates (source: TEA ArcGIS Schools 2024-25)**

| Output column | Description |
|---|---|
| `latitude` | WGS84 decimal degrees (geometry.y from ArcGIS point) |
| `longitude` | WGS84 decimal degrees (geometry.x from ArcGIS point) |
| `geocode_source` | "TEA ArcGIS Schools 2024-25" or null (unmatched) |
| `arcgis_source_year` | "2024-25" (constant) |
| `arcgis_matched` | True if campus had a feature in the ArcGIS layer |

### Caveats

- **"Not Rated" is not missing data.** TEA assigns "Not Rated" to new schools,
  DAEP campuses, and other campuses that are assessed but exempted from a letter
  grade. `accountability_rating_2025 = "Not Rated"` is a real value; null means
  the campus was not in the accountability file at all.
- **ArcGIS coordinates are geocoder output**, derived from a 2024-25 AskTED
  snapshot. They may differ from the exact building location. Use for display and
  approximate mapping only; do not use for surveying or legal boundaries.
- **ArcGIS item was last modified 2026-01-15** (data content is school year
  2024-25). Campus IDs that appeared after that update may not have coordinates.
- **Optional flag columns** (CFLAEATYPE, CFLDAEP, CFLJJ, CFLALTED, CFLRTF) are
  included only if they appear in the downloaded accountability CSV. Their
  presence is recorded in `accountability_join_report.json`
  (`optional_columns_present`).

---

## Phase 5 — Final Dataset Cleanup and Submission Exports

Phase 5 reads `cohort_enriched.csv` (151 columns), drops 72 columns with
documented reasons, validates 12 quality checks, and writes the submission-ready
dataset plus supporting metadata files.

### Prerequisites

Python 3.11+ and the packages in `requirements.txt`.  
`data/processed/cohort_enriched.csv` must already exist (output of Phase 4).

### Running Phase 5

```
python scripts/build_final.py
```

Saves:

| File | Description |
|---|---|
| `data/processed/dallas_school_insights.csv` | Final dataset — 60 rows x 79 columns |
| `data/processed/dallas_school_insights.parquet` | Same, with typed nullable numerics |
| `data/processed/data_dictionary.csv` | Schema for all 79 columns |
| `data/processed/data_quality_report.json` | 12 automated quality checks |
| `data/processed/source_coverage_report.csv` | Match rate per source |

**Run tests**

```
pytest tests/
```

All 253 Phase 1–5 tests pass.

### Column selection rationale

79 of the 151 enriched columns are included in the final dataset. The 72 dropped
columns fall into these categories:

| Category | Count | Examples |
|---|---|---|
| Pipeline flags / constant metadata | 11 | `tapr_matched`, `crdc_collection_year`, `geocode_source` |
| TAPR numerators / denominators (rates kept) | 9 | `tapr_att_all_days_present_2024`, `tapr_chronic_abs_all_numerator_2024` |
| Accountability — redundant or all-null | 2 | `acct_charter_flag_2025` (dup of `district_type`), `acct_alt_ed_type_2025` (all-null) |
| CRDC all-null columns | 10 | non-binary gender counts (`_x_`), mechanical/seclusion student counts |
| CRDC very sparse columns | 3 | `crdc_rs_phys_students_*` (4/60 schools have data) |
| CRDC M/F breakdowns (totals kept) | 37 | `crdc_tot_enr_m_2122`, `crdc_idea_iss_students_f_2122`, … |

Full drop reasons are in `scripts/build_final.py` (`DROPPED_LOG` dict) and in
`data/processed/data_dictionary.csv` (`caveat` column).

### Data dictionary schema

`data/processed/data_dictionary.csv` has one row per final column:

| Column | Meaning |
|---|---|
| `column_name` | Column name in `dallas_school_insights.csv` |
| `data_type` | Python/pandas type |
| `definition` | Plain-English description |
| `source` | Originating data source |
| `source_year` | Year of the source data |
| `raw_cleaned_or_derived` | cleaned = sentinel removal / type coercion; derived = computed from other columns |
| `coverage_percent` | % of 60 rows with a non-null value |
| `caveat` | Suppression rules, known gaps, or interpretation notes |

### Source coverage

| Source | Year | Matched / 60 | % |
|---|---|---|---|
| TEA AskTED | 2025 | 60 | 100% |
| TAPR | 2025 | 60 | 100% |
| TEA Accountability | 2025 | 60 | 100% |
| TEA ArcGIS Schools | 2024-25 | 60 | 100% |
| CRDC | 2021-22 | 58 | 96.7% |

### Quality checks (all passing)

1. Row count equals 60  
2. No duplicate campus IDs  
3. No duplicate NCES school IDs  
4. Required identity fields fully populated  
5. All percentage columns in [0, 100]  
6. All count columns non-negative  
7. Accountability rating codes only A/B/C/D/F/"Not Rated" or null  
8. Latitude in [32.5, 33.2], longitude in [-97.2, -96.4]  
9. No suppression sentinels (-1/-2/-3/-9) remaining in output  
10. No all-null analytical columns in final dataset  
11. Accountability score in plausible range  
12. CRDC column coverage at least 90%

---

## Phase 6 — Supabase Schema, Migration, and Data Load

Phase 6 uploads the final 60-school dataset to a Supabase Postgres database.
The local CSV/Parquet files remain the source of truth; Supabase is the
downstream read replica used by the dashboard.

### Prerequisites

```
pip install -r requirements.txt   # adds supabase>=2.0.0, python-dotenv>=1.0.0
```

You also need a Supabase project. Get your credentials from
**Project Settings → API**:

| Setting | Where to find it |
|---|---|
| Project URL | Settings → API → Project URL |
| Service role key | Settings → API → service_role (secret) |

### Environment variables

Copy `.env.example` to `.env` and fill in real values:

```
cp .env.example .env
# edit .env with your SUPABASE_URL and SUPABASE_SERVICE_KEY
```

`.env` is git-ignored. Never commit real credentials.

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Service role JWT — bypasses RLS for writes |

### Migration instructions

Migration files live in `migrations/`. Apply them once, in order:

```
# 1. Create public.schools (79 columns, campus_id PK)
# 2. Create public.pipeline_runs (load audit table)
# 3. Enable RLS; add SELECT-only policies for anon + authenticated
```

Apply via the Supabase dashboard SQL editor (paste each file in order), or
via the Supabase CLI:

```
supabase db push
```

Or use the MCP server (already applied for the connected project):

```
mcp apply_migration --name create_schools --query @migrations/20260614000001_create_schools.sql
```

### Load command

After migrations are applied and `.env` is configured:

```
python scripts/load_supabase.py
```

The script:
1. Reads `data/processed/dallas_school_insights.parquet`
2. Deletes all existing rows from `public.schools`
3. Inserts 60 rows in chunks
4. Validates that exactly 60 rows are present
5. Appends one record to `public.pipeline_runs`

### Security model

| Role | schools | pipeline_runs |
|---|---|---|
| `anon` | SELECT only | no access |
| `authenticated` | SELECT only | no access |
| `service_role` | full access (bypasses RLS) | full access |

Public INSERT / UPDATE / DELETE are not permitted.

### Local fallback

The local CSV and Parquet files are always the authoritative source:

```
data/processed/dallas_school_insights.csv     # human-readable
data/processed/dallas_school_insights.parquet # typed, used by load script
```

If Supabase is unavailable, read from these files directly.

### Run Phase 6 tests

```
pytest tests/test_phase6.py -v
```

These tests are entirely local (no network) and verify:
- Migration files exist and contain correct DDL
- All 79 final columns appear in the migration SQL
- RLS is enabled with SELECT-only policies; no public write policies
- `.env.example` has required credential keys
- `load_supabase.py` references correct env vars, parquet, and row count
- `_nan_to_none` correctly handles NaN / pd.NA / numpy scalars

---

## Phase 7 — Streamlit Dashboard

A four-page Streamlit dashboard that reads from Supabase when credentials are
available and falls back to the local Parquet file automatically.

### Local run

```
pip install -r requirements.txt
streamlit run dashboard/app.py
```

Opens at **http://localhost:8501**.

### Environment variables (optional)

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` — enables live Supabase reads |
| `SUPABASE_ANON_KEY` | Supabase anonymous (public) key — used by the dashboard (not the service role key) |

If neither variable is set, the dashboard silently falls back to
`data/processed/dallas_school_insights.parquet`. A badge in the sidebar
shows which source is active.

### Data source fallback behaviour

1. Dashboard calls `dashboard/data_loader.py:load_data()`.
2. If `SUPABASE_URL` and `SUPABASE_ANON_KEY` are both set, it queries
   `public.schools` via the Supabase Python client.
3. On any error (missing credentials, network failure, empty response), it
   loads `data/processed/dallas_school_insights.parquet` instead.
4. Every page displays a **"Data source"** badge showing which path was used.

### Dashboard pages

| Page | File | Content |
|---|---|---|
| **School Explorer** | `dashboard/pages/01_school_explorer.py` | Summary cards (total schools, ISD/charter split, median enrollment, A/B share); filters for level, operator, rating, enrollment; Dallas map (Plotly Mapbox); sortable school table |
| **Special Education** | `dashboard/pages/02_special_education.py` | TAPR SpEd % distribution and ranked bar; CRDC IDEA enrollment; disability ISS/OOS/expulsion/restraint/seclusion/harassment counts (tabs); nulls preserved and labelled |
| **Culture & Safety** | `dashboard/pages/03_culture_safety.py` | Attendance and chronic absence rates (TAPR 2024); OOS suspension instances by disability status (CRDC 2021-22); teacher experience distribution; accountability as context; explicit note that climate survey data was unavailable |
| **School Detail** | `dashboard/pages/04_school_detail.py` | All available fields for one school; missing fields table with documented reasons; source coverage report |

### Dashboard files

```
dashboard/
  app.py                      Main entry point / home page
  data_loader.py              Supabase → Parquet fallback loader
  components.py               Reusable Plotly/Streamlit components
  pages/
    01_school_explorer.py
    02_special_education.py
    03_culture_safety.py
    04_school_detail.py
.streamlit/
  config.toml                 Theme and server settings
```

### Phase 7 tests

```
pytest tests/test_phase7.py -v
```

36 tests covering:
- Local Parquet fallback loading
- Supabase failure triggers fallback (mocked)
- Required columns present after load
- Filters preserve valid rows and all columns
- All-null subsets handled without crash
- Null values not silently converted to zero
- All dashboard files exist

### Known data limitations

- No public climate survey data (student/staff satisfaction, PEARS incidents)
  was available for this cohort. Culture & Safety uses attendance, chronic
  absence, and discipline counts as proxy indicators only.
- CRDC data are from 2021-22. Do not compare CRDC counts with current TAPR rates.
- 2 of 60 schools (NCES IDs 481623022813, 480021123204) have no CRDC match;
  all CRDC columns are null for those two rows.
- ArcGIS coordinates are geocoder output for approximate display only.
- "Not Rated" is a real TEA designation — not missing data.
