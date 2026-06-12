# Safety and Climate Source Discovery

Verified from official source pages on 2026-06-11/12.

## Decision

No additional reproducible, current, campus-level Texas or Dallas ISD safety or
climate download was verified.

- Reject the Texas School Safety Center survey report for campus comparison:
  it is a 2016 aggregate research report with no campus IDs or row-level data.
- Reject Dallas ISD Campus Climate Survey reports from the reproducible core:
  the reports exist, but the exact route redirects to the MyData login and the
  landing page labels the content "Secure users only."
- Reject TEA's separate discipline products for campus comparison because TEA
  publishes them only at state, region, and district levels.
- Use CRDC's campus administrative measures as the available safety proxy, but
  do not describe them as lived-experience or climate-survey results.

## Texas School Safety Center

### Search API

- Public site: `https://txssc.txstate.edu/`
- Search endpoint:
  `https://manage.txssc.txstate.edu/api/v1/search-form-submit/{term}`
- Method/status: `GET`, `200`
- Content type: `application/json; charset=utf-8`
- Authentication: none
- Pagination/row limit: not exposed for tested searches
- Search for `PEARS`: empty JSON array
- Search for `survey`: returned report/toolkit pages, including the School
  Safety Practices Survey Report

No PEARS machine-readable dataset, download, or campus-level schema was exposed
by the official search endpoint or the inspected TxSSC pages. "PEARS" should
not appear in the implementation plan as an available source unless TEA/TxSSC
provides a specific authenticated or public endpoint.

### Texas School Safety Practices Survey Report

- Public page:
  `https://txssc.txstate.edu/research/reports/practices/`
- PDF:
  `https://locker.txssc.txstate.edu/f460091c5eda8166c7e8c0a450569bdc/2016-School-Safety-Practices-Survery-Report.pdf`
- Methods/status: page `GET 200`; PDF `HEAD 200`
- Formats: HTML and PDF
- PDF content type/size: `application/pdf`, 381,898 bytes
- Authentication: none
- Year: 2016
- Respondents stated on page: 487 administrators, 273 teachers, and 118 law
  enforcement officers
- Sampling: selected schools across Texas, stratified by community type
- Campus ID/NCES ID: none in the public report
- Row-level export: none found
- Dallas identification: none

This source is authoritative background research but stale and unsuitable for
joining or comparing Dallas campuses. It cannot populate campus safety fields.

## Dallas ISD Campus Climate Survey

- Public landing page: `https://mydata.dallasisd.org/`
- Exact report route:
  `https://mydata.dallasisd.org/PORT/SPRING_MVC/SecuredReports?group=Surveys`
- Landing page status/format: `GET 200`, HTML
- Report-route response without credentials: `302`
- Redirect target: `https://mydata.dallasisd.org/index.jsp`
- Authentication: required
- Public statement: "Campus Climate Survey Reports" are available under
  `Reports > Surveys`, in a section labeled "Secure users only"
- Public machine-readable file: none found
- Campus ID/NCES ID/schema: unavailable without authentication
- Coverage and year: cannot be independently verified from a public export

The reports are likely highly relevant, but they fail reproducibility and
public-access requirements. Do not scrape or automate around the login. A
future integration would require Dallas ISD to publish a sanctioned export or
provide project credentials and redistribution permission.

The current Dallas ISD public district-reports page exposes accountability,
TAPR, and report-card links, not campus-level climate survey data.

## Official discipline outside TAPR

TEA's official Discipline Data Products page and its Discipline Action Group
Summary expose state, region, and district reports only. They do not provide a
campus-level downloadable file or campus identifier. They therefore cannot
support valid comparisons among Dallas schools.

CRDC remains the approved campus-level administrative source for ISS, OOS,
expulsion, restraint/seclusion, disability-based harassment, referrals/arrests,
and selected offense incidents. It is historical (2021-22) and self-reported.

## Realistic culture and safety fields

Approved:

- TAPR 2024 attendance rate and chronic-absence rate, all students and special
  education
- TAPR 2025 teacher average experience, average district tenure, and
  beginning-teacher share
- CRDC 2021-22 ISS and OOS student counts/rates by disability
- CRDC 2021-22 OOS instances and days missed
- CRDC 2021-22 expulsions
- CRDC 2021-22 restraint and seclusion
- CRDC 2021-22 disability-based harassment/bullying reports
- CRDC 2021-22 law-enforcement referrals, arrests, and selected offenses

Not verified and therefore not approved:

- campus climate survey score
- parent experience score
- student belonging/safety perception score
- campus safety audit score
- PEARS incident count
- current Texas campus incident feed
- DAEP referral count/rate
- teacher turnover rate
- teacher certification rate
- LRE/inclusion percentage

## Lived experience recommendation

Unofficial sentiment is not necessary to deliver a defensible first version of
the two-theme dataset, provided the project states that its culture/safety
features are administrative proxies rather than direct lived-experience
measures.

It is necessary only if the assessment interprets "lived experience" as a hard
requirement for perceptions, narratives, or current climate. In that case,
unstructured public reviews are the only broadly reproducible fallback found,
but they should be an explicitly optional, separately scored layer with source
provenance, review-count thresholds, date windows, and bias warnings. They
should never be merged into the official-data index as if representative.

The preferred future source is a sanctioned public Dallas ISD campus climate
survey export. Until one exists, do not fabricate a survey-equivalent field.

## Required project-plan changes

1. Treat AskTED as identity, TAPR as current Texas profile, accountability as
   context, and CRDC as historical civil-rights/safety context.
2. Remove TxSSC PEARS and Dallas ISD climate ingestion tasks from the core
   pipeline; retain them as documented future-source gaps.
3. Add source-year suffixes to all analytical fields.
4. Add denominator, suppression/sentinel, and source-quality columns.
5. Left join every feature source to the AskTED cohort so missing historical
   coverage remains visible.
6. Do not produce a single culture/safety score unless the plan documents
   weighting, missingness, year mismatch, and the administrative-proxy caveat.

