"""Mathematical models for Signalized Intersection Queuing Theory.

Implements:
1. D/D/1 Deterministic Uniform Red-Phase Delay (Webster's First Term / HCM 2010)
2. Coordinate-Transformed M/D/1 Time-Dependent Overflow Delay (Akcelik / Pollaczek-Khinchine)
3. Little's Law for Average Queue Length (L_q = lambda * W)
4. Expected Maximum Back-of-Queue (Q_max)
5. Classical M/M/1 continuous queue baseline for educational contrast
6. HCM Level of Service (LOS Grades A to F)
"""

import math
from typing import Dict, Tuple, Optional
from config.constants import get_hcm_los
from models.schemas import ApproachInput, ApproachQueuingResult, IntersectionEvaluation


def compute_effective_service_rate(sat_flow_vps: float, green_sec: float, cycle_sec: float) -> float:
    """Calculate effective service rate mu_eff = s * (g / C) across full cycle in veh/sec."""
    if cycle_sec <= 0.0 or green_sec <= 0.0:
        return 0.0
    return sat_flow_vps * (green_sec / cycle_sec)


def compute_degree_of_saturation(arrival_rate_vps: float, eff_service_rate_vps: float) -> float:
    """Calculate degree of saturation (traffic intensity) rho = lambda / mu_eff."""
    if arrival_rate_vps <= 0.0:
        return 0.0
    if eff_service_rate_vps <= 0.0:
        return 999.0
    return arrival_rate_vps / eff_service_rate_vps


def compute_uniform_delay_d1(cycle_sec: float, green_sec: float, rho: float) -> float:
    """Calculate D/D/1 uniform delay d1 (seconds/vehicle).

    Formula (HCM / Webster):
        d1 = 0.5 * C * (1 - g/C)^2 / (1 - min(1, rho) * (g/C))

    Guaranteed numerically safe: bounded at (C - g)/2 when rho >= 1.0.
    """
    if cycle_sec <= 0.0 or green_sec >= cycle_sec:
        return 0.0
    green_ratio = green_sec / cycle_sec
    red_ratio = 1.0 - green_ratio
    denominator = 1.0 - min(1.0, max(0.0, rho)) * green_ratio
    if denominator <= 1e-6:
        denominator = 1e-6
    return (0.5 * cycle_sec * (red_ratio ** 2)) / denominator


def compute_overflow_delay_d2(
    arrival_rate_vps: float,
    eff_service_rate_vps: float,
    rho: float,
    analysis_period_sec: float = 900.0
) -> float:
    """Calculate incremental random / overflow delay d2 (seconds/vehicle).

    Uses the coordinate-transformed M/D/1 delay equation over analysis period T.
    When rho < 1 and T is large, asymptotically matches Pollaczek-Khinchine M/D/1:
        d2 -> rho / (2 * mu_eff * (1 - rho))
    When rho >= 1 (oversaturated), gracefully transitions to linear deterministic queue growth:
        d2 ~ (T / 2) * (rho - 1)
    """
    if arrival_rate_vps <= 1e-6 or eff_service_rate_vps <= 1e-6 or analysis_period_sec <= 0.0:
        return 0.0

    T = analysis_period_sec
    diff = rho - 1.0
    # Coordinate transformation term: 4 * rho / (mu_eff * T)
    stochastic_component = (4.0 * rho) / (eff_service_rate_vps * T)
    radicand = max(0.0, (diff ** 2) + stochastic_component)
    d2 = (T / 4.0) * (diff + math.sqrt(radicand))
    return max(0.0, d2)


def compute_mm1_baseline_wait(arrival_rate_vps: float, eff_service_rate_vps: float, rho: float) -> Optional[float]:
    """Compute classical textbook M/M/1 waiting time W_q = rho / (mu_eff * (1 - rho)).
    Only defined for steady-state undersaturated queues (rho < 1.0)."""
    if arrival_rate_vps <= 1e-6:
        return 0.0
    if rho < 0.999 and eff_service_rate_vps > arrival_rate_vps:
        return rho / (eff_service_rate_vps * (1.0 - rho))
    return None


