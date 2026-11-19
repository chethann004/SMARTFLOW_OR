"""Custom CSS styling and visual components for a clean, academic, professional interface."""

import streamlit as st

CUSTOM_CSS = """
<style>
    /* Global Typography & Spacing */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2.5rem;
        max-width: 1400px;
    }
    
    /* Header card */
    .smartflow-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    .smartflow-header h1 {
        color: #ffffff !important;
        font-size: 2.1rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .smartflow-header p {
        color: #dbe4ee;
        font-size: 1.05rem;
        margin: 0.3rem 0 0 0;
    }

    /* Metric Card */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e1e8ed;
        border-radius: 10px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .metric-card-title {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: #64748b;
        font-weight: 600;
        margin-bottom: 0.3rem;
    }
    .metric-card-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.1;
    }
    .metric-card-delta {
        font-size: 0.85rem;
        font-weight: 600;
        margin-top: 0.3rem;
    }
    .delta-positive { color: #10b981; }
    .delta-negative { color: #ef4444; }
    .delta-neutral { color: #64748b; }

    /* Academic math highlight box */
    .math-card {
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6;
        border-radius: 0 8px 8px 0;
        padding: 1rem 1.4rem;
        margin: 1rem 0;
    }

    /* Status badges */
    .los-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.9rem;
    }
    .los-A { background-color: #d1fae5; color: #065f46; }
    .los-B { background-color: #ecfccb; color: #3f6212; }
    .los-C { background-color: #fef3c7; color: #92400e; }
    .los-D { background-color: #ffedd5; color: #9a3412; }
    .los-E { background-color: #fee2e2; color: #991b1b; }
    .los-F { background-color: #fecdd3; color: #881337; }

    /* Custom Streamlit Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 6px 6px 0 0;
        font-weight: 600;
    }
</style>
"""

def apply_custom_styles():
    """Inject custom CSS into Streamlit page."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_header():
    """Render top banner header."""
    st.markdown(
        """
        <div class="smartflow-header">
            <h1>🚦 SmartFlow OR</h1>
            <p>An Intelligent Traffic Signal Optimization & Microscopic Simulation System Using Operations Research</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_metric_card(title: str, value: str, delta: str = "", delta_type: str = "positive"):
    """Render a styled metric card."""
    delta_class = f"delta-{delta_type}"
    delta_html = f'<div class="metric-card-delta {delta_class}">{delta}</div>' if delta else ""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title">{title}</div>
            <div class="metric-card-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True
    )

