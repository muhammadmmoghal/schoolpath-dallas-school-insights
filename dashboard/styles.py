"""
SchoolPath Dallas — Design System v4
Reference: schoolpath dashboard ui design.png

Font pairing:  Sora (headings / KPI values) + DM Sans (body, labels, UI)
Sidebar:       #173F35  deep forest green  (CSS-overrides config.toml secondary)
Page bg:       #EEF2F0  soft gray-green workspace
Cards:         #FFFFFF  border #D5DEDA  radius 6px
Accent:        #2F6B57  forest green
Amber:         #C47B1A  warnings / caveats only
"""
from __future__ import annotations

import re

import streamlit as st

# ── Design tokens ──────────────────────────────────────────────────────────────

COLORS = {
    # Canvas
    "page_bg":            "#EEF2F0",
    # Sidebar — forest green palette (all CSS-driven, independent of config.toml)
    "sidebar_bg":         "#173F35",
    "sidebar_deeper":     "#12342C",
    "sidebar_active_bg":  "#2F6B57",
    "sidebar_hover_bg":   "#275947",
    "sidebar_text":       "#F4F7F5",
    "sidebar_text_muted": "#C5D6CF",
    "sidebar_text_tiny":  "#9DB8AD",
    "sidebar_divider":    "rgba(255,255,255,0.18)",
    # Cards
    "card_bg":            "#FFFFFF",
    "card_border":        "#D5DEDA",
    # Text
    "text_primary":       "#1A1D23",
    "text_secondary":     "#3D4A5C",
    "text_muted":         "#6B7A8D",
    "text_caption":       "#8DA3A0",
    # Accent (green)
    "accent":             "#2F6B57",
    "accent_mid":         "#3D8B6E",
    "accent_light":       "#E7F0EC",
    # Input controls
    "input_bg":           "#FFFFFF",
    "input_border":       "#CBD5D1",
    "input_hover_border": "#6B8F82",
    "input_focus_border": "#2F6B57",
    "dropdown_bg":        "#FFFFFF",
    "option_selected_bg": "#E7F0EC",
    "option_selected_txt":"#173F35",
    "tag_bg":             "#DCF0E8",
    # Amber (warnings)
    "amber":              "#C47B1A",
    "amber_bg":           "#FFF8EC",
    "amber_border":       "#FAD89B",
    # Note (green-tinted)
    "note_bg":            "#EEF7F3",
    "note_border":        "#A8D5BE",
    "note_text":          "#1A3D2C",
    # Misc
    "divider":            "#D5DEDA",
    "shadow":             "rgba(23, 63, 53, 0.07)",
}

FONTS = {
    "heading": "'Sora', 'Manrope', sans-serif",
    "body":    "'DM Sans', 'Inter', 'Segoe UI', sans-serif",
}

# ── Master CSS ─────────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

/* ══════════════════════════════════════════════════════════════════════════
   BASE
   ══════════════════════════════════════════════════════════════════════════ */

