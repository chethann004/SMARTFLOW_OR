"""Discrete-time (1-second step) microscopic simulation engine for 4-way traffic junctions.

Uses Common Random Numbers (CRN) to feed identical vehicle arrival streams to both
Fixed-Time and SmartFlow OR Optimized controllers for statistically rigorous comparison.
"""

from collections import deque
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

from models.schemas import (
    ApproachInput,
    SignalTimingConfig,
    IntersectionEvaluation,
    EmergencyPreemptionResult,
    SimulationTrace
)


class SignalControllerState:
    """Manages the cyclic phase state machine for a 4-way intersection."""

    def __init__(
        self,
        green_splits: Dict[str, float],
        cycle_sec: float,
        intergreen_sec: float,
        preemption_blocks: Optional[List[Dict[str, Any]]] = None,
        preemption_start_sec: Optional[float] = None
    ):
        self.sequence = ["North", "South", "East", "West"]
        self.green_splits = green_splits
        self.cycle_sec = cycle_sec
        self.intergreen_sec = intergreen_sec
        self.preemption_blocks = preemption_blocks
        self.preemption_start_sec = preemption_start_sec

    def get_signal_states_at_time(self, t_sec: float) -> Tuple[Dict[str, str], str]:
        """Return dict of {direction: 'GREEN' | 'YELLOW' | 'RED'} and currently active phase."""
        # Handle emergency preemption window if active
        if self.preemption_blocks and self.preemption_start_sec is not None:
            rel_t = t_sec - self.preemption_start_sec
            total_preempt_len = self.preemption_blocks[-1]["phase_end_sec"] if self.preemption_blocks else 0.0

            if 0.0 <= rel_t < total_preempt_len:
                for block in self.preemption_blocks:
                    if block["start_sec"] <= rel_t < block["phase_end_sec"]:
                        active_p = block["phase"]
                        if rel_t < block["green_end_sec"]:
                            color = "GREEN"
                        else:
                            color = "YELLOW"
                        states = {d: "RED" for d in self.sequence}
                        states[active_p] = color
                        return states, active_p

        # Normal cyclic operation
        cycle_pos = t_sec % self.cycle_sec
        cumulative_t = 0.0

        for d in self.sequence:
            g = self.green_splits.get(d, 10.0)
            g_end = cumulative_t + g
            phase_end = g_end + self.intergreen_sec

            if cumulative_t <= cycle_pos < phase_end:
                color = "GREEN" if cycle_pos < g_end else "YELLOW"
                states = {direction: "RED" for direction in self.sequence}
                states[d] = color
                return states, d

            cumulative_t = phase_end

        # Default fallback
        states = {d: "RED" for d in self.sequence}
        states["North"] = "GREEN"
        return states, "North"


