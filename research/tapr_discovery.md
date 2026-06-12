# TEA TAPR and Accountability Discovery

Verified from the command line on 2026-06-11/12. All requests were read-only.
No statewide file is committed to the repository; only compact schema samples
are retained under `research/schema_samples/`.

## Decision

Approve the 2024-25 TAPR student, attendance, and staff downloads and the 2025
campus accountability summary. Use the current AskTED site-address download as
the canonical roster and join these files by the nine-digit TEA campus ID.

Do not use TEA's separate Discipline Data Products for campus comparisons.
TEA explicitly publishes those reports only at state, region, and district
levels.

## 2024-25 TAPR Data Download

- Public page:
  `https://rptsvr1.tea.texas.gov/perfreport/tapr/2025/index.html`
- Download form:
  `https://rptsvr1.tea.texas.gov/perfreport/tapr/tapr_dd_download.html?year=2025`
- Machine endpoint: `POST https://rptsvr1.tea.texas.gov/cgi/sas/broker`
- Authentication: none
- Pagination: none; each request returns one statewide CSV
- HTTP status: `200`
- Content type: returned as TEA's malformed
  `text/&content_type.-separated-values`
- Collection/release: TAPR 2024-25. Some measures explicitly refer to 2024.
- Rows: 9,084 campus rows in each tested file
- Dallas ISD rows: 239
- Dallas County-number prefix `057`: 775
- Current active Dallas-city AskTED campuses matched: 351 of 362 (**97.0%**)
- Campus ID: `CAMPUS`, a zero-padded nine-digit TEA campus ID
- District ID: `DISTRICT`, a zero-padded six-digit county-district ID
- NCES ID: not present; obtain it from AskTED
- Dallas filter: build the Dallas-city cohort in AskTED using
  `School Site City = DALLAS`, then inner/left join TAPR by `CAMPUS`

The POST body uses these common parameters:

```text
_service=marykay
_program=perfrept.perfmast.sas
_debug=0
tapr=all_c
ccyy=2025
sumlev=C
level=Campus
id=
prgopt=reports/tapr/dd/dd_tapr_step_7.sas
datafmt=csv
```

The returned CSV has two header rows: a descriptive label row followed by the
machine field-name row.

### Student information

Additional POST parameters:

```text
dsname=STUD
key=ETALL
key=NTALL
key=ETBIL
key=ETVOC
key=ETVHS
key=ETGIF
key=ETSPE
key=NTBIL
key=NTVOC
key=NTVHS
key=NTGIF
key=NTSPE
```

Exact filename: `2025 Campus Student Information.csv`

Relevant verified fields:

| Field | Meaning |
|---|---|
| `CPETALLC` | Student membership, all students count |
| `CPETSPEC` | Student membership, special education count |
| `CPETSPEP` | Student membership, special education percent |
| `CPNTALLC` | Student enrollment, all students count |
| `CPNTSPEC` | Student enrollment, special education count |
| `CPNTSPEP` | Student enrollment, special education percent |

Use `CPETSPEP` as the primary current special-education share because it is a
published percentage with its matching membership denominator. Preserve the
count and denominator as well.

### Attendance and chronic absenteeism

Additional POST parameters:

```text
dsname=DROP_ATT
key=AT24
key=CA24
var_type=N
var_type=D
var_type=R
```

Exact filename: `2025 Campus Attendance Absenteeism Dropout.csv`

Relevant verified fields:

| Field | Meaning |
|---|---|
| `CA0AT24N` | All-student days present |
| `CA0AT24D` | All-student days membership |
| `CA0AT24R` | All-student attendance rate |
| `CS0AT24N` | Special-ed days present |
| `CS0AT24D` | Special-ed days membership |
| `CS0AT24R` | Special-ed attendance rate |
| `CA0CA24N` | All-student chronic-absence numerator |
| `CA0CA24D` | All-student chronic-absence denominator |
| `CA0CA24R` | All-student chronic-absence rate |
| `CS0CA24N` | Special-ed chronic-absence numerator |
| `CS0CA24D` | Special-ed chronic-absence denominator |
| `CS0CA24R` | Special-ed chronic-absence rate |

These fields refer to 2024, despite being distributed in the 2024-25 TAPR
release. Name derived columns with the measure year, for example
`attendance_rate_2024`, rather than implying they are 2025 observations.

### Staff information

Additional POST parameters:

```text
dsname=STAF
key=ST00F
key=ST01F
key=ST06F
key=ST11F
key=ST21F
key=ST30F
key=STKID
key=SHEXP
key=SHTEN
key=SLEXP
key=SLTEN
key=STEXP
key=STTEN
key=STTOS
key=SUTOS
key=SSTOS
key=STURN
key=PSCTOSA
```

Exact filename: `2025 Campus Staff Information.csv`

Relevant verified fields:

| Field | Meaning |
|---|---|
| `CPSTEXPA` | Average years of teacher experience |
| `CPSTTENA` | Average teacher years with the district |
| `CPST00FC` | Beginning-teacher FTE count |
| `CPST00FP` | Beginning-teacher FTE percent |
| `CPST01FP` | Teacher FTE percent with 1-5 years |
| `CPST06FP` | Teacher FTE percent with 6-10 years |
| `CPST11FP` | Teacher FTE percent with 11-20 years |
| `CPST21FP` | Teacher FTE percent with 21-30 years |
| `CPST30FP` | Teacher FTE percent with more than 30 years |

