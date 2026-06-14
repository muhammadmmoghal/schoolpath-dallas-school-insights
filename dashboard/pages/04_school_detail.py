"""
School Detail — complete data profile for a single school, organized by topic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from components import LEVEL_LABELS, OPERATOR_LABELS, RATING_COLORS, fmt_value, source_badge
from data_loader import load_data

DATA_DICT_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "data_dictionary.csv"
SOURCE_COV_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "source_coverage_report.csv"

st.title("School Detail")
st.caption("Complete data profile for one school — all available fields, source years, and documented gaps.")


# ── Load ──────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Loading…")
def get_data():
    return load_data()


@st.cache_data
def get_data_dict():
    return pd.read_csv(DATA_DICT_PATH) if DATA_DICT_PATH.exists() else pd.DataFrame()


@st.cache_data
def get_source_cov():
    return pd.read_csv(SOURCE_COV_PATH) if SOURCE_COV_PATH.exists() else pd.DataFrame()


try:
    df, source = get_data()
except Exception as exc:
    st.error(f"Failed to load data: {exc}")
    st.stop()

source_badge(source)

data_dict = get_data_dict()
source_cov = get_source_cov()


# ── School selector ───────────────────────────────────────────────────────────

school_names = sorted(df["school_name"].dropna().unique())
selected_name = st.selectbox("Select a school", school_names)
row = df[df["school_name"] == selected_name].iloc[0]

# Infer CRDC match status from key CRDC columns (crdc_matched was dropped in cleanup)
_crdc_key_cols = ["crdc_idea_enr_total_2122", "crdc_tot_enr_total_2122"]
crdc_matched = any(pd.notna(row.get(c)) for c in _crdc_key_cols if c in df.columns)

st.divider()

# ── Section 1: School Identity ─────────────────────────────────────────────────

st.subheader("School Identity")

col1, col2, col3 = st.columns(3)
with col1:
    st.write(f"**School:** {row.get('school_name', '—')}")
    st.write(f"**District / Operator:** {row.get('district_name', '—')}")
    op = row.get("operator_type")
    st.write(f"**Operator Type:** {OPERATOR_LABELS.get(op, str(op) if pd.notna(op) else '—')}")
    st.write(f"**District Type:** {row.get('district_type', '—')}")
with col2:
    lv = row.get("school_level")
    st.write(f"**School Level:** {LEVEL_LABELS.get(lv, str(lv) if pd.notna(lv) else '—')}")
    st.write(f"**Grade Range:** {row.get('grade_range', '—')}")
    st.write(f"**Instruction Type:** {row.get('instruction_type', '—')}")
    st.write(f"**Magnet Status:** {row.get('magnet_status', '—')}")
with col3:
    st.write(f"**Address:** {row.get('school_site_address', '—')}")
    st.write(f"**ZIP Code:** {row.get('school_site_zip', '—')}")
    st.write(f"**TEA Campus ID:** {row.get('campus_id', '—')}")
    st.write(f"**NCES School ID:** {row.get('nces_school_id', '—')}")

st.divider()

# ── Section 2: Enrollment & Accountability ─────────────────────────────────────

st.subheader("Enrollment & Accountability")

# Enrollment row
col4, col5, col6 = st.columns(3)
with col4:
    enr = row.get("enrollment")
    st.metric(
        "Enrollment (AskTED Oct 2025)",
        fmt_value(enr, "count") if pd.notna(enr) else "—",
        help="Source: AskTED 2025",
    )
with col5:
    mem = row.get("tapr_membership_all_count_2025")
    st.metric(
        "Total Membership (TAPR 2025)",
        fmt_value(mem, "count") if pd.notna(mem) else "—",
        help="Source: TEA TAPR 2025",
    )
with col6:
    sped_pct = row.get("tapr_membership_sped_pct_2025")
    st.metric(
        "Special Ed % of Membership (TAPR 2025)",
        fmt_value(sped_pct, "pct") if pd.notna(sped_pct) else "—",
        help="Source: TEA TAPR 2025",
    )

# Accountability row
rating = row.get("accountability_rating_2025")
score = row.get("accountability_score_2025")
status = row.get("accountability_status_2025")
rating_color = RATING_COLORS.get(str(rating), "#888888") if pd.notna(rating) else "#888888"

col7, col8, col9 = st.columns(3)
with col7:
    if pd.notna(rating):
        st.markdown(
            f"<h2 style='color:{rating_color};margin:0'>{rating}</h2>",
            unsafe_allow_html=True,
        )
        st.caption("TEA 2025 Overall Accountability Rating")
    else:
        st.metric("Accountability Rating (2025)", "—")
with col8:
    st.metric(
        "Accountability Score (2025)",
        fmt_value(score, "count") if pd.notna(score) else "—",
        help="Source: TEA 2025 Campus Accountability Summary",
    )
with col9:
    st.metric(
        "Accountability Status (2025)",
        str(status) if pd.notna(status) else "—",
        help="'Rated' (A–F) or 'Not Rated' (TEA designation)",
    )

grade_low = row.get("acct_grade_low_2025")
grade_high = row.get("acct_grade_high_2025")
grade_span = row.get("acct_grade_span_2025")
if pd.notna(grade_span):
    st.caption(f"Grade span: {grade_span} (grades {grade_low}–{grade_high})")
else:
    st.caption("Grade span: not reported in accountability file.")

st.divider()

# ── Section 3: Special Education ──────────────────────────────────────────────

st.subheader("Special Education")

col10, col11, col12 = st.columns(3)
with col10:
    sped_ct = row.get("tapr_membership_sped_count_2025")
    st.metric(
        "SpEd Membership Count (TAPR 2025)",
        fmt_value(sped_ct, "count") if pd.notna(sped_ct) else "—",
    )
with col11:
    idea_enr = row.get("crdc_idea_enr_total_2122")
    st.metric(
        "IDEA Enrollment (CRDC 2021-22)",
        fmt_value(idea_enr, "count") if pd.notna(idea_enr) else "— (not reported)",
        help="Source: CRDC 2021-22. Historical count — not comparable to current TAPR.",
    )
with col12:
    s504_enr = row.get("crdc_504_enr_total_2122")
    st.metric(
        "Section 504 Enrollment (CRDC 2021-22)",
        fmt_value(s504_enr, "count") if pd.notna(s504_enr) else "— (not reported)",
        help="Source: CRDC 2021-22.",
    )

if not crdc_matched:
    st.warning(
        "This school had **no CRDC match** — all CRDC fields are null. "
        f"(NCES ID: {row.get('nces_school_id', '—')})"
    )
else:
    st.caption(
        "CRDC 2021-22 disability-related discipline counts — "
        "raw counts, not rates. Null = not reported; 0 = reported zero incidents."
    )
    SPED_DISC: dict[str, str] = {
        "crdc_idea_iss_students_total_2122": "IDEA Students Receiving ISS (2021-22)",
        "crdc_oos_instances_idea_2122": "IDEA OOS Suspension Instances (2021-22)",
        "crdc_idea_mult_oos_total_2122": "IDEA Multiple OOS Suspensions (2021-22)",
        "crdc_rs_mech_instances_idea_2122": "Mechanical Restraint Instances — IDEA (2021-22)",
        "crdc_rs_phys_instances_idea_2122": "Physical Restraint Instances — IDEA (2021-22)",
        "crdc_rs_secl_instances_idea_2122": "Seclusion Instances — IDEA (2021-22)",
        "crdc_hb_dis_allegations_2122": "Disability Harassment Allegations (2021-22)",
    }
    disc_rows = []
    for col_name, label in SPED_DISC.items():
        val = row.get(col_name)
        if pd.notna(val):
            display_val = f"{int(val):,}"
        else:
            display_val = "— (not reported)"
        disc_rows.append({"Measure": label, "Value": display_val})
    st.dataframe(pd.DataFrame(disc_rows), hide_index=True, use_container_width=True)

st.divider()

# ── Section 4: Attendance & Discipline ────────────────────────────────────────

st.subheader("Attendance & Chronic Absence (TAPR 2024)")
st.caption("Source: TEA TAPR 2025 release; attendance measures are for year 2024.")

ATTEND_FIELDS: list[tuple[str, str]] = [
    ("tapr_att_all_rate_2024", "All-Student Attendance (%)"),
    ("tapr_att_sped_rate_2024", "Special-Ed Attendance (%)"),
    ("tapr_chronic_abs_all_rate_2024", "All-Student Chronic Absence (%)"),
    ("tapr_chronic_abs_sped_rate_2024", "Special-Ed Chronic Absence (%)"),
]

att_cols = st.columns(len(ATTEND_FIELDS))
for col_st, (field, label) in zip(att_cols, ATTEND_FIELDS):
    val = row.get(field)
    with col_st:
        st.metric(label, fmt_value(val, "pct") if pd.notna(val) else "—")

st.divider()

# ── Section 5: Teacher Staffing ────────────────────────────────────────────────

st.subheader("Teacher Staffing (TAPR 2025)")
st.caption("Source: TEA TAPR 2025.")

col17, col18, col19 = st.columns(3)
with col17:
    exp = row.get("tapr_avg_teacher_exp_years_2025")
    st.metric(
        "Avg. Teacher Experience",
        f"{exp:.1f} yrs" if pd.notna(exp) else "—",
        help="Average years of teaching experience across all teachers.",
    )
with col18:
    ten = row.get("tapr_avg_teacher_tenure_years_2025")
    st.metric(
        "Avg. District Tenure",
        f"{ten:.1f} yrs" if pd.notna(ten) else "—",
        help="Average years with this specific district (not total career).",
    )
with col19:
    beg = row.get("tapr_beginning_teacher_fte_pct_2025")
    st.metric(
        "Beginning Teachers (FTE %)",
        fmt_value(beg, "pct") if pd.notna(beg) else "—",
    )

EXP_BANDS: list[tuple[str, str]] = [
    ("tapr_beginning_teacher_fte_pct_2025", "Beginning (< 1 yr)"),
    ("tapr_teacher_1to5yr_pct_2025", "1–5 Years"),
    ("tapr_teacher_6to10yr_pct_2025", "6–10 Years"),
    ("tapr_teacher_11to20yr_pct_2025", "11–20 Years"),
    ("tapr_teacher_21to30yr_pct_2025", "21–30 Years"),
    ("tapr_teacher_over30yr_pct_2025", "Over 30 Years"),
]
band_rows = []
for col_name, lbl in EXP_BANDS:
    val = row.get(col_name)
    if pd.notna(val):
        display_val = f"{float(val):.1f}%"
    else:
        display_val = "— (not reported)"
    band_rows.append({"Experience Band": lbl, "FTE %": display_val})
st.dataframe(pd.DataFrame(band_rows), hide_index=True, use_container_width=False)

st.divider()

# ── Section 6: Data Coverage ──────────────────────────────────────────────────

st.subheader("Data Coverage")
st.caption(
    "Source-match rates are cohort-wide (all 60 schools), not specific to this school. "
    "A school may have different coverage from the cohort average."
)

if not source_cov.empty:
    st.dataframe(source_cov, hide_index=True, use_container_width=True)
else:
    st.info("Source coverage report not found — run scripts/build_final.py to generate it.")

crdc_status = "matched to CRDC" if crdc_matched else "NOT matched to CRDC"
st.caption(
    f"This school is **{crdc_status}** (NCES ID: {row.get('nces_school_id', '—')}). "
    "Source: CRDC 2021-22."
)

st.divider()

# ── Section 7: Missing Data ────────────────────────────────────────────────────

st.subheader("Missing Data for This School")
st.caption(
    "Fields where this school's value is null, with documented reasons from the data dictionary. "
    "Null means unreported, suppressed, or not applicable — not zero."
)

if not data_dict.empty:
    missing_rows = []
    for _, drow in data_dict.iterrows():
        col_name = drow["column_name"]
        if col_name not in df.columns:
            continue
        val = row.get(col_name)
        if pd.isna(val):
            missing_rows.append(
                {
                    "Column": col_name,
                    "Description": drow.get("definition", ""),
                    "Source": drow.get("source", ""),
                    "Year": str(drow.get("source_year", "")),
                    "Reason / Caveat": drow.get("caveat", ""),
                }
            )
    if missing_rows:
        st.dataframe(
            pd.DataFrame(missing_rows),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(f"{len(missing_rows)} of {len(df.columns)} fields are null for this school.")
    else:
        st.success("No null fields for this school — all 79 columns have reported values.")
else:
    null_cols = [c for c in df.columns if pd.isna(row.get(c))]
    st.write(
        f"**{len(null_cols)} null fields** (data dictionary not found; run scripts/build_final.py): "
        f"{', '.join(null_cols) if null_cols else 'none'}"
    )
