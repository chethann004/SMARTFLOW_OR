"""Tab 5: Parametric Sensitivity Analysis, Tipping Points, and LP Shadow Prices."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any

from models.schemas import ApproachInput, SignalTimingConfig, IntersectionEvaluation
from core.sensitivity import perform_demand_sweep, perform_global_scaling_sweep, extract_shadow_prices_summary


def render_sensitivity_tab(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    opt_eval: IntersectionEvaluation,
    cycle_curve: Dict[float, float]
):
    """Render the parametric sensitivity curves, saturation tipping points, and dual values."""
    st.subheader("🔬 Operations Research Sensitivity Analysis & Tipping Points")
    st.caption("Investigate how signal timing plans and queues respond to traffic demand variations and cycle adjustments.")

    # --- 1. Approach Demand Scaling Sweep ---
    target_dir = st.selectbox(
        "Select Approach Direction for Parametric Demand Sweep (50% to 150%)",
        options=list(approaches.keys()),
        index=0
    )

    sweep_res = perform_demand_sweep(target_dir, approaches, timing, eval_cycle_sec=opt_eval.cycle_time_sec)
    records = sweep_res["records"]
    df_sweep = pd.DataFrame(records)
    tipping = sweep_res["tipping_points"]

    # Tipping Point Cards
    st.markdown("#### 🚨 Saturation Tipping Points for Approach: " + target_dir)
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        f_85 = f"{tipping['fixed_85_near_capacity'] * 100:.0f}%" if tipping['fixed_85_near_capacity'] else "N/A"
        f_100 = f"{tipping['fixed_100_breakdown'] * 100:.0f}%" if tipping['fixed_100_breakdown'] else ">150%"
        st.warning(
            f"**Fixed-Time Baseline Tipping Points**:\n"
            f"- Near Capacity (rho >= 0.85): **{f_85}** of base volume\n"
            f"- Oversaturated Breakdown (rho >= 1.00): **{f_100}** of base volume"
        )
    with col_t2:
        o_85 = f"{tipping['opt_85_near_capacity'] * 100:.0f}%" if tipping['opt_85_near_capacity'] else ">150%"
        o_100 = f"{tipping['opt_100_breakdown'] * 100:.0f}%" if tipping['opt_100_breakdown'] else ">150%"
        st.success(
            f"**SmartFlow LP Optimized Tipping Points**:\n"
            f"- Near Capacity (rho >= 0.85): **{o_85}** of base volume\n"
            f"- Oversaturated Breakdown (rho >= 1.00): **{o_100}** of base volume"
        )

    # Plotly Sensitivity Curves: Wait Time vs Multiplier
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        fig_wait = go.Figure()
        fig_wait.add_trace(go.Scatter(
            x=df_sweep["multiplier"] * 100.0,
            y=df_sweep["fixed_wait_sec"],
            mode="lines+markers",
            name="Fixed-Time Delay (s)",
            line=dict(color="#e74c3c", width=2.5)
        ))
        fig_wait.add_trace(go.Scatter(
            x=df_sweep["multiplier"] * 100.0,
            y=df_sweep["opt_wait_sec"],
            mode="lines+markers",
            name="LP Optimized Delay (s)",
            line=dict(color="#2ecc71", width=2.5)
        ))
        fig_wait.update_layout(
            title=f"<b>{target_dir} Vehicle Delay vs. Demand Scaling</b>",
            xaxis_title="Demand Multiplier (% of base volume)",
            yaxis_title="Average Delay (seconds)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=20, t=50, b=30),
            height=320
        )
        st.plotly_chart(fig_wait, width="stretch")

    with col_g2:
        fig_green = go.Figure()
        fig_green.add_trace(go.Scatter(
            x=df_sweep["multiplier"] * 100.0,
            y=df_sweep["fixed_green_sec"],
            mode="lines",
            name="Fixed Green (s)",
            line=dict(color="#95a5a6", width=2, dash="dash")
        ))
        fig_green.add_trace(go.Scatter(
            x=df_sweep["multiplier"] * 100.0,
            y=df_sweep["opt_green_sec"],
            mode="lines+markers",
            name="LP Reallocated Green (s)",
            line=dict(color="#3498db", width=2.5)
        ))
        fig_green.update_layout(
            title=f"<b>{target_dir} Optimal Green Allocation vs. Demand</b>",
            xaxis_title="Demand Multiplier (% of base volume)",
            yaxis_title="Allocated Green Time (s)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=20, t=50, b=30),
            height=320
        )
        st.plotly_chart(fig_green, width="stretch")

    # --- 2. Cycle Time U-Curve (C vs Total Delay) ---
    st.markdown("---")
    st.markdown("#### 🔄 Cycle Length Sensitivity U-Curve")
    if cycle_curve:
        c_vals = sorted(list(cycle_curve.keys()))
        d_vals = [cycle_curve[c] for c in c_vals]

        fig_u = go.Figure()
        fig_u.add_trace(go.Scatter(
            x=c_vals,
            y=d_vals,
            mode="lines+markers",
            name="Total Delay vs Cycle Length",
            line=dict(color="#8e44ad", width=2.5)
        ))
        # Highlight global optimum
        fig_u.add_trace(go.Scatter(
            x=[opt_eval.cycle_time_sec],
            y=[opt_eval.demand_weighted_avg_wait_sec],
            mode="markers",
            name=f"Optimal Cycle C* = {opt_eval.cycle_time_sec:.0f}s",
            marker=dict(size=14, color="#f1c40f", symbol="star")
        ))
        fig_u.update_layout(
            title="<b>Intersection Average Delay vs. Cycle Length C (Demonstrating Webster's U-Shape)</b>",
            xaxis_title="Cycle Length C (seconds)",
            yaxis_title="Demand-Weighted Delay (s/veh)",
            margin=dict(l=40, r=20, t=50, b=30),
            height=300
        )
        st.plotly_chart(fig_u, width="stretch")
        st.caption("Explanation: Short cycles waste too large a fraction of time on clearance lost time ($L/C$); long cycles impose excessive waiting during long red intervals.")

    # --- 3. LP Dual Values / Shadow Prices Table ---
    st.markdown("---")
    st.markdown("#### 💰 Linear Programming Dual Values (Shadow Prices)")
    sp_data = extract_shadow_prices_summary(opt_eval)
    st.dataframe(pd.DataFrame(sp_data), width="stretch", hide_index=True)
