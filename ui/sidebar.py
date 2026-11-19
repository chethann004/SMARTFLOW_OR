"""Sidebar control panel for scenario loading, 4-way volume inputs, signal parameters, and database persistence."""

import streamlit as st
from typing import Dict, Tuple, Optional
from config.constants import (
    DIRECTIONS,
    DEFAULT_CYCLE_MIN,
    DEFAULT_CYCLE_MAX,
    DEFAULT_FIXED_CYCLE,
    DEFAULT_YELLOW,
    DEFAULT_ALL_RED,
    DEFAULT_SATURATION_PER_LANE_VPH,
    DEFAULT_MIN_GREEN,
    DEFAULT_MAX_GREEN,
    DEFAULT_ANALYSIS_PERIOD_SEC,
    DEFAULT_RANDOM_SEED
)
from config.presets import PRESET_SCENARIOS
from models.schemas import ApproachInput, SignalTimingConfig
from database.repository import list_scenarios, load_scenario, save_scenario, delete_scenario


def render_sidebar() -> Tuple[Dict[str, ApproachInput], SignalTimingConfig, bool]:
    """Render the sidebar controls and return (approaches, timing_config, trigger_run)."""
    st.sidebar.title("🛠️ Intersection Controls")

    # --- 1. Scenario Management ---
    st.sidebar.subheader("📂 Scenario Selection")
    preset_names = list(PRESET_SCENARIOS.keys())
    saved_db_scenarios = list_scenarios()
    saved_names = [f"💾 {s['name']} (ID: {s['id']})" for s in saved_db_scenarios]

    all_scenario_options = ["Custom Input"] + preset_names + saved_names

    selected_scenario = st.sidebar.selectbox(
        "Load Preset or Saved Scenario",
        options=all_scenario_options,
        index=1  # Default to "Balanced Urban Flow"
    )

    # Initialize or populate session state defaults based on selection
    if "loaded_scenario_name" not in st.session_state or st.session_state.loaded_scenario_name != selected_scenario:
        st.session_state.loaded_scenario_name = selected_scenario

        if selected_scenario in PRESET_SCENARIOS:
            scen_data = PRESET_SCENARIOS[selected_scenario]
            st.session_state.cycle_min = scen_data.get("cycle_min", DEFAULT_CYCLE_MIN)
            st.session_state.cycle_max = scen_data.get("cycle_max", DEFAULT_CYCLE_MAX)
            st.session_state.fixed_cycle = scen_data.get("fixed_cycle", DEFAULT_FIXED_CYCLE)
            for d in DIRECTIONS:
                app_data = scen_data["approaches"][d]
                st.session_state[f"{d}_vol"] = float(app_data["volume_vph"])
                st.session_state[f"{d}_lanes"] = int(app_data["num_lanes"])
                st.session_state[f"{d}_sat"] = float(app_data["sat_flow_lane"])
                st.session_state[f"{d}_min_g"] = float(app_data["min_green"])
                st.session_state[f"{d}_max_g"] = float(app_data["max_green"])
                st.session_state[f"{d}_weight"] = float(app_data.get("weight", 1.0))

        elif selected_scenario.startswith("💾 "):
            # Extract scenario ID
            scen_id = int(selected_scenario.split("ID: ")[1].rstrip(")"))
            loaded = load_scenario(scen_id)
            if loaded:
                timing, apps, _, _ = loaded
                st.session_state.cycle_min = timing.cycle_min
                st.session_state.cycle_max = timing.cycle_max
                st.session_state.fixed_cycle = timing.fixed_cycle_time
                for d in DIRECTIONS:
                    app_obj = apps[d]
                    st.session_state[f"{d}_vol"] = float(app_obj.volume_vph)
                    st.session_state[f"{d}_lanes"] = int(app_obj.num_lanes)
                    st.session_state[f"{d}_sat"] = float(app_obj.saturation_per_lane_vph)
                    st.session_state[f"{d}_min_g"] = float(app_obj.min_green_sec)
                    st.session_state[f"{d}_max_g"] = float(app_obj.max_green_sec)
                    st.session_state[f"{d}_weight"] = float(app_obj.priority_weight)

    # --- 2. 4-Way Approach Inputs ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚗 4-Way Traffic Demand")

    approaches: Dict[str, ApproachInput] = {}
    direction_icons = {"North": "⬆️ North", "South": "⬇️ South", "East": "➡️ East", "West": "⬅️ West"}

    for d in DIRECTIONS:
        with st.sidebar.expander(f"{direction_icons[d]} Approach", expanded=(d in ("North", "South"))):
            vol = st.number_input(
                f"{d} Volume (veh/hr)",
                min_value=0.0,
                max_value=3500.0,
                value=float(st.session_state.get(f"{d}_vol", 600.0)),
                step=50.0,
                key=f"input_{d}_vol"
            )
            col1, col2 = st.columns(2)
            with col1:
                lanes = st.number_input(
                    f"Lanes",
                    min_value=1,
                    max_value=6,
                    value=int(st.session_state.get(f"{d}_lanes", 2)),
                    step=1,
                    key=f"input_{d}_lanes"
                )
            with col2:
                sat_flow = st.number_input(
                    f"Sat Flow/Lane",
                    min_value=1000.0,
                    max_value=2400.0,
                    value=float(st.session_state.get(f"{d}_sat", DEFAULT_SATURATION_PER_LANE_VPH)),
                    step=50.0,
                    key=f"input_{d}_sat"
                )

            col3, col4 = st.columns(2)
            with col3:
                min_g = st.number_input(
                    f"Min Green (s)",
                    min_value=5.0,
                    max_value=30.0,
                    value=float(st.session_state.get(f"{d}_min_g", DEFAULT_MIN_GREEN)),
                    step=1.0,
                    key=f"input_{d}_min_g"
                )
            with col4:
                max_g = st.number_input(
                    f"Max Green (s)",
                    min_value=25.0,
                    max_value=90.0,
                    value=float(st.session_state.get(f"{d}_max_g", DEFAULT_MAX_GREEN)),
                    step=5.0,
                    key=f"input_{d}_max_g"
                )

            weight = st.slider(
                f"{d} Priority Weight",
                min_value=0.5,
                max_value=3.0,
                value=float(st.session_state.get(f"{d}_weight", 1.0)),
                step=0.1,
                key=f"input_{d}_weight",
                help="Higher weight penalizes delay more heavily in the LP objective function."
            )

            approaches[d] = ApproachInput(
                direction=d,
                volume_vph=vol,
                num_lanes=int(lanes),
                saturation_per_lane_vph=sat_flow,
                min_green_sec=min_g,
                max_green_sec=max_g,
                priority_weight=weight
            )

    # Optional PCU Helper
    with st.sidebar.expander("🧮 PCU (Passenger Car Unit) Helper"):
        st.caption("Convert mixed vehicle counts to equivalent PCU/hr:")
        pcu_cars = st.number_input("Cars (1.0 PCU)", min_value=0, value=400, step=25)
        pcu_2w = st.number_input("Two-Wheelers (0.5 PCU)", min_value=0, value=300, step=25)
        pcu_bus = st.number_input("Buses / Trucks (2.5 PCU)", min_value=0, value=40, step=5)
        total_pcu = (pcu_cars * 1.0) + (pcu_2w * 0.5) + (pcu_bus * 2.5)
        st.info(f"**Total Calculated**: {total_pcu:.0f} PCU/hr")

    # --- 3. Signal Timing & Simulation Settings ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Signal & Simulation Settings")

    col_c1, col_c2 = st.sidebar.columns(2)
    with col_c1:
        c_min = st.number_input(
            "Cycle Min (s)",
            min_value=40.0,
            max_value=120.0,
            value=float(st.session_state.get("cycle_min", DEFAULT_CYCLE_MIN)),
            step=5.0
        )
    with col_c2:
        c_max = st.number_input(
            "Cycle Max (s)",
            min_value=80.0,
            max_value=180.0,
            value=float(st.session_state.get("cycle_max", DEFAULT_CYCLE_MAX)),
            step=5.0
        )

    fixed_c = st.sidebar.number_input(
        "Fixed-Time Baseline Cycle (s)",
        min_value=60.0,
        max_value=160.0,
        value=float(st.session_state.get("fixed_cycle", DEFAULT_FIXED_CYCLE)),
        step=5.0
    )

    with st.sidebar.expander("Advanced Signal Parameters"):
        yellow = st.number_input("Yellow Clearance (s)", min_value=2.0, max_value=5.0, value=DEFAULT_YELLOW, step=0.5)
        all_red = st.number_input("All-Red Clearance (s)", min_value=0.5, max_value=3.0, value=DEFAULT_ALL_RED, step=0.5)
        analysis_period = st.number_input("Analysis Period (s)", min_value=300.0, max_value=3600.0, value=DEFAULT_ANALYSIS_PERIOD_SEC, step=300.0)
        sim_seed = st.number_input("Simulation Random Seed", min_value=1, max_value=99999, value=DEFAULT_RANDOM_SEED, step=1)

    timing_config = SignalTimingConfig(
        cycle_min=c_min,
        cycle_max=c_max,
        fixed_cycle_time=fixed_c,
        yellow_time=yellow,
        all_red_time=all_red,
        analysis_period_sec=analysis_period,
        random_seed=int(sim_seed)
    )

    # --- 4. Primary Run & Save Actions ---
    st.sidebar.markdown("---")
    trigger_run = st.sidebar.button("🚀 Run Optimization & Simulation", type="primary", width="stretch")

    with st.sidebar.expander("💾 Save Current Scenario to SQLite"):
        scen_name_input = st.text_input("Scenario Name", value=f"Scenario_{selected_scenario.replace(' ', '_')}")
        scen_desc_input = st.text_area("Scenario Notes", value="Custom parameters configured in sidebar.")
        if st.button("Save to Database", width="stretch"):
            if scen_name_input.strip():
                new_id = save_scenario(scen_name_input.strip(), scen_desc_input.strip(), timing_config, approaches)
                st.success(f"Saved to SQLite as ID #{new_id}!")
                st.rerun()
            else:
                st.error("Please enter a valid scenario name.")

    return approaches, timing_config, trigger_run

