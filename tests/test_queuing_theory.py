"""Unit tests for Queuing Theory formulas, Little's Law, and edge cases."""

import pytest
import math
from models.schemas import ApproachInput, SignalTimingConfig
from core.queuing_theory import (
    compute_effective_service_rate,
    compute_degree_of_saturation,
    compute_uniform_delay_d1,
    compute_overflow_delay_d2,
    evaluate_approach_queuing,
    evaluate_intersection
)
from config.constants import get_hcm_los


def test_arrival_and_saturation_rates():
    app = ApproachInput(direction="North", volume_vph=720.0, num_lanes=2, saturation_per_lane_vph=1800.0)
    assert math.isclose(app.arrival_rate_vps, 720.0 / 3600.0, rel_tol=1e-5)
    assert math.isclose(app.sat_flow_rate_vps, (2 * 1800.0) / 3600.0, rel_tol=1e-5)
    assert math.isclose(app.flow_ratio_y, 0.2, rel_tol=1e-5)


def test_effective_service_rate_and_rho():
    sat_vps = 1.0  # 1 veh/s
    green_sec = 30.0
    cycle_sec = 100.0
    mu_eff = compute_effective_service_rate(sat_vps, green_sec, cycle_sec)
    assert math.isclose(mu_eff, 0.3, rel_tol=1e-5)

    arr_vps = 0.15
    rho = compute_degree_of_saturation(arr_vps, mu_eff)
    assert math.isclose(rho, 0.5, rel_tol=1e-5)


def test_uniform_delay_d1():
    cycle = 100.0
    green = 40.0
    rho = 0.5
    d1 = compute_uniform_delay_d1(cycle, green, rho)
    assert d1 > 0.0
    assert d1 < cycle

    # Zero green gives 0 or large
    assert compute_uniform_delay_d1(100.0, 100.0, 0.5) == 0.0


def test_overflow_delay_d2_undersaturated_and_oversaturated():
    # Undersaturated
    d2_under = compute_overflow_delay_d2(0.1, 0.3, 0.33, analysis_period_sec=900.0)
    assert d2_under >= 0.0
    assert d2_under < 10.0

    # Oversaturated (rho = 1.2)
    d2_over = compute_overflow_delay_d2(0.36, 0.3, 1.2, analysis_period_sec=900.0)
    assert d2_over > d2_under
    assert d2_over > 50.0  # noticeable queue delay accumulation


def test_zero_flow_edge_case():
    app = ApproachInput(direction="West", volume_vph=0.0)
    res = evaluate_approach_queuing(app, green_sec=15.0, cycle_sec=80.0)
    assert res.avg_wait_time_sec == 0.0
    assert res.avg_queue_length_veh == 0.0
    assert res.degree_of_saturation_rho == 0.0


def test_littles_law_consistency():
    app = ApproachInput(direction="South", volume_vph=600.0, num_lanes=2)
    res = evaluate_approach_queuing(app, green_sec=25.0, cycle_sec=100.0)
    expected_lq = res.arrival_rate_vps * res.avg_wait_time_sec
    assert math.isclose(res.avg_queue_length_veh, expected_lq, rel_tol=1e-5)


def test_hcm_los_mapping():
    assert get_hcm_los(5.0)[0] == "A"
    assert get_hcm_los(15.0)[0] == "B"
    assert get_hcm_los(25.0)[0] == "C"
    assert get_hcm_los(45.0)[0] == "D"
    assert get_hcm_los(65.0)[0] == "E"
    assert get_hcm_los(95.0)[0] == "F"
    # Saturation > 1.0 forces LOS F
    assert get_hcm_los(5.0, degree_of_sat_rho=1.1)[0] == "F"

