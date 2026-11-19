"""Linear Programming solver for optimal green signal allocation and cycle length.

Formulates and solves a Separable Convex Piecewise-Linear Program using PuLP (CBC):
    Minimize: Total weighted queued vehicles (Little's Law: sum(w_i * lambda_i * W_i(g_i)))
    Subject to:
        sum(g_i) = C - L  (Cycle Time Budget)
        g_min_i <= g_i <= g_max_i  (Safety and Starvation Bounds)
        L_hat_i >= w_i * lambda_i * [W_i(g_k) + W'_i(g_k) * (g_i - g_k)]  (Convex Tangents)
        s_i * g_i + q_ovf_i >= lambda_i * C  (Capacity Overflow Accounting)
"""

import time
import math
import os
import shutil
import logging
from typing import Dict, Tuple, Optional, List, Any
import numpy as np
import pulp

try:
    from pulp import LpProblem, LpVariable, LpContinuous, lpSum, COIN_CMD
except ImportError:
    LpProblem = getattr(pulp, "LpProblem", None)
    LpVariable = getattr(pulp, "LpVariable", None)
    LpContinuous = getattr(pulp, "LpContinuous", "Continuous")
    lpSum = getattr(pulp, "lpSum", sum)
    COIN_CMD = getattr(pulp, "COIN_CMD", None)

# Canonical status map across all PuLP versions
LP_STATUS_MAP: Dict[int, str] = {
    0: "Not Solved",
    1: "Optimal",
    -1: "Infeasible",
    -2: "Unbounded",
    -3: "Undefined",
}

try:
    from pulp import LpStatus
except (ImportError, AttributeError):
    try:
        from pulp.constants import LpStatus
    except (ImportError, AttributeError):
        LpStatus = LP_STATUS_MAP

logger = logging.getLogger(__name__)

from models.schemas import ApproachInput, SignalTimingConfig, IntersectionEvaluation
from core.queuing_theory import (
    compute_effective_service_rate,
    compute_degree_of_saturation,
    compute_uniform_delay_d1,
    compute_overflow_delay_d2,
    evaluate_intersection
)


def get_lp_status_str(prob: pulp.LpProblem, solve_result: Any = None) -> str:
    """Safely retrieve human-readable solver status string across PuLP 2.x, 3.x, and 4.x+.

    Handles:
    - PuLP 2.x int status codes via pulp.LpStatus dictionary.
    - PuLP 4.x LpSolveStatus IntEnum or solve statistics objects.
    - Missing or shadowed module attributes with canonical fallback dictionary.
    """
    # 1. Check if pulp or pulp.constants has LpStatus dictionary
    status_dict = getattr(pulp, "LpStatus", None)
    if status_dict is None:
        try:
            from pulp import constants
            status_dict = getattr(constants, "LpStatus", None)
        except (ImportError, AttributeError):
            status_dict = None
    if not isinstance(status_dict, dict):
        status_dict = LP_STATUS_MAP

    # 2. Extract status value from problem or solver output
    status_val = getattr(prob, "status", None)
    if status_val is None and solve_result is not None:
        status_val = getattr(solve_result, "status", solve_result)

    # 3. If status_val is an Enum (e.g. LpSolveStatus in PuLP 4.x)
    if hasattr(status_val, "name"):
        return str(status_val.name)

    # 4. If status_val is already a string
    if isinstance(status_val, str):
        return status_val

    # 5. Look up integer status code in dictionary
    if status_val in status_dict:
        return str(status_dict[status_val])
    if status_val in LP_STATUS_MAP:
        return str(LP_STATUS_MAP[status_val])

    return f"Status_{status_val}" if status_val is not None else "Optimal"


def find_cbc_executable() -> Optional[str]:
    """Detect the CBC (COIN-OR Branch and Cut) executable on the current system.

    Checks in priority order:
    1. Environment variables CBC_PATH and PULP_CBC_PATH.
    2. System PATH (via shutil.which).
    3. PuLP's bundled CBC binary (pulp_cbc_path).
    4. Known PuLP platform-specific solver directories (win/64, win/32, linux, osx).

    Returns:
        Absolute path to the executable if found and accessible, otherwise None.
    """
    for env_var in ("CBC_PATH", "PULP_CBC_PATH"):
        custom_path = os.environ.get(env_var)
        if custom_path and os.path.isfile(custom_path):
            return os.path.abspath(custom_path)

    which_cbc = shutil.which("cbc") or shutil.which("cbc.exe")
    if which_cbc and os.path.isfile(which_cbc):
        return os.path.abspath(which_cbc)

    try:
        from pulp.apis.core import pulp_cbc_path
        if pulp_cbc_path and os.path.isfile(pulp_cbc_path):
            return os.path.abspath(pulp_cbc_path)
    except (ImportError, AttributeError):
        pass

    try:
        pulp_dir = os.path.dirname(pulp.__file__)
        platform_candidates = [
            os.path.join(pulp_dir, "solverdir", "cbc", "win", "64", "cbc.exe"),
            os.path.join(pulp_dir, "solverdir", "cbc", "win", "32", "cbc.exe"),
            os.path.join(pulp_dir, "solverdir", "cbc", "linux", "64", "cbc"),
            os.path.join(pulp_dir, "solverdir", "cbc", "osx", "64", "cbc"),
            os.path.join(pulp_dir, "solverdir", "cbc", "osx", "arm64", "cbc"),
        ]
        for candidate in platform_candidates:
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)
    except Exception:
        pass

    return None


