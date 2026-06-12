# TEA and AskTED Source Discovery

Verified from the command line on 2026-06-11/12 using read-only `curl` requests and
PowerShell CSV/JSON inspection. Large responses used for discovery were kept only
in the system temporary directory. The repository contains only small samples.

## Executive recommendation

1. **Canonical school roster:** use the direct AskTED site-address download:
   `https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadSite.aspx`.
   It returned a current, unauthenticated CSV with 9,808 campus rows, 49 columns,
   October 2025 enrollment, and row update timestamps from 2026-06-11.
2. **Stable school identifier:** use the nine-character TEA campus number from
   `School Number`/`school_number`/`USER_School_Number`, stored as text after
   removing the source's leading apostrophe. Its first six characters are the TEA
   district number. Keep NCES school ID as a secondary crosswalk, not the primary
   key.
3. **TEA sources worth integrating:** direct AskTED for identity and operator
   data; the current-schools FeatureServer only for geocoded points; the 2026
   district FeatureServer for approximate district boundaries; optionally the
   county layer for spatial county assignment.
4. **Reject as a master source:** the Socrata AskTED resource `hzek-udky` is a
   static May 2025 snapshot, and the ArcGIS school layer is a derivative 2024-25
   snapshot with geocoding artifacts. Historical ArcGIS school layers, CTE files,
   census assets, and old boundary layers are out of scope.
5. **Still needed:** campus-level special-education, discipline, attendance,
   demographics, accountability, and climate/safety sources. None are exposed in
   the verified AskTED schemas or the 43-dataset ArcGIS Hub catalog.

## Source 1: TEA ArcGIS Hub

### Platform and discovery

- Public page: `https://schoolsdata2-tea-texas.opendata.arcgis.com/`
- Platform: ArcGIS Hub backed by ArcGIS Online organization
  `5MVN2jsqIrNZD4tP`.
- Hub site item: `7f78c00bdaf948d9b777b6cb296ca7c2`.
- Catalog group exposed by the site:
  `47666ca4acd24bda9f9d0be855437252`.
- Machine-readable catalog:
  `https://schoolsdata2-tea-texas.opendata.arcgis.com/api/search/v1/collections/dataset/items`
- The documented search API is OGC-style. `limit` accepts 0-100 and pagination
  uses one-based `startindex`; the response includes a `next` link.
- A limited request returned HTTP 200, `application/geo+json`, 43 matched
  datasets, and 5 returned records.
- Search headers exposed a short-window limit of 10 requests for the portal
  search throttler. The API landing and collection endpoints exposed a limit of
  100 requests with reset value 1. Treat these as observed headers, not a
  contractual quota.
- No authentication was required.

The catalog has school points, district boundaries, counties, ESC boundaries,
historical school layers, census assets, and CTE files. Title searches over the
catalog found no accountability, rating, demographic, attendance, discipline,
special-education, or staff datasets.

### Current schools FeatureServer

- Item ID: `80c162b9008a40d681c127874722670f`
- Item title: `Schools 2024 to 2025`
- Service:
  `https://services2.arcgis.com/5MVN2jsqIrNZD4tP/arcgis/rest/services/Schools_2024_to_2025/FeatureServer`
- Layer 0: `Schools2024to2025`
- Item modified: 2026-01-15, but the content is explicitly school year 2024-25
  and its enrollment field is October 2024.
- Layer metadata request: HTTP 200 GET, `application/json`.
- Authentication: none.
- Records: 9,739 statewide point features.
- Maximum records per query: 2,000.
- Pagination: supported with `resultOffset` and `resultRecordCount`.
- Query formats: JSON, GeoJSON, and PBF. The Hub page also advertises generated
  CSV, KML, and shapefile downloads.
- Rate-limit headers: none observed on FeatureServer requests.

The layer has 117 fields. Most are geocoder output; the authoritative source
columns are prefixed `USER_`. Important fields include:

