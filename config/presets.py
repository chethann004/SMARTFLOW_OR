"""Predefined realistic traffic scenarios for demonstration, testing, and academic evaluation."""

from typing import Dict, Any

PRESET_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "Balanced Urban Flow": {
        "description": "Standard balanced traffic across all approaches with light-to-moderate demand.",
        "cycle_min": 60.0,
        "cycle_max": 120.0,
        "fixed_cycle": 100.0,
        "approaches": {
            "North": {"volume_vph": 650.0, "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 50.0, "weight": 1.0},
            "South": {"volume_vph": 600.0, "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 50.0, "weight": 1.0},
            "East":  {"volume_vph": 550.0, "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 50.0, "weight": 1.0},
            "West":  {"volume_vph": 520.0, "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 50.0, "weight": 1.0},
        }
    },
    "Morning Peak (North Commuter Rush)": {
        "description": "Heavy inbound commuter traffic along Northbound arterial with lower opposing and cross traffic.",
        "cycle_min": 70.0,
        "cycle_max": 140.0,
        "fixed_cycle": 120.0,
        "approaches": {
            "North": {"volume_vph": 1400.0, "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 15.0, "max_green": 70.0, "weight": 1.5},
            "South": {"volume_vph": 450.0,  "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 40.0, "weight": 1.0},
            "East":  {"volume_vph": 380.0,  "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 35.0, "weight": 1.0},
            "West":  {"volume_vph": 320.0,  "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 35.0, "weight": 1.0},
        }
    },
    "East-West Commercial Corridor": {
        "description": "Major East-West commercial artery carrying heavy logistics and transit volumes.",
        "cycle_min": 70.0,
        "cycle_max": 130.0,
        "fixed_cycle": 110.0,
        "approaches": {
            "North": {"volume_vph": 420.0,  "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 40.0, "weight": 1.0},
            "South": {"volume_vph": 460.0,  "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 10.0, "max_green": 40.0, "weight": 1.0},
            "East":  {"volume_vph": 1250.0, "num_lanes": 3, "sat_flow_lane": 1800.0, "min_green": 15.0, "max_green": 65.0, "weight": 1.2},
            "West":  {"volume_vph": 1180.0, "num_lanes": 3, "sat_flow_lane": 1800.0, "min_green": 15.0, "max_green": 65.0, "weight": 1.2},
        }
    },
    "Near Capacity Gridlock Test": {
        "description": "High volumes across all directions testing optimization limits and saturation tipping points.",
        "cycle_min": 90.0,
        "cycle_max": 160.0,
        "fixed_cycle": 130.0,
        "approaches": {
            "North": {"volume_vph": 1100.0, "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 12.0, "max_green": 55.0, "weight": 1.0},
            "South": {"volume_vph": 1050.0, "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 12.0, "max_green": 55.0, "weight": 1.0},
            "East":  {"volume_vph": 980.0,  "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 12.0, "max_green": 55.0, "weight": 1.0},
            "West":  {"volume_vph": 1020.0, "num_lanes": 2, "sat_flow_lane": 1800.0, "min_green": 12.0, "max_green": 55.0, "weight": 1.0},
        }
    }
}

