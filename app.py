"""
VoyageReady AI — Streamlit Web Application
A premium, dark-mode trip planning dashboard.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# ── Path setup ───────────────────────────────────────────────────────────────
VOYAGER_DIR = Path(__file__).parent
sys.path.insert(0, str(VOYAGER_DIR))
sys.path.insert(0, str(VOYAGER_DIR.parent / "llm_gatewayV2"))

from models import (
    SessionState, TripConfig, TripType,
)
import agent as ag

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VoyageReady AI",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS — premium dark glassmorphism theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Sora:wght@400;600;700&display=swap');

/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0a0f1e 0%, #0d1a2e 50%, #0a1528 100%) !important;
    font-family: 'Inter', sans-serif;
    color: #e2e8f0;
}
[data-testid="stSidebar"] {
    background: rgba(15, 23, 42, 0.95) !important;
    border-right: 1px solid rgba(99, 179, 237, 0.15);
}

/* ── Hero header ── */
.hero-header {
    background: linear-gradient(135deg, rgba(56,189,248,0.15), rgba(139,92,246,0.15));
    border: 1px solid rgba(99,179,237,0.25);
    border-radius: 20px;
    padding: 28px 36px;
    margin-bottom: 24px;
    backdrop-filter: blur(20px);
    text-align: center;
}
.hero-header h1 {
    font-family: 'Sora', sans-serif;
    font-size: 2.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, #38bdf8, #818cf8, #c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.hero-header p { color: #94a3b8; font-size: 1.05rem; margin-top: 6px; }

/* ── Cards ── */
.glass-card {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(99,179,237,0.18);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    backdrop-filter: blur(14px);
}
.metric-card {
    background: linear-gradient(135deg, rgba(56,189,248,0.08), rgba(139,92,246,0.08));
    border: 1px solid rgba(99,179,237,0.22);
    border-radius: 14px;
    padding: 16px 18px;
    text-align: center;
}
.metric-card .value {
    font-size: 1.6rem; font-weight: 700;
    background: linear-gradient(135deg, #38bdf8, #818cf8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.metric-card .label { font-size: 0.78rem; color: #64748b; margin-top: 2px; }

/* ── Chat ── */
.chat-bubble-user {
    background: linear-gradient(135deg, rgba(56,189,248,0.15), rgba(99,102,241,0.15));
    border: 1px solid rgba(56,189,248,0.25);
    border-radius: 18px 18px 4px 18px;
    padding: 14px 18px; margin: 8px 0; margin-left: 15%;
    font-size: 0.95rem; color: #e2e8f0;
}
.chat-bubble-ai {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(139,92,246,0.25);
    border-radius: 18px 18px 18px 4px;
    padding: 14px 18px; margin: 8px 0; margin-right: 5%;
    font-size: 0.95rem; color: #e2e8f0;
}
.chat-role { font-size: 0.75rem; font-weight: 600; margin-bottom: 6px; }
.chat-role-user { color: #38bdf8; }
.chat-role-ai   { color: #a78bfa; }

/* ── Milestone pills ── */
.ms-pill {
    display: inline-block; padding: 4px 12px; border-radius: 99px;
    font-size: 0.78rem; font-weight: 600; margin: 3px;
}
.ms-pending   { background: rgba(251,191,36,0.15);  border: 1px solid rgba(251,191,36,0.4);  color: #fbbf24; }
.ms-completed { background: rgba(52,211,153,0.15);  border: 1px solid rgba(52,211,153,0.4);  color: #34d399; }
.ms-overdue   { background: rgba(248,113,113,0.15); border: 1px solid rgba(248,113,113,0.4); color: #f87171; }

/* ── Section title ── */
.section-title {
    font-family: 'Sora', sans-serif;
    font-size: 1.05rem; font-weight: 600; color: #38bdf8;
    border-bottom: 1px solid rgba(56,189,248,0.2);
    padding-bottom: 6px; margin-bottom: 14px;
}

/* ── Buttons ── */
.stButton>button {
    background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    padding: 10px 22px !important; transition: opacity 0.2s;
}
.stButton>button:hover { opacity: 0.88 !important; }

/* Sidebar inputs */
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stNumberInput input,
[data-testid="stSidebar"] .stSelectbox select {
    background: rgba(15,23,42,0.9) !important;
    border-color: rgba(99,179,237,0.25) !important;
    color: #e2e8f0 !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session state helpers
# ─────────────────────────────────────────────────────────────────────────────

def _init_session() -> None:
    if "voyage_state" not in st.session_state:
        st.session_state.voyage_state = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "onboarded" not in st.session_state:
        st.session_state.onboarded = False


_init_session()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Trip onboarding form
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 12px 0 20px;">
        <span style="font-size:2.4rem;">✈️</span>
        <h2 style="font-family:'Sora',sans-serif; font-size:1.3rem;
                   background:linear-gradient(135deg,#38bdf8,#818cf8);
                   -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                   margin:4px 0 0;">VoyageReady AI</h2>
        <p style="color:#475569; font-size:0.78rem; margin:0;">Trip Planning Agent</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">🌍 Trip Setup</div>', unsafe_allow_html=True)

    destination    = st.text_input("Destination", value="Tokyo, Japan", key="dest_input")
    trip_type_raw  = st.selectbox("Trip Type", ["VACATION", "BUSINESS"], key="trip_type_input")
    total_days     = st.number_input("Total Days Until Departure", min_value=1, max_value=365, value=30, key="days_input")
    current_day    = st.number_input("Current Countdown Day", min_value=1, max_value=int(total_days), value=1, key="cday_input")
    total_budget   = st.number_input("Total Budget", min_value=100.0, value=5000.0, step=100.0, key="budget_input")
    currency_sym   = st.text_input("Currency Symbol", value="$", max_chars=3, key="cur_input")

    st.markdown("---")
    if st.button("🚀 Initialise Trip", use_container_width=True):
        try:
            cfg = TripConfig(
                destination=destination,
                trip_type=TripType(trip_type_raw),
                total_days=int(total_days),
                current_day=int(current_day),
                total_budget=float(total_budget),
                currency_symbol=currency_sym,
            )
            st.session_state.voyage_state = SessionState.initialise(cfg)
            st.session_state.chat_history = []
            st.session_state.onboarded    = True
            st.success("Trip initialised! Start chatting below.")
        except Exception as e:
            st.error(f"Configuration error: {e}")




# ─────────────────────────────────────────────────────────────────────────────
# Main content area
# ─────────────────────────────────────────────────────────────────────────────

# Hero header
st.markdown("""
<div class="hero-header">
    <h1>✈️ VoyageReady AI</h1>
    <p>Your Autonomous Trip Planning Agent · Itinerary · Bookings · Local Tips</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.onboarded:
    # ── Welcome screen ──
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="glass-card">
            <h3 style="color:#38bdf8;">🌍 Trip Planner</h3>
            <p style="color:#94a3b8; font-size:0.9rem;">
            Destination-aware itinerary planning.
            Personalised recommendations for business or vacation.
            </p>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="glass-card">
            <h3 style="color:#a78bfa;">📋 Booking Guide</h3>
            <p style="color:#94a3b8; font-size:0.9rem;">
            Flights, hotels, transit passes, eSIMs.
            Milestone tracking with automatic overdue alerts.
            </p>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="glass-card">
            <h3 style="color:#34d399;">🗺️ Local Insider</h3>
            <p style="color:#94a3b8; font-size:0.9rem;">
            Best neighbourhoods, transport hacks, safety tips,
            packing lists, and weather-aware advice.
            </p>
        </div>""", unsafe_allow_html=True)
    st.info("👈 Configure your trip in the sidebar and click **Initialise Trip** to begin.")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard — live metrics + trip overview
# ─────────────────────────────────────────────────────────────────────────────

state: SessionState = st.session_state.voyage_state
cfg = state.config


# Top metrics row
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f"""<div class="metric-card">
        <div class="value">Day {cfg.current_day}</div>
        <div class="label">of {cfg.total_days} total</div></div>""", unsafe_allow_html=True)
with m2:
    st.markdown(f"""<div class="metric-card">
        <div class="value">{cfg.days_remaining}d</div>
        <div class="label">until departure</div></div>""", unsafe_allow_html=True)
with m3:
    st.markdown(f"""<div class="metric-card">
        <div class="value">{cfg.currency_symbol}{cfg.total_budget:,.0f}</div>
        <div class="label">total budget</div></div>""", unsafe_allow_html=True)
with m4:
    st.markdown(f"""<div class="metric-card">
        <div class="value">{cfg.trip_type.value}</div>
        <div class="label">{cfg.destination}</div></div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Chat interface
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown('<div class="section-title">💬 Chat with VoyageReady AI</div>', unsafe_allow_html=True)

