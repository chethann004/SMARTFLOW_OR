"""Report generation and export utilities for academic documentation and research analysis."""

import io
from typing import Dict, Any, List
import pandas as pd

from models.schemas import IntersectionEvaluation, EmergencyPreemptionResult, SimulationTrace


def generate_comparison_dataframe(
    fixed_eval: IntersectionEvaluation,
    opt_eval: IntersectionEvaluation
) -> pd.DataFrame:
    """Generate side-by-side comparison DataFrame across approaches and KPIs."""
    rows = []
    directions = list(fixed_eval.approaches.keys())

    for d in directions:
        f_app = fixed_eval.approaches[d]
        o_app = opt_eval.approaches[d]

        wait_diff = f_app.avg_wait_time_sec - o_app.avg_wait_time_sec
        wait_pct = (wait_diff / max(0.1, f_app.avg_wait_time_sec)) * 100.0

        rows.append({
            "Approach": d,
            "Arrival (vph)": round(f_app.arrival_rate_vps * 3600.0, 0),
            "Fixed Green (s)": round(f_app.allocated_green_sec, 1),
            "Opt Green (s)": round(o_app.allocated_green_sec, 1),
            "Fixed Rho (v/c)": round(f_app.degree_of_saturation_rho, 3),
            "Opt Rho (v/c)": round(o_app.degree_of_saturation_rho, 3),
            "Fixed Delay (s)": round(f_app.avg_wait_time_sec, 1),
            "Opt Delay (s)": round(o_app.avg_wait_time_sec, 1),
            "Delay Saved (%)": round(wait_pct, 1),
            "Fixed Queue (veh)": round(f_app.avg_queue_length_veh, 1),
            "Opt Queue (veh)": round(o_app.avg_queue_length_veh, 1),
            "Fixed LOS": f_app.los_grade,
            "Opt LOS": o_app.los_grade
        })

    # Summary row
    int_wait_diff = fixed_eval.demand_weighted_avg_wait_sec - opt_eval.demand_weighted_avg_wait_sec
    int_wait_pct = (int_wait_diff / max(0.1, fixed_eval.demand_weighted_avg_wait_sec)) * 100.0

    rows.append({
        "Approach": "INTERSECTION (AVG)",
        "Arrival (vph)": round(sum(f.arrival_rate_vps * 3600.0 for f in fixed_eval.approaches.values()), 0),
        "Fixed Green (s)": round(fixed_eval.total_green_sec, 1),
        "Opt Green (s)": round(opt_eval.total_green_sec, 1),
        "Fixed Rho (v/c)": round(fixed_eval.max_saturation_rho, 3),
        "Opt Rho (v/c)": round(opt_eval.max_saturation_rho, 3),
        "Fixed Delay (s)": round(fixed_eval.demand_weighted_avg_wait_sec, 1),
        "Opt Delay (s)": round(opt_eval.demand_weighted_avg_wait_sec, 1),
        "Delay Saved (%)": round(int_wait_pct, 1),
        "Fixed Queue (veh)": round(fixed_eval.total_avg_queue_veh, 1),
        "Opt Queue (veh)": round(opt_eval.total_avg_queue_veh, 1),
        "Fixed LOS": fixed_eval.intersection_los,
        "Opt LOS": opt_eval.intersection_los
    })

    return pd.DataFrame(rows)


