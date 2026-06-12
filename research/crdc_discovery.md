# CRDC School-Level Discovery

Verified from the command line on 2026-06-11/12 using the official U.S.
Department of Education Civil Rights Data Collection site.

## Decision

Approve the 2021-22 CRDC public-use school files for historical campus-level
discipline, restraint/seclusion, harassment, offenses, and disability
comparisons. It is the most recent publicly downloadable school-level CRDC
dataset currently linked by the official site.

The official page lists 2023-24 survey forms but no 2023-24 downloadable data
file. Do not claim 2023-24 data are available until the downloadable-file table
contains an actual data export.

## Endpoint

- Public page: `https://civilrightsdata.ed.gov/data`
- Machine-readable download:
  `https://civilrightsdata.ed.gov/assets/ocr/docs/2021-22-crdc-data.zip`
- Method/status: `GET`, `200`
- Content type: `application/x-zip-compressed`
- Content length: 832,409,504 bytes
- Last modified: 2025-01-10
- Byte ranges: supported (`206 Partial Content`)
- Authentication: none
- Pagination/row limit: none; ZIP archive
- Collection year: 2021-22
- Update model: static public-use release, not an actively updated API

The discovery pass fetched the ZIP central directory and byte ranges for the
needed stored CSV members instead of repeatedly downloading the 832 MB archive.

## Exact ZIP members

| Member | Uncompressed bytes | Columns in sampled header |
|---|---:|---:|
| `SCH/Enrollment.csv` | 69,490,696 | 233 |
| `SCH/Expulsions.csv` | 38,099,232 | 142 |
| `SCH/Harassment and Bullying.csv` | 40,302,611 | 159 |
| `SCH/Offenses.csv` | 16,276,989 | 33 |
| `SCH/Referrals and Arrests.csv` | 25,407,182 | 84 |
| `SCH/Restraint and Seclusion.csv` | 44,980,168 | 131 |
| `SCH/School Characteristics.csv` | 23,706,645 | 34 |
| `SCH/Suspensions.csv` | 49,553,658 | 189 |

These members are stored without compression in the ZIP, which permits
targeted range inspection. Production ingestion can still stream the official
ZIP once and select only these members.

## Identifiers and joins

Every tested school file begins with:

```text
LEA_STATE,LEA_STATE_NAME,LEAID,LEA_NAME,SCHID,SCH_NAME,COMBOKEY,JJ
```

- `COMBOKEY`: 12-character NCES school identifier; use this as the CRDC join key
- `LEAID`: seven-character NCES district identifier
- `SCHID`: five-character school suffix in the characteristics file; some topic
  files can lose display padding, so do not join on unnormalized `SCHID`
- TEA campus ID: not present
- Crosswalk: AskTED `NCES School ID` -> CRDC `COMBOKEY`
- Dallas ISD NCES LEA ID: `4816230`

Use IDs as strings and preserve leading zeroes.

## Coverage

The 2021-22 school-characteristics member contains:

- 8,924 Texas school rows
- 237 Dallas ISD rows (`LEAID = 4816230`)
- Both traditional and charter schools (Texas charter indicator counts:
  7,950 `No`, 974 `Yes`)

Against the current AskTED physical-site Dallas-city roster:

- 362 active Dallas-city campuses
- 361 unique valid current NCES school IDs
- 347 matched CRDC `COMBOKEY` values
- Expected current-roster join coverage: **96.1%**

The remaining gaps are consistent with collection-year churn, new campuses,
reserved/future-use campuses, and identifier changes. For a selected 40-80
school cohort, preserve unmatched records and report feature missingness rather
than substituting district values.

## Exact relevant fields

All CRDC topic values are counts or indicators. Rates must be calculated with
the corresponding enrollment denominator and clearly labeled as derived.

### Enrollment and special education

From `SCH/Enrollment.csv`:

- Total enrollment: `TOT_ENR_M`, `TOT_ENR_F`, `TOT_ENR_X`
- IDEA enrollment: `SCH_ENR_IDEA_M`, `SCH_ENR_IDEA_F`,
  `SCH_ENR_IDEA_X`
- Alternate total IDEA fields: `TOT_IDEAENR_M`, `TOT_IDEAENR_F`,
  `TOT_IDEAENR_X`
- Section 504 enrollment: `SCH_ENR_504_M`, `SCH_ENR_504_F`,
  `SCH_ENR_504_X`

Compute an IDEA share only after choosing and documenting a consistent
numerator family. TAPR provides the fresher Texas special-ed percentage and
should be primary; CRDC enrollment is the denominator for CRDC discipline rates.

CRDC does not provide a verified least-restrictive-environment/inclusion field
in these school-level members.

### Suspensions

From `SCH/Suspensions.csv`:

- IDEA students receiving ISS:
  `TOT_DISCWDIS_ISS_IDEA_M`, `TOT_DISCWDIS_ISS_IDEA_F`
- 504 students receiving ISS:
  `SCH_DISCWDIS_ISS_504_M`, `SCH_DISCWDIS_ISS_504_F`
