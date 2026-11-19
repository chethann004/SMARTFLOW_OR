"""SQLite connection and schema manager for SmartFlow OR."""

import sqlite3
import os
from typing import Optional

DB_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "smartflow_or.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    cycle_min REAL NOT NULL DEFAULT 60.0,
    cycle_max REAL NOT NULL DEFAULT 150.0,
    fixed_cycle_time REAL NOT NULL DEFAULT 120.0,
    yellow_time REAL NOT NULL DEFAULT 3.0,
    all_red_time REAL NOT NULL DEFAULT 1.0,
    startup_lost_time REAL NOT NULL DEFAULT 2.0,
    yellow_gain REAL NOT NULL DEFAULT 2.0,
    analysis_period_sec REAL NOT NULL DEFAULT 900.0,
    random_seed INTEGER NOT NULL DEFAULT 42,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS approach_inputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('North', 'South', 'East', 'West')),
    volume_vph REAL NOT NULL,
    num_lanes INTEGER NOT NULL DEFAULT 2,
    saturation_per_lane_vph REAL NOT NULL DEFAULT 1800.0,
    min_green_sec REAL NOT NULL DEFAULT 10.0,
    max_green_sec REAL NOT NULL DEFAULT 65.0,
    priority_weight REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY(scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE,
    UNIQUE(scenario_id, direction)
);

CREATE TABLE IF NOT EXISTS optimization_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER,
    run_type TEXT NOT NULL CHECK(run_type IN ('fixed', 'lp_optimized', 'emergency_milp')),
    solver_name TEXT NOT NULL,
    solver_status TEXT NOT NULL,
    solve_time_ms REAL NOT NULL,
    cycle_time_sec REAL NOT NULL,
    total_lost_time_sec REAL NOT NULL,
    intersection_flow_ratio_y REAL NOT NULL,
    avg_wait_time_sec REAL NOT NULL,
    total_avg_queue_veh REAL NOT NULL,
    max_saturation_rho REAL NOT NULL,
    throughput_vph REAL NOT NULL,
    intersection_los TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scenario_id) REFERENCES scenarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS approach_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    arrival_rate_vps REAL NOT NULL,
    saturation_rate_vps REAL NOT NULL,
    effective_service_rate_vps REAL NOT NULL,
    allocated_green_sec REAL NOT NULL,
    degree_of_saturation_rho REAL NOT NULL,
    uniform_delay_d1_sec REAL NOT NULL,
    overflow_delay_d2_sec REAL NOT NULL,
    avg_wait_time_sec REAL NOT NULL,
    avg_queue_length_veh REAL NOT NULL,
    max_queue_length_veh REAL NOT NULL,
    los_grade TEXT NOT NULL,
    lp_shadow_price REAL,
    FOREIGN KEY(run_id) REFERENCES optimization_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS emergency_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    direction TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    arrival_time_sec REAL NOT NULL,
    current_active_phase TEXT NOT NULL,
    elapsed_active_green_sec REAL NOT NULL,
    ev_wait_normal_sec REAL NOT NULL,
    ev_wait_preempted_sec REAL NOT NULL,
    time_saved_sec REAL NOT NULL,
    schedule_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES optimization_runs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER,
    fixed_run_id INTEGER,
    opt_run_id INTEGER,
    duration_sec INTEGER NOT NULL,
    arrival_mode TEXT NOT NULL,
    random_seed INTEGER NOT NULL,
    fixed_sim_avg_wait_sec REAL NOT NULL,
    opt_sim_avg_wait_sec REAL NOT NULL,
    fixed_sim_max_queue_veh REAL NOT NULL,
    opt_sim_max_queue_veh REAL NOT NULL,
    fixed_sim_throughput_veh INTEGER NOT NULL,
    opt_sim_throughput_veh INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scenario_id) REFERENCES scenarios(id) ON DELETE SET NULL,
    FOREIGN KEY(fixed_run_id) REFERENCES optimization_runs(id) ON DELETE SET NULL,
    FOREIGN KEY(opt_run_id) REFERENCES optimization_runs(id) ON DELETE SET NULL
);
"""

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return an active SQLite connection with Row factory and Foreign Keys enabled."""
    path = db_path or DB_FILE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_database(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indexes."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()