| Field | ArcGIS type | Meaning/sample |
|---|---|---|
| `USER_School_Number` | string | `'043910052` |
| `USER_District_Number` | string | `'043910` |
| `USER_School_Name` | string | `FRANKFORD MIDDLE` |
| `USER_District_Name` | string | `PLANO ISD` |
| `USER_District_Type` | string | `INDEPENDENT` or `CHARTER` |
| `USER_Charter_Type` | string | null or `OPEN ENROLLMENT CHARTER` |
| `USER_Instruction_Type` | string | `REGULAR INSTRUCTIONAL` |
| `USER_Grade_Range` | string | `'06-08` |
| `USER_School_Enrollment_as_of_Oc` | integer | `839` |
| `USER_School_Site_Street_Address` | string | `7706 OSAGE PLAZA PKWY` |
| `USER_School_Site_City` | string | `DALLAS` |
| `USER_County_Number` | string | `'043` |
| `USER_NCES_School_ID` | string | `'483510007834` |
| geometry / `DisplayX`, `DisplayY` | point/double | `-96.771843`, `32.993541` |

Nulls are JSON `null`. For example, non-charters have null
`USER_Charter_Type`; optional address inputs and status dates can also be null.
Identifiers include a literal leading apostrophe and must be normalized as text.

Verified restrictive filters:

- `USER_School_Site_City='DALLAS'`: 375 rows.
- `USER_District_Number='''057905'`: 248 rows.
- `USER_County_Number='''057'`: 800 rows.

The apostrophe in the source value must be escaped in ArcGIS SQL. City is the
best simple filter for schools physically addressed in Dallas. District number
selects Dallas ISD only and excludes Dallas charter campuses and campuses run by
other districts. County is substantially overbroad. A bounding box is possible
but is less reliable than site city because Dallas has irregular municipal
boundaries and nearby municipalities.

Risk: the layer is derived from AskTED and is older than the current direct
download. It also contains geocoder fields and occasional differences between
mailing and site addresses. Use it as a location enrichment keyed by normalized
TEA campus number, not as the master roster.

### School district boundaries

- Item ID: `9b888324392d40999ff63f5790ac8c8c`
- Item title: `School Districts 2026`
- Service:
  `https://services2.arcgis.com/5MVN2jsqIrNZD4tP/arcgis/rest/services/School_Districts__2026/FeatureServer`
- Layer 0: `SchoolDistricts_SY2526`
- Item modified: 2026-04-30.
- Records: 1,017 polygon features.
- Maximum records per query: 2,000; pagination supported.
- Query formats: JSON, GeoJSON, and PBF.
- Authentication: none.

Key fields are `DISTRICT_C` (six-character TEA district ID), `DISTRICT`
(hyphenated ID), `DISTRICT_N` (numeric ID), `NCES_DISTR`, and `NAME`. A
restrictive query for `DISTRICT_C='057905'` returned Dallas ISD and its polygon.
The layer is suitable for approximate district geography and point-in-polygon
enrichment. The Hub warns that spatial data is informational, not surveyed, and
not suitable for critical legal or engineering use.

### Counties and other geography

The Counties item `c71146b6426248a5a484d8b3c192b9fe` resolves to a public
FeatureServer with fields including `CNTYFIPS` and `NAME`. It was last modified
2023-02-28. It is useful only for spatial county assignment. ESC item
`d273301a15b343a99d4c8211b7c112e0` was modified 2024-06-12 and is not needed
for the SchoolPath feature set.

## Source 2: Socrata AskTED snapshot

- Public page:
  `https://data.texas.gov/dataset/AskTED-Data-May-09-2025/hzek-udky/about_data`
- Platform: Socrata.
- Resource ID: `hzek-udky`.
- Metadata: `https://data.texas.gov/api/views/hzek-udky`
- Rows API: `https://data.texas.gov/resource/hzek-udky.json`
- Limited request: `GET ...json?$limit=5` returned HTTP 200,
  `application/json;charset=utf-8`.
- Authentication: not required for the tested reads.
- Rows: 9,763; columns: 41.
- Rows updated: 2025-05-14; row-level `update_date` values are 2025-05-09.
- Metadata says update frequency is annually.
- Pagination: SoQL `$limit` and `$offset`; no continuation token.
- Row limit: the API accepted the tested `$limit=5`. No numeric maximum was
  advertised in the response.
