"""Strongly typed dataclasses for inputs, outputs, schedules, and simulation records."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from config.constants import (
    DEFAULT_CYCLE_MIN,
    DEFAULT_CYCLE_MAX,
    DEFAULT_FIXED_CYCLE,
    DEFAULT_YELLOW,
    DEFAULT_ALL_RED,
    DEFAULT_STARTUP_LOST,
    DEFAULT_YELLOW_GAIN,
    DEFAULT_ANALYSIS_PERIOD_SEC,
    DEFAULT_RANDOM_SEED,
    DEFAULT_MIN_GREEN,
    DEFAULT_MAX_GREEN,
    DEFAULT_SATURATION_PER_LANE_VPH,
    DEFAULT_LANES,
    get_hcm_los
)


@dataclass
class ApproachInput:
    """Manual and physical parameters for one approach direction."""
    direction: str
    volume_vph: float
    num_lanes: int = DEFAULT_LANES
    saturation_per_lane_vph: float = DEFAULT_SATURATION_PER_LANE_VPH
    min_green_sec: float = DEFAULT_MIN_GREEN
    max_green_sec: float = DEFAULT_MAX_GREEN
    priority_weight: float = 1.0

    @property
    def arrival_rate_vps(self) -> float:
        """Arrival rate lambda in vehicles per second."""
        return max(0.0, self.volume_vph) / 3600.0

    @property
    def sat_flow_rate_vps(self) -> float:
        """Saturation discharge rate s in vehicles per second during green."""
        lanes = max(1, self.num_lanes)
        sat_lane = max(100.0, self.saturation_per_lane_vph)
        return (lanes * sat_lane) / 3600.0

    @property
    def flow_ratio_y(self) -> float:
        """Flow ratio y = lambda / s."""
        s = self.sat_flow_rate_vps
        return (self.arrival_rate_vps / s) if s > 0 else 0.0


@dataclass
class SignalTimingConfig:
    """Global intersection timing, lost time parameters, and simulation settings."""
    cycle_min: float = DEFAULT_CYCLE_MIN
    cycle_max: float = DEFAULT_CYCLE_MAX
    fixed_cycle_time: float = DEFAULT_FIXED_CYCLE
    yellow_time: float = DEFAULT_YELLOW
    all_red_time: float = DEFAULT_ALL_RED
    startup_lost_time: float = DEFAULT_STARTUP_LOST
    yellow_gain: float = DEFAULT_YELLOW_GAIN
    analysis_period_sec: float = DEFAULT_ANALYSIS_PERIOD_SEC
    random_seed: int = DEFAULT_RANDOM_SEED

    @property
    def intergreen_per_phase(self) -> float:
        """Yellow + All-Red clearance interval per phase."""
        return self.yellow_time + self.all_red_time

    @property
    def lost_time_per_phase(self) -> float:
        """Effective lost time per phase l = (Y + AR) + l_start - e_gain."""
        return self.intergreen_per_phase + self.startup_lost_time - self.yellow_gain

    @property
    def total_lost_time(self) -> float:
        """Total lost time per cycle across 4 phases."""
        return 4.0 * self.lost_time_per_phase


@dataclass
class ApproachQueuingResult:
    """Exact Operations Research Queuing metrics for one approach under a timing plan."""
    direction: str
    allocated_green_sec: float
    cycle_time_sec: float
    arrival_rate_vps: float
    saturation_rate_vps: float
    flow_ratio_y: float
    effective_service_rate_vps: float
    degree_of_saturation_rho: float
    uniform_delay_d1_sec: float
    overflow_delay_d2_sec: float
    avg_wait_time_sec: float
    avg_queue_length_veh: float
    max_queue_length_veh: float
    los_grade: str
    los_description: str
    mm1_reference_wait_sec: Optional[float] = None
    lp_shadow_price: Optional[float] = None


@dataclass
class IntersectionEvaluation:
    """Comprehensive analytical performance summary for an entire 4-way intersection."""
    plan_name: str
    cycle_time_sec: float
    total_lost_time_sec: float
    total_green_sec: float
    sum_flow_ratio_y: float
    is_oversaturated: bool
    approaches: Dict[str, ApproachQueuingResult]
    demand_weighted_avg_wait_sec: float
    total_avg_queue_veh: float
    max_saturation_rho: float
    intersection_los: str
    total_throughput_vph: float
    solver_status: str = "Optimal"
    solve_time_ms: float = 0.0


@dataclass
class EmergencyPreemptionResult:
    """Scheduling output and trade-off metrics for Emergency Vehicle preemption."""
    approach: str
    vehicle_type: str
    arrival_time_sec: float
    current_active_phase: str
    elapsed_active_green_sec: float
    ev_wait_normal_sec: float
    ev_wait_preempted_sec: float
    time_saved_sec: float
    schedule_blocks: List[Dict[str, Any]]
    recovery_makespan_sec: float
    cross_street_extra_delay_sec: float


@dataclass
class SimulationTrace:
    """Detailed results from microscopic discrete-time (1s) simulation."""
    scenario_name: str
    duration_sec: int
    arrival_mode: str
    random_seed: int
    fixed_summary: Dict[str, Any]
    opt_summary: Dict[str, Any]
    second_by_second_records: List[Dict[str, Any]] = field(default_factory=list)
    analytical_vs_sim_comparison: Dict[str, Any] = field(default_factory=dict)

