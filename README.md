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

## Phase 4 (not yet implemented)

| Phase | Content |
|---|---|
| 4 | Supabase load (optional) and dashboard |
