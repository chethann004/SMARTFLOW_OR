"""Tab 1: Executive KPI Dashboard and Fixed-Time vs LP-Optimized Performance Comparison."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any

from models.schemas import IntersectionEvaluation
from services.report_service import generate_comparison_dataframe
from config.constants import COLOR_PALETTE


def render_dashboard_tab(
    fixed_eval: IntersectionEvaluation,
    opt_eval: IntersectionEvaluation,
    cycle_curve: Dict[float, float]
):
    """Render the primary comparative dashboard."""
    st.subheader("📊 Executive Performance Comparison: Fixed-Time vs. SmartFlow LP")

    # --- 1. Top KPI Summary Cards ---
    col1, col2, col3, col4 = st.columns(4)

    # Average Delay & Reduction
    f_wait = fixed_eval.demand_weighted_avg_wait_sec
    o_wait = opt_eval.demand_weighted_avg_wait_sec
    wait_diff = f_wait - o_wait
    wait_pct = (wait_diff / max(0.1, f_wait)) * 100.0

    with col1:
        st.metric(
            label="Avg. Waiting Time",
            value=f"{o_wait:.1f} s",
            delta=f"-{wait_diff:.1f} s (-{wait_pct:.1f}%)" if wait_pct >= 0 else f"+{abs(wait_diff):.1f} s",
            delta_color="normal" if wait_pct >= 0 else "inverse"
        )

    # Total Queue Length
    f_queue = fixed_eval.total_avg_queue_veh
    o_queue = opt_eval.total_avg_queue_veh
    q_diff = f_queue - o_queue
    q_pct = (q_diff / max(0.1, f_queue)) * 100.0
    with col2:
        st.metric(
            label="Total Queued Vehicles",
            value=f"{o_queue:.1f} veh",
            delta=f"-{q_diff:.1f} veh (-{q_pct:.1f}%)" if q_pct >= 0 else f"+{abs(q_diff):.1f} veh",
            delta_color="normal" if q_pct >= 0 else "inverse"
        )

    # Max Degree of Saturation (rho)
    f_rho = fixed_eval.max_saturation_rho
    o_rho = opt_eval.max_saturation_rho
    with col3:
        st.metric(
            label="Max Saturation (v/c ratio)",
            value=f"{o_rho:.2f}",
            delta=f"{o_rho - f_rho:+.2f} vs Fixed ({f_rho:.2f})",
            delta_color="inverse" if o_rho < f_rho else "normal"
        )

    # Intersection Level of Service (LOS)
    f_los = fixed_eval.intersection_los
    o_los = opt_eval.intersection_los
    with col4:
        st.metric(
            label="Intersection LOS",
            value=f"Grade {o_los}",
            delta=f"Baseline was Grade {f_los}",
            delta_color="off"
        )

    st.markdown("---")

    # --- 2. Interactive Plotly Comparison Visualizations ---
    c_left, c_right = st.columns(2)

    directions = list(fixed_eval.approaches.keys())

    # Left Chart: Delay per Approach
    with c_left:
        fig_delay = go.Figure()
        fig_delay.add_trace(go.Bar(
            x=directions,
            y=[fixed_eval.approaches[d].avg_wait_time_sec for d in directions],
            name="Fixed-Time Baseline",
            marker_color=COLOR_PALETTE["Fixed"],
            text=[f"{fixed_eval.approaches[d].avg_wait_time_sec:.1f}s" for d in directions],
            textposition="auto"
        ))
        fig_delay.add_trace(go.Bar(
            x=directions,
            y=[opt_eval.approaches[d].avg_wait_time_sec for d in directions],
            name="SmartFlow LP Optimized",
            marker_color=COLOR_PALETTE["Optimized"],
            text=[f"{opt_eval.approaches[d].avg_wait_time_sec:.1f}s" for d in directions],
            textposition="auto"
        ))
        fig_delay.update_layout(
            title="<b>Average Vehicle Delay (s/veh) by Approach</b>",
            barmode="group",
            yaxis_title="Delay (seconds)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=20, t=50, b=30),
            height=340
        )
        st.plotly_chart(fig_delay, width="stretch")

    # Right Chart: Green Allocation Shifts
    with c_right:
        fig_green = go.Figure()
        fig_green.add_trace(go.Bar(
            x=directions,
            y=[fixed_eval.approaches[d].allocated_green_sec for d in directions],
            name="Fixed Green (s)",
            marker_color="#95a5a6",
            text=[f"{fixed_eval.approaches[d].allocated_green_sec:.1f}s" for d in directions],
            textposition="auto"
        ))
        fig_green.add_trace(go.Bar(
            x=directions,
            y=[opt_eval.approaches[d].allocated_green_sec for d in directions],
            name="LP Optimized Green (s)",
            marker_color="#3498db",
            text=[f"{opt_eval.approaches[d].allocated_green_sec:.1f}s" for d in directions],
            textposition="auto"
        ))
        fig_green.update_layout(
            title="<b>Green Time Allocation Shift (seconds)</b>",
            barmode="group",
            yaxis_title="Green Duration (s)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=20, t=50, b=30),
            height=340
        )
        st.plotly_chart(fig_green, width="stretch")

    # --- 3. Saturation (v/c) Degree Bar Chart with Critical Capacity Line ---
    fig_sat = go.Figure()
    fig_sat.add_trace(go.Bar(
        x=directions,
        y=[fixed_eval.approaches[d].degree_of_saturation_rho for d in directions],
        name="Fixed-Time Saturation (rho)",
        marker_color="#e74c3c"
    ))
    fig_sat.add_trace(go.Bar(
        x=directions,
        y=[opt_eval.approaches[d].degree_of_saturation_rho for d in directions],
        name="LP Optimized Saturation (rho)",
        marker_color="#2ecc71"
    ))
    # Add horizontal critical capacity threshold at rho = 1.0
    fig_sat.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="#c0392b",
        annotation_text="Critical Capacity Threshold (rho = 1.0)",
        annotation_position="top left"
    )
    fig_sat.update_layout(
        title="<b>Degree of Saturation (Traffic Intensity rho = lambda / mu_eff)</b>",
        barmode="group",
        yaxis_title="Saturation Ratio (rho)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=50, b=30),
        height=300
    )
    st.plotly_chart(fig_sat, width="stretch")

    # --- 4. Detailed Data Table ---
    st.subheader("📋 Comprehensive Analytical Performance Table")
    df_comp = generate_comparison_dataframe(fixed_eval, opt_eval)
    st.dataframe(
        df_comp.style.background_gradient(subset=["Delay Saved (%)"], cmap="Greens"),
        width="stretch",
        hide_index=True
    )

    # --- 5. Academic Operations Research Takeaway Box ---
    st.info(
        f"""
        **💡 Operations Research Takeaway**:
        - **Optimal Cycle Selected**: $C^* = {opt_eval.cycle_time_sec:.0f}\\text{{ s}}$ (evaluated over candidates $[{opt_eval.cycle_time_sec - 10:.0f}\\text{{ s}}, {opt_eval.cycle_time_sec + 10:.0f}\\text{{ s}}]$).
        - **Total Available Green Time**: $C^* - L = {opt_eval.total_green_sec:.1f}\\text{{ s}}$ (Lost time per cycle $L = {opt_eval.total_lost_time_sec:.1f}\\text{{ s}}$).
        - **Critical Flow Ratio**: $Y = \\sum y_i = {opt_eval.sum_flow_ratio_y:.3f}$. The LP solver reallocates green budget from light approaches to bottleneck approaches, balancing degree of saturation $\\rho$ and minimizing total queuing delay via convex piecewise-linear optimization.
        """
    )

