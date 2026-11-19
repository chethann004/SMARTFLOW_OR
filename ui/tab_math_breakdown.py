"""Tab 3: Step-by-Step Operations Research Mathematical Models and Live Formula Calculations."""

import streamlit as st
import pandas as pd
from typing import Dict, Any

from models.schemas import ApproachInput, SignalTimingConfig, IntersectionEvaluation


def render_math_breakdown_tab(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    opt_eval: IntersectionEvaluation,
    fixed_eval: IntersectionEvaluation
):
    """Render the academic step-by-step mathematical breakdown with live substituted values."""
    st.subheader("📐 Operations Research Mathematical Models & Live Derivations")
    st.markdown(
        """
        This tab exposes the formal mathematical formulations underpinning **SmartFlow OR**.
        Every equation is populated dynamically with the active scenario parameters.
        """
    )

    # --- 1. Traffic Flow & Capacity Fundamentals ---
    with st.expander("1. Flow Rates, Capacity & Webster's Theory", expanded=True):
        st.markdown(
            r"""
            ### 1.1 Arrival Rate ($\lambda_i$) & Saturation Flow Rate ($s_i$)
            For each approach $i \in \{\text{North, South, East, West}\}$:
            $$\lambda_i = \frac{V_i}{3600} \quad (\text{veh/s}), \qquad s_i = \frac{n_i \cdot S_{\text{lane}}}{3600} \quad (\text{veh/s})$$
            where $V_i$ is manual arrival volume ($\text{veh/hr}$), $n_i$ is the number of lanes, and $S_{\text{lane}}$ is saturation flow per lane (default $1800\text{ veh/hr/lane} = 0.5\text{ veh/s/lane}$).
            """
        )

        flow_table = []
        for d, a in approaches.items():
            flow_table.append({
                "Approach": d,
                "Volume V_i (vph)": a.volume_vph,
                "Arrival Rate lambda_i (vps)": f"{a.arrival_rate_vps:.4f}",
                "Lanes n_i": a.num_lanes,
                "Saturation s_i (vps)": f"{a.sat_flow_rate_vps:.3f}",
                "Flow Ratio y_i": f"{a.flow_ratio_y:.4f}"
            })
        st.dataframe(pd.DataFrame(flow_table), width="stretch", hide_index=True)

        sum_y_str = f"{opt_eval.sum_flow_ratio_y:.4f}"
        lost_t_str = f"{opt_eval.total_lost_time_sec:.1f}"
        st.markdown(
            f"""
            ### 1.2 Total Critical Intersection Flow Ratio ($Y$) & Theoretical Webster Cycle
            $$Y = \\sum_{{i=1}}^4 y_i = {sum_y_str}$$
            Total effective lost time per cycle:
            $$L = 4 \\times \\big[(Y_{{\\text{{yellow}}}} + AR) + l_{{\\text{{start}}}} - e_{{\\text{{gain}}}}\\big] = {lost_t_str}\\text{{ s}}$$
            """
        )

        if opt_eval.sum_flow_ratio_y < 0.95:
            webster_c = (1.5 * opt_eval.total_lost_time_sec + 5.0) / (1.0 - opt_eval.sum_flow_ratio_y)
            st.latex(
                f"C_{{\\text{{Webster}}}}^* = \\frac{{1.5 L + 5}}{{1 - Y}} = \\frac{{1.5({lost_t_str}) + 5}}{{1 - {sum_y_str}}} = {webster_c:.1f}\\text{{ s}}"
            )
        else:
            st.warning(
                f"⚠️ Total critical flow ratio Y = {opt_eval.sum_flow_ratio_y:.3f} >= 0.95 (near or above junction capacity). "
                f"Webster's formula diverges to infinity under saturation, demonstrating why our PuLP LP optimizer with "
                f"coordinate-transformed M/D/1 is required to select a realistic optimal cycle."
            )

    # --- 2. Queuing Theory Delay Decomposition ---
    with st.expander("2. Queuing Theory Model: D/D/1 Uniform + M/D/1 Overflow Delay", expanded=True):
        st.markdown(
            r"""
            Because signalized approaches receive service cyclically during green phases rather than continuously,
            total average delay per vehicle is decomposed into two distinct components:
            $$W_i = d_{1, i} + d_{2, i}$$
            """
        )

        st.markdown(
            r"""
            #### (A) Deterministic Uniform Red-Phase Delay ($d_{1, i}$ — $D/D/1$ Polygon)
            $$d_{1, i} = \frac{C \left(1 - \frac{g_i}{C}\right)^2}{2 \left(1 - \min(1, \rho_i) \cdot \frac{g_i}{C}\right)}$$
            When $\rho_i < 1$, this represents the exact average waiting time of vehicles queued during the red phase.
            When $\rho_i \ge 1$, it cleanly bounds at $\frac{C - g_i}{2}$ without division-by-zero errors.
            """
        )

        st.markdown(
            r"""
            #### (B) Stochastic Overflow Delay ($d_{2, i}$ — Coordinate-Transformed $M/D/1$)
            Over an evaluation horizon of $T = 900\text{ s}$ (15 minutes):
            $$d_{2, i} = \frac{T}{4} \left[ (\rho_i - 1) + \sqrt{(\rho_i - 1)^2 + \frac{4 \rho_i}{\mu_{\text{eff}, i} \cdot T}} \right]$$
            - For $\rho_i < 1$, as $T \to \infty$, this converges to Pollaczek-Khinchine $M/D/1$: $\frac{\rho_i}{2 \mu_{\text{eff}, i}(1 - \rho_i)} = \frac{\rho_i^2}{2 \lambda_i (1 - \rho_i)}$.
            - For $\rho_i \ge 1$, it models linear deterministic queue growth $\frac{T}{2}(\rho_i - 1)$.
            """
        )

        st.markdown(
            r"""
            #### (C) Little's Law for Average Queue Length ($L_{q, i}$)
            $$L_{q, i} = \lambda_i \cdot W_i \quad (\text{vehicles})$$
            Expected maximum back-of-queue at end of red:
            $$Q_{\max, i} = \lambda_i (C - g_i) + \lambda_i \cdot d_{2, i} \quad (\text{vehicles})$$
            """
        )

        # Live calculation breakdown table for the optimized plan
        q_breakdown = []
        for d, res in opt_eval.approaches.items():
            q_breakdown.append({
                "Approach": d,
                "Green g_i (s)": f"{res.allocated_green_sec:.1f}",
                "Cap mu_eff (vps)": f"{res.effective_service_rate_vps:.3f}",
                "Sat. rho (v/c)": f"{res.degree_of_saturation_rho:.3f}",
                "Uniform d1 (s)": f"{res.uniform_delay_d1_sec:.2f}",
                "Overflow d2 (s)": f"{res.overflow_delay_d2_sec:.2f}",
                "Total Delay W_i (s)": f"{res.avg_wait_time_sec:.2f}",
                "Queue L_q (veh)": f"{res.avg_queue_length_veh:.2f}",
                "Max Queue Q_max (veh)": f"{res.max_queue_length_veh:.1f}",
                "HCM LOS": res.los_grade
            })
        st.dataframe(pd.DataFrame(q_breakdown), width="stretch", hide_index=True)

    # --- 3. Linear Programming Formulation (PuLP) ---
    with st.expander("3. Linear Programming (LP) Green Allocation Formulation", expanded=True):
        st.markdown(
            f"""
            ### 3.1 LP Decision Model
            - **Decision Variables**:
              - $g_N, g_S, g_E, g_W \\ge 0$: Effective green allocations ($\\text{{s}}$).
              - $\\hat{{L}}_{{q, i}} \\ge 0$: Piecewise-linear convex envelope queue variables.
              - $q_{{\\text{{ovf}}, i}} \\ge 0$: Unmet cycle capacity overflow penalty slack.
            - **Objective Function**:
              $$\\min Z = \\sum_{{i \\in \\mathcal{{I}}}} \\hat{{L}}_{{q, i}} + 10 \\sum_{{i \\in \\mathcal{{I}}}} q_{{\\text{{ovf}}, i}}$$
            - **Constraints**:
              1. **Cycle Budget**:
                 $$g_N + g_S + g_E + g_W = C^* - L = {opt_eval.cycle_time_sec:.1f} - {opt_eval.total_lost_time_sec:.1f} = {opt_eval.total_green_sec:.1f}\\text{{ s}}$$
              2. **Bounds**: $g_{{\\min, i}} \\le g_i \\le g_{{\\max, i}} \\quad \\forall i$.
              3. **Convex Supporting Hyperplanes (Tangent Cuts)**:
                 $$\\hat{{L}}_{{q, i}} \\ge w_i \\lambda_i \\left[ W_i(g_k) + W_i'(g_k)(g_i - g_k) \\right] \\quad \\forall k \\in \\{{0, \\dots, K\\}}$$
            - **Solver Used**: PuLP CBC (Coin-OR Branch and Cut)
            - **Solver Status**: `{opt_eval.solver_status}` (Solved in {opt_eval.solve_time_ms:.1f} ms)
            """
        )

    # --- 4. Textbook M/M/1 Comparison Note ---
    with st.expander("4. Textbook M/M/1 Queue Comparison (Educational Note)"):
        st.markdown(
            r"""
            In introductory Operations Research courses, students study continuous $M/M/1$ queues:
            $$W_{q, M/M/1} = \frac{\rho_i}{\mu_{\text{eff}, i} (1 - \rho_i)} \quad (\text{for } \rho_i < 1)$$
            **Why $M/M/1$ alone does not model traffic signals accurately**:
            - At a traffic signal, service is **intermittent** (0 veh/s during red, $s_i$ veh/s during green).
            - Vehicles arriving during red accumulate deterministic delay $d_1$, which $M/M/1$ completely ignores.
            - That is why Highway Engineering uses **Webster's / HCM formulation** combining $D/D/1$ cyclic red-phase delay with coordinate-transformed $M/D/1$ overflow delay!
            """
        )
        mm1_rows = []
        for d, res in opt_eval.approaches.items():
            mm1_val = f"{res.mm1_reference_wait_sec:.1f} s" if res.mm1_reference_wait_sec else "N/A (rho >= 1)"
            mm1_rows.append({
                "Approach": d,
                "Saturation rho": f"{res.degree_of_saturation_rho:.3f}",
                "SmartFlow Delay (d1 + d2)": f"{res.avg_wait_time_sec:.1f} s",
                "Continuous M/M/1 Reference": mm1_val
            })
        st.dataframe(pd.DataFrame(mm1_rows), width="stretch", hide_index=True)