# Render history
chat_container = st.container()
with chat_container:
    for entry in st.session_state.chat_history:
        role, content = entry[0], entry[1]
        meta = entry[2] if len(entry) > 2 else None
        tool_calls = entry[3] if len(entry) > 3 else None
        if role == "user":
            st.markdown(f"""<div class="chat-bubble-user">
                <div class="chat-role chat-role-user">🧑 You</div>
            </div>""", unsafe_allow_html=True)
            st.markdown(content)
        else:
            # Show MCP tool calls before the AI response
            if tool_calls:
                for tc in tool_calls:
                    status_icon = "✅" if tc.get("status") == "success" else "❌"
                    args_str = ", ".join(f'{k}="{v}"' for k, v in tc.get("args", {}).items())
                    with st.expander(f"🔧 Tool call: `{tc['tool']}({args_str})` {status_icon}", expanded=False):
                        st.code(tc.get("result", ""), language=None)

            # AI response — render label as HTML, content as plain markdown
            st.markdown("""<div class="chat-bubble-ai">
                <div class="chat-role chat-role-ai">✈️ VoyageReady AI</div>
            </div>""", unsafe_allow_html=True)
            st.markdown(content)

            # Show LLM metadata bar
            if meta:
                thinking_icon = "🧠" if meta.reasoning_applied else "⚡"
                thinking_label = "Thinking Mode Active" if meta.reasoning_applied else "Direct Response"
                badges = []
                # Thinking badge
                if meta.reasoning_applied:
                    badges.append(f"🧠 **{thinking_label}**")
                else:
                    badges.append(f"⚡ {thinking_label}")
                # Tool badge
                if tool_calls:
                    badges.append(f"🔧 **{len(tool_calls)} tool(s)**")
                # Provider + stats
                badges.append(f"📡 {meta.provider}/{meta.model}")
                badges.append(f"📥 {meta.input_tokens} → 📤 {meta.output_tokens} tokens")
                badges.append(f"⏱️ {meta.latency_ms}ms")
                st.caption(" · ".join(badges))

                # Show thinking text in a collapsible expander
                if meta.thinking_text:
                    with st.expander("🧠 View LLM Thinking Process", expanded=False):
                        st.markdown(meta.thinking_text)