The tested campus file does **not** contain teacher turnover or teacher
certification fields. The form key named `STURN` did not produce a turnover
column. Do not map `CPSTTENA` to turnover; it is tenure with the district.

## TAPR masking and missing values

Official masking page:
`https://rptsvr1.tea.texas.gov/perfreport/tapr/2025/masking.html`

Verified rules relevant to this project:

- `-1`: small denominator suppression, including attendance denominators below
  900 days membership and chronic-absence denominators from 1 through 4.
- `-2`: invalid, improbable, or out-of-range result.
- `-3`: complementary suppression.
- Blank or the download's unavailable symbol: unavailable/not applicable.
- Zero remains a real zero in contexts where TEA explicitly distinguishes zero
  from suppression.

Load measure columns as nullable numeric values after translating these codes.
Retain a separate quality/suppression flag rather than converting them to zero.

## 2025 Campus Accountability Ratings

- Public page:
  `https://tea.texas.gov/school-and-district-leaders/accountability/academic-accountability/performance-reporting/2025-accountability-rating-system`
- Download form:
  `https://rptsvr1.tea.texas.gov/perfreport/account/acct_download?year=2025`
- Machine endpoint:
  `https://rptsvr1.tea.texas.gov/cgi/sas/broker/?_service=marykay&_program=perfrept.perfmast.sas&_debug=0&ccyy=2025&dsname=RATE&sumlev=C&key=RATE&key=GRD&key=FLAG&datafmt=C&prgopt=reports%2Facct%2Fdd%2Fdd_get_data.sas`
- Method/status: `GET`, `200`
- Content type: `text/comma-separated-values`
- Authentication: none
- Pagination/row limit: none; full statewide CSV
- Exact filename: `2025 Campus Accountability Summary.csv`
- Rows: 9,084 campus rows
- Dallas ISD rows: 239
- Current active Dallas-city AskTED campuses matched: 351 of 362 (**97.0%**)
- Ratings observed: A, B, C, D, F, and `Not Rated`

Relevant verified fields:

| Field | Meaning |
|---|---|
| `CAMPUS` | Nine-digit TEA campus ID |
| `DISTRICT` | Six-digit TEA district ID |
| `COUNTY` | Three-digit county number |
| `C_RATING` | Overall accountability rating |
| `CDALLS` | Overall numeric score |
| `GRDTYPE`, `GRDSPAN`, `GRDLOW`, `GRDHIGH` | Grade configuration |
| `CFLCHART` | Charter flag |
| `CFLAEC`, `CFLAEATYPE` | Alternative-education flags |
| `CFLDAEP`, `CFLJJ`, `CFLALTED`, `CFLRTF` | Special campus-type flags |

This file is suitable for a contextual outcome/label. It should not be blended
into a culture or special-education index without a documented rationale.

## Separate TEA discipline products

- Public page:
  `https://rptsvr1.tea.texas.gov/adhocrpt/Disciplinary_Data_Products/Disciplinary_Data_Products.html`
- Report index:
  `https://rptsvr1.tea.texas.gov/adhocrpt/Disciplinary_Data_Products/Disciplinary_Reports.html`
- Method/status/format: `GET`, `200`, `text/html`
- Authentication: none
- Scope stated by TEA: state, region, or district
- Campus ID: absent because campus-level reports are not offered

The Discipline Action Group page likewise offers only state, region, and
district summaries. These products include ISS, OSS, DAEP/JJAEP, and expulsion
concepts but cannot support valid campus comparisons. Reject them from the
campus pipeline. Use CRDC for campus-level discipline, with its older collection
year and reporting-quality caveats made explicit.

## Schema implications

- Keep: special-ed membership percent/count, attendance, chronic absenteeism,
  teacher experience, beginning-teacher share, accountability rating/score.
- Rename: generic `attendance_rate` to `attendance_rate_2024`; generic
  `special_ed_percent` to `tapr_special_ed_membership_pct_2025`.
- Remove from the TAPR mapping: `teacher_turnover_rate`,
  `teacher_certification_rate`, `iss_rate`, `oss_rate`, `daep_rate`,
  `expulsion_rate`, `restraint_rate`, `seclusion_rate`, and LRE/inclusion.
  Those fields are not present in the tested TAPR files.
- DAEP is only a campus-type flag (`CFLDAEP`) in the accountability file, not a
  count or referral rate.

## Exact implementation-plan sequence

1. Pin the five official endpoints: AskTED site-address CSV, the three TAPR
   broker request bodies, and the accountability URL.
2. Save retrieval timestamp, HTTP status, response headers, exact filename, and
   a file checksum for every run.
3. Build the cohort from active AskTED rows whose normalized
   `School Site City` equals `DALLAS`; keep traditional and charter campuses.
4. Normalize TEA IDs as strings: strip a leading apostrophe, validate six or
   nine digits, and left-pad only after validation.
5. Parse TAPR's second row as the machine header and keep only the verified
   fields listed above.
6. Convert blank, `-1`, `-2`, and `-3` values to nullable measures plus an
   explicit source-quality code.
7. Left join each source to the AskTED roster by nine-digit campus ID and emit a
   per-source match flag.
8. Assert expected baseline coverage near 351 of the current 362 active
   Dallas-city campuses; investigate material changes rather than silently
   dropping records.
9. Add source and measure year to every output field and data dictionary entry.
10. Keep CRDC ingestion separate because it joins through NCES ID and represents
    2021-22, not the current TAPR year.
