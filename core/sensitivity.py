"""Parametric sensitivity analysis, tipping-point identification, and LP shadow price extraction."""

from typing import Dict, List, Optional, Any
import numpy as np

from models.schemas import ApproachInput, SignalTimingConfig, IntersectionEvaluation
from core.lp_optimizer import (
    solve_green_allocation_lp,
    compute_fixed_time_baseline,
    optimize_cycle_and_green
)
from core.queuing_theory import evaluate_intersection


def extract_shadow_prices_summary(eval_result: IntersectionEvaluation) -> List[Dict[str, Any]]:
    """Extract and format LP dual values (shadow prices) and interpret their economic/OR meaning."""
    summary: List[Dict[str, Any]] = []

    # Cycle budget dual
    for direction, app_res in eval_result.approaches.items():
        sp = app_res.lp_shadow_price or 0.0
        summary.append({
            "Constraint": f"Capacity Floor ({direction})",
            "Direction": direction,
            "Shadow_Price": round(sp, 4),
            "Interpretation": (
                f"Adding 1 veh capacity reduces objective delay by {abs(sp):.3f} veh-sec"
                if abs(sp) > 1e-4 else "Constraint is non-binding (approach has slack capacity)."
            )
        })

    return summary


def perform_demand_sweep(
    target_direction: str,
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    multipliers: Optional[List[float]] = None,
    eval_cycle_sec: Optional[float] = None
) -> Dict[str, Any]:
    """Perform parametric sensitivity analysis by scaling volume on a single approach.

    Returns:
        Dictionary with records table, tipping points, and comparison points.
    """
    if multipliers is None:
        multipliers = list(np.arange(0.5, 1.6, 0.1))

    base_app = approaches.get(target_direction)
    if not base_app:
        raise ValueError(f"Unknown approach: {target_direction}")

    cycle_sec = eval_cycle_sec or timing.fixed_cycle_time
    lost_time = timing.total_lost_time

    records: List[Dict[str, Any]] = []
    tipping_point_85_opt: Optional[float] = None
    tipping_point_100_opt: Optional[float] = None
    tipping_point_85_fixed: Optional[float] = None
    tipping_point_100_fixed: Optional[float] = None

    for mult in multipliers:
        mult = round(float(mult), 2)
        scaled_vph = base_app.volume_vph * mult

        # Deep clone approach inputs with scaled volume
        cloned_apps: Dict[str, ApproachInput] = {}
        for d, a in approaches.items():
            if d == target_direction:
                cloned_apps[d] = ApproachInput(
                    direction=d,
                    volume_vph=scaled_vph,
                    num_lanes=a.num_lanes,
                    saturation_per_lane_vph=a.saturation_per_lane_vph,
                    min_green_sec=a.min_green_sec,
                    max_green_sec=a.max_green_sec,
                    priority_weight=a.priority_weight
                )
            else:
                cloned_apps[d] = ApproachInput(
                    direction=d,
                    volume_vph=a.volume_vph,
                    num_lanes=a.num_lanes,
                    saturation_per_lane_vph=a.saturation_per_lane_vph,
                    min_green_sec=a.min_green_sec,
                    max_green_sec=a.max_green_sec,
                    priority_weight=a.priority_weight
                )

        # Evaluate Fixed-Time Baseline
        fixed_eval = compute_fixed_time_baseline(cloned_apps, timing)
        fixed_target = fixed_eval.approaches[target_direction]

        # Evaluate LP-Optimized Timing for the operational cycle
        greens, shadow_prices, _, status, solve_time = solve_green_allocation_lp(
            cloned_apps, cycle_sec, lost_time, timing.analysis_period_sec
        )
        opt_eval = evaluate_intersection(
            cloned_apps, greens, cycle_sec, lost_time, "SmartFlow LP Optimized",
            status, solve_time, shadow_prices
        )
        opt_target = opt_eval.approaches[target_direction]

        # Track tipping points
        if opt_target.degree_of_saturation_rho >= 0.85 and tipping_point_85_opt is None:
            tipping_point_85_opt = mult
        if opt_target.degree_of_saturation_rho >= 1.00 and tipping_point_100_opt is None:
            tipping_point_100_opt = mult

        if fixed_target.degree_of_saturation_rho >= 0.85 and tipping_point_85_fixed is None:
            tipping_point_85_fixed = mult
        if fixed_target.degree_of_saturation_rho >= 1.00 and tipping_point_100_fixed is None:
            tipping_point_100_fixed = mult

        records.append({
            "multiplier": mult,
            "volume_vph": round(scaled_vph, 1),
            "opt_green_sec": round(opt_target.allocated_green_sec, 1),
            "fixed_green_sec": round(fixed_target.allocated_green_sec, 1),
            "opt_rho": round(opt_target.degree_of_saturation_rho, 3),
            "fixed_rho": round(fixed_target.degree_of_saturation_rho, 3),
            "opt_wait_sec": round(opt_target.avg_wait_time_sec, 1),
            "fixed_wait_sec": round(fixed_target.avg_wait_time_sec, 1),
            "opt_queue_veh": round(opt_target.avg_queue_length_veh, 1),
            "fixed_queue_veh": round(fixed_target.avg_queue_length_veh, 1),
            "intersection_opt_wait": round(opt_eval.demand_weighted_avg_wait_sec, 1),
            "intersection_fixed_wait": round(fixed_eval.demand_weighted_avg_wait_sec, 1)
        })

    return {
        "target_direction": target_direction,
        "base_volume_vph": base_app.volume_vph,
        "records": records,
        "tipping_points": {
            "opt_85_near_capacity": tipping_point_85_opt,
            "opt_100_breakdown": tipping_point_100_opt,
            "fixed_85_near_capacity": tipping_point_85_fixed,
            "fixed_100_breakdown": tipping_point_100_fixed
        }
    }