html, body, [class*="css"] {
    font-family: 'DM Sans', 'Inter', 'Segoe UI', sans-serif !important;
}
.stApp {
    background-color: #EEF2F0 !important;
}
.main .block-container,
[data-testid="stAppViewBlockContainer"] {
    max-width: 1240px;
    padding-top: 0 !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    padding-bottom: 4rem !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   TYPOGRAPHY
   ══════════════════════════════════════════════════════════════════════════ */

h1, h2, h3, h4 {
    font-family: 'Sora', 'Manrope', sans-serif !important;
    letter-spacing: -0.02em !important;
    color: #1A1D23 !important;
}
h1 { font-weight: 700 !important; font-size: 1.75rem !important; }
h2 { font-weight: 600 !important; font-size: 1.0rem  !important; margin-bottom: 0.1rem !important; }
h3 { font-weight: 600 !important; font-size: 0.9rem  !important; }
p, li { color: #3D4A5C; line-height: 1.65; }

/* ══════════════════════════════════════════════════════════════════════════
   SIDEBAR — forest green (#173F35 palette)
   NOTE: secondaryBackgroundColor in config.toml is set to a light value so
   inputs stay white. The sidebar gets its dark green purely via CSS here.
   ══════════════════════════════════════════════════════════════════════════ */

section[data-testid="stSidebar"] {
    background-color: #173F35 !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
    background-color: #173F35 !important;
}

/* All text inside sidebar defaults to muted green-white */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] a,
section[data-testid="stSidebar"] label {
    color: #C5D6CF !important;
}

/* Nav links — inactive */
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
    border-radius: 5px !important;
    margin: 1px 8px !important;
    padding: 0.42rem 0.9rem !important;
    color: #C5D6CF !important;
    font-family: 'DM Sans', 'Inter', sans-serif !important;
    font-size: 0.855rem !important;
    font-weight: 400 !important;
    transition: background 0.12s, color 0.12s;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {
    background-color: #275947 !important;
    color: #F4F7F5 !important;
}
/* Active / selected nav item */
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {
    background-color: #2F6B57 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}
/* Force inheritable color on nav link children */
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span,
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] p,
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] div {
    color: inherit !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   INPUT CONTROLS — white backgrounds, green focus/accent
   Fixes: dark select boxes caused by secondaryBackgroundColor
   ══════════════════════════════════════════════════════════════════════════ */

/* ── Select box trigger / container ── */
div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border-color: #CBD5D1 !important;
    border-radius: 6px !important;
    color: #1F2933 !important;
}
div[data-baseweb="select"] > div:hover {
    border-color: #6B8F82 !important;
}
/* Inner sub-divs (BaseWeb nests deeply) */
div[data-baseweb="select"] > div > div {
    background-color: #FFFFFF !important;
    color: #1F2933 !important;
}
/* All text / spans inside select box trigger */
div[data-baseweb="select"] span {
    color: #1F2933 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.875rem !important;
}
/* Chevron icon color */
div[data-baseweb="select"] svg {
    fill: #6B8F82 !important;
    color: #6B8F82 !important;
}

/* ── Text input inside select (used by searchable selects) ── */
div[data-baseweb="select"] input,
div[data-baseweb="input"] input {
    background-color: #FFFFFF !important;
    color: #1F2933 !important;
    font-family: 'DM Sans', sans-serif !important;
}
div[data-baseweb="input"] {
    background-color: #FFFFFF !important;
    border-color: #CBD5D1 !important;
    border-radius: 6px !important;
}

/* ── Dropdown popover (renders at document root, not inside .main) ── */
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div {
    background-color: #FFFFFF !important;
    border: 1px solid #C8D5D0 !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 18px rgba(23,63,53,0.13) !important;
}
/* Options list container */
ul[data-baseweb="menu"],
div[data-baseweb="menu"] {
    background-color: #FFFFFF !important;
    padding: 4px !important;
}
/* Individual option */
li[role="option"],
[data-baseweb="menu-item"],
[data-baseweb="menu-item"] div,
[data-baseweb="option"] {
    background-color: #FFFFFF !important;
    color: #1F2933 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.875rem !important;
    border-radius: 4px !important;
}
li[role="option"]:hover,
[data-baseweb="menu-item"]:hover {
    background-color: #E7F0EC !important;
    color: #173F35 !important;
}
li[role="option"][aria-selected="true"],
[data-baseweb="menu-item"][aria-selected="true"],
[data-baseweb="menu-item"][aria-selected="true"] div {
    background-color: #E7F0EC !important;
    color: #173F35 !important;
    font-weight: 500 !important;
}

/* ── Multiselect tags ── */
[data-baseweb="tag"] {
    background-color: #DCF0E8 !important;
    border-radius: 4px !important;
    border: 1px solid #A8D5BE !important;
}
[data-baseweb="tag"] span {
    color: #173F35 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
}
/* Tag remove × icon */
[data-baseweb="tag"] svg {
    fill: #2F6B57 !important;
}