def _create_lp_variable(
    prob: pulp.LpProblem,
    name: str,
    lowBound: Optional[float] = None,
    upBound: Optional[float] = None,
    cat: str = pulp.LpContinuous
) -> pulp.LpVariable:
    """Create an LpVariable compatible with both PuLP 2.x and PuLP 4.x+ APIs."""
    if hasattr(prob, "add_variable"):
        return prob.add_variable(name, lowBound=lowBound, upBound=upBound, cat=cat)
    try:
        return pulp.LpVariable(name, lowBound=lowBound, upBound=upBound, cat=cat)
    except TypeError:
        if hasattr(prob, "add_variable"):
            return prob.add_variable(name, lowBound=lowBound, upBound=upBound, cat=cat)
        return pulp.LpVariable(name, lowBound, upBound, cat)


def _get_solver(time_limit: int = 5):
    """Retrieve an available, verified solver instance supporting both PuLP 2.x and PuLP 4.x+.

    Uses COIN_CMD with an explicitly resolved CBC executable path (or PULP_CBC_CMD),
    with fallbacks to HiGHS, GLPK, or default solver.

    Raises:
        RuntimeError: If no functional linear programming solver can be located.
    """
    cbc_path = find_cbc_executable()

    # 1. Use COIN_CMD with explicitly detected executable path
    if cbc_path and hasattr(pulp, "COIN_CMD"):
        try:
            solver = pulp.COIN_CMD(path=cbc_path, msg=0, timeLimit=time_limit)
            if solver.available():
                return solver
        except Exception as e:
            logger.debug("COIN_CMD initialization with path %s failed: %s", cbc_path, e)

    # 2. Try precompiled bundled PULP_CBC_CMD
    if hasattr(pulp, "PULP_CBC_CMD"):
        try:
            solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit)
            if solver.available():
                return solver
        except Exception as e:
            logger.debug("PULP_CBC_CMD initialization failed: %s", e)

    # 3. Try COIN_CMD with system PATH
    if hasattr(pulp, "COIN_CMD"):
        try:
            solver = pulp.COIN_CMD(msg=0, timeLimit=time_limit)
            if solver.available():
                return solver
        except Exception:
            pass

    # 4. Fallback to HiGHS solver
    if hasattr(pulp, "HiGHS_CMD"):
        try:
            solver = pulp.HiGHS_CMD(msg=0, timeLimit=time_limit)
            if solver.available():
                return solver
        except Exception:
            pass

    # 5. Fallback to GLPK solver
    if hasattr(pulp, "GLPK_CMD"):
        try:
            solver = pulp.GLPK_CMD(msg=0, timeLimit=time_limit)
            if solver.available():
                return solver
        except Exception:
            pass

    # 6. Try pulp.getSolver
    try:
        solver = pulp.getSolver("PULP_CBC_CMD", timeLimit=time_limit, msg=0)
        if solver.available():
            return solver
    except Exception:
        pass

    raise RuntimeError(
        "COIN-OR CBC solver executable ('cbc.exe' / 'cbc') not found or not executable.\n"
        "SmartFlow OR requires an Operations Research Linear Programming solver.\n\n"
        "Troubleshooting steps:\n"
        "1. Verify PuLP is installed with precompiled CBC binaries: pip install 'pulp>=2.8.0,<3.0.0'\n"
        "2. If using a custom CBC installation, set the CBC_PATH environment variable to cbc.exe\n"
        "   or ensure 'cbc' is accessible on your system PATH."
    )


def _approach_delay_func(g: float, approach: ApproachInput, cycle_sec: float, period_sec: float) -> float:
    """Evaluate pure queuing delay W_i(g) for a given green time g."""
    if g <= 0.0 or cycle_sec <= 0.0:
        return 999.0
    arr_rate = approach.arrival_rate_vps
    sat_rate = approach.sat_flow_rate_vps
    eff_mu = compute_effective_service_rate(sat_rate, g, cycle_sec)
    rho = compute_degree_of_saturation(arr_rate, eff_mu)
    d1 = compute_uniform_delay_d1(cycle_sec, g, rho)
    d2 = compute_overflow_delay_d2(arr_rate, eff_mu, rho, period_sec)
    return d1 + d2


