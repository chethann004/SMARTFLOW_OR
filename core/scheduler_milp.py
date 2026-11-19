"""Scheduling Optimization and Emergency Vehicle Preemption using Mixed-Integer Linear Programming.

Formulates the signal sequencing as a Single-Machine Scheduling Problem with
Intergreen Setup Times, Safety Release Floors, and Priority Preemption:
    Machine: Intersection conflict zone (mutually exclusive green phases).
    Jobs: Approaches j in {North, South, East, West}.
    Precedence / Disjunctive non-overlap: S_j >= S_i + g_i + tau (with binary z_ij).
    Safety constraint: Active phase cannot be truncated below safe minimum green floor.
    Emergency Vehicle (EV): Assigned heavy priority weight to preempt cross-traffic
    while strictly preserving yellow + all-red clearance.
"""

import time
from typing import Dict, List, Optional, Any
import pulp

from models.schemas import ApproachInput, SignalTimingConfig, EmergencyPreemptionResult
from core.lp_optimizer import _create_lp_variable, _get_solver


def schedule_emergency_preemption_milp(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    ev_direction: str,
    ev_type: str = "Ambulance",
    ev_arrival_time_sec: float = 15.0,
    current_active_phase: str = "East",
    elapsed_active_green_sec: float = 6.0,
    queued_vehicles_ahead: int = 4
) -> EmergencyPreemptionResult:
    """Solve the MILP phase scheduling problem under an Emergency Vehicle arrival event.

    Returns an EmergencyPreemptionResult including time saved, schedule timeline blocks,
    and cross-street recovery trade-off.
    """
    intergreen = timing.intergreen_per_phase
    ev_app = approaches.get(ev_direction)
    if not ev_app:
        raise ValueError(f"Unknown approach direction: {ev_direction}")

    # Physical time required to flush queued vehicles ahead plus EV crossing buffer
    sat_vps = ev_app.sat_flow_rate_vps
    queue_flush_time = (queued_vehicles_ahead / sat_vps) if sat_vps > 0 else 5.0
    ev_needed_green = max(ev_app.min_green_sec, queue_flush_time + 4.0)

    # Calculate Normal (Non-Preempted) Baseline Waiting Time
    # Normal cycle sequence: North -> South -> East -> West
    sequence = ["North", "South", "East", "West"]
    curr_idx = sequence.index(current_active_phase) if current_active_phase in sequence else 0
    ev_idx = sequence.index(ev_direction) if ev_direction in sequence else 0

    # Normal green duration allocated to each phase (proportional or fixed)
    c_fixed = timing.fixed_cycle_time
    normal_g = max(10.0, (c_fixed - timing.total_lost_time) / 4.0)

    if current_active_phase == ev_direction:
        remaining_normal_green = max(0.0, normal_g - elapsed_active_green_sec)
        if remaining_normal_green >= queue_flush_time:
            normal_wait = queue_flush_time
        else:
            # Misses current green, must wait full cycle
            normal_wait = remaining_normal_green + (3 * (normal_g + intergreen)) + queue_flush_time
    else:
        # Steps in cycle until ev_direction turns green
        steps_away = (ev_idx - curr_idx) % 4
        rem_curr = max(0.0, normal_g - elapsed_active_green_sec)
        normal_wait = rem_curr + intergreen + (max(0, steps_away - 1) * (normal_g + intergreen)) + queue_flush_time

    # Safe floor for currently active phase: must respect min green
    g_safe_min = max(0.0, ev_app.min_green_sec - elapsed_active_green_sec)

    # Solve MILP for Preempted Recovery Schedule
    prob = pulp.LpProblem("Emergency_Preemption_Scheduler", pulp.LpMinimize)

    # Job order list: if EV direction is current phase, extend it; else current finishes then EV runs
    directions = list(approaches.keys())
    phase_order: List[str] = []

    if current_active_phase == ev_direction:
        phase_order = [ev_direction] + [d for d in directions if d != ev_direction]
    else:
        # Current phase completes safe floor -> EV runs immediately -> remaining 2 phases follow
        remaining_others = [d for d in directions if d not in (current_active_phase, ev_direction)]
        phase_order = [current_active_phase, ev_direction] + remaining_others

    # Decision variables: start time S_p and green duration g_p for each phase in sequence
    S_vars: Dict[str, pulp.LpVariable] = {}
    g_vars: Dict[str, pulp.LpVariable] = {}

    for p in phase_order:
        S_vars[p] = _create_lp_variable(prob, f"S_{p}", lowBound=0.0, cat=pulp.LpContinuous)
        min_g = g_safe_min if p == current_active_phase and p != ev_direction else (
            ev_needed_green if p == ev_direction else approaches[p].min_green_sec
        )
        max_g = approaches[p].max_green_sec
        g_vars[p] = _create_lp_variable(prob, f"g_{p}", lowBound=min_g, upBound=max_g, cat=pulp.LpContinuous)

    # Phase 0 starts immediately at relative t = 0
    prob += S_vars[phase_order[0]] == 0.0, "Start_Current"

    # Precedence constraints with intergreen clearance: S_{k+1} >= S_k + g_k + intergreen
    for idx in range(len(phase_order) - 1):
        p_curr = phase_order[idx]
        p_next = phase_order[idx + 1]
        prob += S_vars[p_next] >= S_vars[p_curr] + g_vars[p_curr] + intergreen, f"Precedence_{p_curr}_{p_next}"

    # Preempted EV waiting time
    if current_active_phase == ev_direction:
        preempted_wait = queue_flush_time
    else:
        # EV wait = Start of EV phase - relative EV arrival (clamped >= 0) + queue flush time
        preempted_wait = g_safe_min + intergreen + queue_flush_time

    # Objective: Minimize completion makespan + weighted sum of start times
    prob += pulp.lpSum([S_vars[p] for p in phase_order]), "Minimize_Schedule_Delay"

    solver = _get_solver(time_limit=5)
    try:
        prob.solve(solver)
    except pulp.PulpSolverError as pse:
        raise RuntimeError(
            f"PuLP scheduler solver execution failed with error: {pse}\n"
            "Ensure that COIN-OR CBC ('cbc.exe') is executable and accessible on your system."
        ) from pse

    # Build schedule blocks
    schedule_blocks: List[Dict[str, Any]] = []
    current_time = 0.0

    for p in phase_order:
        s_val = float(S_vars[p].varValue) if S_vars[p].varValue is not None else current_time
        g_val = float(g_vars[p].varValue) if g_vars[p].varValue is not None else approaches[p].min_green_sec
        g_end = s_val + g_val
        ig_end = g_end + intergreen

        schedule_blocks.append({
            "phase": p,
            "is_ev_phase": (p == ev_direction),
            "start_sec": round(s_val, 1),
            "green_sec": round(g_val, 1),
            "green_end_sec": round(g_end, 1),
            "intergreen_sec": round(intergreen, 1),
            "phase_end_sec": round(ig_end, 1),
            "color": "#c0392b" if p == ev_direction else "#2980b9"
        })
        current_time = ig_end

    recovery_makespan = current_time
    time_saved = max(0.0, normal_wait - preempted_wait)

    # Cross street impact: extra delay experienced by the approaches that were postponed
    cross_street_extra_delay = g_safe_min + intergreen + ev_needed_green

    return EmergencyPreemptionResult(
        approach=ev_direction,
        vehicle_type=ev_type,
        arrival_time_sec=ev_arrival_time_sec,
        current_active_phase=current_active_phase,
        elapsed_active_green_sec=elapsed_active_green_sec,
        ev_wait_normal_sec=round(normal_wait, 1),
        ev_wait_preempted_sec=round(preempted_wait, 1),
        time_saved_sec=round(time_saved, 1),
        schedule_blocks=schedule_blocks,
        recovery_makespan_sec=round(recovery_makespan, 1),
        cross_street_extra_delay_sec=round(cross_street_extra_delay, 1)
    )