# Quick-start prompt chips
st.markdown("**Quick prompts:**")
qcols = st.columns(4)
quick_prompts = [
    "Plan my first 3 days",
    "What's the weather like?",
    "Best neighbourhoods to stay",
    "Create a packing list",
]
triggered_prompt = None
for i, (col, prompt) in enumerate(zip(qcols, quick_prompts)):
    with col:
        if st.button(prompt, key=f"qp_{i}", use_container_width=True):
            triggered_prompt = prompt

# Chat input
user_input = st.chat_input("Ask about your trip — itinerary, bookings, weather, packing…")
if triggered_prompt:
    user_input = triggered_prompt

if user_input:
    st.session_state.chat_history.append(("user", user_input, None, None))

    with st.spinner("VoyageReady AI is planning…"):
        try:
            response = ag.chat(st.session_state.voyage_state, user_input)
            ai_text = response.markdown_output or "_(No response generated)_"
            meta = response.llm_metadata
            tool_calls = response.tool_calls if response.tool_calls else None
            st.session_state.chat_history.append(("ai", ai_text, meta, tool_calls))
        except Exception as e:
            err_msg = f"⚠️ Error calling the AI gateway: `{e}`\n\n*Is llm_gatewayV2 running on port 8100?*"
            st.session_state.chat_history.append(("ai", err_msg, None, None))

    st.rerun()