def export_csv_report(
    fixed_eval: IntersectionEvaluation,
    opt_eval: IntersectionEvaluation,
    sim_trace: SimulationTrace
) -> str:
    """Format full academic evaluation and simulation metrics into a downloadable CSV string."""
    df_comp = generate_comparison_dataframe(fixed_eval, opt_eval)
    buf = io.StringIO()
    buf.write("# SMARTFLOW OR - TRAFFIC SIGNAL OPTIMIZATION REPORT\n")
    buf.write(f"# Fixed-Time Cycle: {fixed_eval.cycle_time_sec}s | Optimized Cycle: {opt_eval.cycle_time_sec}s\n")
    buf.write(f"# Lost Time: {opt_eval.total_lost_time_sec}s | Total Intersection Flow Ratio Y: {opt_eval.sum_flow_ratio_y:.3f}\n")
    buf.write(f"# Simulation Duration: {sim_trace.duration_sec}s | Mode: {sim_trace.arrival_mode}\n\n")

    buf.write("## 1. ANALYTICAL QUEUING & LP METRICS\n")
    df_comp.to_csv(buf, index=False)

    buf.write("\n## 2. DISCRETE-TIME SIMULATION BENCHMARK\n")
    sim_rows = [
        {"Metric": "Average Waiting Time (s)", "Fixed-Time Controller": sim_trace.fixed_summary.get("avg_wait_sec"), "SmartFlow OR Controller": sim_trace.opt_summary.get("avg_wait_sec")},
        {"Metric": "Maximum Queue Length (veh)", "Fixed-Time Controller": sim_trace.fixed_summary.get("max_queue_veh"), "SmartFlow OR Controller": sim_trace.opt_summary.get("max_queue_veh")},
        {"Metric": "Total Completed Throughput (veh)", "Fixed-Time Controller": sim_trace.fixed_summary.get("throughput_veh"), "SmartFlow OR Controller": sim_trace.opt_summary.get("throughput_veh")}
    ]
    pd.DataFrame(sim_rows).to_csv(buf, index=False)

    return buf.getvalue()


def export_markdown_academic_report(
    fixed_eval: IntersectionEvaluation,
    opt_eval: IntersectionEvaluation,
    sim_trace: SimulationTrace,
    em_res: EmergencyPreemptionResult = None
) -> str:
    """Generate structured Markdown project report for MCA academic submission and viva."""
    df_comp = generate_comparison_dataframe(fixed_eval, opt_eval)
    table_md = df_comp.to_markdown(index=False)

    em_section = ""
    if em_res:
        em_section = f"""
## 3. Emergency Vehicle Priority Scheduling (MILP)
- **Preempted Vehicle**: {em_res.vehicle_type} on approach **{em_res.approach}**
- **Normal Cycle Wait Time**: {em_res.normal_wait_sec} seconds
- **Preempted Wait Time**: {em_res.preempted_wait_sec} seconds
- **Response Time Saved**: **{em_res.time_saved_sec} seconds** ({round((em_res.time_saved_sec / max(0.1, em_res.normal_wait_sec)) * 100.0, 1)}% faster)
- **Phase Sequence**: `{" -> ".join([b["phase"] for b in em_res.schedule_blocks])}`
"""

    md = f"""# SmartFlow OR: Intelligent Traffic Signal Optimization System
**Academic Operations Research Project Report**

---

## 1. Executive Summary
- **Baseline Fixed-Time Average Waiting Time**: {fixed_eval.demand_weighted_avg_wait_sec:.1f} s/veh (LOS {fixed_eval.intersection_los})
- **SmartFlow OR Optimized Average Waiting Time**: {opt_eval.demand_weighted_avg_wait_sec:.1f} s/veh (LOS {opt_eval.intersection_los})
- **Net Delay Reduction**: **{((fixed_eval.demand_weighted_avg_wait_sec - opt_eval.demand_weighted_avg_wait_sec) / max(0.1, fixed_eval.demand_weighted_avg_wait_sec)) * 100.0:.1f}%**
- **Optimal Cycle Length ($C^*$)**: **{opt_eval.cycle_time_sec:.0f} s** (vs Fixed Cycle {fixed_eval.cycle_time_sec:.0f} s)
- **Critical Intersection Flow Ratio ($Y$)**: {opt_eval.sum_flow_ratio_y:.3f}

---

## 2. Approach-by-Approach Operations Research Performance Table
{table_md}
{em_section}
---

## 4. Discrete-Time Microscopic Simulation Validation
A 1-second step Common Random Numbers (CRN) simulation ran over a {sim_trace.duration_sec} s horizon:
- **Fixed-Time Simulated Wait Time**: {sim_trace.fixed_summary.get('avg_wait_sec', 0.0):.1f} s
- **Optimized Simulated Wait Time**: {sim_trace.opt_summary.get('avg_wait_sec', 0.0):.1f} s
- **Fixed-Time Maximum Queue**: {sim_trace.fixed_summary.get('max_queue_veh', 0)} vehicles
- **Optimized Maximum Queue**: {sim_trace.opt_summary.get('max_queue_veh', 0)} vehicles

---
*Report generated automatically by SmartFlow OR decision support engine.*
"""
    return md