- Export formats verified: JSON, CSV, and XML. Standard Socrata query parameters
  apply to each.
- Rate limits: no numeric limit headers were present in tested SODA responses.
  An app token is prudent for repeated automated requests, but was not required.

The schema contains roster, district/operator, mailing address, grade range,
charter type, enrollment, and limited staff contacts. It does not contain site
addresses, latitude/longitude, accountability, demographics, attendance,
discipline, special education, or boundaries.

Important types:

- Text: `school_number`, `district_number`, `nces_school_id`,
  `school_street_address`, `school_city`, `grade_range`, `district_type`,
  `charter_type`, `instruction_type`.
- Number: `district_enrollment_as_of`, `school_enrollment_as_of_oct`.
- Calendar/floating timestamps: `school_status_date`, `update_date`.

Socrata omits null properties in JSON rows. In the sample, `charter_type` and
`school_status_date` are absent when null. Identifiers again contain a literal
leading apostrophe. Verified counts were 398 rows with mailing
`school_city='DALLAS'`, 248 Dallas ISD rows, and 800 Dallas County rows.

This dataset is authoritative in provenance and highly reproducible because the
resource ID and snapshot are stable, but it is stale relative to direct AskTED.
Use it only as a pinned fallback or regression fixture.

## Source 3: Direct TEA AskTED download

- Main page: `https://tea.texas.gov/AskTED`
- The main page redirects to the ASP.NET AskTED application.
- Machine endpoint with physical site addresses:
  `https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadSite.aspx`
- Alternate endpoint without site-address columns:
  `https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadDefault.aspx`
- Platform: dynamically generated downloadable CSV from an ASP.NET application.
- Method/status: unauthenticated GET, HTTP 200.
- Content type: `text/csv`.
- Content disposition: `attachment;filename=Directory.csv`.
- Pagination/row limit: none; each request returns the full statewide file.
- Rate-limit headers: none observed.
- Current site-address download: 9,808 rows and 49 columns.
- Row updates: 2026-06-11 05:38:12 through 05:38:32 in the inspected response.

The direct download is actively maintained rather than a static dated snapshot:
it had October 2025 enrollment and 2026 update timestamps, while Socrata still
had October 2024 enrollment and May 2025 updates.

All CSV values initially parse as strings. Numeric enrollment fields should be
converted after treating sentinel values such as `-1` as missing/unknown.
Blank strings represent nulls. Observed statewide blank counts in the current
site-address download:

- `Charter Type`: 8,657 blank, 1,151 populated.
- `School Site Street Address`: 3 blank.
- `School Site City`: 3 blank.
- `School Principal`: 488 blank.
- `School Status Date`: 3,932 blank.
- `NCES School ID`: 0 blank in this snapshot.

The file had 9,631 active and 177 under-construction campuses. Verified Dallas
counts were:

- Physical `School Site City = DALLAS`: 368.
- Mailing `School City = DALLAS`: 384.
- TEA district number `057905` (Dallas ISD): 243.
- TEA county number `057` (Dallas County): 785.

The best Dallas filter for a city-focused roster is normalized physical
`School Site City = DALLAS`, followed by active status and explicit handling of
under-construction/zero-enrollment campuses. This still yields far more than the
assessment's desired 40-80 schools, so the project plan must define a
deterministic, documented cohort rule rather than silently treating Dallas ISD
or Dallas County as equivalent to the city.

Reproducibility risk: the URL is stable but the content changes in place and the
response does not advertise a version identifier. Every ingestion must record
retrieval timestamp, SHA-256, row count, schema, and min/max `Update Date`.

## Capability matrix

| Capability | Direct AskTED | Socrata AskTED | ArcGIS schools | ArcGIS districts |
|---|---:|---:|---:|---:|
| Campus roster | Yes | Yes, stale | Yes, derivative | No |
| School point locations | Address only | Mailing address only | Yes | No |
| District/operator | Yes | Yes | Yes | Yes |
| Grades served | Yes | Yes | Yes | No |
| Charter status | Yes | Yes | Yes | No |
| Accountability ratings | No | No | No | No |
| Enrollment | Yes | Yes, older | Yes, older | No |
| Demographics | No | No | No | No |
| Attendance | No | No | No | No |
| Discipline | No | No | No | No |
| Special-ed population/indicators | No | No | No | No |
| Staff information | Principal/superintendent | Same | Same | No |
| Geographic boundaries | No | No | No | District polygons |

