"""Database repository providing typed CRUD queries for scenarios, OR runs, and simulation logs."""

import json
from typing import Dict, List, Optional, Any, Tuple
from database.db_manager import get_connection, init_database
from models.schemas import (
    ApproachInput,
    SignalTimingConfig,
    IntersectionEvaluation,
    EmergencyPreemptionResult,
    SimulationTrace
)


def ensure_db_ready(db_path: Optional[str] = None) -> None:
    """Ensure database schema exists before executing queries."""
    init_database(db_path)


def save_scenario(
    name: str,
    description: str,
    timing: SignalTimingConfig,
    approaches: Dict[str, ApproachInput],
    db_path: Optional[str] = None
) -> int:
    """Insert or replace a named scenario with its 4 approach configurations."""
    ensure_db_ready(db_path)
    conn = get_connection(db_path)
    with conn:
        # Check if scenario exists
        cur = conn.execute("SELECT id FROM scenarios WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            scenario_id = row["id"]
            conn.execute(
                """
                UPDATE scenarios SET
                    description = ?, cycle_min = ?, cycle_max = ?, fixed_cycle_time = ?,
                    yellow_time = ?, all_red_time = ?, startup_lost_time = ?, yellow_gain = ?,
                    analysis_period_sec = ?, random_seed = ?
                WHERE id = ?
                """,
                (
                    description, timing.cycle_min, timing.cycle_max, timing.fixed_cycle_time,
                    timing.yellow_time, timing.all_red_time, timing.startup_lost_time, timing.yellow_gain,
                    timing.analysis_period_sec, timing.random_seed, scenario_id
                )
            )
            conn.execute("DELETE FROM approach_inputs WHERE scenario_id = ?", (scenario_id,))
        else:
            cur = conn.execute(
                """
                INSERT INTO scenarios (
                    name, description, cycle_min, cycle_max, fixed_cycle_time,
                    yellow_time, all_red_time, startup_lost_time, yellow_gain,
                    analysis_period_sec, random_seed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name, description, timing.cycle_min, timing.cycle_max, timing.fixed_cycle_time,
                    timing.yellow_time, timing.all_red_time, timing.startup_lost_time, timing.yellow_gain,
                    timing.analysis_period_sec, timing.random_seed
                )
            )
            scenario_id = cur.lastrowid

        for direction, app in approaches.items():
            conn.execute(
                """
                INSERT INTO approach_inputs (
                    scenario_id, direction, volume_vph, num_lanes, saturation_per_lane_vph,
                    min_green_sec, max_green_sec, priority_weight
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scenario_id, direction, app.volume_vph, app.num_lanes,
                    app.saturation_per_lane_vph, app.min_green_sec, app.max_green_sec, app.priority_weight
                )
            )
    conn.close()
    return scenario_id


def load_scenario(scenario_id: int, db_path: Optional[str] = None) -> Optional[Tuple[SignalTimingConfig, Dict[str, ApproachInput], str, str]]:
    """Load a scenario by ID. Returns (timing, approaches, name, description) or None."""
    ensure_db_ready(db_path)
    conn = get_connection(db_path)
    cur = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    timing = SignalTimingConfig(
        cycle_min=row["cycle_min"],
        cycle_max=row["cycle_max"],
        fixed_cycle_time=row["fixed_cycle_time"],
        yellow_time=row["yellow_time"],
        all_red_time=row["all_red_time"],
        startup_lost_time=row["startup_lost_time"],
        yellow_gain=row["yellow_gain"],
        analysis_period_sec=row["analysis_period_sec"],
        random_seed=row["random_seed"]
    )
    name = row["name"]
    desc = row["description"] or ""

    approaches: Dict[str, ApproachInput] = {}
    app_cur = conn.execute("SELECT * FROM approach_inputs WHERE scenario_id = ?", (scenario_id,))
    for a_row in app_cur.fetchall():
        approaches[a_row["direction"]] = ApproachInput(
            direction=a_row["direction"],
            volume_vph=a_row["volume_vph"],
            num_lanes=a_row["num_lanes"],
            saturation_per_lane_vph=a_row["saturation_per_lane_vph"],
            min_green_sec=a_row["min_green_sec"],
            max_green_sec=a_row["max_green_sec"],
            priority_weight=a_row["priority_weight"]
        )
    conn.close()
    return timing, approaches, name, desc


def list_scenarios(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all saved scenarios with summary metadata."""
    ensure_db_ready(db_path)
    conn = get_connection(db_path)
    cur = conn.execute("SELECT id, name, description, created_at FROM scenarios ORDER BY id DESC")
    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results


def delete_scenario(scenario_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a scenario and its cascaded records."""
    ensure_db_ready(db_path)
    conn = get_connection(db_path)
    with conn:
        cur = conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        deleted = cur.rowcount > 0
    conn.close()
    return deleted


def save_optimization_run(
    scenario_id: Optional[int],
    eval_result: IntersectionEvaluation,
    db_path: Optional[str] = None
) -> int:
    """Save an intersection optimization evaluation and its 4 approach metrics."""
    ensure_db_ready(db_path)
    conn = get_connection(db_path)
    run_type_map = {
        "Fixed-Time Baseline": "fixed",
        "SmartFlow LP Optimized": "lp_optimized"
    }
    run_type = run_type_map.get(eval_result.plan_name, "lp_optimized")

    with conn:
        cur = conn.execute(
            """
            INSERT INTO optimization_runs (
                scenario_id, run_type, solver_name, solver_status, solve_time_ms,
                cycle_time_sec, total_lost_time_sec, intersection_flow_ratio_y,
                avg_wait_time_sec, total_avg_queue_veh, max_saturation_rho,
                throughput_vph, intersection_los
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id, run_type, eval_result.plan_name, eval_result.solver_status,
                eval_result.solve_time_ms, eval_result.cycle_time_sec, eval_result.total_lost_time_sec,
                eval_result.sum_flow_ratio_y, eval_result.demand_weighted_avg_wait_sec,
                eval_result.total_avg_queue_veh, eval_result.max_saturation_rho,
                eval_result.total_throughput_vph, eval_result.intersection_los
            )
        )
        run_id = cur.lastrowid

        for direction, app_res in eval_result.approaches.items():
            conn.execute(
                """
                INSERT INTO approach_results (
                    run_id, direction, arrival_rate_vps, saturation_rate_vps,
                    effective_service_rate_vps, allocated_green_sec, degree_of_saturation_rho,
                    uniform_delay_d1_sec, overflow_delay_d2_sec, avg_wait_time_sec,
                    avg_queue_length_veh, max_queue_length_veh, los_grade, lp_shadow_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, direction, app_res.arrival_rate_vps, app_res.saturation_rate_vps,
                    app_res.effective_service_rate_vps, app_res.allocated_green_sec,
                    app_res.degree_of_saturation_rho, app_res.uniform_delay_d1_sec,
                    app_res.overflow_delay_d2_sec, app_res.avg_wait_time_sec,
                    app_res.avg_queue_length_veh, app_res.max_queue_length_veh,
                    app_res.los_grade, app_res.lp_shadow_price
                )
            )
    conn.close()
    return run_id


def save_emergency_event(
    run_id: Optional[int],
    em_res: EmergencyPreemptionResult,
    db_path: Optional[str] = None
) -> int:
    """Save an Emergency Vehicle priority event and resulting schedule blocks."""
    ensure_db_ready(db_path)
    conn = get_connection(db_path)
    schedule_json = json.dumps(em_res.schedule_blocks)
    with conn:
        cur = conn.execute(
            """
            INSERT INTO emergency_events (
                run_id, direction, vehicle_type, arrival_time_sec, current_active_phase,
                elapsed_active_green_sec, ev_wait_normal_sec, ev_wait_preempted_sec,
                time_saved_sec, schedule_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, em_res.approach, em_res.vehicle_type, em_res.arrival_time_sec,
                em_res.current_active_phase, em_res.elapsed_active_green_sec,
                em_res.ev_wait_normal_sec, em_res.ev_wait_preempted_sec,
                em_res.time_saved_sec, schedule_json
            )
        )
        event_id = cur.lastrowid
    conn.close()
    return event_id


def save_simulation_run(
    scenario_id: Optional[int],
    fixed_run_id: Optional[int],
    opt_run_id: Optional[int],
    trace: SimulationTrace,
    db_path: Optional[str] = None
) -> int:
    """Save macroscopic simulation summary metrics."""
    ensure_db_ready(db_path)
    conn = get_connection(db_path)
    with conn:
        cur = conn.execute(
            """
            INSERT INTO simulation_runs (
                scenario_id, fixed_run_id, opt_run_id, duration_sec, arrival_mode,
                random_seed, fixed_sim_avg_wait_sec, opt_sim_avg_wait_sec,
                fixed_sim_max_queue_veh, opt_sim_max_queue_veh,
                fixed_sim_throughput_veh, opt_sim_throughput_veh
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id, fixed_run_id, opt_run_id, trace.duration_sec,
                trace.arrival_mode, trace.random_seed,
                trace.fixed_summary.get("avg_wait_sec", 0.0),
                trace.opt_summary.get("avg_wait_sec", 0.0),
                trace.fixed_summary.get("max_queue_veh", 0.0),
                trace.opt_summary.get("max_queue_veh", 0.0),
                trace.fixed_summary.get("throughput_veh", 0),
                trace.opt_summary.get("throughput_veh", 0)
            )
        )
        sim_id = cur.lastrowid
    conn.close()
    return sim_id


def list_recent_evaluations(limit: int = 15, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recent optimization and baseline evaluations."""
    ensure_db_ready(db_path)
    conn = get_connection(db_path)
    cur = conn.execute(
        """
        SELECT o.*, s.name as scenario_name
        FROM optimization_runs o
        LEFT JOIN scenarios s ON o.scenario_id = s.id
        ORDER BY o.id DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