def run_discrete_junction_simulation(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    fixed_eval: IntersectionEvaluation,
    opt_eval: IntersectionEvaluation,
    duration_sec: int = 900,
    arrival_mode: str = "Poisson",
    random_seed: int = 42,
    emergency_event: Optional[EmergencyPreemptionResult] = None
) -> SimulationTrace:
    """Run dual-controller 1-second step simulation using Common Random Numbers (CRN)."""
    rng = np.random.default_rng(random_seed)

    # 1. Pre-generate Common Random Arrival stream for all approaches
    # arrivals_stream[d][t] = number of vehicles arriving at second t
    arrivals_stream: Dict[str, List[int]] = {d: [0] * duration_sec for d in approaches}

    for d, app in approaches.items():
        lam = app.arrival_rate_vps
        if arrival_mode.lower() == "deterministic":
            acc = 0.0
            for t in range(duration_sec):
                acc += lam
                if acc >= 1.0:
                    cnt = int(acc)
                    arrivals_stream[d][t] = cnt
                    acc -= cnt
        else:
            # Poisson arrival events
            arrivals_stream[d] = list(rng.poisson(lam, duration_sec))

    # 2. Setup Signal Controllers
    fixed_greens = {d: fixed_eval.approaches[d].allocated_green_sec for d in approaches}
    opt_greens = {d: opt_eval.approaches[d].allocated_green_sec for d in approaches}

    intergreen = timing.intergreen_per_phase

    fixed_ctrl = SignalControllerState(
        green_splits=fixed_greens,
        cycle_sec=fixed_eval.cycle_time_sec,
        intergreen_sec=intergreen
    )

    opt_ctrl = SignalControllerState(
        green_splits=opt_greens,
        cycle_sec=opt_eval.cycle_time_sec,
        intergreen_sec=intergreen,
        preemption_blocks=emergency_event.schedule_blocks if emergency_event else None,
        preemption_start_sec=emergency_event.arrival_time_sec if emergency_event else None
    )

    # Simulation State Tracking for Fixed Controller
    fixed_queues: Dict[str, deque] = {d: deque() for d in approaches}
    fixed_discharged_waits: Dict[str, List[float]] = {d: [] for d in approaches}
    fixed_discharge_acc: Dict[str, float] = {d: 0.0 for d in approaches}
    fixed_max_q: Dict[str, int] = {d: 0 for d in approaches}

    # Simulation State Tracking for Optimized Controller
    opt_queues: Dict[str, deque] = {d: deque() for d in approaches}
    opt_discharged_waits: Dict[str, List[float]] = {d: [] for d in approaches}
    opt_discharge_acc: Dict[str, float] = {d: 0.0 for d in approaches}
    opt_max_q: Dict[str, int] = {d: 0 for d in approaches}

    second_records: List[Dict[str, Any]] = []

    # 3. Step through time second-by-second (t = 0 to duration_sec - 1)
    record_sample_interval = max(1, duration_sec // 180)  # ~180 points for smooth charts

    for t in range(duration_sec):
        # A. Arrivals happen identically for both
        for d in approaches:
            arr_count = arrivals_stream[d][t]
            for _ in range(arr_count):
                fixed_queues[d].append(t)
                opt_queues[d].append(t)

        # B. Get current signal states
        fixed_signals, fixed_active = fixed_ctrl.get_signal_states_at_time(float(t))
        opt_signals, opt_active = opt_ctrl.get_signal_states_at_time(float(t))

        # C. Discharge physics for Fixed controller
        for d, app in approaches.items():
            if fixed_signals[d] == "GREEN":
                sat_rate = app.sat_flow_rate_vps
                fixed_discharge_acc[d] += sat_rate
                while fixed_discharge_acc[d] >= 1.0 and fixed_queues[d]:
                    arr_time = fixed_queues[d].popleft()
                    wait_sec = float(t - arr_time)
                    fixed_discharged_waits[d].append(wait_sec)
                    fixed_discharge_acc[d] -= 1.0
            else:
                fixed_discharge_acc[d] = 0.0

            q_len = len(fixed_queues[d])
            if q_len > fixed_max_q[d]:
                fixed_max_q[d] = q_len

        # D. Discharge physics for Optimized controller
        for d, app in approaches.items():
            if opt_signals[d] == "GREEN":
                sat_rate = app.sat_flow_rate_vps
                opt_discharge_acc[d] += sat_rate
                while opt_discharge_acc[d] >= 1.0 and opt_queues[d]:
                    arr_time = opt_queues[d].popleft()
                    wait_sec = float(t - arr_time)
                    opt_discharged_waits[d].append(wait_sec)
                    opt_discharge_acc[d] -= 1.0
            else:
                opt_discharge_acc[d] = 0.0

            q_len = len(opt_queues[d])
            if q_len > opt_max_q[d]:
                opt_max_q[d] = q_len

        # E. Sample timeseries data for visual replay and graphs
        if t % record_sample_interval == 0 or t == duration_sec - 1:
            second_records.append({
                "time_sec": t,
                "fixed_active": fixed_active,
                "opt_active": opt_active,
                "fixed_signals": fixed_signals,
                "opt_signals": opt_signals,
                "fixed_queues": {d: len(fixed_queues[d]) for d in approaches},
                "opt_queues": {d: len(opt_queues[d]) for d in approaches},
                "total_fixed_queue": sum(len(fixed_queues[d]) for d in approaches),
                "total_opt_queue": sum(len(opt_queues[d]) for d in approaches)
            })

    # 4. Compute comprehensive summary statistics
    # Account for unserved queued vehicles at end of simulation to prevent oversaturation truncation bias
    for d in approaches:
        for arr_time in fixed_queues[d]:
            fixed_discharged_waits[d].append(float(duration_sec - arr_time))
        for arr_time in opt_queues[d]:
            opt_discharged_waits[d].append(float(duration_sec - arr_time))

    all_fixed_waits = [w for d in approaches for w in fixed_discharged_waits[d]]
    all_opt_waits = [w for d in approaches for w in opt_discharged_waits[d]]

    fixed_avg_wait = float(np.mean(all_fixed_waits)) if all_fixed_waits else 0.0
    opt_avg_wait = float(np.mean(all_opt_waits)) if all_opt_waits else 0.0

    fixed_throughput = sum(len(fixed_discharged_waits[d]) - len(fixed_queues[d]) for d in approaches)
    opt_throughput = sum(len(opt_discharged_waits[d]) - len(opt_queues[d]) for d in approaches)

    fixed_summary = {
        "avg_wait_sec": round(fixed_avg_wait, 1),
        "max_queue_veh": max(fixed_max_q.values()) if fixed_max_q else 0,
        "throughput_veh": fixed_throughput,
        "per_approach_avg_wait": {
            d: round(float(np.mean(fixed_discharged_waits[d])), 1) if fixed_discharged_waits[d] else 0.0
            for d in approaches
        },
        "per_approach_max_queue": dict(fixed_max_q)
    }

    opt_summary = {
        "avg_wait_sec": round(opt_avg_wait, 1),
        "max_queue_veh": max(opt_max_q.values()) if opt_max_q else 0,
        "throughput_veh": opt_throughput,
        "per_approach_avg_wait": {
            d: round(float(np.mean(opt_discharged_waits[d])), 1) if opt_discharged_waits[d] else 0.0
            for d in approaches
        },
        "per_approach_max_queue": dict(opt_max_q)
    }

    # Analytical vs Simulated Validation Comparison Table
    analytical_vs_sim: Dict[str, Dict[str, float]] = {}
    for d in approaches:
        analytical_vs_sim[d] = {
            "analytical_opt_wait": opt_eval.approaches[d].avg_wait_time_sec,
            "simulated_opt_wait": opt_summary["per_approach_avg_wait"].get(d, 0.0),
            "analytical_fixed_wait": fixed_eval.approaches[d].avg_wait_time_sec,
            "simulated_fixed_wait": fixed_summary["per_approach_avg_wait"].get(d, 0.0),
            "simulated_opt_max_q": opt_summary["per_approach_max_queue"].get(d, 0),
            "simulated_fixed_max_q": fixed_summary["per_approach_max_queue"].get(d, 0)
        }

    return SimulationTrace(
        scenario_name="4-Way Junction Common-Random Simulation",
        duration_sec=duration_sec,
        arrival_mode=arrival_mode,
        random_seed=random_seed,
        fixed_summary=fixed_summary,
        opt_summary=opt_summary,
        second_by_second_records=second_records,
        analytical_vs_sim_comparison=analytical_vs_sim
    )

