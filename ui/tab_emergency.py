"""Tab 4: Mixed-Integer Linear Programming (MILP) Emergency Vehicle Preemption & Scheduling."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any

from models.schemas import ApproachInput, SignalTimingConfig, EmergencyPreemptionResult
from services.intersection_service import run_emergency_preemption_pipeline


def render_schedule_gantt(em_res: EmergencyPreemptionResult) -> go.Figure:
    """Render a clean interactive Plotly Gantt chart showing the preempted phase timeline."""
    fig = go.Figure()

    blocks = em_res.schedule_blocks

    for b in blocks:
        p_name = b["phase"]
        s_t = b["start_sec"]
        g_end = b["green_end_sec"]
        ig_end = b["phase_end_sec"]
        is_ev = b["is_ev_phase"]

        # Green bar
        fig.add_trace(go.Bar(
            name=f"{p_name} Green",
            y=[p_name],
            x=[g_end - s_t],
            base=[s_t],
            orientation="h",
            marker=dict(color="#c0392b" if is_ev else "#2980b9"),
            text=f"<b>{'[EMERGENCY] ' if is_ev else ''}{p_name}</b><br>{s_t}s - {g_end}s ({g_end - s_t:.1f}s)",
            textposition="inside",
            hoverinfo="text",
            showlegend=False
        ))

        # Yellow + All-Red Clearance bar
        ig_dur = ig_end - g_end
        if ig_dur > 0:
            fig.add_trace(go.Bar(
                name="Clearance",
                y=[p_name],
                x=[ig_dur],
                base=[g_end],
                orientation="h",
                marker=dict(color="#f39c12"),
                text="Clearance",
                textposition="inside",
                hoverinfo="text",
                showlegend=False
            ))

    fig.update_layout(
        title="<b>Preempted Phase Execution Timeline (Gantt Chart)</b>",
        xaxis_title="Timeline from Preemption Trigger (seconds)",
        yaxis=dict(autorange="reversed"),
        barmode="stack",
        margin=dict(l=60, r=20, t=50, b=30),
        height=280
    )
    return fig


def render_emergency_tab(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig
):
    """Render the MILP Emergency Vehicle scheduling simulator and trade-off analysis."""
    st.subheader("🚑 Emergency Vehicle Preemption & Scheduling Optimization (MILP)")
    st.caption("Single-machine disjunctive scheduling ($1 \\mid r_j, \\tau \\mid \\sum w_j C_j$) with safe phase truncation.")

    # --- 1. Parameter Inputs ---
    col1, col2, col3 = st.columns(3)
    with col1:
        ev_type = st.selectbox("Vehicle Type", ["Ambulance", "Fire Truck", "Police Patrol"], index=0)
        ev_dir = st.selectbox("EV Arrival Direction", list(approaches.keys()), index=0)
    with col2:
        curr_phase = st.selectbox("Currently Active Green Phase", list(approaches.keys()), index=2)
        elapsed_green = st.number_input("Elapsed Green on Active Phase (s)", min_value=0.0, max_value=40.0, value=7.0, step=1.0)
    with col3:
        arr_time = st.number_input("EV Arrival Timestamp (s)", min_value=0.0, max_value=60.0, value=12.0, step=1.0)
        q_ahead = st.number_input("Queued Vehicles Ahead of EV", min_value=0, max_value=20, value=3, step=1)

    # --- 2. Solve MILP Schedule ---
    em_res = run_emergency_preemption_pipeline(
        approaches=approaches,
        timing=timing,
        ev_direction=ev_dir,
        ev_type=ev_type,
        ev_arrival_time_sec=arr_time,
        current_active_phase=curr_phase,
        elapsed_active_green_sec=elapsed_green,
        queued_vehicles_ahead=int(q_ahead),
        persist_to_db=False
    )

    # --- 3. Results Metrics ---
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(
            label="Normal Cycle EV Wait",
            value=f"{em_res.ev_wait_normal_sec:.1f} s",
            help="Waiting time if the EV had to wait for the fixed signal rotation."
        )
    with m2:
        st.metric(
            label="Preempted EV Wait",
            value=f"{em_res.ev_wait_preempted_sec:.1f} s",
            delta=f"-{em_res.time_saved_sec:.1f} s",
            delta_color="normal"
        )
    with m3:
        pct_saved = (em_res.time_saved_sec / max(0.1, em_res.ev_wait_normal_sec)) * 100.0
        st.metric(
            label="Response Time Saved",
            value=f"{em_res.time_saved_sec:.1f} s",
            delta=f"{pct_saved:.1f}% faster",
            delta_color="normal"
        )
    with m4:
        st.metric(
            label="Recovery Makespan",
            value=f"{em_res.recovery_makespan_sec:.1f} s",
            help="Total time to cycle through EV flush and restore all delayed approaches."
        )

    # --- 4. Plotly Gantt Chart ---
    st.plotly_chart(render_schedule_gantt(em_res), width="stretch")

    # --- 5. Operations Research Trade-off Analysis ---
    st.info(
        f"""
        **⚖️ Preemption Trade-off Analysis**:
        - **Emergency Priority Gain**: The {ev_type} on approach **{ev_dir}** clears the intersection in **{em_res.ev_wait_preempted_sec:.1f} s**, saving **{em_res.time_saved_sec:.1f} seconds**.
        - **Safety Clearance Guaranteed**: The active phase (**{curr_phase}**) is not instantaneously cut to zero; it satisfies a safe minimum floor before a mandatory **{timing.intergreen_per_phase:.1f} s yellow + all-red clearance**.
        - **Cross-Street Impact**: Postponed cross-street traffic experiences a temporary additional holding delay of **+{em_res.cross_street_extra_delay_sec:.1f} s** before returning to normal optimal green splits.
        """
    )

