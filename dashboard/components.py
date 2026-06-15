"""
Reusable Streamlit UI components for the SchoolPath Dallas dashboard.
Visual styling is centralized in styles.py.
"""
from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from styles import inject_global_styles  # re-exported for backwards compatibility

RATING_ORDER = ["A", "B", "C", "D", "F", "Not Rated"]
RATING_COLORS = {
    "A": "#2ecc71",
    "B": "#27ae60",
    "C": "#f39c12",
    "D": "#e67e22",
    "F": "#e74c3c",
    "Not Rated": "#95a5a6",
}
LEVEL_ORDER = ["elementary", "middle", "high", "mixed"]
LEVEL_LABELS: dict[str, str] = {
    "elementary": "Elementary",
    "middle": "Middle",
    "high": "High School",
    "mixed": "Multi-Level",
}
OPERATOR_LABELS: dict[str, str] = {
    "isd": "Independent School District",
    "charter": "Charter School",
}


# Keep inject_global_css as an alias so any code that calls it keeps working.
def inject_global_css() -> None:
    inject_global_styles()


def fmt_value(val, fmt: str = "auto", unit: str = "") -> str:
    """
    Format a single value for display.
    - None / NaN / pd.NA  → "—"
    - 0 is explicitly preserved as "0" (never shown as null)
    - fmt="pct"   → "X.X%"
    - fmt="count" → "X,XXX"
    - fmt="float1"→ "X.X"
    - fmt="auto"  → best guess from type
    """
    if val is None:
        return "—"
    try:
        if pd.isna(val):
            return "—"
    except (TypeError, ValueError):
        pass
    try:
        fval = float(val)
        if math.isnan(fval):
            return "—"
    except (TypeError, ValueError):
        return str(val)

    if fmt == "pct":
        return f"{fval:.1f}%{(' ' + unit) if unit else ''}"
    if fmt == "count":
        return f"{int(fval):,}{(' ' + unit) if unit else ''}"
    if fmt == "float1":
        return f"{fval:.1f}{(' ' + unit) if unit else ''}"
    # auto
    if fval == int(fval) and abs(fval) < 1e9:
        return f"{int(fval):,}"
    return f"{fval:.1f}"


def source_badge(source: str, *, show_technical_expander: bool = False) -> None:
    """
    Render a compact source badge (plain / light-background variant).
    Also ensures global styles are injected.
    """
    inject_global_styles()
    from styles import render_source_badge
    render_source_badge(source)
    if show_technical_expander:
        with st.expander("Technical source details"):
            st.code(source)


def metric_card(label: str, value: str | int | float, help: str = "") -> None:
    st.metric(label=label, value=value, help=help or None)


def null_note(col_name: str, n_null: int, total: int, friendly_name: str = "") -> None:
    if n_null > 0:
        pct = n_null / total * 100
        display_name = friendly_name or col_name
        st.caption(
            f"⚠ {n_null} of {total} schools ({pct:.0f}%) have no reported value "
            f"for **{display_name}** — shown as missing, not zero."
        )


# ── Chart components ───────────────────────────────────────────────────────────

_FONT = dict(family="'DM Sans', 'Inter', sans-serif", size=12, color="#334155")


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    source_label: str,
    color: str | None = None,
    color_map: dict | None = None,
    category_orders: dict | None = None,
    height: int = 420,
) -> None:
    """Horizontal bar chart with a source annotation."""
    fig = px.bar(
        df,
        x=x,
        y=y,
        title=title,
        color=color,
        color_discrete_map=color_map,
        category_orders=category_orders,
        orientation="h",
        height=height,
    )
    fig.update_layout(font=_FONT, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    _annotate_source(fig, source_label)
    st.plotly_chart(fig, use_container_width=True)


def scatter_map(
    df: pd.DataFrame,
    title: str | None,
    source_label: str,
    color_col: str = "accountability_rating_2025",
    hover_cols: list[str] | None = None,
    height: int = 480,
) -> None:
    plot_df = df.dropna(subset=["latitude", "longitude"]).copy()
    if plot_df.empty:
        st.warning("No coordinate data available for map.")
        return

    plot_df["_rating_label"] = plot_df[color_col].fillna("Unknown")

    hover = hover_cols or ["school_name", "district_name", "enrollment", color_col]
    fig = px.scatter_mapbox(
        plot_df,
        lat="latitude",
        lon="longitude",
        color="_rating_label",
        color_discrete_map={**RATING_COLORS, "Unknown": "#bdc3c7"},
        hover_name="school_name",
        hover_data={c: True for c in hover if c in plot_df.columns and c != "school_name"},
        title=title or None,
        mapbox_style="carto-positron",
        zoom=10,
        center={"lat": 32.78, "lon": -96.8},
        height=height,
    )
    fig.update_layout(
        font=_FONT,
        legend_title_text="Rating",
        margin=dict(l=0, r=0, t=30 if title else 5, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    _annotate_source(fig, source_label)
    st.plotly_chart(fig, use_container_width=True)


def distribution_histogram(
    df: pd.DataFrame,
    col: str,
    title: str,
    source_label: str,
    xaxis_title: str = "",
    nbins: int = 20,
    height: int = 360,
) -> None:
    plot_df = df[col].dropna()
    if plot_df.empty:
        st.info(f"No reported values for **{xaxis_title or col}**.")
        return
    fig = px.histogram(
        plot_df,
        x=col,
        nbins=nbins,
        title=title,
        height=height,
    )
    fig.update_xaxes(title_text=xaxis_title or col)
    fig.update_yaxes(title_text="Schools")
    fig.update_layout(font=_FONT, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    _annotate_source(fig, source_label)
    st.plotly_chart(fig, use_container_width=True)


def box_plot(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    source_label: str,
    category_orders: dict | None = None,
    x_labels: dict | None = None,
    height: int = 400,
) -> None:
    plot_df = df[[x, y]].dropna().copy()
    if plot_df.empty:
        st.info(f"No reported values for **{y}** by **{x}**.")
        return
    if x_labels:
        plot_df[x] = plot_df[x].map(x_labels).fillna(plot_df[x])
    fig = px.box(
        plot_df,
        x=x,
        y=y,
        title=title,
        category_orders=category_orders,
        height=height,
    )
    fig.update_layout(font=_FONT, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    _annotate_source(fig, source_label)
    st.plotly_chart(fig, use_container_width=True)


def _annotate_source(fig: go.Figure, source_label: str) -> None:
    fig.add_annotation(
        text=f"Source: {source_label}",
        xref="paper",
        yref="paper",
        x=1,
        y=-0.12,
        showarrow=False,
        font=dict(size=10, color="#94A3B8"),
        xanchor="right",
    )
