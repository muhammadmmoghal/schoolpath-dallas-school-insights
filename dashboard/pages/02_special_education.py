"""
Special Education — analytical view of special-ed membership and disability-related
discipline, restraint, and harassment counts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from components import (
    LEVEL_LABELS,
    LEVEL_ORDER,
    box_plot,
    distribution_histogram,
    null_note,
    source_badge,
)
from data_loader import load_data

st.title("Special Education")

st.info(
    "**Two data sources — two different years:**  \n"
    "Special-ed membership percentages are from **TEA TAPR 2025** (current year).  \n"
    "Enrollment counts, discipline, restraint, and harassment figures are from "
    "**CRDC 2021-22** (historical). These measures are not directly comparable.  \n"
    "**Null values** mean unreported, suppressed, or not applicable — never zero. "
    "CRDC does not apply small-cell suppression; a reported zero is a real zero.  \n"
    "**2 of 60 schools** had no CRDC match; all CRDC columns are null for those rows."
)

# ── Load ──────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Loading…")
def get_data():
    return load_data()


try:
    df, source = get_data()
except Exception as exc:
    st.error(f"Failed to load data: {exc}")
    st.stop()

source_badge(source)
n = len(df)

# ── Section 1: KPI Cards ──────────────────────────────────────────────────────

sped_col = "tapr_membership_sped_pct_2025"
sped_valid = df[sped_col].dropna()
med_sped = sped_valid.median()
max_sped = sped_valid.max()
n_above_20 = int((sped_valid > 20).sum())
crdc_coverage = int(df["crdc_idea_enr_total_2122"].notna().sum())

st.divider()
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric(
        "Median Special Ed %",
        f"{med_sped:.1f}%" if pd.notna(med_sped) else "—",
        help="Cohort median — TAPR 2025",
    )
with k2:
    st.metric(
        "Highest Reported",
        f"{max_sped:.1f}%" if pd.notna(max_sped) else "—",
        help="Single school with highest special-ed membership % (TAPR 2025)",
    )
with k3:
    st.metric(
        "Schools Above 20%",
        n_above_20,
        help="Schools where special-ed membership exceeds 20% of total (TAPR 2025)",
    )
with k4:
    st.metric(
        "CRDC Coverage",
        f"{crdc_coverage} / {n}",
        help="Schools with CRDC 2021-22 data available",
    )

# ── Section 2: TAPR SpEd Membership % ────────────────────────────────────────

st.divider()
st.subheader("Special Education Membership % (TAPR 2025)")
st.caption(
    "Source: TEA TAPR 2025. "
    "Denominator: all-student membership. "
    "TEA masking codes (-1, blank) converted to null."
)

null_note(
    sped_col, df[sped_col].isna().sum(), n,
    friendly_name="Special Ed Membership %",
)

col1, col2 = st.columns(2)

with col1:
    distribution_histogram(
        df,
        col=sped_col,
        title="Distribution of Special Ed Membership %",
        source_label="TEA TAPR 2025",
        xaxis_title="Special Ed % of Membership",
        nbins=15,
        height=340,
    )

with col2:
    level_display_df = df[[sped_col, "school_level"]].copy()
    level_display_df["school_level"] = level_display_df["school_level"].map(LEVEL_LABELS).fillna(level_display_df["school_level"])
    level_cat_order = [LEVEL_LABELS.get(l, l) for l in LEVEL_ORDER if LEVEL_LABELS.get(l, l) in level_display_df["school_level"].values]
    box_plot(
        level_display_df,
        x="school_level",
        y=sped_col,
        title="Special Ed % by School Level",
        source_label="TEA TAPR 2025",
        category_orders={"school_level": level_cat_order},
        height=340,
    )

# Factual takeaway
if pd.notna(med_sped):
    rng_min = sped_valid.min()
    rng_max = sped_valid.max()
    st.caption(
        f"Cohort median: **{med_sped:.1f}%**. "
        f"Range: {rng_min:.1f}% – {rng_max:.1f}%. "
        f"{n_above_20} school{'s' if n_above_20 != 1 else ''} "
        f"exceed 20% special-ed membership. "
        "Enrollment size is not controlled for; larger schools may have higher counts with similar rates."
    )

# Ranked bar — schools by SpEd %
ranked = (
    df[["school_name", sped_col, "school_level"]]
    .dropna(subset=[sped_col])
    .copy()
)
ranked["school_level"] = ranked["school_level"].map(LEVEL_LABELS).fillna(ranked["school_level"])
ranked = ranked.sort_values(sped_col, ascending=True)

if not ranked.empty:
    fig_ranked = px.bar(
        ranked,
        x=sped_col,
        y="school_name",
        orientation="h",
        color="school_level",
        title="Special Ed Membership % — All Schools, Ranked (TAPR 2025)",
        labels={sped_col: "Special Ed % of Membership", "school_name": ""},
        height=max(400, len(ranked) * 14),
        category_orders={"school_level": [LEVEL_LABELS.get(l, l) for l in LEVEL_ORDER]},
    )
    fig_ranked.add_annotation(
        text="Source: TEA TAPR 2025",
        xref="paper", yref="paper", x=1, y=-0.05,
        showarrow=False, font=dict(size=10, color="#888888"), xanchor="right",
    )
    st.plotly_chart(fig_ranked, use_container_width=True)

# ── Section 3: Attendance Disparity ──────────────────────────────────────────

st.divider()
st.subheader("Attendance Disparity: All Students vs. Special Education (TAPR 2024)")
st.caption(
    "Source: TEA TAPR 2025 release; attendance measures are for year 2024. "
    "A positive gap means special-ed students have a lower attendance rate than all students. "
    "Null where either measure was suppressed."
)

att_all = "tapr_att_all_rate_2024"
att_sped = "tapr_att_sped_rate_2024"

gap_df = df[["school_name", att_all, att_sped, "school_level"]].dropna(
    subset=[att_all, att_sped]
).copy()
gap_df["Attendance Gap (All minus SpEd)"] = gap_df[att_all] - gap_df[att_sped]
gap_df["school_level"] = gap_df["school_level"].map(LEVEL_LABELS).fillna(gap_df["school_level"])
gap_df = gap_df.sort_values("Attendance Gap (All minus SpEd)", ascending=False)

if not gap_df.empty:
    fig_gap = px.bar(
        gap_df,
        x="Attendance Gap (All minus SpEd)",
        y="school_name",
        orientation="h",
        color="school_level",
        title="Attendance Rate Gap (All Students minus Special Ed) — TAPR 2024",
        labels={"school_name": "", "Attendance Gap (All minus SpEd)": "Gap (percentage points)"},
        height=max(380, len(gap_df) * 14),
        category_orders={"school_level": [LEVEL_LABELS.get(l, l) for l in LEVEL_ORDER]},
    )
    fig_gap.add_vline(x=0, line_dash="dash", line_color="#888888")
    fig_gap.add_annotation(
        text="Source: TEA TAPR 2025 release, measure year 2024",
        xref="paper", yref="paper", x=1, y=-0.05,
        showarrow=False, font=dict(size=10, color="#888888"), xanchor="right",
    )
    st.plotly_chart(fig_gap, use_container_width=True)

    n_gap_pos = int((gap_df["Attendance Gap (All minus SpEd)"] > 0).sum())
    med_gap = gap_df["Attendance Gap (All minus SpEd)"].median()
    st.caption(
        f"In **{n_gap_pos}** of {len(gap_df)} schools with data, "
        "special-ed attendance is lower than all-student attendance. "
        f"Cohort median gap: **{med_gap:.1f} percentage points**."
    )
else:
    st.info("Attendance disparity data not available.")

# ── Section 4: CRDC IDEA Enrollment ──────────────────────────────────────────

st.divider()
st.subheader("CRDC: IDEA Enrollment Count (2021-22)")
st.caption(
    "Source: CRDC 2021-22. Raw enrollment counts — not comparable to current-year TAPR rates. "
    "CRDC sentinel -9 mapped to null. Zero is a real reported zero."
)

idea_col = "crdc_idea_enr_total_2122"
null_note(idea_col, df[idea_col].isna().sum(), n, friendly_name="IDEA Enrollment (CRDC 2021-22)")

distribution_histogram(
    df,
    col=idea_col,
    title="IDEA Enrollment Count per School (CRDC 2021-22)",
    source_label="CRDC 2021-22",
    xaxis_title="IDEA Students Enrolled",
    nbins=15,
    height=320,
)

# ── Section 5: Disability Discipline Counts ────────────────────────────────────

st.divider()
st.subheader("CRDC: Disability-Related Discipline Counts (2021-22)")
st.warning(
    "These are **raw counts**, not rates. Schools vary in size. "
    "Comparing counts across schools without normalizing by IDEA enrollment is misleading. "
    "Null does not mean zero — it means the figure was not reported or not applicable."
)

DISCIPLINE_COLS: dict[str, str] = {
    "crdc_idea_iss_students_total_2122": "IDEA Students — In-School Suspension (ISS)",
    "crdc_oos_instances_idea_2122": "IDEA Students — Out-of-School Suspension Instances",
    "crdc_idea_sing_oos_total_2122": "IDEA — Single OOS Suspension",
    "crdc_idea_mult_oos_total_2122": "IDEA — Multiple OOS Suspensions",
    "crdc_idea_exp_with_svc_total_2122": "IDEA Expulsions With Services",
    "crdc_idea_exp_no_svc_total_2122": "IDEA Expulsions Without Services",
    "crdc_idea_exp_zerotol_total_2122": "IDEA Zero-Tolerance Expulsions",
}

disc_tabs = st.tabs(list(DISCIPLINE_COLS.values()))
for tab, (col, label) in zip(disc_tabs, DISCIPLINE_COLS.items()):
    with tab:
        if col not in df.columns:
            st.info(f"Data for **{label}** is not in the current dataset.")
            continue
        null_note(col, df[col].isna().sum(), n, friendly_name=label)
        plot_df = (
            df[["school_name", col]]
            .dropna(subset=[col])
            .sort_values(col, ascending=True)
        )
        if plot_df.empty:
            st.info("All values null — no reported data for this measure.")
            continue
        n_nonzero = int((plot_df[col] > 0).sum())
        fig = px.bar(
            plot_df,
            x=col,
            y="school_name",
            orientation="h",
            title=f"{label} — Per School (CRDC 2021-22)",
            labels={col: "Count", "school_name": ""},
            height=max(380, len(plot_df) * 14),
        )
        fig.add_annotation(
            text="Source: CRDC 2021-22",
            xref="paper", yref="paper", x=1, y=-0.08,
            showarrow=False, font=dict(size=10, color="#888888"), xanchor="right",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"{n_nonzero} of {len(plot_df)} schools with data reported at least one incident. "
            f"{n - len(plot_df)} school{'s' if n - len(plot_df) != 1 else ''} "
            "had no reported value for this measure."
        )

# ── Section 6: Restraint and Seclusion ────────────────────────────────────────

st.divider()
st.subheader("CRDC: Restraint and Seclusion — IDEA Students (2021-22)")
st.caption(
    "Source: CRDC 2021-22. Instance counts (not student counts). "
    "Null = not reported or not applicable. Zero = reported zero instances."
)

RS_COLS: dict[str, str] = {
    "crdc_rs_mech_instances_idea_2122": "Mechanical Restraint Instances",
    "crdc_rs_phys_instances_idea_2122": "Physical Restraint Instances",
    "crdc_rs_secl_instances_idea_2122": "Seclusion Instances",
}

rs_tabs = st.tabs(list(RS_COLS.values()))
for tab, (col, label) in zip(rs_tabs, RS_COLS.items()):
    with tab:
        if col not in df.columns:
            st.info(f"Data for **{label}** is not in the current dataset.")
            continue
        null_note(col, df[col].isna().sum(), n, friendly_name=label)
        plot_df = (
            df[["school_name", col]]
            .dropna(subset=[col])
            .sort_values(col, ascending=True)
        )
        if plot_df.empty:
            st.info("All values null for this measure.")
            continue
        fig = px.bar(
            plot_df,
            x=col,
            y="school_name",
            orientation="h",
            title=f"{label} per School (CRDC 2021-22)",
            labels={col: "Instances", "school_name": ""},
            height=max(360, len(plot_df) * 14),
        )
        fig.add_annotation(
            text="Source: CRDC 2021-22",
            xref="paper", yref="paper", x=1, y=-0.08,
            showarrow=False, font=dict(size=10, color="#888888"), xanchor="right",
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Section 7: Harassment ─────────────────────────────────────────────────────

st.divider()
st.subheader("CRDC: Harassment and Bullying — Disability Basis (2021-22)")
st.caption(
    "Source: CRDC 2021-22. "
    "'Allegations' = formal allegations filed by the school. "
    "'Students reported' = students reported as having been harassed. "
    "'Students disciplined' = alleged harassers who received disciplinary action. "
    "Null = not reported. Zero = reported zero incidents."
)

HB_COLS: dict[str, str] = {
    "crdc_hb_dis_allegations_2122": "Harassment Allegations (Disability Basis)",
    "crdc_hb_dis_reported_total_2122": "Students Reported as Harassed",
    "crdc_hb_dis_disciplined_total_2122": "Alleged Harassers Disciplined",
}

for col, label in HB_COLS.items():
    if col not in df.columns:
        continue
    null_note(col, df[col].isna().sum(), n, friendly_name=label)
    plot_df = (
        df[["school_name", col]]
        .dropna(subset=[col])
        .sort_values(col, ascending=True)
    )
    if plot_df.empty:
        st.info(f"All values null for **{label}**.")
        continue
    with st.expander(label, expanded=False):
        fig = px.bar(
            plot_df,
            x=col,
            y="school_name",
            orientation="h",
            title=f"{label} per School (CRDC 2021-22)",
            labels={col: "Count", "school_name": ""},
            height=max(340, len(plot_df) * 14),
        )
        fig.add_annotation(
            text="Source: CRDC 2021-22",
            xref="paper", yref="paper", x=1, y=-0.08,
            showarrow=False, font=dict(size=10, color="#888888"), xanchor="right",
        )
        st.plotly_chart(fig, use_container_width=True)
