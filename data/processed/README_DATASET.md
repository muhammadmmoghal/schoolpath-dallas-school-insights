# SchoolPath Dallas — Dataset README

## What This Dataset Represents

This dataset provides a recruiter-facing profile of **60 Dallas-area public schools** that serve students with disabilities (IDEA/IEP). Each row is one campus. Columns span school identity, enrollment, Texas accountability ratings, special-education staffing and attendance metrics (from TAPR), federal civil-rights discipline and safety data (from CRDC), and geocoordinates for mapping.

The dataset is designed to help special-education recruiters quickly compare campuses across dimensions that matter for SpEd hiring: population served, teacher experience, discipline climate, and accountability trajectory.

---

## Cohort: Size and Selection Method

**60 schools** were selected from the Texas Education Agency (TEA) AskTED roster using the following criteria applied in sequence:

| Step | Filter | Retained |
|------|--------|----------|
| Geography | `SCHOOL_SITE_CITY = DALLAS` | ~380 campuses |
| Status | `SCHOOL_STATUS = Active` | — |
| District type | Public (ISD or Charter); private schools excluded | — |
| Instruction type | Regular or Alternative Instructional; DAEP and JJAEP excluded | — |
| SpEd population | Schools with at least one enrolled IDEA student (TAPR 2025) | 60 |

The 60 schools represent **12 charter** and **48 ISD** campuses across four levels: 32 elementary, 10 high, 9 middle, and 9 mixed (spanning multiple levels). Accountability ratings for 2025: A (18), B (22), C (8), D (10), F (2).

---

## Files in This Deliverable

| File | Description |
|------|-------------|
| `dallas_school_insights.csv` | Main dataset — 60 rows × 79 columns. One row per campus. |
| `data_dictionary.csv` | Column-by-column reference: display name, definition, source, year, derivation method, coverage %, null/suppression notes, and caveats. |
| `source_coverage_report.csv` | Join-level summary — how many of the 60 schools matched each source, and on which key. |

---

## Data Sources and Years

| Source | Year | What It Contributes | Join Key |
|--------|------|---------------------|----------|
| TEA AskTED | 2025 (Oct snapshot) | School identity, enrollment, address, grade range, magnet flag | `campus_id` |
| TEA TAPR (Texas Academic Performance Report) | 2024–25 | SpEd membership/enrollment counts and %, attendance rates, chronic absence rates, teacher experience and tenure distribution | `campus_id` |
| TEA 2025 Campus Accountability Summary | 2025 | Accountability rating (A–F), numeric score, grade span | `campus_id` |
| CRDC (Civil Rights Data Collection) | 2021–22 | IDEA discipline (ISS, OOS, expulsion), restraint/seclusion, harassment/bullying by disability, law enforcement referrals, campus safety offenses | `nces_school_id` (= CRDC COMBOKEY) |
| TEA ArcGIS Schools Layer | 2024–25 | Latitude / longitude for mapping | `campus_id` |

---

## Important Limitations

1. **CRDC year lag.** Civil-rights data are from the 2021–22 school year — three years before the accountability and TAPR data (2024–25). Use CRDC metrics as structural indicators, not current snapshots.

2. **Two schools have no CRDC match.** `BIOMEDICAL PREPARATORY AT UT SOUTHWESTERN` (campus 057905371) and `IDEA A W BROWN COLLEGE PREPARATORY` (campus 108807209) did not match on NCES school ID. All their CRDC columns are null.

3. **CRDC zeros are real zeros, not suppressed values.** The CRDC 2021–22 collection does not apply data-quality suppression; a zero means the school reported zero events. However, under-reporting by schools is possible.

4. **TAPR suppressed values are null, not zero.** TEA uses masking codes (−1, −2, −3) for cells with small denominators or data quality issues. These are stored as null in this dataset, never as zero. Do not interpret null as "no students affected."

5. **Attendance columns (`tapr_att_*_2024`) reflect 2023–24.** Despite appearing in the 2024–25 TAPR file, these rates are computed on 2023–24 attendance data.

6. **Teacher experience data for two schools is zero/suppressed.** `PEGASUS CHARTER H S` (campus 057802001) shows 0.0 years average experience — this is a TEA-reported value and may reflect data suppression or a genuinely new staff cohort.

7. **Coordinates are for display only.** Lat/lon come from a 2024–25 ArcGIS geocoder snapshot and are not survey-grade. Expected Dallas range: latitude 32.5–33.2, longitude −97.2 to −96.4.

8. **School level is derived.** The `school_level` column is derived from `grade_range` using TEA grade-span conventions. Schools serving non-standard spans are classified as `mixed`.

---

## Opening the CSV

**Excel:** Open normally. Set column A (`campus_id`) and column C (`nces_school_id`) as Text format before loading to preserve leading zeros.

**Python / pandas:**
```python
import pandas as pd
df = pd.read_csv(
    "dallas_school_insights.csv",
    dtype={"campus_id": str, "district_id": str, "nces_school_id": str, "school_site_zip": str}
)
```

**Encoding:** UTF-8. No BOM.

---

## Live Dashboard

An interactive recruiter dashboard for this dataset is deployed at:

**https://schoolpath-dallas.streamlit.app/**

The dashboard provides filtered school lookup, side-by-side comparison, a discipline/safety explorer, and an interactive map.

---

## Contact

Dataset compiled by SchoolPath Dallas. Source data are public records from TEA and the U.S. Department of Education.
