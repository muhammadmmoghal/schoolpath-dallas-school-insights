"""
School Explorer — filters, map, and sortable school table.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from components import (
    LEVEL_LABELS,
    LEVEL_ORDER,
    OPERATOR_LABELS,
    RATING_COLORS,
    RATING_ORDER,
    metric_card,
    scatter_map,
    source_badge,
)
from data_loader import load_data

st.title("School Explorer")

# ── Load data ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Loading school data…")
def get_data():
    return load_data()


try:
    df, source = get_data()
except Exception as exc:
    st.error(f"Failed to load data: {exc}")
    st.stop()

source_badge(source)

# ── Summary cards ─────────────────────────────────────────────────────────────

total = len(df)
n_charter = int((df["operator_type"] == "charter").sum())
n_isd = int((df["operator_type"] == "isd").sum())
med_enr = int(df["enrollment"].median()) if df["enrollment"].notna().any() else None

rated = df["accountability_rating_2025"].isin(["A", "B"])
n_ab = int(rated.sum())
ab_pct = f"{n_ab / total * 100:.0f}%" if total else "—"

c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Total Schools", total, "60-school Dallas cohort (AskTED 2025)")
with c2:
    metric_card(
        "ISD / Charter",
        f"{n_isd} / {n_charter}",
        "Independent school district vs. open-enrollment charter",
    )
with c3:
    metric_card(
        "Median Enrollment",
        f"{med_enr:,}" if med_enr is not None else "—",
        "Enrollment as of October 2025 (AskTED)",
    )
with c4:
    metric_card(
        "A / B Accountability",
        ab_pct,
        "Share of schools rated A or B (TEA 2025)",
    )

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────

st.subheader("Filters")

# Build display-value ↔ raw-value maps so the UI shows friendly names
_level_display = {
    raw: LEVEL_LABELS.get(raw, raw.title())
    for raw in sorted(df["school_level"].dropna().unique(),
                      key=lambda x: LEVEL_ORDER.index(x) if x in LEVEL_ORDER else 99)
}
_level_display_to_raw = {v: k for k, v in _level_display.items()}
level_options = list(_level_display.values())

_op_display = {raw: OPERATOR_LABELS.get(raw, raw.title())
               for raw in sorted(df["operator_type"].dropna().unique())}
_op_display_to_raw = {v: k for k, v in _op_display.items()}
op_options = list(_op_display.values())

ratings_available = [r for r in RATING_ORDER if r in df["accountability_rating_2025"].values]

enr_min = int(df["enrollment"].min())
enr_max = int(df["enrollment"].max())

col_a, col_b, col_c, col_d = st.columns(4)

with col_a:
    sel_levels_display = st.multiselect(
        "School Level", level_options, default=level_options
    )
    sel_levels = [_level_display_to_raw[x] for x in sel_levels_display]

with col_b:
    sel_ops_display = st.multiselect(
        "Operator Type", op_options, default=op_options
    )
    sel_ops = [_op_display_to_raw[x] for x in sel_ops_display]

with col_c:
    sel_ratings = st.multiselect(
        "Accountability Rating (2025)", ratings_available, default=ratings_available
    )

with col_d:
    sel_enr = st.slider(
        "Enrollment",
        min_value=enr_min,
        max_value=enr_max,
        value=(enr_min, enr_max),
        help="October 2025 enrollment (AskTED)",
    )

mask = (
    df["school_level"].isin(sel_levels)
    & df["operator_type"].isin(sel_ops)
    & df["accountability_rating_2025"].isin(sel_ratings)
    & df["enrollment"].between(sel_enr[0], sel_enr[1])
)
filtered = df[mask].copy()

st.caption(f"Showing **{len(filtered)}** of {total} schools after filters.")

if filtered.empty:
    st.warning("No schools match the current filters.")
    st.stop()

st.divider()

# ── Map ───────────────────────────────────────────────────────────────────────

st.subheader("Dallas School Map")
st.caption(
    "Color = TEA 2025 accountability rating. "
    "Coordinates: TEA ArcGIS Schools 2024-25 (geocoder output, display only)."
)

scatter_map(
    filtered,
    title=None,
    source_label="TEA ArcGIS 2024-25 | TEA Accountability 2025",
    hover_cols=["district_name", "school_level", "operator_type", "enrollment"],
)

st.divider()

# ── Sortable table ────────────────────────────────────────────────────────────

st.subheader("School Comparison Table")
st.caption("Sources: AskTED 2025 | TAPR 2025 | TEA Accountability 2025")

# Default columns with plain-English headers
DEFAULT_COL_MAP: dict[str, str] = {
    "school_name": "School",
    "district_name": "District / Operator",
    "school_level": "School Level",
    "operator_type": "Operator Type",
    "enrollment": "Enrollment",
    "accountability_rating_2025": "Accountability Rating",
    "accountability_score_2025": "Score",
    "tapr_membership_sped_pct_2025": "Special Ed %",
    "tapr_att_all_rate_2024": "Attendance %",
    "tapr_chronic_abs_all_rate_2024": "Chronic Absence %",
}

# Optional extra columns
OPTIONAL_COL_MAP: dict[str, str] = {
    "tapr_membership_sped_count_2025": "Special Ed Count",
    "crdc_idea_enr_total_2122": "IDEA Enrollment (CRDC 2021-22)",
    "tapr_avg_teacher_exp_years_2025": "Avg. Teacher Experience (yrs)",
    "tapr_beginning_teacher_fte_pct_2025": "Beginning Teachers (%)",
    "grade_range": "Grade Range",
    "magnet_status": "Magnet Status",
    "acct_grade_span_2025": "Grade Span (Accountability)",
}

with st.expander("Add optional columns"):
    available_optional = {
        label: col
        for col, label in OPTIONAL_COL_MAP.items()
        if col in filtered.columns
    }
    sel_optional_labels = st.multiselect(
        "Optional columns", list(available_optional.keys()), default=[]
    )
    sel_optional_cols = {available_optional[lbl]: lbl for lbl in sel_optional_labels}

# Build display DataFrame
present_default = {col: lbl for col, lbl in DEFAULT_COL_MAP.items() if col in filtered.columns}
all_col_map = {**present_default, **sel_optional_cols}

display = filtered[list(all_col_map.keys())].copy()

# Apply friendly labels to categorical columns
display["school_level"] = display["school_level"].map(LEVEL_LABELS).fillna(display["school_level"])
display["operator_type"] = display["operator_type"].map(OPERATOR_LABELS).fillna(display["operator_type"])

display = display.rename(columns=all_col_map)

# Round floats for readability
for col in display.select_dtypes(include="float").columns:
    display[col] = display[col].round(1)

# Sort controls
sort_options = list(all_col_map.values())
default_sort = "Enrollment" if "Enrollment" in sort_options else sort_options[0]
sort_col_ui, sort_dir_ui = st.columns([3, 1])
with sort_col_ui:
    sort_col = st.selectbox("Sort by", sort_options, index=sort_options.index(default_sort))
with sort_dir_ui:
    sort_asc = st.checkbox("Ascending", value=False)

display = display.sort_values(sort_col, ascending=sort_asc, na_position="last")

# Column configuration for Streamlit dataframe
col_cfg: dict = {}
if "Enrollment" in display.columns:
    col_cfg["Enrollment"] = st.column_config.NumberColumn("Enrollment (Oct 2025)", format="%d")
if "Score" in display.columns:
    col_cfg["Score"] = st.column_config.NumberColumn("Score (2025)", format="%d")
if "Special Ed %" in display.columns:
    col_cfg["Special Ed %"] = st.column_config.NumberColumn("Special Ed % (TAPR 2025)", format="%.1f")
if "Attendance %" in display.columns:
    col_cfg["Attendance %"] = st.column_config.NumberColumn("Attendance % (TAPR 2024)", format="%.1f")
if "Chronic Absence %" in display.columns:
    col_cfg["Chronic Absence %"] = st.column_config.NumberColumn("Chronic Abs % (TAPR 2024)", format="%.1f")

st.dataframe(
    display,
    column_config=col_cfg,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "**Note:** Empty cells indicate unreported or suppressed values — not zero. "
    "Accountability Score is the numeric TEA campus score; Rating is the letter grade."
)