## Evaluation

| Source | Authority | Freshness | Reproducibility | Joinability | Recommended use |
|---|---|---|---|---|---|
| Direct AskTED site download | TEA system of record | Best; current on request | Medium; mutable URL, must hash | Excellent via TEA campus/district IDs | Master identity roster |
| Socrata `hzek-udky` | Official state portal/TEA attribution | Poor; May 2025 snapshot | Excellent | Excellent | Pinned fallback/test fixture |
| ArcGIS schools 2024-25 | Official TEA derivative | Older roster; item touched Jan 2026 | Good with item/layer URL | Excellent via campus ID | Coordinates and geocoding only |
| ArcGIS districts 2026 | Official TEA geography | Current 2026 layer | Good | Excellent via district ID | Approximate district boundaries |
| ArcGIS counties | Official TEA locator support layer | Old but stable geography | Good | Spatial/FIPS | Optional county enrichment |
| Historical/CTE/census Hub items | Mixed official catalog assets | Varies | Varies | Poor for requested features | Reject for this assessment |

## Additional sources required

The project needs authoritative, campus-level datasets outside these links:

1. TEA accountability ratings and School Report Card/TAPR extracts.
2. PEIMS or TAPR campus demographics, enrollment by student group, attendance,
   and special-education counts/percentages.
3. TEA discipline reports with campus identifiers and suppressions documented.
4. Staff qualifications/turnover datasets if staffing is used as a culture
   proxy.
5. Civil Rights Data Collection school-level discipline, restraint/seclusion,
   harassment, and disability fields as a federal complement.
6. A defensible climate/safety source, such as district climate surveys, TEA
   school-safety data, or another source with campus IDs and documented years.

These sources must be separately discovered and schema-verified. No claim should
be made that AskTED or the ArcGIS portal contains these outcomes.

## Exact next steps for Claude Code's project plan

1. Define the 40-80-school cohort before implementation. Start from active
   campuses whose normalized physical site city is Dallas; document exclusions
   for under-construction, zero/unknown enrollment, DAEP/JJAEP, and duplicate
   grade-level campuses. Use a deterministic rule or stratified sample if the
   result remains above 80.
2. Plan a raw ingestion step for `DownloadSite.aspx` that records URL, retrieval
   UTC timestamp, response headers, SHA-256, byte size, row count, column list,
   and min/max update timestamp.
3. Normalize leading apostrophes from TEA/NCES IDs while preserving them as
   zero-padded strings. Assert nine-character campus IDs and six-character
   district IDs; derive district ID from the first six campus-ID characters and
   compare it with the supplied district field.
4. Model canonical `schools` from direct AskTED. Keep mailing and physical site
   addresses separate. Convert blank strings and enrollment sentinel `-1` to
   explicit nulls with reason codes.
5. Query the ArcGIS school layer only for the selected campus IDs, in small
   batches, requesting a short `outFields` list and point geometry. Do not
   download the statewide 117-field layer.
6. Join coordinates on normalized TEA campus ID and report unmatched,
   duplicate, and low-quality/geocoded records. Prefer site-address fields over
   geocoder labels.
7. Query the 2026 district boundary layer only for district IDs represented in
   the cohort. Store its item ID, layer URL, modified date, and spatial
   reference.
8. Treat Socrata `hzek-udky` as a fixed comparison fixture. Add a freshness test
   that prevents it from replacing a newer direct AskTED extraction.
9. Run separate endpoint discovery for the six additional feature-source
   categories above. Require campus-level TEA IDs or a documented NCES/TEA
   crosswalk, data year, suppression rules, and a small sample before selecting
   each source.
10. Include data-contract tests for schema drift, unique campus IDs, valid
    district prefixes, Dallas cohort size of 40-80, coordinate bounds near
    Dallas, null/sentinel handling, and join coverage.

