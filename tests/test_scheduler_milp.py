"""Unit tests for the MILP phase scheduler and Emergency Vehicle preemption engine."""

import pytest
from models.schemas import ApproachInput, SignalTimingConfig
from core.scheduler_milp import schedule_emergency_preemption_milp


@pytest.fixture
def standard_intersection():
    return {
        "North": ApproachInput("North", volume_vph=800.0, num_lanes=2),
        "South": ApproachInput("South", volume_vph=700.0, num_lanes=2),
        "East":  ApproachInput("East",  volume_vph=500.0, num_lanes=2),
        "West":  ApproachInput("West",  volume_vph=450.0, num_lanes=2),
    }


def test_emergency_preemption_saves_time(standard_intersection):
    timing = SignalTimingConfig()
    # East is currently green, Ambulance arrives on North
    res = schedule_emergency_preemption_milp(
        approaches=standard_intersection,
        timing=timing,
        ev_direction="North",
        ev_type="Ambulance",
        ev_arrival_time_sec=10.0,
        current_active_phase="East",
        elapsed_active_green_sec=8.0,
        queued_vehicles_ahead=3
    )

    assert res.ev_wait_preempted_sec < res.ev_wait_normal_sec
    assert res.time_saved_sec > 0.0
    assert len(res.schedule_blocks) >= 4

    # Verify intergreen clearance gap between consecutive blocks
    blocks = res.schedule_blocks
    for idx in range(len(blocks) - 1):
        curr_b = blocks[idx]
        next_b = blocks[idx + 1]
        # Next start must be at or after current green_end + intergreen
        assert next_b["start_sec"] >= curr_b["green_end_sec"] + curr_b["intergreen_sec"] - 1e-2


def test_ev_on_currently_active_phase(standard_intersection):
    timing = SignalTimingConfig()
    # North is active and ambulance arrives on North
    res = schedule_emergency_preemption_milp(
        approaches=standard_intersection,
        timing=timing,
        ev_direction="North",
        ev_type="Ambulance",
        ev_arrival_time_sec=5.0,
        current_active_phase="North",
        elapsed_active_green_sec=4.0,
        queued_vehicles_ahead=2
    )

    # EV wait is minimal since phase is already active
    assert res.ev_wait_preempted_sec < 10.0
    assert res.schedule_blocks[0]["phase"] == "North"
