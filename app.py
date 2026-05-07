"""
app.py — Streamlit entry point for Bill Splitter.
Handles page config, global CSS, session state, and step routing.
"""
import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BillSplit",
    page_icon="🧾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Base & fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Hide default Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Animated gradient header ── */
    .app-header {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 40%, #a78bfa 100%);
        border-radius: 20px;
        padding: 32px 36px 26px;
        margin-bottom: 28px;
        box-shadow: 0 12px 40px rgba(99, 102, 241, 0.3);
        position: relative;
        overflow: hidden;
    }
    .app-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 260px;
        height: 260px;
        background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
        border-radius: 50%;
    }
    .app-header h1 {
        font-size: 2.1rem;
        font-weight: 800;
        color: #fff;
        margin: 0 0 6px 0;
        letter-spacing: -0.5px;
    }
    .app-header p {
        font-size: 0.9rem;
        color: rgba(255,255,255,0.78);
        margin: 0;
        font-weight: 400;
    }

    /* ── Step progress pills ── */
    .step-bar {
        display: flex;
        gap: 8px;
        margin-bottom: 28px;
        flex-wrap: wrap;
        align-items: center;
    }
    .step-pill {
        padding: 5px 16px;
        border-radius: 999px;
        font-size: 0.73rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        transition: all 0.25s ease;
    }
    .step-pill-done {
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
    .step-pill-active {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: #fff;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3), 0 4px 12px rgba(99, 102, 241, 0.25);
    }
    .step-pill-todo {
        background: rgba(255,255,255,0.04);
        color: #64748b;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .step-dot {
        width: 4px;
        height: 4px;
        border-radius: 50%;
        background: #334155;
        display: inline-block;
    }

    /* ── Card-style containers (glassmorphism) ── */
    .card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .card:hover {
        border-color: rgba(99, 102, 241, 0.2);
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.08);
    }

    /* ── Flagged item highlight ── */
    .flagged-badge {
        display: inline-block;
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: #fff;
        font-size: 0.65rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 999px;
        margin-left: 8px;
        vertical-align: middle;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
    }

    /* ── Subtle divider ── */
    hr { border-color: rgba(255,255,255,0.06) !important; }

    /* ── Button tweaks ── */
    div[data-testid="stButton"] > button {
        border-radius: 12px;
        font-weight: 600;
        letter-spacing: 0.2px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    div[data-testid="stButton"] > button:active {
        transform: translateY(0);
    }

    /* ── Expander styling ── */
    details[data-testid="stExpander"] {
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 14px !important;
        background: rgba(255,255,255,0.02);
    }

    /* ── Input field polish ── */
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        border-radius: 10px !important;
    }

    /* ── Progress bar color ── */
    div[data-testid="stProgress"] > div > div {
        background: linear-gradient(90deg, #6366f1, #8b5cf6) !important;
    }

    /* ── Multiselect tags ── */
    span[data-baseweb="tag"] {
        background: rgba(99, 102, 241, 0.2) !important;
        border-color: rgba(99, 102, 241, 0.3) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state defaults ──────────────────────────────────────────────────────
from vlm import PROVIDER_PRESETS

DEFAULTS: dict = {
    "step": 1,
    "people": [],
    "items": [],
    "global_tax": 0.0,
    "assignments": {},
    "tip": 0.0,
    "result_people": [],
    "manual_mode": False,
    "vlm_provider": "Custom",
    "vlm_base_url": PROVIDER_PRESETS["Custom"]["base_url"],
    "vlm_model": PROVIDER_PRESETS["Custom"]["model"],
    "vlm_api_key": PROVIDER_PRESETS["Custom"]["api_key"],
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="app-header">'
    '<h1>🧾 BillSplit</h1>'
    '<p>Snap a receipt · tag who ordered what · settle up instantly.</p>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Step progress bar ──────────────────────────────────────────────────────────
STEP_LABELS = ["Names", "Upload", "Review", "Assign", "Tip", "Results"]
STEP_ICONS  = ["👥", "📷", "✏️", "🏷️", "💰", "📊"]


def _pill(label: str, idx: int, current: int) -> str:
    step_num = idx + 1
    if step_num < current:
        cls = "step-pill-done"
        icon = "✓ "
    elif step_num == current:
        cls = "step-pill-active"
        icon = f"{STEP_ICONS[idx]} "
    else:
        cls = "step-pill-todo"
        icon = ""
    return f'<span class="step-pill {cls}">{icon}{label}</span>'


_DOT = '<span class="step-dot"></span>'
pills = _DOT.join(_pill(lbl, i, st.session_state["step"]) for i, lbl in enumerate(STEP_LABELS))
st.markdown(f'<div class="step-bar">{pills}</div>', unsafe_allow_html=True)

# ── Router ─────────────────────────────────────────────────────────────────────
from ui import render_names, render_upload, render_review, render_assign, render_tip, render_results

step = st.session_state["step"]

if step == 1:
    render_names()
elif step == 2:
    render_upload()
elif step == 3:
    render_review()
elif step == 4:
    render_assign()
elif step == 5:
    render_tip()
elif step == 6:
    render_results()
else:
    st.error("Unknown step — resetting.")
    st.session_state.update(DEFAULTS)
    st.rerun()
