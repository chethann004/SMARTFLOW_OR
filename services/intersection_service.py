"""High-level application coordinator linking inputs, OR engines, simulation, and SQLite storage."""

from typing import Dict, Tuple, Optional, Any
from models.schemas import (
    ApproachInput,
    SignalTimingConfig,
    IntersectionEvaluation,
    EmergencyPreemptionResult,
    SimulationTrace
)
from core.lp_optimizer import (
    optimize_cycle_and_green,
    compute_fixed_time_baseline
)
from core.scheduler_milp import schedule_emergency_preemption_milp
from core.simulation import run_discrete_junction_simulation
from core.sensitivity import perform_demand_sweep, perform_global_scaling_sweep, extract_shadow_prices_summary
from database.repository import (
    save_optimization_run,
    save_emergency_event,
    save_simulation_run
)


def evaluate_scenario_full(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    scenario_id: Optional[int] = None,
    persist_to_db: bool = True
) -> Tuple[IntersectionEvaluation, IntersectionEvaluation, Dict[float, float]]:
    """Execute complete analytical evaluation of Fixed-Time Baseline and SmartFlow LP Optimized."""
    # 1. Evaluate Fixed-Time Baseline
    fixed_eval = compute_fixed_time_baseline(approaches, timing)

    # 2. Joint LP Optimization over Cycle C and Green splits g_i
    opt_eval, cycle_curve = optimize_cycle_and_green(approaches, timing)

    # 3. Persist to SQLite if requested
    if persist_to_db:
        fixed_run_id = save_optimization_run(scenario_id, fixed_eval)
        opt_run_id = save_optimization_run(scenario_id, opt_eval)

    return fixed_eval, opt_eval, cycle_curve


def run_emergency_preemption_pipeline(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    ev_direction: str,
    ev_type: str = "Ambulance",
    ev_arrival_time_sec: float = 15.0,
    current_active_phase: str = "East",
    elapsed_active_green_sec: float = 6.0,
    queued_vehicles_ahead: int = 4,
    opt_run_id: Optional[int] = None,
    persist_to_db: bool = True
) -> EmergencyPreemptionResult:
    """Run MILP Emergency Vehicle Preemption scheduler and optionally persist event to SQLite."""
    em_res = schedule_emergency_preemption_milp(
        approaches=approaches,
        timing=timing,
        ev_direction=ev_direction,
        ev_type=ev_type,
        ev_arrival_time_sec=ev_arrival_time_sec,
        current_active_phase=current_active_phase,
        elapsed_active_green_sec=elapsed_active_green_sec,
        queued_vehicles_ahead=queued_vehicles_ahead
    )
    if persist_to_db:
        save_emergency_event(opt_run_id, em_res)
    return em_res


def run_junction_simulation_pipeline(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    fixed_eval: IntersectionEvaluation,
    opt_eval: IntersectionEvaluation,
    duration_sec: int = 900,
    arrival_mode: str = "Poisson",
    random_seed: int = 42,
    emergency_event: Optional[EmergencyPreemptionResult] = None,
    scenario_id: Optional[int] = None,
    fixed_run_id: Optional[int] = None,
    opt_run_id: Optional[int] = None,
    persist_to_db: bool = True
) -> SimulationTrace:
    """Run discrete-time (1s) Common Random Numbers simulation and optionally persist to SQLite."""
    trace = run_discrete_junction_simulation(
        approaches=approaches,
        timing=timing,
        fixed_eval=fixed_eval,
        opt_eval=opt_eval,
        duration_sec=duration_sec,
        arrival_mode=arrival_mode,
        random_seed=random_seed,
        emergency_event=emergency_event
    )
    if persist_to_db:
        save_simulation_run(scenario_id, fixed_run_id, opt_run_id, trace)
    return trace