- OOS suspension instances:
  `SCH_OOSINSTANCES_WODIS`, `SCH_OOSINSTANCES_IDEA`,
  `SCH_OOSINSTANCES_504`
- IDEA students receiving one OOS suspension:
  `TOT_DISCWDIS_SINGOOS_IDEA_M`, `TOT_DISCWDIS_SINGOOS_IDEA_F`
- IDEA students receiving multiple OOS suspensions:
  `TOT_DISCWDIS_MULTOOS_IDEA_M`, `TOT_DISCWDIS_MULTOOS_IDEA_F`
- IDEA days missed due to OOS suspension:
  `SCH_DAYSMISSED_IDEA_M`, `SCH_DAYSMISSED_IDEA_F`

Calculate student suspension rates from student counts, not suspension-instance
counts. Keep instance rates and student rates as different measures.

### Expulsions

From `SCH/Expulsions.csv`:

- IDEA expulsions with educational services:
  `TOT_DISCWDIS_EXPWE_IDEA_M`, `TOT_DISCWDIS_EXPWE_IDEA_F`
- IDEA expulsions without educational services:
  `TOT_DISCWDIS_EXPWOE_IDEA_M`, `TOT_DISCWDIS_EXPWOE_IDEA_F`
- IDEA zero-tolerance expulsions:
  `TOT_DISCWDIS_EXPZT_IDEA_M`, `TOT_DISCWDIS_EXPZT_IDEA_F`

### Restraint and seclusion

From `SCH/Restraint and Seclusion.csv`:

- IDEA instances:
  `SCH_RSINSTANCES_MECH_IDEA`, `SCH_RSINSTANCES_PHYS_IDEA`,
  `SCH_RSINSTANCES_SECL_IDEA`
- IDEA students:
  `TOT_RS_IDEA_MECH_M`, `TOT_RS_IDEA_MECH_F`,
  `TOT_RS_IDEA_PHYS_M`, `TOT_RS_IDEA_PHYS_F`,
  `TOT_RS_IDEA_SECL_M`, `TOT_RS_IDEA_SECL_F`

### Harassment and bullying

From `SCH/Harassment and Bullying.csv`:

- Allegations based on disability: `SCH_HBALLEGATIONS_DIS`
- Students reported harassed/bullied based on disability:
  `TOT_HBREPORTED_DIS_M`, `TOT_HBREPORTED_DIS_F`
- IDEA students reported:
  `SCH_HBREPORTED_DIS_IDEA_M`, `SCH_HBREPORTED_DIS_IDEA_F`
- Students disciplined for disability-based harassment:
  `TOT_HBDISCIPLINED_DIS_M`, `TOT_HBDISCIPLINED_DIS_F`
- IDEA students disciplined:
  `SCH_HBDISCIPLINED_DIS_IDEA_M`,
  `SCH_HBDISCIPLINED_DIS_IDEA_F`

These are administrative reports, not student perceptions of climate.

### Referrals, arrests, and offenses

From `SCH/Referrals and Arrests.csv`:

- IDEA referrals to law enforcement:
  `TOT_DISCWDIS_REF_IDEA_M`, `TOT_DISCWDIS_REF_IDEA_F`
- IDEA school-related arrests:
  `TOT_DISCWDIS_ARR_IDEA_M`, `TOT_DISCWDIS_ARR_IDEA_F`

From `SCH/Offenses.csv`:

- Assault with/without weapon: `SCH_OFFENSE_ATTWW`,
  `SCH_OFFENSE_ATTWOW`
- Possession of weapon: `SCH_OFFENSE_POSSWX`
- Robbery with/without weapon: `SCH_OFFENSE_ROBWW`,
  `SCH_OFFENSE_ROBWOW`
- Threat with/without weapon: `SCH_OFFENSE_THRWW`,
  `SCH_OFFENSE_THRWOW`
- Firearm/homicide indicators: `SCH_FIREARM_IND`, `SCH_HOMICIDE_IND`

CRDC has no Texas DAEP referral field.

## Missingness, suppression, and reliability

- `-9` is present in the actual CSV schema samples and must be treated as a
  non-value/not-applicable sentinel, never as a count.
- Zero is also common and is not interchangeable with `-9`.
- The official CRDC FAQ states that 2021-22 data-quality suppression was not
  applied, so public files can contain raw district-reported values that are
  internally inconsistent or all zero.
- Public-use privacy protection applies small random adjustments to some counts.
- Small-count rates should be accompanied by denominators and quality flags.
- A zero-heavy campus should not automatically be interpreted as safer; it may
  reflect reporting practice.

## Schema implications

- Rename generic fields to include source and year, for example
  `crdc_idea_oos_student_rate_2021_22`.
- Separate `students`, `instances`, and `days_missed` measures.
- Remove any proposed CRDC `daep_referral_rate`, `lre_percent`,
  `climate_score`, or `teacher_turnover` field; none was verified.
- Keep CRDC as historical context, not as a claim about current-year conditions.