def solve_green_allocation_lp(
    approaches: Dict[str, ApproachInput],
    cycle_sec: float,
    lost_time_sec: float,
    analysis_period_sec: float = 900.0,
    num_breakpoints: int = 24
) -> Tuple[Dict[str, float], Dict[str, float], float, str, float]:
    """Solve the green signal allocation LP for a fixed cycle length C.

    Returns:
        (optimal_greens, shadow_prices, objective_value, solver_status, elapsed_ms)
    """
    start_t = time.perf_counter()
    available_green = cycle_sec - lost_time_sec

    sum_min = sum(a.min_green_sec for a in approaches.values())
    sum_max = sum(a.max_green_sec for a in approaches.values())

    # Check structural feasibility
    if available_green < sum_min:
        status = f"Infeasible: Available green ({available_green:.1f}s) < sum of min greens ({sum_min:.1f}s)"
        # Fallback to proportional floor
        factor = available_green / max(1.0, sum_min)
        fallback_g = {d: max(1.0, a.min_green_sec * factor) for d, a in approaches.items()}
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        return fallback_g, {}, 9999.0, status, elapsed_ms

    prob = pulp.LpProblem("Signal_Green_Optimization", pulp.LpMinimize)

    # Decision variables
    g_vars: Dict[str, pulp.LpVariable] = {}
    delay_vars: Dict[str, pulp.LpVariable] = {}
    ovf_vars: Dict[str, pulp.LpVariable] = {}

    for d, a in approaches.items():
        # Clamp bounds within physical reality
        lb = a.min_green_sec
        ub = min(a.max_green_sec, available_green)
        if ub < lb:
            ub = lb
        g_vars[d] = _create_lp_variable(prob, f"g_{d}", lowBound=lb, upBound=ub, cat=pulp.LpContinuous)
        delay_vars[d] = _create_lp_variable(prob, f"Lhat_{d}", lowBound=0.0, cat=pulp.LpContinuous)
        ovf_vars[d] = _create_lp_variable(prob, f"q_ovf_{d}", lowBound=0.0, cat=pulp.LpContinuous)

    # Objective: Minimize total weighted queued vehicles + overflow penalty
    obj_terms = [delay_vars[d] for d in approaches] + [10.0 * ovf_vars[d] for d in approaches]
    prob += pulp.lpSum(obj_terms), "Total_Weighted_Queue"

    # Cycle conservation constraint: sum(g_i) == C - L
    prob += pulp.lpSum([g_vars[d] for d in approaches]) == available_green, "Cycle_Budget"

    # Capacity overflow constraints: s_i * g_i + q_ovf_i >= lambda_i * C
    for d, a in approaches.items():
        cycle_demand = a.arrival_rate_vps * cycle_sec
        prob += a.sat_flow_rate_vps * g_vars[d] + ovf_vars[d] >= cycle_demand, f"Capacity_{d}"

    # Convex tangent cuts for each approach
    delta_step = 0.2  # for numerical derivative
    for d, a in approaches.items():
        lb = a.min_green_sec
        ub = min(a.max_green_sec, available_green)
        if ub <= lb:
            breakpoints = [lb]
        else:
            breakpoints = list(np.linspace(lb, ub, num_breakpoints))

        w_factor = a.priority_weight * a.arrival_rate_vps
        for idx, g_k in enumerate(breakpoints):
            w_k = _approach_delay_func(g_k, a, cycle_sec, analysis_period_sec)
            w_fwd = _approach_delay_func(g_k + delta_step, a, cycle_sec, analysis_period_sec)
            w_bwd = _approach_delay_func(max(1.0, g_k - delta_step), a, cycle_sec, analysis_period_sec)
            slope = (w_fwd - w_bwd) / (g_k + delta_step - max(1.0, g_k - delta_step))
            intercept = w_k - slope * g_k

            # L_hat_i >= w_factor * (slope * g_i + intercept)
            prob += delay_vars[d] >= w_factor * (slope * g_vars[d] + intercept), f"Tangent_{d}_{idx}"

    # Solve using CBC or available solver
    solver = _get_solver(time_limit=5)
    solve_res = None
    try:
        solve_res = prob.solve(solver)
    except pulp.PulpSolverError as pse:
        raise RuntimeError(
            f"PuLP solver execution failed with error: {pse}\n"
            "Ensure that COIN-OR CBC ('cbc.exe') is executable and accessible on your system."
        ) from pse

    status_str = get_lp_status_str(prob, solve_result=solve_res)

    optimal_greens: Dict[str, float] = {}
    for d in approaches:
        val = g_vars[d].varValue
        optimal_greens[d] = float(val) if val is not None else approaches[d].min_green_sec

    # Normalize green times strictly to available green if solver had tiny rounding drift
    g_sum = sum(optimal_greens.values())
    if abs(g_sum - available_green) > 1e-4 and g_sum > 0:
        optimal_greens = {d: (g / g_sum) * available_green for d, g in optimal_greens.items()}

    # Extract shadow prices (dual values)
    shadow_prices: Dict[str, float] = {}
    cycle_budget_con = prob.constraints.get("Cycle_Budget")
    if cycle_budget_con and cycle_budget_con.pi is not None:
        shadow_prices["cycle_budget"] = float(cycle_budget_con.pi)

    for d in approaches:
        cap_con = prob.constraints.get(f"Capacity_{d}")
        if cap_con and cap_con.pi is not None:
            shadow_prices[d] = float(cap_con.pi)
        else:
            shadow_prices[d] = 0.0

    elapsed_ms = (time.perf_counter() - start_t) * 1000.0
    obj_val = float(pulp.value(prob.objective)) if prob.objective else 0.0

    return optimal_greens, shadow_prices, obj_val, status_str, elapsed_ms