/* ── Slider ── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background-color: #2F6B57 !important;
    border-color: #2F6B57 !important;
}

/* ── Widget labels ── */
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stSlider"] label,
[data-testid="stNumberInput"] label,
[data-testid="stCheckbox"] label,
[data-testid="stTextInput"] label {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    color: #3D4A5C !important;
}

/* ── Buttons ── */
[data-testid="baseButton-primary"],
.stButton > button[kind="primary"] {
    background-color: #2F6B57 !important;
    border-color: #2F6B57 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
}
.stButton > button {
    font-family: 'DM Sans', sans-serif !important;
    border-radius: 6px !important;
}

/* ── Checkbox ── */
[data-baseweb="checkbox"] [data-checked="true"] {
    background-color: #2F6B57 !important;
    border-color: #2F6B57 !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   METRIC CARDS  (st.metric — interior pages)
   ══════════════════════════════════════════════════════════════════════════ */

[data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #D5DEDA !important;
    border-radius: 6px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 4px rgba(23,63,53,0.07) !important;
}
[data-testid="stMetricLabel"] > div,
[data-testid="stMetricLabel"] label,
[data-testid="stMetricLabel"] p {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.67rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: #6B7A8D !important;
}
[data-testid="stMetricValue"] > div,
[data-testid="stMetricValue"] {
    font-family: 'Sora', 'Manrope', sans-serif !important;
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    color: #1A1D23 !important;
    line-height: 1.15 !important;
    letter-spacing: -0.025em !important;
}
[data-testid="stMetricDelta"] {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.75rem !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   BORDERED CONTAINERS  (st.container(border=True))
   ══════════════════════════════════════════════════════════════════════════ */

[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1px solid #D5DEDA !important;
    border-radius: 6px !important;
    box-shadow: 0 1px 4px rgba(23,63,53,0.07) !important;
    padding: 0.1rem !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   EXPANDERS
   ══════════════════════════════════════════════════════════════════════════ */

.main [data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #D5DEDA !important;
    border-radius: 6px !important;
    box-shadow: 0 1px 3px rgba(23,63,53,0.06) !important;
}
.main [data-testid="stExpander"] summary {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    color: #3D4A5C !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   TABS
   ══════════════════════════════════════════════════════════════════════════ */

[data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    color: #6B7A8D !important;
    font-size: 0.85rem !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    color: #2F6B57 !important;
    font-weight: 600 !important;
}
[data-baseweb="tab-highlight"] {
    background-color: #2F6B57 !important;
}
[data-baseweb="tab-list"] {
    background: transparent !important;
}
[data-baseweb="tab-border"] {
    background-color: #D5DEDA !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   DIVIDER
   ══════════════════════════════════════════════════════════════════════════ */

hr {
    border-color: #D5DEDA !important;
    border-top-width: 1px !important;
    opacity: 1 !important;
    margin: 1rem 0 !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   CAPTIONS
   ══════════════════════════════════════════════════════════════════════════ */

.stCaption p,
[data-testid="stCaptionContainer"] p,
small {
    font-family: 'DM Sans', sans-serif !important;
    color: #8DA3A0 !important;
    font-size: 0.74rem !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   DATAFRAMES
   ══════════════════════════════════════════════════════════════════════════ */

[data-testid="stDataFrame"] {
    border-radius: 6px !important;
    overflow: hidden !important;
    border: 1px solid #D5DEDA !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   ALERTS
   ══════════════════════════════════════════════════════════════════════════ */

[data-testid="stAlert"] {
    border-radius: 6px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.875rem !important;
}

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Sidebar brand
   ══════════════════════════════════════════════════════════════════════════ */

.sp-brand {
    padding: 1.3rem 1.2rem 0.8rem 1.2rem;
}
.sp-brand-name {
    font-family: 'Sora', 'Manrope', sans-serif;
    font-size: 1.0rem;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.015em;
    line-height: 1.2;
}
.sp-brand-sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.65rem;
    font-weight: 400;
    color: #9DB8AD;
    letter-spacing: 0.01em;
    margin-top: 3px;
}
.sp-brand-sep {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.18);
    margin: 0.75rem 0.8rem 0.15rem 0.8rem;
}

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Overview header
   Compact white card with green left accent — matches reference header style
   ══════════════════════════════════════════════════════════════════════════ */

.sp-overview-header {
    background: #FFFFFF;
    border: 1px solid #D5DEDA;
    border-left: 4px solid #2F6B57;
    border-radius: 0 6px 6px 0;
    padding: 1.35rem 1.75rem 1.25rem 1.6rem;
    margin: 1.25rem 0 0 0;
    box-shadow: 0 1px 4px rgba(23,63,53,0.07);
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
}
.sp-overview-eyebrow {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: #2F6B57;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}
.sp-overview-title {
    font-family: 'Sora', 'Manrope', sans-serif;
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: #1A1D23;
    line-height: 1.15;
    margin: 0 0 0.3rem 0;
}
.sp-overview-subtitle {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.84rem;
    color: #6B7A8D;
    line-height: 1.5;
    max-width: 560px;
}

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: KPI cards row  (label + help icon + value + descriptor)
   ══════════════════════════════════════════════════════════════════════════ */

.sp-kpi-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 9px;
    margin: 1rem 0 0 0;
}
.sp-kpi-card {
    background: #FFFFFF;
    border: 1px solid #D5DEDA;
    border-radius: 6px;
    padding: 0.9rem 1rem;
    box-shadow: 0 1px 3px rgba(23,63,53,0.07);
    min-width: 0;
}
.sp-kpi-text { min-width: 0; }
/* Label row: label text + help icon side-by-side */
.sp-kpi-label-row {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 0.18rem;
}
.sp-kpi-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B7A8D;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
/* Circular help / info icon */
.sp-kpi-help {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background: #C8D8D2;
    color: #FFFFFF;
    font-size: 0.52rem;
    font-weight: 800;
    font-family: 'DM Sans', sans-serif;
    font-style: normal;
    line-height: 1;
    cursor: help;
    position: relative;
    user-select: none;
}
/* Tooltip bubble */
.sp-kpi-help::after {
    content: attr(data-tip);
    position: absolute;
    bottom: calc(100% + 7px);
    left: 50%;
    transform: translateX(-50%);
    background: #1A2E20;
    color: #F4F7F5;
    padding: 7px 10px;
    border-radius: 5px;
    font-size: 0.7rem;
    font-weight: 400;
    line-height: 1.5;
    white-space: normal;
    width: 210px;
    text-align: left;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.15s ease;
    z-index: 9999;
    box-shadow: 0 4px 14px rgba(23,63,53,0.22);
}
.sp-kpi-help:hover::after {
    opacity: 1;
}
.sp-kpi-value {
    font-family: 'Sora', 'Manrope', sans-serif;
    font-size: 1.45rem;
    font-weight: 700;
    color: #1A1D23;
    line-height: 1.1;
    letter-spacing: -0.02em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.sp-kpi-desc {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.63rem;
    color: #8DA3A0;
    margin-top: 0.18rem;
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Source badge
   ══════════════════════════════════════════════════════════════════════════ */

.sp-source-badge-plain {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #F5F8F6;
    border: 1px solid #D5DEDA;
    border-radius: 4px;
    padding: 0.2rem 0.65rem;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.72rem;
    color: #6B7A8D;
    margin-bottom: 0.8rem;
    margin-top: 0.1rem;
    white-space: nowrap;
}
.sp-source-badge-plain strong { color: #3D4A5C; font-weight: 500; }

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Page header (interior pages)
   ══════════════════════════════════════════════════════════════════════════ */

.sp-page-header {
    padding: 1.35rem 0 0.9rem 0;
    margin-bottom: 1rem;
    border-bottom: 1px solid #D5DEDA;
}
.sp-page-eyebrow {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: #2F6B57;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}
.sp-page-title {
    font-family: 'Sora', 'Manrope', sans-serif;
    font-size: 1.45rem;
    font-weight: 700;
    letter-spacing: -0.024em;
    color: #1A1D23;
    margin: 0;
    line-height: 1.2;
}
.sp-page-subtitle {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.82rem;
    color: #6B7A8D;
    margin-top: 0.25rem;
    line-height: 1.5;
}

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Card header (inside bordered containers)
   ══════════════════════════════════════════════════════════════════════════ */

.sp-card-header {
    padding: 0.8rem 1.2rem 0.5rem 1.2rem;
    border-bottom: 1px solid #EFF3F1;
    margin-bottom: 0.6rem;
}
.sp-card-title {
    font-family: 'Sora', 'Manrope', sans-serif;
    font-size: 0.85rem;
    font-weight: 600;
    color: #1A1D23;
    letter-spacing: -0.01em;
}
.sp-card-caption {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.7rem;
    color: #8DA3A0;
    margin-top: 2px;
}

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Filter header
   ══════════════════════════════════════════════════════════════════════════ */

.sp-filter-header {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.63rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6B7A8D;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #D5DEDA;
}

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Caveat card (amber)
   ══════════════════════════════════════════════════════════════════════════ */

.sp-caveat {
    background: #FFF8EC;
    border: 1px solid #FAD89B;
    border-left: 3px solid #C47B1A;
    border-radius: 6px;
    padding: 0.85rem 1.1rem;
    margin-bottom: 0.95rem;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.84rem;
    color: #7A4A0A;
    line-height: 1.65;
}
.sp-caveat-heading {
    font-weight: 700;
    font-size: 0.67rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8A4A08;
    margin-bottom: 0.35rem;
}
.sp-caveat strong { color: #5A2E00; font-weight: 600; }

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Note card (forest green)
   ══════════════════════════════════════════════════════════════════════════ */

.sp-note {
    background: #EEF7F3;
    border: 1px solid #A8D5BE;
    border-left: 3px solid #2F6B57;
    border-radius: 6px;
    padding: 0.85rem 1.1rem;
    margin-bottom: 0.95rem;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.84rem;
    color: #1A3D2C;
    line-height: 1.65;
}
.sp-note-heading {
    font-weight: 700;
    font-size: 0.67rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #2F6B57;
    margin-bottom: 0.35rem;
}
.sp-note strong { color: #1A3D29; font-weight: 600; }

/* ══════════════════════════════════════════════════════════════════════════
   CUSTOM: Insight grid (Overview — "What This Answers")
   ══════════════════════════════════════════════════════════════════════════ */

.sp-insight-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 9px;
    margin: 0.45rem 0 0.2rem 0;
}
.sp-insight-card {
    background: #F9FBF9;
    border: 1px solid #D5DEDA;
    border-radius: 6px;
    padding: 0.8rem 0.95rem;
}
.sp-insight-title {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.79rem;
    font-weight: 600;
    color: #1A1D23;
    margin-bottom: 0.18rem;
    letter-spacing: -0.005em;
}
.sp-insight-body {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.74rem;
    color: #6B7A8D;
    line-height: 1.5;
}
</style>
"""


def inject_global_styles() -> None:
    """Inject the SchoolPath v4 design system CSS. Safe to call multiple times."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _md(text: str) -> str:
    """Convert **bold** and newline markdown to inline HTML."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    return text.replace("  \n", "<br>").replace("\n", "<br>")


# ── HTML component builders ────────────────────────────────────────────────────

def render_sidebar_brand() -> None:
    """Brand mark at the top of the dark forest-green sidebar."""
    st.sidebar.markdown(
        """
        <div class="sp-brand">
            <div class="sp-brand-name">SchoolPath Data</div>
            <div class="sp-brand-sub">Dallas School Data Platform</div>
        </div>
        <hr class="sp-brand-sep">
        """,
        unsafe_allow_html=True,
    )


def render_overview_header(subtitle: str, source_icon: str, source_label: str) -> None:
    """
    Compact white card header for the Overview page.
    Green left-accent border, title + subtitle, source badge right-aligned.
    """
    st.markdown(
        f"""
        <div class="sp-overview-header">
            <div>
                <div class="sp-overview-eyebrow">Overview</div>
                <div class="sp-overview-title">SchoolPath Data</div>
                <div class="sp-overview-subtitle">{subtitle}</div>
            </div>
            <div class="sp-source-badge-plain"
                 style="margin:0;flex-shrink:0;align-self:center;">
                <span>{source_icon}</span>
                <span><strong>Data:</strong> {source_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_row(kpis: list[dict]) -> None:
    """
    Render 6 KPI cards in a horizontal grid matching the reference image.
    Each dict: {label, value, desc, tooltip}
    """
    cards = ""
    for k in kpis:
        tip = k.get("tooltip", "").replace('"', "&quot;")
        cards += (
            f'<div class="sp-kpi-card">'
            f'  <div class="sp-kpi-text">'
            f'    <div class="sp-kpi-label-row">'
            f'      <span class="sp-kpi-label">{k["label"]}</span>'
            f'      <span class="sp-kpi-help" data-tip="{tip}">?</span>'
            f'    </div>'
            f'    <div class="sp-kpi-value">{k["value"]}</div>'
            f'    <div class="sp-kpi-desc">{k.get("desc", "")}</div>'
            f'  </div>'
            f'</div>'
        )
    st.markdown(f'<div class="sp-kpi-row">{cards}</div>', unsafe_allow_html=True)


def render_source_badge(source: str) -> None:
    """Compact source badge (light, for interior pages)."""
    from data_loader import friendly_source_label
    friendly = friendly_source_label(source)
    icon = "🟢" if "Supabase" in source else "🟡"
    st.markdown(
        f'<div class="sp-source-badge-plain">'
        f'<span>{icon}</span>'
        f'<span><strong>Data source:</strong> {friendly}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_page_header(
    title: str,
    subtitle: str = "",
    eyebrow: str = "SchoolPath Data",
) -> None:
    """Compact branded header for interior pages."""
    sub_html = f'<div class="sp-page-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="sp-page-header">
            <div class="sp-page-eyebrow">{eyebrow}</div>
            <div class="sp-page-title">{title}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_card_header(title: str, caption: str = "") -> None:
    """Header bar inside a bordered section card."""
    cap_html = f'<div class="sp-card-caption">{caption}</div>' if caption else ""
    st.markdown(
        f'<div class="sp-card-header">'
        f'<div class="sp-card-title">{title}</div>'
        f'{cap_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_filter_header() -> None:
    st.markdown('<div class="sp-filter-header">Filters</div>', unsafe_allow_html=True)


def render_caveat_card(heading: str, content: str) -> None:
    """Amber-accented caveat card for data limitation warnings."""
    st.markdown(
        f'<div class="sp-caveat">'
        f'<div class="sp-caveat-heading">{heading}</div>'
        f'{_md(content)}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_note_card(heading: str, content: str) -> None:
    """Forest-green note card for data context."""
    st.markdown(
        f'<div class="sp-note">'
        f'<div class="sp-note-heading">{heading}</div>'
        f'{_md(content)}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_insight_grid() -> None:
    """Four compact insight cards for the Overview 'What This Answers' section."""
    st.markdown(
        """
        <div class="sp-insight-grid">
            <div class="sp-insight-card">
                <div class="sp-insight-title">Special Education Access</div>
                <div class="sp-insight-body">
                    Which schools serve the highest proportion of students with
                    disabilities, and how do CRDC-reported discipline, restraint,
                    and harassment counts vary?
                </div>
            </div>
            <div class="sp-insight-card">
                <div class="sp-insight-title">Attendance &amp; Chronic Absence</div>
                <div class="sp-insight-body">
                    How do attendance and chronic-absence rates compare across
                    school levels and operator types?
                </div>
            </div>
            <div class="sp-insight-card">
                <div class="sp-insight-title">Culture &amp; Safety Indicators</div>
                <div class="sp-insight-body">
                    What do attendance, chronic absence, discipline counts, and
                    staffing data suggest about school environment?
                </div>
            </div>
            <div class="sp-insight-card">
                <div class="sp-insight-title">School-Level Detail</div>
                <div class="sp-insight-body">
                    Complete data profile for one school — all fields, source
                    years, and documented gaps.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
