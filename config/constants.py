"""Global constants, default traffic engineering parameters, and styling rules."""

from typing import Final, Tuple, Dict

DIRECTIONS: Final[Tuple[str, ...]] = ("North", "South", "East", "West")

# Signal timing defaults (in seconds)
DEFAULT_CYCLE_MIN: Final[float] = 60.0
DEFAULT_CYCLE_MAX: Final[float] = 150.0
DEFAULT_FIXED_CYCLE: Final[float] = 120.0
DEFAULT_YELLOW: Final[float] = 3.0
DEFAULT_ALL_RED: Final[float] = 1.0
DEFAULT_STARTUP_LOST: Final[float] = 2.0
DEFAULT_YELLOW_GAIN: Final[float] = 2.0
DEFAULT_INTERGREEN: Final[float] = DEFAULT_YELLOW + DEFAULT_ALL_RED  # 4.0s
DEFAULT_LOST_PER_PHASE: Final[float] = DEFAULT_INTERGREEN + DEFAULT_STARTUP_LOST - DEFAULT_YELLOW_GAIN  # 4.0s

# Capacity and evaluation defaults
DEFAULT_SATURATION_PER_LANE_VPH: Final[float] = 1800.0  # vehicles/hour/lane (0.5 veh/s/lane)
DEFAULT_MIN_GREEN: Final[float] = 10.0
DEFAULT_MAX_GREEN: Final[float] = 65.0
DEFAULT_LANES: Final[int] = 2
DEFAULT_ANALYSIS_PERIOD_SEC: Final[float] = 900.0  # 15 minutes
DEFAULT_SIM_STEP_SEC: Final[float] = 1.0
DEFAULT_RANDOM_SEED: Final[int] = 42

# Highway Capacity Manual (HCM) Signalized Intersection Delay Levels of Service (LOS)
# Threshold is maximum average control delay in seconds
HCM_LOS_THRESHOLDS: Final[Tuple[Tuple[float, str, str], ...]] = (
    (10.0, "A", "Free Flow: Very low delay, high progression quality."),
    (20.0, "B", "Stable Operation: Good progression, brief waiting periods."),
    (35.0, "C", "Acceptable Delay: Noticeable cycle queues, moderate delay."),
    (55.0, "D", "Tolerable Delay: Increasing congestion, cycle failures noticeable."),
    (80.0, "E", "Near Capacity: Unstable flow, long queues, high delay."),
    (float("inf"), "F", "Oversaturated: Forced flow, extreme delay, breakdown."),
)

def get_hcm_los(avg_wait_sec: float, degree_of_sat_rho: float = 0.0) -> Tuple[str, str]:
    """Return HCM LOS Grade and descriptive definition.
    If degree of saturation exceeds 1.0, LOS is designated as F regardless of delay."""
    if degree_of_sat_rho > 1.0:
        return "F", "Oversaturated: Flow ratio exceeds approach capacity (rho > 1.0)."
    for threshold, grade, desc in HCM_LOS_THRESHOLDS:
        if avg_wait_sec <= threshold:
            return grade, desc
    return "F", "Oversaturated: Control delay exceeds 80 seconds."

# Visual color mapping
COLOR_PALETTE: Final[Dict[str, str]] = {
    "North": "#2980b9",      # Blue
    "South": "#27ae60",      # Green
    "East": "#d35400",       # Orange
    "West": "#8e44ad",       # Purple
    "Fixed": "#7f8c8d",      # Gray
    "Optimized": "#16a085",  # Teal
    "Emergency": "#c0392b",  # Red
    "Background": "#f8f9fa"
}