def compute_webster_optimal_cycle(approaches: Dict[str, ApproachInput], lost_time_sec: float) -> Optional[float]:
    """Calculate theoretical Webster's optimal cycle length C* = (1.5 * L + 5) / (1 - Y).
    Only valid if total flow ratio Y < 1.0.
    """
    sum_y = sum(a.flow_ratio_y for a in approaches.values())
    if sum_y >= 0.95 or sum_y <= 0.0:
        return None
    c_opt = (1.5 * lost_time_sec + 5.0) / (1.0 - sum_y)
    return float(c_opt)


def optimize_cycle_and_green(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig
) -> Tuple[IntersectionEvaluation, Dict[float, float]]:
    """Perform joint optimization over cycle length C and green splits g_i.

    Returns:
        (best_evaluation, cycle_delay_curve_dict)
    """
    lost_time = timing.total_lost_time
    c_min = timing.cycle_min
    c_max = timing.cycle_max

    # Build candidate cycle lengths
    cycle_candidates = list(np.arange(c_min, c_max + 1.0, 5.0))
    c_webster = compute_webster_optimal_cycle(approaches, lost_time)
    if c_webster and c_min <= c_webster <= c_max:
        cycle_candidates.append(round(c_webster, 1))
    cycle_candidates = sorted(list(set(cycle_candidates)))

    best_eval: Optional[IntersectionEvaluation] = None
    best_avg_wait = float("inf")
    cycle_curve: Dict[float, float] = {}

    for c in cycle_candidates:
        greens, shadow_prices, _, status, solve_time = solve_green_allocation_lp(
            approaches=approaches,
            cycle_sec=c,
            lost_time_sec=lost_time,
            analysis_period_sec=timing.analysis_period_sec
        )
        eval_run = evaluate_intersection(
            approaches=approaches,
            green_splits=greens,
            cycle_sec=c,
            total_lost_time_sec=lost_time,
            plan_name="SmartFlow LP Optimized",
            solver_status=status,
            solve_time_ms=solve_time,
            shadow_prices=shadow_prices
        )
        cycle_curve[round(c, 1)] = eval_run.demand_weighted_avg_wait_sec

        if eval_run.demand_weighted_avg_wait_sec < best_avg_wait:
            best_avg_wait = eval_run.demand_weighted_avg_wait_sec
            best_eval = eval_run

    if best_eval is None:
        # Fallback to midpoint cycle if candidates were empty
        mid_c = (c_min + c_max) / 2.0
        greens, shadow_prices, _, status, solve_time = solve_green_allocation_lp(
            approaches, mid_c, lost_time, timing.analysis_period_sec
        )
        best_eval = evaluate_intersection(
            approaches, greens, mid_c, lost_time, "SmartFlow LP Optimized", status, solve_time, shadow_prices
        )

    return best_eval, cycle_curve


def compute_fixed_time_baseline(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig
) -> IntersectionEvaluation:
    """Evaluate standard Fixed-Time controller using equal green splits."""
    c_fixed = timing.fixed_cycle_time
    lost_time = timing.total_lost_time
    available_green = max(0.0, c_fixed - lost_time)
    equal_g = available_green / 4.0
    splits = {d: equal_g for d in approaches}
    return evaluate_intersection(
        approaches=approaches,
        green_splits=splits,
        cycle_sec=c_fixed,
        total_lost_time_sec=lost_time,
        plan_name="Fixed-Time Baseline",
        solver_status="Deterministic Equal Split",
        solve_time_ms=0.1
    )

