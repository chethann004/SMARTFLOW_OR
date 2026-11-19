"""SmartFlow OR: An Intelligent Traffic Signal Optimization System Using Operations Research Techniques.

Main application entry point for the Streamlit web interface.
"""

import streamlit as st
import os

from database.db_manager import init_database
from ui.styles import apply_custom_styles, render_header
from ui.sidebar import render_sidebar
from ui.tab_dashboard import render_dashboard_tab
from ui.tab_simulation import render_simulation_tab
from ui.tab_math_breakdown import render_math_breakdown_tab
from ui.tab_emergency import render_emergency_tab
from ui.tab_sensitivity import render_sensitivity_tab
from ui.tab_reports import render_reports_tab
from services.intersection_service import evaluate_scenario_full, run_junction_simulation_pipeline

# Configure Streamlit page
st.set_page_config(
    page_title="SmartFlow OR - Traffic Signal Optimization",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database schema
init_database()

# Apply CSS styling
apply_custom_styles()

# Render top header
render_header()

# Render sidebar controls
approaches, timing_config, trigger_run = render_sidebar()

# Session state evaluation pipeline
should_run = trigger_run or ("opt_eval" not in st.session_state)

if should_run:
    with st.spinner("Solving Operations Research LP & Running Microscopic Simulation..."):
        fixed_eval, opt_eval, cycle_curve = evaluate_scenario_full(
            approaches=approaches,
            timing=timing_config,
            persist_to_db=True
        )
        sim_trace = run_junction_simulation_pipeline(
            approaches=approaches,
            timing=timing_config,
            fixed_eval=fixed_eval,
            opt_eval=opt_eval,
            duration_sec=int(timing_config.analysis_period_sec),
            arrival_mode="Poisson",
            random_seed=timing_config.random_seed,
            persist_to_db=True
        )
        st.session_state["fixed_eval"] = fixed_eval
        st.session_state["opt_eval"] = opt_eval
        st.session_state["cycle_curve"] = cycle_curve
        st.session_state["sim_trace"] = sim_trace
        st.session_state["current_approaches"] = approaches
        st.session_state["current_timing"] = timing_config

fixed_eval = st.session_state["fixed_eval"]
opt_eval = st.session_state["opt_eval"]
cycle_curve = st.session_state["cycle_curve"]
sim_trace = st.session_state["sim_trace"]
curr_apps = st.session_state.get("current_approaches", approaches)
curr_timing = st.session_state.get("current_timing", timing_config)

# Render Main 6 Tabs
tabs = st.tabs([
    "📊 Overview & Comparison",
    "🚦 4-Way Junction Simulation",
    "📐 Mathematical Models & Calculations",
    "🚑 Emergency Priority (MILP)",
    "🔬 Sensitivity & Tipping Points",
    "📑 History & Academic Reports"
])

with tabs[0]:
    render_dashboard_tab(fixed_eval, opt_eval, cycle_curve)

with tabs[1]:
    render_simulation_tab(sim_trace, curr_apps, curr_timing, fixed_eval, opt_eval)

with tabs[2]:
    render_math_breakdown_tab(curr_apps, curr_timing, opt_eval, fixed_eval)

with tabs[3]:
    render_emergency_tab(curr_apps, curr_timing)

with tabs[4]:
    render_sensitivity_tab(curr_apps, curr_timing, opt_eval, cycle_curve)

with tabs[5]:
    render_reports_tab(fixed_eval, opt_eval, sim_trace)

