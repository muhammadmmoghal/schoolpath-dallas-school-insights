"""
Culture & Safety Indicators — attendance, chronic absence, discipline,
and staffing as administrative proxies for school environment.
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
    RATING_COLORS,
    RATING_ORDER,
    box_plot,
    distribution_histogram,
    null_note,
    source_badge,
)
from data_loader import load_data
from styles import (
    inject_global_styles,
    render_page_header,
    render_card_header,
    render_caveat_card,
)

inject_global_styles()

render_page_header(
    "Culture & Safety Indicators",
    subtitle="Attendance, chronic absence, discipline, and staffing as administrative proxies.",
)

render_caveat_card(
    heading="Data limitation",
    content=(
        "Attendance, chronic absence, discipline counts, and staffing stability are "
        "administrative indicators of school environment — not direct measures of school "
        "culture or safety.  \n"
        "**No public campus-level climate survey data** (student satisfaction, staff "
        "satisfaction, PEARS incidents) was available for this cohort.  \n"
        "Patterns in these indicators may reflect many factors beyond school culture. "
        "Causal inferences should not be drawn."
    ),
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

att_col = "tapr_att_all_rate_2024"
ca_col  = "tapr_chronic_abs_all_rate_2024"
exp_col = "tapr_avg_teacher_exp_years_2025"

med_att = df[att_col].median()
med_ca  = df[ca_col].median()
med_exp = df[exp_col].median()

st.divider()

att_threshold = st.slider(
    "Attendance threshold — highlight schools below (%)",
    min_value=80, max_value=99, value=95, step=1,
    help="Adjust to see how many schools fall below a given attendance rate.",
)
n_below_threshold = int((df[att_col] < att_threshold).sum())

with st.container(border=True):
    render_card_header("Key Metrics", caption="TAPR 2024 (attendance) | TAPR 2025 (staffing)")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric(
            "Median Attendance",
            f"{med_att:.1f}%" if pd.notna(med_att) else "—",
            help="All-student attendance rate — TAPR 2024",
        )
    with k2:
        st.metric(
            "Median Chronic Absence",
            f"{med_ca:.1f}%" if pd.notna(med_ca) else "—",
            help="All-student chronic-absence rate — TAPR 2024",
        )
    with k3:
        st.metric(
            f"Below {att_threshold}% Attendance",
            n_below_threshold,
            help=f"Schools with all-student attendance rate below {att_threshold}%",
        )
    with k4:
        st.metric(
            "Median Teacher Experience",
            f"{med_exp:.1f} yrs" if pd.notna(med_exp) else "—",
            help="Average years of teaching experience — TAPR 2025",
        )

# ── Section 2: Attendance ─────────────────────────────────────────────────────

st.divider()
with st.container(border=True):
    render_card_header(
        "Attendance Rate (TAPR 2024)",
        caption=(
            "Source: TEA TAPR 2025 release; measure year is 2024. "
            "Rate = days present ÷ days membership × 100. TEA masking codes converted to null."
        ),
    )

    att_sped_col = "tapr_att_sped_rate_2024"
    null_note(att_col, df[att_col].isna().sum(), n, friendly_name="All-Student Attendance Rate")

    col1, col2 = st.columns(2)
    with col1:
        distribution_histogram(
            df, col=att_col,
            title="All-Student Attendance Rate",
            source_label="TEA TAPR 2024",
            xaxis_title="Attendance Rate (%)",
            nbins=12, height=310,
        )
    with col2:
        distribution_histogram(
            df, col=att_sped_col,
            title="Special-Ed Attendance Rate",
            source_label="TEA TAPR 2024",
            xaxis_title="Special Ed Attendance Rate (%)",
            nbins=12, height=310,
        )

    att_level_df = df[[att_col, "school_level"]].copy()
    att_level_df["school_level"] = att_level_df["school_level"].map(LEVEL_LABELS).fillna(att_level_df["school_level"])
    level_cat = [LEVEL_LABELS.get(l, l) for l in LEVEL_ORDER if LEVEL_LABELS.get(l, l) in att_level_df["school_level"].values]
    box_plot(
        att_level_df,
        x="school_level", y=att_col,
        title="All-Student Attendance Rate by School Level (TAPR 2024)",
        source_label="TEA TAPR 2024",
        category_orders={"school_level": level_cat},
        height=350,
    )

    if pd.notna(med_att):
        att_valid = df[att_col].dropna()
        st.caption(
            f"Cohort median attendance: **{med_att:.1f}%**. "
            f"Range: {att_valid.min():.1f}% – {att_valid.max():.1f}%. "
            f"**{n_below_threshold}** school{'s' if n_below_threshold != 1 else ''} "
            f"fall below {att_threshold}%."
        )

    plot_scatter = df[["school_name", att_col, ca_col, "school_level", "operator_type"]].dropna(
        subset=[att_col, ca_col]
    ).copy()
    plot_scatter["school_level"] = plot_scatter["school_level"].map(LEVEL_LABELS).fillna(plot_scatter["school_level"])

    if not plot_scatter.empty:
        fig_scatter = px.scatter(
            plot_scatter,
            x=att_col, y=ca_col,
            color="school_level",
            hover_name="school_name",
            hover_data={"operator_type": True},
            title="Attendance Rate vs. Chronic Absence Rate (TAPR 2024)",
            labels={
                att_col: "All-Student Attendance Rate (%)",
                ca_col:  "Chronic Absence Rate (%)",
            },
            category_orders={"school_level": [LEVEL_LABELS.get(l, l) for l in LEVEL_ORDER]},
            height=390,
        )
        fig_scatter.update_layout(
            font=dict(family="'DM Sans', 'Inter', sans-serif", size=12, color="#334155"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        fig_scatter.add_annotation(
            text="Source: TEA TAPR 2025 release, measure year 2024",
            xref="paper", yref="paper", x=1, y=-0.12,
            showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# ── Section 3: Chronic Absence ────────────────────────────────────────────────

st.divider()
with st.container(border=True):
    render_card_header(
        "Chronic Absence Rate (TAPR 2024)",
        caption=(
            "Chronic absence = student present fewer than 90% of enrolled days. "
            "Higher rate = more students chronically absent."
        ),
    )

    ca_sped_col = "tapr_chronic_abs_sped_rate_2024"
    null_note(ca_col, df[ca_col].isna().sum(), n, friendly_name="All-Student Chronic Absence Rate")

    col3, col4 = st.columns(2)
    with col3:
        distribution_histogram(
            df, col=ca_col,
            title="All-Student Chronic Absence Rate",
            source_label="TEA TAPR 2024",
            xaxis_title="Chronic Absence Rate (%)",
            nbins=12, height=310,
        )
    with col4:
        distribution_histogram(
            df, col=ca_sped_col,
            title="Special-Ed Chronic Absence Rate",
            source_label="TEA TAPR 2024",
            xaxis_title="Special Ed Chronic Abs Rate (%)",
            nbins=12, height=310,
        )

    if pd.notna(med_ca):
        ca_valid  = df[ca_col].dropna()
        n_high_ca = int((ca_valid > 20).sum())
        st.caption(
            f"Cohort median chronic absence: **{med_ca:.1f}%**. "
            f"Range: {ca_valid.min():.1f}% – {ca_valid.max():.1f}%. "
            f"{n_high_ca} school{'s' if n_high_ca != 1 else ''} exceed 20% chronic absence."
        )

# ── Section 4: Discipline ─────────────────────────────────────────────────────

st.divider()
with st.container(border=True):
    render_card_header(
        "Out-of-School Suspension Instances by Disability Status (CRDC 2021-22)",
        caption="Historical data. Instance counts, not rates or student counts.",
    )
    st.warning(
        "Data from 2021-22 (historical). These are **instance counts**, not student counts or rates. "
        "Do not compare directly with current-year TAPR figures. "
        "**2 of 60 schools** have no CRDC data. "
        "Null does not mean zero — it means the figure was not reported."
    )

    OOS_COLS: dict[str, str] = {
        "crdc_oos_instances_no_dis_2122": "Students Without Disabilities",
        "crdc_oos_instances_idea_2122":   "IDEA Students",
        "crdc_oos_instances_504_2122":    "Section 504 Students",
    }

    oos_tabs = st.tabs(list(OOS_COLS.values()))
    for tab, (col, label) in zip(oos_tabs, OOS_COLS.items()):
        with tab:
            if col not in df.columns:
                st.info(f"Data for **{label}** is not available in the current dataset.")
                continue
            null_note(col, df[col].isna().sum(), n, friendly_name=f"OOS Instances — {label}")
            plot_df = df[["school_name", col, "school_level"]].dropna(subset=[col]).copy()
            if plot_df.empty:
                st.info("All values null for this measure.")
                continue
            plot_df["school_level"] = plot_df["school_level"].map(LEVEL_LABELS).fillna(plot_df["school_level"])
            plot_df = plot_df.sort_values(col, ascending=True)
            fig = px.bar(
                plot_df,
                x=col, y="school_name",
                color="school_level",
                orientation="h",
                title=f"OOS Suspension Instances — {label} (CRDC 2021-22)",
                labels={col: "Instances", "school_name": ""},
                height=max(380, len(plot_df) * 14),
                category_orders={"school_level": [LEVEL_LABELS.get(l, l) for l in LEVEL_ORDER]},
            )
            fig.update_layout(
                font=dict(family="'DM Sans', 'Inter', sans-serif", size=12, color="#334155"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            fig.add_annotation(
                text="Source: CRDC 2021-22",
                xref="paper", yref="paper", x=1, y=-0.08,
                showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right",
            )
            st.plotly_chart(fig, use_container_width=True)

    with st.expander("Law Enforcement Referrals and Offense Incidents (CRDC 2021-22)", expanded=False):
        st.caption("Source: CRDC 2021-22 — Referrals & Arrests and Offenses files.")
        REF_OFF_COLS: dict[str, str] = {
            "crdc_idea_ref_law_total_2122":     "IDEA Students — Law Enforcement Referrals",
            "crdc_idea_arr_total_2122":         "IDEA Students — Arrested",
            "crdc_offense_assault_with_wpn_2122":"Assault With Weapon Incidents",
            "crdc_offense_assault_no_wpn_2122": "Assault Without Weapon Incidents",
            "crdc_offense_wpn_possession_2122": "Weapon Possession Incidents",
        }
        for col, label in REF_OFF_COLS.items():
            if col not in df.columns:
                continue
            n_nonzero = int((df[col].dropna() > 0).sum())
            n_null    = int(df[col].isna().sum())
            st.write(
                f"**{label}:** {n_nonzero} school{'s' if n_nonzero != 1 else ''} reported "
                f"more than zero; {n_null} school{'s' if n_null != 1 else ''} had no "
                "reported value."
            )

# ── Section 5: Teacher Staffing ───────────────────────────────────────────────

st.divider()
with st.container(border=True):
    render_card_header(
        "Teacher Staffing Context (TAPR 2025)",
        caption=(
            "Staffing data contextualizes school environment — not a direct measure of quality. "
            "District tenure = years with this district, not total career."
        ),
    )

    STAFF_COLS: dict[str, str] = {
        "tapr_avg_teacher_exp_years_2025":    "Avg. Teacher Experience (yrs)",
        "tapr_avg_teacher_tenure_years_2025": "Avg. District Tenure (yrs)",
        "tapr_beginning_teacher_fte_pct_2025":"Beginning Teachers (FTE %)",
    }

    col5, col6, col7 = st.columns(3)
    for col_st, (col, label) in zip([col5, col6, col7], STAFF_COLS.items()):
        with col_st:
            valid = df[col].dropna()
            if valid.empty:
                st.metric(label, "—")
            else:
                st.metric(label, f"{valid.median():.1f}", help=f"Median across {len(valid)} schools with data")

    EXP_BANDS: list[tuple[str, str]] = [
        ("tapr_beginning_teacher_fte_pct_2025", "Beginning (<1 yr)"),
        ("tapr_teacher_1to5yr_pct_2025",        "1–5 Years"),
        ("tapr_teacher_6to10yr_pct_2025",       "6–10 Years"),
        ("tapr_teacher_11to20yr_pct_2025",      "11–20 Years"),
        ("tapr_teacher_21to30yr_pct_2025",      "21–30 Years"),
        ("tapr_teacher_over30yr_pct_2025",      "Over 30 Years"),
    ]

    band_cols_present = [c for c, _ in EXP_BANDS if c in df.columns]
    if band_cols_present:
        band_labels = {c: lbl for c, lbl in EXP_BANDS}
        band_df = df[["school_name"] + band_cols_present].dropna(subset=band_cols_present, how="all")
        if not band_df.empty:
            melted = band_df.melt(
                id_vars="school_name",
                value_vars=band_cols_present,
                var_name="Experience Band",
                value_name="FTE %",
            )
            melted["Experience Band"] = melted["Experience Band"].map(band_labels)
            melted = melted.dropna(subset=["FTE %"])
            if not melted.empty:
                fig_bands = px.bar(
                    melted,
                    x="school_name", y="FTE %",
                    color="Experience Band",
                    title="Teacher Experience Band Distribution per School (TAPR 2025)",
                    labels={"school_name": ""},
                    barmode="stack",
                    height=440,
                    category_orders={"Experience Band": [lbl for _, lbl in EXP_BANDS]},
                )
                fig_bands.update_xaxes(tickangle=45)
                fig_bands.update_layout(
                    font=dict(family="'DM Sans', 'Inter', sans-serif", size=12, color="#334155"),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                fig_bands.add_annotation(
                    text="Source: TEA TAPR 2025",
                    xref="paper", yref="paper", x=1, y=-0.25,
                    showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right",
                )
                st.plotly_chart(fig_bands, use_container_width=True)

                if pd.notna(med_exp):
                    beg_valid = df["tapr_beginning_teacher_fte_pct_2025"].dropna()
                    med_beg   = beg_valid.median()
                    st.caption(
                        f"Cohort median teacher experience: **{med_exp:.1f} years**. "
                        f"Median share of beginning teachers (< 1 year experience): "
                        f"**{med_beg:.1f}%**."
                    )

# ── Section 6: Accountability as Context ─────────────────────────────────────

st.divider()
with st.container(border=True):
    render_card_header(
        "Accountability Rating — For Context Only (TEA 2025)",
        caption="Not a direct measure of school culture or safety. 'Not Rated' is a real TEA designation.",
    )

    rating_counts = (
        df["accountability_rating_2025"]
        .value_counts()
        .reindex(RATING_ORDER)
        .dropna()
        .reset_index()
    )
    rating_counts.columns = ["Rating", "Schools"]

    fig_rate = px.bar(
        rating_counts,
        x="Rating", y="Schools",
        color="Rating",
        color_discrete_map=RATING_COLORS,
        title="Accountability Rating Distribution — 60 Schools (TEA 2025)",
        height=330,
    )
    fig_rate.update_layout(
        showlegend=False,
        font=dict(family="'DM Sans', 'Inter', sans-serif", size=12, color="#334155"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig_rate.add_annotation(
        text="Source: TEA 2025 Campus Accountability Summary",
        xref="paper", yref="paper", x=1, y=-0.12,
        showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right",
    )
    st.plotly_chart(fig_rate, use_container_width=True)
