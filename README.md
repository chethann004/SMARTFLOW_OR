# SmartFlow OR 🚦
### An Intelligent Traffic Signal Optimization System Using Operations Research Techniques

---

## 📌 Project Overview
**SmartFlow OR** is an academic decision-support, optimization, and simulation application developed for a 4-way signalized traffic intersection (`North`, `South`, `East`, `West`).

Rather than relying on visual approximations or heuristic rules, **SmartFlow OR** implements formal mathematical techniques from **Operations Research (OR)**:
1. **Linear Programming (LP)**: Separable convex piecewise-linear delay minimization solved via **PuLP (CBC)** to compute optimal green signal splits ($g_N, g_S, g_E, g_W$) and cycle length ($C^*$).
2. **Queuing Theory**: Cyclic signalized $D/D/1$ uniform delay + time-dependent coordinate-transformed $M/D/1$ overflow delay + Little's Law ($L_q = \lambda W$) + Highway Capacity Manual (HCM) Level of Service (LOS A–F).
3. **Scheduling Optimization (MILP)**: Single-machine disjunctive scheduling ($1 \mid r_j, \tau \mid \sum w_j C_j$) with safe floor active phase truncation and emergency priority preemption (Ambulances, Fire Trucks, Police).
4. **Sensitivity Analysis**: LP shadow prices / dual variables ($\partial Z / \partial (C-L)$) and parametric demand scaling ($50\% \text{ to } 150\%$) identifying saturation tipping points ($\rho = 0.85$ and $\rho = 1.00$).

---

## 🏗️ Technology Stack
- **Language**: Python 3.10+ / 3.12+
- **Web UI & Dashboard**: Streamlit
- **Optimization Solver**: PuLP (with bundled Coin-OR CBC solver)
- **Scientific Computing & Data**: NumPy, Pandas, Matplotlib, Tabulate
- **Interactive Visualizations**: Plotly
- **Database Persistence**: SQLite3 (`smartflow_or.db`)
- **Testing Harness**: Pytest

---

## 📐 Operations Research Formulations

### 1. Traffic Capacity & Flow Parameters
- **Arrival Rate**: $\lambda_i = \frac{V_i}{3600} \text{ veh/s}$ where $V_i$ is hourly traffic volume.
- **Saturation Flow Rate**: $s_i = \frac{n_i \cdot S_{\text{lane}}}{3600} \text{ veh/s}$ where $n_i$ is lane count and $S_{\text{lane}} = 1800 \text{ veh/hr/lane}$.
- **Flow Ratio**: $y_i = \frac{\lambda_i}{s_i}, \quad Y = \sum_{i=1}^4 y_i$.
- **Effective Lost Time per Cycle**: $L = 4 \times \big[(Y_{\text{yellow}} + AR) + l_{\text{start}} - e_{\text{gain}}\big] = 16\text{ s}$.

### 2. Signalized Queuing Theory ($D/D/1 + M/D/1$)
- **Effective Service Rate**: $\mu_{\text{eff}, i} = s_i \cdot \frac{g_i}{C}$
- **Degree of Saturation (Traffic Intensity)**: $\rho_i = \frac{\lambda_i}{\mu_{\text{eff}, i}} = \frac{\lambda_i C}{s_i g_i}$
- **Uniform Cyclic Delay ($D/D/1$)**:
  $$d_{1, i} = \frac{0.5 \cdot C \cdot \left(1 - \frac{g_i}{C}\right)^2}{1 - \min(1, \rho_i)\cdot \frac{g_i}{C}}$$
- **Random Overflow Delay ($M/D/1$ Coordinate Transformation)**:
  $$d_{2, i} = \frac{T}{4} \left[ (\rho_i - 1) + \sqrt{(\rho_i - 1)^2 + \frac{4 \rho_i}{\mu_{\text{eff}, i} \cdot T}} \right]$$
- **Total Delay & Little's Law**:
  $$W_i = d_{1, i} + d_{2, i} \quad (\text{s/veh}), \qquad L_{q, i} = \lambda_i \cdot W_i \quad (\text{vehicles})$$