def evaluate_approach_queuing(
    approach: ApproachInput,
    green_sec: float,
    cycle_sec: float,
    analysis_period_sec: float = 900.0,
    lp_shadow_price: Optional[float] = None
) -> ApproachQueuingResult:
    """Perform complete Operations Research evaluation of an approach under a timing plan."""
    arr_rate = approach.arrival_rate_vps
    sat_rate = approach.sat_flow_rate_vps
    flow_ratio = approach.flow_ratio_y

    eff_mu = compute_effective_service_rate(sat_rate, green_sec, cycle_sec)
    rho = compute_degree_of_saturation(arr_rate, eff_mu)

    if arr_rate <= 1e-6:
        d1 = 0.0
        d2 = 0.0
        total_wait = 0.0
    else:
        d1 = compute_uniform_delay_d1(cycle_sec, green_sec, rho)
        d2 = compute_overflow_delay_d2(arr_rate, eff_mu, rho, analysis_period_sec)
        total_wait = d1 + d2

    # Little's Law: Average queue length L_q = lambda * W
    avg_queue = arr_rate * total_wait

    # Back of queue: deterministic red arrivals + stochastic overflow queue
    red_time = max(0.0, cycle_sec - green_sec)
    max_queue = (arr_rate * red_time) + (arr_rate * d2)

    los_grade, los_desc = get_hcm_los(total_wait, rho)
    mm1_wait = compute_mm1_baseline_wait(arr_rate, eff_mu, rho)

    return ApproachQueuingResult(
        direction=approach.direction,
        allocated_green_sec=green_sec,
        cycle_time_sec=cycle_sec,
        arrival_rate_vps=arr_rate,
        saturation_rate_vps=sat_rate,
        flow_ratio_y=flow_ratio,
        effective_service_rate_vps=eff_mu,
        degree_of_saturation_rho=rho,
        uniform_delay_d1_sec=d1,
        overflow_delay_d2_sec=d2,
        avg_wait_time_sec=total_wait,
        avg_queue_length_veh=avg_queue,
        max_queue_length_veh=max_queue,
        los_grade=los_grade,
        los_description=los_desc,
        mm1_reference_wait_sec=mm1_wait,
        lp_shadow_price=lp_shadow_price
    )


def evaluate_intersection(
    approaches: Dict[str, ApproachInput],
    green_splits: Dict[str, float],
    cycle_sec: float,
    total_lost_time_sec: float,
    plan_name: str,
    solver_status: str = "Optimal",
    solve_time_ms: float = 0.0,
    shadow_prices: Optional[Dict[str, float]] = None
) -> IntersectionEvaluation:
    """Evaluate all 4 approaches and calculate demand-weighted intersection-wide KPIs."""
    results: Dict[str, ApproachQueuingResult] = {}
    total_arr_rate = 0.0
    weighted_delay_sum = 0.0
    total_avg_queue = 0.0
    max_rho = 0.0
    sum_y = 0.0
    total_green = sum(green_splits.values())
    total_throughput = 0.0

    for direction, app in approaches.items():
        g_sec = green_splits.get(direction, 10.0)
        sp = shadow_prices.get(direction) if shadow_prices else None
        res = evaluate_approach_queuing(app, g_sec, cycle_sec, lp_shadow_price=sp)
        results[direction] = res

        total_arr_rate += app.arrival_rate_vps
        weighted_delay_sum += app.arrival_rate_vps * res.avg_wait_time_sec
        total_avg_queue += res.avg_queue_length_veh
        sum_y += res.flow_ratio_y
        if res.degree_of_saturation_rho > max_rho:
            max_rho = res.degree_of_saturation_rho

        # Throughput: minimum of arrival volume and effective capacity
        cap_vph = res.effective_service_rate_vps * 3600.0
        total_throughput += min(app.volume_vph, cap_vph)

    demand_avg_wait = (weighted_delay_sum / total_arr_rate) if total_arr_rate > 1e-6 else 0.0
    int_los, _ = get_hcm_los(demand_avg_wait, max_rho)

    is_oversat = sum_y >= (1.0 - (total_lost_time_sec / cycle_sec)) if cycle_sec > total_lost_time_sec else True

    return IntersectionEvaluation(
        plan_name=plan_name,
        cycle_time_sec=cycle_sec,
        total_lost_time_sec=total_lost_time_sec,
        total_green_sec=total_green,
        sum_flow_ratio_y=sum_y,
        is_oversaturated=is_oversat,
        approaches=results,
        demand_weighted_avg_wait_sec=demand_avg_wait,
        total_avg_queue_veh=total_avg_queue,
        max_saturation_rho=max_rho,
        intersection_los=int_los,
        total_throughput_vph=total_throughput,
        solver_status=solver_status,
        solve_time_ms=solve_time_ms
    )
