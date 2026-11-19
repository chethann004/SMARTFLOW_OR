"""Unit tests for the discrete-time 4-way junction simulator and Common Random Numbers."""

import pytest
from models.schemas import ApproachInput, SignalTimingConfig
from core.lp_optimizer import compute_fixed_time_baseline, optimize_cycle_and_green
from core.simulation import run_discrete_junction_simulation


@pytest.fixture
def test_setup():
    apps = {
        "North": ApproachInput("North", volume_vph=1000.0, num_lanes=2),
        "South": ApproachInput("South", volume_vph=500.0, num_lanes=2),
        "East":  ApproachInput("East",  volume_vph=400.0, num_lanes=2),
        "West":  ApproachInput("West",  volume_vph=350.0, num_lanes=2),
    }
    timing = SignalTimingConfig(cycle_min=70.0, cycle_max=120.0, fixed_cycle_time=100.0)
    fixed_eval = compute_fixed_time_baseline(apps, timing)
    opt_eval, _ = optimize_cycle_and_green(apps, timing)
    return apps, timing, fixed_eval, opt_eval


def test_simulation_runs_and_produces_records(test_setup):
    apps, timing, fixed_eval, opt_eval = test_setup
    duration = 300  # 5 min test

    trace = run_discrete_junction_simulation(
        approaches=apps,
        timing=timing,
        fixed_eval=fixed_eval,
        opt_eval=opt_eval,
        duration_sec=duration,
        arrival_mode="Poisson",
        random_seed=42
    )

    assert trace.duration_sec == duration
    assert len(trace.second_by_second_records) > 10
    assert trace.fixed_summary["throughput_veh"] > 0
    assert trace.opt_summary["throughput_veh"] > 0
    assert trace.opt_summary["avg_wait_sec"] > 0.0


def test_simulation_reproducibility(test_setup):
    apps, timing, fixed_eval, opt_eval = test_setup
    duration = 180

    trace1 = run_discrete_junction_simulation(
        apps, timing, fixed_eval, opt_eval, duration_sec=duration, random_seed=99
    )
    trace2 = run_discrete_junction_simulation(
        apps, timing, fixed_eval, opt_eval, duration_sec=duration, random_seed=99
    )

    assert trace1.fixed_summary["throughput_veh"] == trace2.fixed_summary["throughput_veh"]
    assert trace1.opt_summary["throughput_veh"] == trace2.opt_summary["throughput_veh"]
    assert trace1.opt_summary["avg_wait_sec"] == trace2.opt_summary["avg_wait_sec"]