### 3. Linear Programming (LP) Green Allocation
$$\min Z = \sum_{i \in \{N,S,E,W\}} \hat{L}_{q, i} + 10 \sum_{i \in \{N,S,E,W\}} q_{\text{ovf}, i}$$
Subject to:
$$\sum_{i=1}^4 g_i = C - L$$
$$g_{\min, i} \le g_i \le g_{\max, i} \quad \forall i$$
$$\hat{L}_{q, i} \ge w_i \lambda_i \left[ W_i(g_k) + W_i'(g_k)(g_i - g_k) \right] \quad \forall k \in \{0, \dots, K\}$$
$$s_i g_i + q_{\text{ovf}, i} \ge \lambda_i C \quad \forall i$$

---

## 📂 Project Structure
```text
SMARTFLOW_OR/
├── app.py                          # Streamlit application entry point & tab navigation
├── requirements.txt                # Pinned dependencies
├── README.md                       # Comprehensive documentation
├── smartflow_or.db                 # SQLite database (auto-generated)
│
├── config/
│   ├── constants.py                # Engineering defaults, HCM LOS thresholds, colors
│   └── presets.py                  # Realistic scenarios (Balanced, Morning Peak, Corridor, Gridlock)
│
├── models/
│   └── schemas.py                  # Strongly-typed dataclasses for inputs, outputs, schedules
│
├── core/
│   ├── queuing_theory.py           # D/D/1, M/D/1, Little's Law, HCM LOS, M/M/1 reference
│   ├── lp_optimizer.py             # PuLP separable convex piecewise-linear LP solver
│   ├── scheduler_milp.py           # Single-machine MILP phase sequencing & emergency preemption
│   ├── sensitivity.py              # LP shadow prices, parametric demand sweeps, tipping points
│   └── simulation.py               # 1-second step Common Random Numbers (CRN) microscopic simulation
│
├── database/
│   ├── db_manager.py               # SQLite connection helper & schema creation
│   └── repository.py               # Scenario and run history persistence
│
├── services/
│   ├── intersection_service.py     # Pipeline coordinator
│   └── report_service.py           # CSV and Markdown academic report generators
│
├── ui/
│   ├── styles.py                   # Custom CSS cards and badges
│   ├── sidebar.py                  # 4-way volume inputs, scenario selector, signal parameters
│   ├── tab_dashboard.py            # KPI cards & Fixed vs Optimized comparison
│   ├── tab_simulation.py           # 4-way junction simulation & interactive replay
│   ├── tab_math_breakdown.py       # Live LaTeX formula derivations with substituted values
│   ├── tab_emergency.py            # MILP Emergency Vehicle priority & Gantt chart
│   ├── tab_sensitivity.py          # Sensitivity curves, tipping points & dual values
│   └── tab_reports.py              # SQLite run history & CSV/Markdown export
│
└── tests/
    ├── test_queuing_theory.py      # Tests for d1, d2, Little's Law, zero-flow, oversaturation
    ├── test_lp_optimizer.py        # Tests for green budget, bounds, optimality vs fixed time
    ├── test_scheduler_milp.py      # Tests for EV preemption safety & intergreen clearance
    ├── test_simulation.py          # Tests for CRN arrival conservation & throughput
    └── test_database.py            # Tests for SQLite CRUD & transaction logging
```

---

## 🚀 How to Run the Application

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Pytest Verification Suite
```bash
python -m pytest tests -v
```

### 3. Launch the Web Application
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 👥 3-Member Team Work Distribution
- **Member 1 (Math & OR Modeling Lead)**:
  - Formulated Linear Programming piecewise-linear envelope.
  - Implemented Queuing Theory equations ($D/D/1$, $M/D/1$, Little's Law, HCM LOS).
  - Implemented Parametric Sensitivity Analysis and LP shadow prices.
- **Member 2 (Scheduling & Simulation Lead)**:
  - Formulated MILP Single-Machine Phase Scheduling and Emergency Preemption.
  - Implemented 1-second discrete-time Common Random Numbers simulation engine.
  - Built SQLite database schema, foreign-key relationships, and repository.
- **Member 3 (UI, Integration & Reporting Lead)**:
  - Built Streamlit multipage/tabbed architecture and custom CSS styles.
  - Created interactive Plotly visualisations (Gantt chart, 4-way junction schematic, sensitivity curves).
  - Developed CSV and Markdown report generators and presentation materials.