def perform_global_scaling_sweep(
    approaches: Dict[str, ApproachInput],
    timing: SignalTimingConfig,
    multipliers: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """Scale network-wide volume (0.5x to 1.5x) to measure system-wide capacity resilience."""
    if multipliers is None:
        multipliers = list(np.arange(0.5, 1.55, 0.1))

    results: List[Dict[str, Any]] = []
    for mult in multipliers:
        mult = round(float(mult), 2)
        cloned_apps: Dict[str, ApproachInput] = {}
        for d, a in approaches.items():
            cloned_apps[d] = ApproachInput(
                direction=d,
                volume_vph=a.volume_vph * mult,
                num_lanes=a.num_lanes,
                saturation_per_lane_vph=a.saturation_per_lane_vph,
                min_green_sec=a.min_green_sec,
                max_green_sec=a.max_green_sec,
                priority_weight=a.priority_weight
            )

        fixed_eval = compute_fixed_time_baseline(cloned_apps, timing)
        opt_eval, _ = optimize_cycle_and_green(cloned_apps, timing)

        results.append({
            "multiplier": mult,
            "fixed_avg_wait": round(fixed_eval.demand_weighted_avg_wait_sec, 1),
            "opt_avg_wait": round(opt_eval.demand_weighted_avg_wait_sec, 1),
            "wait_reduction_pct": round(
                ((fixed_eval.demand_weighted_avg_wait_sec - opt_eval.demand_weighted_avg_wait_sec)
                 / max(0.1, fixed_eval.demand_weighted_avg_wait_sec)) * 100.0, 1
            ),
            "fixed_max_rho": round(fixed_eval.max_saturation_rho, 3),
            "opt_max_rho": round(opt_eval.max_saturation_rho, 3),
            "fixed_los": fixed_eval.intersection_los,
            "opt_los": opt_eval.intersection_los,
            "opt_cycle_sec": round(opt_eval.cycle_time_sec, 1)
        })

    return results
