"""Unit tests for the Linear Programming green allocation solver and cycle optimizer."""

import pytest
import math
from models.schemas import ApproachInput, SignalTimingConfig
from core.lp_optimizer import (
    solve_green_allocation_lp,
    optimize_cycle_and_green,
    compute_fixed_time_baseline,
    compute_webster_optimal_cycle
)


@pytest.fixture
def asymmetric_traffic():
    return {
        "North": ApproachInput("North", volume_vph=1200.0, num_lanes=2, min_green_sec=10.0, max_green_sec=60.0),
        "South": ApproachInput("South", volume_vph=400.0, num_lanes=2, min_green_sec=10.0, max_green_sec=40.0),
        "East":  ApproachInput("East",  volume_vph=350.0, num_lanes=2, min_green_sec=10.0, max_green_sec=40.0),
        "West":  ApproachInput("West",  volume_vph=300.0, num_lanes=2, min_green_sec=10.0, max_green_sec=40.0),
    }


def test_green_allocation_conservation(asymmetric_traffic):
    cycle = 100.0
    lost = 16.0
    available_green = cycle - lost  # 84s

    greens, shadow_prices, obj, status, solve_time = solve_green_allocation_lp(
        asymmetric_traffic, cycle_sec=cycle, lost_time_sec=lost
    )

    assert status == "Optimal"
    assert math.isclose(sum(greens.values()), available_green, rel_tol=1e-3)
    # Check bounds
    for d, a in asymmetric_traffic.items():
        assert greens[d] >= a.min_green_sec - 1e-3
        assert greens[d] <= a.max_green_sec + 1e-3

    # Heavy Northbound should receive significantly more green than West
    assert greens["North"] > greens["West"]


def test_lp_optimizer_beats_fixed_time_in_asymmetric_flow(asymmetric_traffic):
    timing = SignalTimingConfig(cycle_min=70.0, cycle_max=130.0, fixed_cycle_time=100.0)

    fixed_eval = compute_fixed_time_baseline(asymmetric_traffic, timing)
    opt_eval, _ = optimize_cycle_and_green(asymmetric_traffic, timing)

    # LP Optimized should achieve lower demand-weighted average delay than Fixed-Time
    assert opt_eval.demand_weighted_avg_wait_sec < fixed_eval.demand_weighted_avg_wait_sec
    assert opt_eval.total_avg_queue_veh < fixed_eval.total_avg_queue_veh


def test_webster_optimal_cycle(asymmetric_traffic):
    lost = 16.0
    c_opt = compute_webster_optimal_cycle(asymmetric_traffic, lost)
    assert c_opt is not None
    assert 50.0 < c_opt < 150.0

