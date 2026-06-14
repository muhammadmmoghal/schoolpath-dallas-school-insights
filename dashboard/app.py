"""
SchoolPath Dallas — Streamlit dashboard entry point.

Run with:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

# Ensure this directory (dashboard/) is first on sys.path so that every page
# executed via st.navigation() can import data_loader and components without
# relying on __file__ resolution inside each page file.
_DASHBOARD_DIR = str(Path(__file__).parent.resolve())
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)

import streamlit as st

st.set_page_config(
    page_title="SchoolPath Dallas",
    page_icon="\U0001f3eb",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation(
    [
        st.Page("pages/00_overview.py", title="Overview"),
        st.Page("pages/01_school_explorer.py", title="School Explorer"),
        st.Page("pages/02_special_education.py", title="Special Education"),
        st.Page("pages/03_culture_safety.py", title="Culture & Safety"),
        st.Page("pages/04_school_detail.py", title="School Detail"),
    ]
)
pg.run()
