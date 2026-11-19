"""Unit tests for SQLite database CRUD and persistence."""

import os
import tempfile
import pytest
from models.schemas import ApproachInput, SignalTimingConfig
from core.lp_optimizer import optimize_cycle_and_green, compute_fixed_time_baseline
from core.scheduler_milp import schedule_emergency_preemption_milp
from database.repository import (
    save_scenario,
    load_scenario,
    list_scenarios,
    delete_scenario,
    save_optimization_run,
    save_emergency_event,
    list_recent_evaluations
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_database_scenario_crud(temp_db):
    apps = {
        "North": ApproachInput("North", volume_vph=900.0),
        "South": ApproachInput("South", volume_vph=600.0),
        "East":  ApproachInput("East",  volume_vph=400.0),
        "West":  ApproachInput("West",  volume_vph=350.0),
    }
    timing = SignalTimingConfig(cycle_min=65.0, cycle_max=140.0)

    # Save scenario
    scen_id = save_scenario("Test Scenario", "Demo Description", timing, apps, db_path=temp_db)
    assert scen_id > 0

    # List scenarios
    scenarios = list_scenarios(db_path=temp_db)
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Test Scenario"

    # Load scenario
    loaded_timing, loaded_apps, name, desc = load_scenario(scen_id, db_path=temp_db)
    assert name == "Test Scenario"
    assert loaded_timing.cycle_min == 65.0
    assert loaded_apps["North"].volume_vph == 900.0

    # Delete scenario
    assert delete_scenario(scen_id, db_path=temp_db) is True
    assert len(list_scenarios(db_path=temp_db)) == 0


def test_database_optimization_and_emergency_logging(temp_db):
    apps = {
        "North": ApproachInput("North", volume_vph=800.0),
        "South": ApproachInput("South", volume_vph=600.0),
        "East":  ApproachInput("East",  volume_vph=400.0),
        "West":  ApproachInput("West",  volume_vph=300.0),
    }
    timing = SignalTimingConfig()

    opt_eval, _ = optimize_cycle_and_green(apps, timing)
    run_id = save_optimization_run(scenario_id=None, eval_result=opt_eval, db_path=temp_db)
    assert run_id > 0

    recent = list_recent_evaluations(limit=5, db_path=temp_db)
    assert len(recent) == 1
    assert recent[0]["run_type"] == "lp_optimized"

    em_res = schedule_emergency_preemption_milp(apps, timing, "North")
    ev_id = save_emergency_event(run_id=run_id, em_res=em_res, db_path=temp_db)
    assert ev_id > 0

