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
from data_loader import load_data


@st.cache_data(ttl=300, show_spinner="Loading school data…")
def get_data():
    return load_data()


try:
    df, source = get_data()
except Exception as exc:
    st.error(f"Failed to load data: {exc}")
    st.stop()

# ── Header ─────────────────────────────────────────────────────────────────────

st.title("SchoolPath Dallas")
st.caption(
    "An analytical view of **60 Dallas public schools** across special education,"
    " culture, and safety dimensions."
)
source_badge(source)

# ── KPI row ────────────────────────────────────────────────────────────────────

total = len(df)
n_isd = int((df["operator_type"] == "isd").sum())
n_charter = int((df["operator_type"] == "charter").sum())
med_enr = df["enrollment"].median()
n_ab = int(df["accountability_rating_2025"].isin(["A", "B"]).sum())
ab_pct = n_ab / total * 100 if total else 0.0
med_sped = df["tapr_membership_sped_pct_2025"].median()
med_att = df["tapr_att_all_rate_2024"].median()

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric("Total Schools", total, help="60-school Dallas cohort (AskTED 2025)")
with c2:
    st.metric(
        "ISD / Charter",
        f"{n_isd} / {n_charter}",
        help="Independent school district vs. open-enrollment charter",
    )
with c3:
    st.metric(
        "Median Enrollment",
        f"{int(med_enr):,}" if pd.notna(med_enr) else "—",
        help="October 2025 enrollment (AskTED)",
    )
with c4:
    st.metric(
        "A / B Accountability",
        f"{ab_pct:.0f}%",
        help=f"{n_ab} of {total} schools rated A or B (TEA 2025)",
    )
with c5:
    st.metric(
        "Median Special Ed %",
        f"{med_sped:.1f}%" if pd.notna(med_sped) else "—",
        help="Special-ed membership as % of all membership — TAPR 2025",
    )
with c6:
    st.metric(
        "Median Attendance",
        f"{med_att:.1f}%" if pd.notna(med_att) else "—",
        help="All-student attendance rate — TAPR 2024",
    )

st.divider()

# ── Side-by-side: rating chart + map ──────────────────────────────────────────

col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("Accountability Rating Distribution")
    st.caption("TEA 2025. “Not Rated” is a real TEA designation, not missing data.")

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
        height=300,
    )
    fig_rating.update_traces(textposition="outside")
    fig_rating.update_layout(
        showlegend=False,
        margin=dict(l=0, r=40, t=10, b=40),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=list(reversed(RATING_ORDER)),
        ),
        xaxis_title="Number of Schools",
    )
    fig_rating.add_annotation(
        text="Source: TEA 2025 Campus Accountability",
        xref="paper", yref="paper", x=1, y=-0.18,
        showarrow=False, font=dict(size=10, color="#888888"), xanchor="right",
    )
    st.plotly_chart(fig_rating, use_container_width=True)

with col_right:
    st.subheader("School Locations")
    st.caption(
        "Color = TEA 2025 accountability rating."
        " Coordinates: TEA ArcGIS Schools 2024-25 (geocoder output, display only)."
    )
    scatter_map(
        df,
        title=None,
        source_label="TEA ArcGIS 2024-25 | TEA Accountability 2025",
        hover_cols=["district_name", "school_level", "enrollment"],
        height=320,
    )

st.divider()

# ── What this dashboard answers ───────────────────────────────────────────────

st.subheader("What This Dashboard Answers")
st.markdown(
    """
- **Special education access:** Which schools serve the highest proportion of students with
  disabilities, and how do CRDC-reported discipline, restraint, and harassment counts vary
  across the cohort?
- **Attendance and chronic absence:** How do attendance and chronic-absence rates compare
  across school levels and operator types?
- **Culture and safety indicators:** What do attendance, chronic absence, discipline counts,
  and staffing data suggest about school environment — and what is the data unable to answer?
- **School-level detail:** What is the complete data profile for a single school, including
  documented gaps, source years, and null reasons?
"""
)

st.divider()

# ── Data sources and limitations (expandable) ─────────────────────────────────

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
- **“Not Rated” is a real TEA designation** used for new schools, DAEP campuses, and other
  exempt categories. It is not missing data.
- **No campus-level climate survey data** was available for this cohort. The Culture & Safety
  page uses attendance, chronic absence, and discipline counts as proxy indicators only.
- **2 of 60 schools** (NCES IDs 481623022813 and 480021123204) had no CRDC match;
  all CRDC columns are null for those two rows.
- **Coordinates** are geocoder output from TEA ArcGIS Schools 2024-25, suitable for display
  and approximate mapping only.
"""
    )
