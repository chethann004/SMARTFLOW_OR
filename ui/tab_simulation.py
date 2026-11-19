"""Tab 2: Microscopic Discrete-Time 4-Way Traffic Junction Simulation and Playback."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any

from models.schemas import SimulationTrace, IntersectionEvaluation, ApproachInput, SignalTimingConfig
from services.intersection_service import run_junction_simulation_pipeline


def render_junction_schematic(record: Dict[str, Any], controller_mode: str = "opt") -> go.Figure:
    """Render a clean 2D geometric schematic of the 4-way intersection at simulation time t."""
    fig = go.Figure()

    signals = record[f"{controller_mode}_signals"]
    queues = record[f"{controller_mode}_queues"]
    active = record[f"{controller_mode}_active"]

    # Road layout coordinates (Intersection box from x,y in [-20, 20])
    # North approach: x in [-15, 15], y in [20, 80]
    # South approach: x in [-15, 15], y in [-80, -20]
    # East approach: x in [20, 80], y in [-15, 15]
    # West approach: x in [-80, -20], y in [-15, 15]

    road_color = "#34495e"
    lane_mark_color = "#f1c40f"

    # Roads
    fig.add_shape(type="rect", x0=-15, y0=-90, x1=15, y1=90, fillcolor=road_color, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-90, y0=-15, x1=90, y1=15, fillcolor=road_color, line_width=0, layer="below")
    # Center junction box
    fig.add_shape(type="rect", x0=-15, y0=-15, x1=15, y1=15, fillcolor="#2c3e50", line_color="#bdc3c7", line_width=1)

    # Center lane divider dashed lines
    fig.add_shape(type="line", x0=0, y0=20, x1=0, y1=85, line=dict(color=lane_mark_color, width=2, dash="dash"))
    fig.add_shape(type="line", x0=0, y0=-20, x1=0, y1=-85, line=dict(color=lane_mark_color, width=2, dash="dash"))
    fig.add_shape(type="line", x0=20, y0=0, x1=85, y1=0, line=dict(color=lane_mark_color, width=2, dash="dash"))
    fig.add_shape(type="line", x0=-20, y0=0, x1=-85, y1=0, line=dict(color=lane_mark_color, width=2, dash="dash"))

    # Signal lights coordinates and colors
    signal_coords = {
        "North": {"x": -8, "y": 25, "text_pos": "top center"},
        "South": {"x": 8, "y": -25, "text_pos": "bottom center"},
        "East": {"x": 25, "y": 8, "text_pos": "middle right"},
        "West": {"x": -25, "y": -8, "text_pos": "middle left"}
    }
    color_map = {"GREEN": "#2ecc71", "YELLOW": "#f39c12", "RED": "#e74c3c"}

    for d, coord in signal_coords.items():
        state = signals.get(d, "RED")
        fill = color_map.get(state, "#e74c3c")
        q_count = queues.get(d, 0)

        # Signal beacon circle
        fig.add_trace(go.Scatter(
            x=[coord["x"]],
            y=[coord["y"]],
            mode="markers+text",
            marker=dict(size=24, color=fill, line=dict(color="#ffffff", width=2)),
            text=[f"<b>{d.upper()}</b><br>{state}"],
            textposition=coord["text_pos"],
            textfont=dict(color="#ffffff" if state != "YELLOW" else "#000000", size=10),
            hoverinfo="text",
            showlegend=False
        ))

        # Queue text callouts
        q_label_positions = {
            "North": {"x": 0, "y": 55},
            "South": {"x": 0, "y": -55},
            "East": {"x": 55, "y": 0},
            "West": {"x": -55, "y": 0}
        }
        fig.add_trace(go.Scatter(
            x=[q_label_positions[d]["x"]],
            y=[q_label_positions[d]["y"]],
            mode="text",
            text=[f"🚗 Queue: <b>{q_count}</b> veh"],
            textfont=dict(color="#ffffff", size=12),
            showlegend=False
        ))

    # Center label showing current active phase and time
    fig.add_annotation(
        x=0, y=0,
        text=f"<b>ACTIVE:</b><br>{active.upper()}",
        showarrow=False,
        font=dict(color="#f1c40f", size=11),
        align="center"
    )

    fig.update_layout(
        title=f"<b>4-Way Junction Microscopic State (Controller: {controller_mode.upper()})</b>",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-95, 95]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-95, 95], scaleanchor="x", scaleratio=1),
        plot_bgcolor="#1a252f",
        paper_bgcolor="#ffffff",
        margin=dict(l=20, r=20, t=50, b=20),
        height=450
    )
    return fig


def render_simulation_tab(
    sim_trace: SimulationTrace,
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    fixed_eval: IntersectionEvaluation,
    opt_eval: IntersectionEvaluation
):
    """Render the simulation playback, timeseries queue charts, and analytical validation."""
    st.subheader("🚦 4-Way Traffic Junction Simulation & Microscopic Validation")
    st.caption("Discrete-event (1-second step) simulation driven by Common Random Numbers (CRN) for scientific validity.")

    records = sim_trace.second_by_second_records
    if not records:
        st.warning("No simulation records found. Run the simulation to view playback.")
        return

    # --- 1. Interactive Time Scrubber ---
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        time_step = st.slider(
            "⏱️ Simulation Time Scrubber (seconds)",
            min_value=0,
            max_value=sim_trace.duration_sec - 1,
            value=min(60, sim_trace.duration_sec - 1),
            step=max(1, sim_trace.duration_sec // len(records)),
            help="Drag to view junction signal states and queue accumulations at any point in time."
        )

    # Find closest recorded snapshot
    closest_rec = min(records, key=lambda r: abs(r["time_sec"] - time_step))

    with col_t2:
        controller_view = st.radio(
            "Controller View",
            options=["SmartFlow LP Optimized", "Fixed-Time Baseline"],
            index=0
        )
        mode_key = "opt" if controller_view == "SmartFlow LP Optimized" else "fixed"

    # --- 2. Live Junction Schematic ---
    fig_schematic = render_junction_schematic(closest_rec, controller_mode=mode_key)
    st.plotly_chart(fig_schematic, width="stretch")

    # --- 3. Queue Evolution Over Time (Plotly Timeseries) ---
    st.subheader("📈 Queue Buildup & Clearance Over Time")
    time_series_x = [r["time_sec"] for r in records]
    fig_q = go.Figure()

    fig_q.add_trace(go.Scatter(
        x=time_series_x,
        y=[r["total_fixed_queue"] for r in records],
        name="Fixed-Time Total Queue (veh)",
        line=dict(color="#e74c3c", width=2)
    ))
    fig_q.add_trace(go.Scatter(
        x=time_series_x,
        y=[r["total_opt_queue"] for r in records],
        name="SmartFlow LP Total Queue (veh)",
        line=dict(color="#2ecc71", width=2.5)
    ))
    # Mark current scrubber position
    fig_q.add_vline(x=time_step, line_dash="dash", line_color="#3498db", annotation_text="Scrubber Position")

    fig_q.update_layout(
        title="<b>Total Intersection Queued Vehicles vs. Time</b>",
        xaxis_title="Simulation Time (seconds)",
        yaxis_title="Queued Vehicles (veh)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=50, b=30),
        height=320
    )
    st.plotly_chart(fig_q, width="stretch")

    # --- 4. Scientific Validation: Analytical Queuing Theory vs. Simulated Microscopic ---
    st.subheader("🔬 Queuing Theory Validation: Analytical Model vs. Discrete-Time Simulation")
    st.markdown(
        """
        In academic Operations Research, macroscopic Queuing Theory models ($D/D/1 + M/D/1$) must be validated
        against microscopic discrete-time vehicle simulations. Both metrics are displayed side-by-side below:
        """
    )

    val_data = []
    for d in approaches:
        an_opt = opt_eval.approaches[d].avg_wait_time_sec
        sim_opt = sim_trace.opt_summary["per_approach_avg_wait"].get(d, 0.0)
        opt_err = abs(sim_opt - an_opt) / max(1.0, an_opt) * 100.0

        an_fixed = fixed_eval.approaches[d].avg_wait_time_sec
        sim_fixed = sim_trace.fixed_summary["per_approach_avg_wait"].get(d, 0.0)
        fixed_err = abs(sim_fixed - an_fixed) / max(1.0, an_fixed) * 100.0

        val_data.append({
            "Approach": d,
            "Analytical Opt Delay (s)": round(an_opt, 1),
            "Simulated Opt Delay (s)": round(sim_opt, 1),
            "Opt Model Variance (%)": f"{opt_err:.1f}%",
            "Analytical Fixed Delay (s)": round(an_fixed, 1),
            "Simulated Fixed Delay (s)": round(sim_fixed, 1),
            "Fixed Model Variance (%)": f"{fixed_err:.1f}%",
            "Simulated Max Queue (veh)": sim_trace.opt_summary["per_approach_max_queue"].get(d, 0)
        })

    val_df = pd.DataFrame(val_data)
    st.dataframe(val_df, width="stretch", hide_index=True)

