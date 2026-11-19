"""Tab 6: SQLite Historical Evaluations, Run History, and Academic Report Exports."""

import streamlit as st
import pandas as pd
from typing import Dict, Any

from models.schemas import IntersectionEvaluation, SimulationTrace
from database.repository import list_recent_evaluations
from services.report_service import export_csv_report, export_markdown_academic_report


def render_reports_tab(
    fixed_eval: IntersectionEvaluation,
    opt_eval: IntersectionEvaluation,
    sim_trace: SimulationTrace
):
    """Render SQLite historical run tables and download buttons for CSV and Markdown reports."""
    st.subheader("📑 Academic Reports, Data Exports & SQLite Evaluation History")

    # --- 1. Export Buttons ---
    st.markdown("#### 📥 Export Project Reports")
    col1, col2 = st.columns(2)

    csv_data = export_csv_report(fixed_eval, opt_eval, sim_trace)
    with col1:
        st.download_button(
            label="📊 Download Comprehensive CSV Report",
            data=csv_data,
            file_name="smartflow_or_metrics_report.csv",
            mime="text/csv",
            width="stretch"
        )

    md_report = export_markdown_academic_report(fixed_eval, opt_eval, sim_trace)
    with col2:
        st.download_button(
            label="📄 Download Academic Project Markdown Report",
            data=md_report,
            file_name="smartflow_or_academic_report.md",
            mime="text/markdown",
            width="stretch"
        )

    st.markdown("---")

    # --- 2. SQLite Historical Runs Browser ---
    st.markdown("#### 🗄️ Recent SQLite Optimization Runs")
    recent_runs = list_recent_evaluations(limit=15)
    if recent_runs:
        df_history = pd.DataFrame(recent_runs)
        cols_to_show = [
            "id", "scenario_name", "run_type", "cycle_time_sec",
            "avg_wait_time_sec", "total_avg_queue_veh", "max_saturation_rho",
            "intersection_los", "solver_status", "created_at"
        ]
        available_cols = [c for c in cols_to_show if c in df_history.columns]
        st.dataframe(df_history[available_cols], width="stretch", hide_index=True)
    else:
        st.info("No saved runs found in SQLite yet. Runs are persisted automatically when evaluated.")

    st.markdown("---")

    # --- 3. Academic Group Project Details & Viva Summary ---
    with st.expander("🎓 MCA Group Project Documentation & Viva Reference", expanded=True):
        st.markdown(
            r"""
            ### Project Overview
            - **Title**: SmartFlow OR — An Intelligent Traffic Signal Optimization System Using Operations Research Techniques
            - **Course**: Master of Computer Applications (MCA)
            - **Core Technology**: Python, Streamlit, PuLP (CBC Solver), NumPy, Pandas, Plotly, SQLite
            
            ### Operations Research Techniques Implemented
            1. **Linear Programming (LP)**: Separable convex piecewise-linear delay minimization subject to cycle budget, pedestrian/driver safety bounds, and capacity constraints.
            2. **Queuing Theory**: Cyclic signalized $D/D/1$ uniform delay + time-dependent coordinate-transformed $M/D/1$ overflow delay (Akçelik) + Little's Law ($L_q = \lambda W$) + HCM Level of Service (LOS A–F).
            3. **Scheduling Optimization (MILP)**: Single-machine disjunctive scheduling ($1 \\mid r_j, \\tau \\mid \\sum w_j C_j$) with safe floor active phase truncation and emergency priority preemption.
            4. **Sensitivity Analysis**: LP shadow prices / dual variables ($\partial Z / \partial (C-L)$) and parametric volume scaling ($50\\% \\text{ to } 150\\%$) determining saturation tipping points ($\\rho = 0.85$ and $\\rho = 1.00$).
            
            ### 3-Member Team Distribution
            - **Member 1 (Math & OR Lead)**: Linear Programming formulation, Queuing Theory derivations, and Sensitivity Analysis.
            - **Member 2 (Simulation & Scheduling Lead)**: MILP Emergency Preemption, 1-second discrete-time simulation engine, and SQLite database.
            - **Member 3 (UI & Integration Lead)**: Streamlit multipage architecture, interactive Plotly visualizations, and academic reporting.
            """
        )
