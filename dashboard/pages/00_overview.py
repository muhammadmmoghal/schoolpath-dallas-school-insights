"""
Overview page — executive summary of the SchoolPath Dallas dataset.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from components import RATING_COLORS, RATING_ORDER, scatter_map, source_badge
from data_loader import load_data, friendly_source_label
from styles import (
    inject_global_styles,
    render_overview_header,
    render_kpi_row,
    render_insight_grid,
    render_card_header,
)


@st.cache_data(ttl=300, show_spinner="Loading school data…")
def get_data():
    return load_data()


inject_global_styles()

try:
    df, source = get_data()
except Exception as exc:
    st.error(f"Failed to load data: {exc}")
    st.stop()

# ── Overview header (white card with green left accent) ───────────────────────

_friendly = friendly_source_label(source)
_src_icon = "🟢" if "Supabase" in source else "🟡"

render_overview_header(
    subtitle="Dallas School Data Platform",
    source_icon=_src_icon,
    source_label=_friendly,
)

# ── KPI row — icon cards matching reference design ────────────────────────────

total     = len(df)
n_isd     = int((df["operator_type"] == "isd").sum())
n_charter = int((df["operator_type"] == "charter").sum())
med_enr   = df["enrollment"].median()
n_ab      = int(df["accountability_rating_2025"].isin(["A", "B"]).sum())
ab_pct    = n_ab / total * 100 if total else 0.0
med_sped  = df["tapr_membership_sped_pct_2025"].median()
med_att   = df["tapr_att_all_rate_2024"].median()

render_kpi_row([
    {
        "label":   "Total Schools",
        "value":   str(total),
        "desc":    "60-school Dallas cohort",
        "tooltip": "Number of schools included in the final Dallas cohort.",
    },
    {
        "label":   "ISD / Charter",
        "value":   f"{n_isd} / {n_charter}",
        "desc":    "Operator type split",
        "tooltip": "Breakdown of independent school district campuses versus charter schools in the cohort.",
    },
    {
        "label":   "Median Enrollment",
        "value":   f"{int(med_enr):,}" if pd.notna(med_enr) else "—",
        "desc":    "Oct 2025 · AskTED",
        "tooltip": "Median student enrollment across the 60 schools, based on the October 2025 AskTED enrollment field.",
    },
    {
        "label":   "A / B Rated",
        "value":   f"{ab_pct:.0f}%",
        "desc":    f"{n_ab} of {total} schools",
        "tooltip": "Percentage of cohort schools receiving an A or B in the 2025 TEA accountability ratings.",
    },
    {
        "label":   "Median SpEd %",
        "value":   f"{med_sped:.1f}%" if pd.notna(med_sped) else "—",
        "desc":    "TAPR 2025",
        "tooltip": "Median percentage of students receiving special education services, based on 2025 TAPR membership data.",
    },
    {
        "label":   "Median Attendance",
        "value":   f"{med_att:.1f}%" if pd.notna(med_att) else "—",
        "desc":    "All students · TAPR 2024",
        "tooltip": "Median all-student attendance rate across the cohort, based on the 2023–24 attendance measure published in the 2025 TAPR release.",
    },
])

st.divider()

# ── Rating chart + map ────────────────────────────────────────────────────────

col_left, col_right = st.columns([1, 2])

with col_left:
    with st.container(border=True):
        render_card_header(
            "Accountability Ratings",
            caption='TEA 2025. "Not Rated" is a real TEA designation.',
        )

        rating_counts = (
            df["accountability_rating_2025"]
            .value_counts()
            .reindex(RATING_ORDER)
            .dropna()
            .reset_index()
        )
        rating_counts.columns = ["Rating", "Schools"]

        fig_rating = px.bar(
            rating_counts,
            x="Schools",
            y="Rating",
            orientation="h",
            color="Rating",
            color_discrete_map=RATING_COLORS,
            text="Schools",
            height=290,
        )
        fig_rating.update_traces(textposition="outside")
        fig_rating.update_layout(
            showlegend=False,
            margin=dict(l=0, r=40, t=10, b=40),
            font=dict(family="'DM Sans', 'Inter', sans-serif", size=12, color="#3D4A5C"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(
                title="",
                categoryorder="array",
                categoryarray=list(reversed(RATING_ORDER)),
            ),
            xaxis_title="Number of Schools",
        )
        fig_rating.add_annotation(
            text="Source: TEA 2025 Campus Accountability",
            xref="paper", yref="paper", x=1, y=-0.2,
            showarrow=False, font=dict(size=10, color="#9AA5B4"), xanchor="right",
        )
        st.plotly_chart(fig_rating, use_container_width=True)

with col_right:
    with st.container(border=True):
        render_card_header(
            "School Locations",
            caption="Color = TEA 2025 accountability rating. Coordinates: TEA ArcGIS 2024-25.",
        )
        scatter_map(
            df,
            title=None,
            source_label="TEA ArcGIS 2024-25 | TEA Accountability 2025",
            hover_cols=["district_name", "school_level", "enrollment"],
            height=310,
        )

st.divider()

# ── What this dashboard answers ───────────────────────────────────────────────

with st.container(border=True):
    render_card_header("What This Dashboard Answers")
    render_insight_grid()

st.divider()

# ── Data sources and limitations ─────────────────────────────────────────────

with st.expander("Data Sources and Limitations", expanded=False):
    st.markdown(
        """
| Source | Purpose | Year | Coverage |
|---|---|---|---|
| TEA AskTED | School roster, enrollment, operator type | 2025 | 60 / 60 |
| TEA TAPR | Demographics, attendance, special-ed %, staffing | 2025 (attendance: 2024) | 60 / 60 |
| TEA Accountability | Overall campus rating (A–F / Not Rated) | 2025 | 60 / 60 |
| TEA ArcGIS Schools | Geographic coordinates | 2024-25 | 60 / 60 |
| CRDC | Disability-related discipline, enrollment, restraint, harassment | 2021-22 | 58 / 60 |

**Key caveats**

- **Null means unreported, not zero.** Suppressed, unavailable, or not-applicable values
  are shown as missing (not substituted with zero) throughout.
- **CRDC data are from 2021-22.** Do not compare CRDC discipline counts directly with
  current-year TAPR attendance or enrollment figures.
- **"Not Rated" is a real TEA designation** used for new schools, DAEP campuses, and other
  exempt categories. It is not missing data.
- **No campus-level climate survey data** was available for this cohort. The Culture & Safety
  page uses attendance, chronic absence, and discipline counts as proxy indicators only.
- **2 of 60 schools** (NCES IDs 481623022813 and 480021123204) had no CRDC match;
  all CRDC columns are null for those two rows.
- **Coordinates** are geocoder output from TEA ArcGIS Schools 2024-25, suitable for display
  and approximate mapping only.
"""
    )
