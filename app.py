"""FIRE – local Streamlit port of the Flutter investment tracker."""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import data_manager as dm

st.set_page_config(
    page_title="FIRE",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

_SESSION_PARAM = "s"   # URL query-param key for the session token
_SESSION_HOURS = 7


# ---------- Styling ----------

LIGHT_CSS_OVERRIDE = """
<style>
/* =============================================================
   LIGHT MODE — comprehensive overrides for Streamlit dark base
   ============================================================= */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stMain"] {
    background: #FFFFFF !important;
    color: #111827 !important;
}

/* Sidebar */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {
    background: #F8FAFC !important;
    border-right: 1px solid #E5E7EB !important;
}
section[data-testid="stSidebar"] *:not(.app-title):not(.badge):not(code) {
    color: #111827 !important;
}

/* Brand title keeps gradient */
.app-title {
    background: linear-gradient(90deg, #FF6B35, #FBBF24) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    color: transparent !important;
}
.app-subtitle {color: #6B7280 !important;}

/* All text defaults */
p, div, span, label, h1, h2, h3, h4, h5, h6, li, small {
    color: #111827;
}

/* FIRE custom cards */
.fire-card, .metric-card {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.metric-card .lbl {color: #6B7280 !important;}
.metric-card .val {color: #111827 !important;}
.fire-card h4 {color: #111827 !important;}
.fire-card .sub, .fire-card .val-row .label {color: #6B7280 !important;}
.fire-card .val-row .value {color: #111827 !important;}

.text-muted {color: #6B7280 !important;}
.text-green {color: #16A34A !important;}
.text-red   {color: #DC2626 !important;}

.section-hdr {
    color: #111827 !important;
    border-bottom: 1px solid #E5E7EB !important;
}

/* Badges — muted variants on light background */
.badge-equity    {background: #DBEAFE !important; color: #1D4ED8 !important;}
.badge-jewellery {background: #FEF3C7 !important; color: #B45309 !important;}
.badge-stocks    {background: #F3E8FF !important; color: #6D28D9 !important;}
.badge-profit    {background: #DCFCE7 !important; color: #15803D !important;}
.badge-loss      {background: #FEE2E2 !important; color: #B91C1C !important;}

/* Streamlit metrics */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px;
    padding: 10px 14px;
}
[data-testid="stMetricValue"] div {color: #111827 !important;}
[data-testid="stMetricLabel"] p {color: #6B7280 !important;}
[data-testid="stMetricDelta"] {color: #16A34A !important;}
[data-testid="stMetricDelta"][data-color="red"],
[data-testid="stMetricDelta"] svg[fill="red"] {color: #DC2626 !important;}

/* Markdown, captions */
.stMarkdown, .stText, .stCaption, .stMarkdown p {color: #111827 !important;}
.stCaption, small {color: #6B7280 !important;}

/* Bordered containers (our holding cards, breakdowns) */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stContainer"] [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
    background: #FFFFFF !important;
    border-color: #E5E7EB !important;
}
[data-testid="stVerticalBlockBorderWrapper"] > div {
    border-color: #E5E7EB !important;
}

/* Buttons */
.stButton > button,
button[kind="secondary"] {
    background: #FFFFFF !important;
    color: #111827 !important;
    border: 1px solid #D1D5DB !important;
}
.stButton > button:hover {
    border-color: #FF6B35 !important;
    color: #FF6B35 !important;
    background: #FFF7ED !important;
}
button[kind="primary"],
.stButton > button[kind="primary"] {
    background: #FF6B35 !important;
    color: #FFFFFF !important;
    border-color: #FF6B35 !important;
}
button[kind="primary"]:hover {
    background: #EA580C !important;
    color: #FFFFFF !important;
}
.stButton > button:disabled {
    background: #F3F4F6 !important;
    color: #9CA3AF !important;
    border-color: #E5E7EB !important;
}

/* Inputs */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
.stDateInput input,
[data-baseweb="input"] input,
[data-baseweb="base-input"] input,
[data-baseweb="textarea"] textarea {
    background: #FFFFFF !important;
    color: #111827 !important;
    border: 1px solid #D1D5DB !important;
    caret-color: #111827 !important;
}
[data-baseweb="input"] {background: #FFFFFF !important;}
.stNumberInput button {
    background: #F3F4F6 !important;
    color: #111827 !important;
    border-color: #D1D5DB !important;
}

/* Selectbox, Radio, Checkbox */
.stSelectbox > div > div,
[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    color: #111827 !important;
    border-color: #D1D5DB !important;
}
[data-baseweb="popover"] {background: #FFFFFF !important; color: #111827 !important;}
[data-baseweb="menu"] {background: #FFFFFF !important;}
[data-baseweb="menu"] li {color: #111827 !important;}
.stRadio label {color: #111827 !important;}
[role="radiogroup"] label {color: #111827 !important;}

/* Dataframe + table */
.stDataFrame, .stTable {background: #FFFFFF !important;}
.stDataFrame [data-testid="stDataFrameResizable"] {background: #FFFFFF !important;}
.stDataFrame th, .stDataFrame td {color: #111827 !important;}

/* Dialog */
[role="dialog"] {
    background: #FFFFFF !important;
    color: #111827 !important;
}
[role="dialog"] * {color: #111827;}

/* Expander */
.streamlit-expanderHeader, [data-testid="stExpander"] summary {
    background: #F9FAFB !important;
    color: #111827 !important;
}
[data-testid="stExpander"] details {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
}

/* Divider */
hr, [data-testid="stDivider"] {border-color: #E5E7EB !important;}

/* Code */
code {
    background: #FEF3C7 !important;
    color: #B45309 !important;
}
pre code {
    background: #F9FAFB !important;
    color: #111827 !important;
}
pre {
    background: #F9FAFB !important;
    border: 1px solid #E5E7EB !important;
}

/* Alerts */
[data-testid="stNotificationContentInfo"],
[data-testid="stAlert"] {color: #111827 !important;}
[data-testid="stAlert"][role="alert"] {background: #FFFBEB !important;}

/* Toast */
[data-testid="stToast"] {
    background: #111827 !important;
    color: #FFFFFF !important;
}

/* Tabs */
button[data-baseweb="tab"] {color: #6B7280 !important;}
button[data-baseweb="tab"][aria-selected="true"] {color: #FF6B35 !important;}

/* Spinner */
[data-testid="stSpinner"] {color: #FF6B35 !important;}

/* History dialog — light mode */
.history-hdr {
    background: #FFFFFF !important;
    border-color: #E5E7EB !important;
}
.history-hdr .meta {color: #6B7280 !important;}
.bubble.buy  {background: #F0FDF4 !important; border-color: #BBF7D0 !important;}
.bubble.buy  .kind {color: #15803D !important;}
.bubble.sell {background: #FEF2F2 !important; border-color: #FECACA !important;}
.bubble.sell .kind {color: #B91C1C !important;}
.bubble .time, .bubble .sub, .bubble .main .total {color: #6B7280 !important;}
</style>
"""

CUSTOM_CSS = """
<style>
    /* Tighten the main container */
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1300px;}

    /* Light chrome cleanup — leave header + sidebar toggles fully intact */
    footer {visibility: hidden;}
    [data-testid="stHeader"] {background: transparent;}

    /* Card */
    .fire-card {
        background: linear-gradient(145deg, #1A1F2E 0%, #161B27 100%);
        border: 1px solid #2A3040;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .fire-card h4 {margin: 0 0 4px 0; font-size: 1.05rem; color: #FAFAFA;}
    .fire-card .sub {color: #8B93A7; font-size: 0.82rem;}
    .fire-card .val-row {display: flex; justify-content: space-between; margin-top: 8px;}
    .fire-card .val-row .label {color: #8B93A7; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.5px;}
    .fire-card .val-row .value {color: #FAFAFA; font-size: 0.95rem; font-weight: 600;}

    /* Badges */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 10px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .badge-equity   {background: rgba(59, 130, 246, 0.15); color: #60A5FA;}
    .badge-jewellery{background: rgba(251, 191, 36, 0.15); color: #FBBF24;}
    .badge-stocks   {background: rgba(168, 85, 247, 0.15); color: #C084FC;}
    .badge-profit   {background: rgba(34, 197, 94,  0.15); color: #4ADE80;}
    .badge-loss     {background: rgba(239, 68, 68,  0.15); color: #F87171;}

    /* Color helpers */
    .text-green {color: #4ADE80; font-weight: 600;}
    .text-red   {color: #F87171; font-weight: 600;}
    .text-muted {color: #8B93A7;}

    /* Metric card */
    .metric-card {
        background: linear-gradient(145deg, #1A1F2E 0%, #161B27 100%);
        border: 1px solid #2A3040;
        border-radius: 12px;
        padding: 14px 18px;
        text-align: left;
        min-height: 96px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .metric-card .lbl {color: #8B93A7; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.8px; margin: 0;}
    .metric-card .val-row {display: flex; align-items: baseline; gap: 10px; margin-top: 4px;}
    .metric-card .val {color: #FAFAFA; font-size: 1.6rem; font-weight: 700;}
    .metric-card .delta {font-size: 0.9rem; font-weight: 600;}

    /* App title */
    .app-title {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(90deg, #FF6B35, #FBBF24);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .app-subtitle {color: #8B93A7; margin-top: 0; font-size: 0.85rem;}

    /* Section header */
    .section-hdr {
        font-size: 1.15rem;
        font-weight: 600;
        color: #FAFAFA;
        margin: 8px 0 12px 0;
        padding-bottom: 6px;
        border-bottom: 1px solid #2A3040;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {background: #12161F;}
    section[data-testid="stSidebar"] .stRadio label {font-size: 0.95rem;}

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        border: 1px solid #2A3040;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        border-color: #FF6B35;
        color: #FF6B35;
    }

    /* Tabs */
    button[data-baseweb="tab"] {font-weight: 500;}

    /* Allocation cards — invisible button overlay so the visual card is clickable */
    [data-testid="stElementContainer"]:has(.alloc-card) + [data-testid="stElementContainer"] {
        margin-top: -135px !important;
        height: 135px !important;
        z-index: 10;
        position: relative;
    }
    [data-testid="stElementContainer"]:has(.alloc-card) + [data-testid="stElementContainer"] [data-testid="stButton"],
    [data-testid="stElementContainer"]:has(.alloc-card) + [data-testid="stElementContainer"] [data-testid="stButton"] > button {
        height: 135px !important;
        width: 100% !important;
        background: transparent !important;
        border: none !important;
        opacity: 0 !important;
        cursor: pointer !important;
        padding: 0 !important;
        box-shadow: none !important;
    }
    [data-testid="stElementContainer"]:has(.alloc-card) + [data-testid="stElementContainer"] [data-testid="stButton"] > button:hover,
    [data-testid="stElementContainer"]:has(.alloc-card) + [data-testid="stElementContainer"] [data-testid="stButton"] > button:focus {
        background: transparent !important;
        outline: none !important;
    }
    .alloc-card {cursor: pointer;}
    .alloc-card:hover {filter: brightness(1.08);}

    /* History dialog — chat-bubble style timeline */
    .history-hdr {
        background: linear-gradient(145deg, #1A1F2E 0%, #161B27 100%);
        border: 1px solid #2A3040;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .history-hdr .name {font-size: 1.25rem; font-weight: 700;}
    .history-hdr .meta {color: #8B93A7; font-size: 0.82rem; margin-top: 4px;}

    .bubble {
        border-radius: 14px;
        padding: 12px 16px;
        margin: 4px 0;
        border: 1px solid;
    }
    .bubble .row1 {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 6px;
    }
    .bubble .kind {font-weight: 700; font-size: 0.92rem; letter-spacing: 0.3px;}
    .bubble .time {font-size: 0.72rem; color: #8B93A7;}
    .bubble .main {font-size: 1.02rem; font-weight: 600;}
    .bubble .main .total {color: #8B93A7; font-weight: 500;}
    .bubble .sub {font-size: 0.82rem; margin-top: 4px; color: #8B93A7;}

    .bubble.buy {
        background: rgba(34, 197, 94, 0.10);
        border-color: rgba(34, 197, 94, 0.30);
        border-bottom-left-radius: 4px;
    }
    .bubble.buy .kind {color: #4ADE80;}

    .bubble.sell {
        background: rgba(239, 68, 68, 0.10);
        border-color: rgba(239, 68, 68, 0.30);
        border-bottom-right-radius: 4px;
    }
    .bubble.sell .kind {color: #F87171;}

</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "theme" not in st.session_state:
    st.session_state.theme = "🌙 Dark"
if st.session_state.theme == "☀️ Light":
    st.markdown(LIGHT_CSS_OVERRIDE, unsafe_allow_html=True)


# ---------- Auth gate ----------

def _make_session_token(password_hash: str) -> str:
    """Create a signed token that expires in SESSION_HOURS."""
    expiry = int(time.time()) + _SESSION_HOURS * 3600
    sig = hmac.new(password_hash.encode(), str(expiry).encode(), hashlib.sha256).hexdigest()
    return f"{expiry}:{sig}"


def _verify_session_token(token: str, password_hash: str) -> bool:
    """Return True if token is valid and not expired."""
    try:
        expiry_str, sig = token.split(":", 1)
        if time.time() > int(expiry_str):
            return False
        expected = hmac.new(password_hash.encode(), expiry_str.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def _set_session_token(password_hash: str) -> None:
    st.query_params[_SESSION_PARAM] = _make_session_token(password_hash)


def _auth_gate() -> None:
    # Already authenticated this session — fast path
    if st.session_state.get("authenticated"):
        return

    config = dm.load_config()
    password_hash = config.get("passwordHash", "")

    # Session token lives in the URL query param — available instantly on every
    # render (no browser round-trip like cookies), so refresh works reliably.
    if password_hash:
        token = st.query_params.get(_SESSION_PARAM, "")
        if token and _verify_session_token(token, password_hash):
            st.session_state.authenticated = True
            return

    # First-time setup — no password set yet
    if not password_hash:
        st.markdown("## 🔥 FIRE — First-time Setup")
        st.markdown("Create a password to protect your data.")
        pwd = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        if st.button("Set password", type="primary"):
            if not pwd:
                st.error("Password cannot be empty.")
            elif pwd != confirm:
                st.error("Passwords do not match.")
            else:
                h = hashlib.sha256(pwd.encode()).hexdigest()
                dm.save_config({"passwordHash": h})
                st.session_state.authenticated = True
                _set_session_token(h)
                st.rerun()
        st.stop()

    # Login screen
    st.markdown("## 🔥 FIRE — Login")
    pwd = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        h = hashlib.sha256(pwd.encode()).hexdigest()
        if h == password_hash:
            st.session_state.authenticated = True
            _set_session_token(h)
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


_auth_gate()


# ---------- Session bootstrap ----------

def _fetch_and_suggest(user: dm.UserSettings) -> tuple[pd.DataFrame, list[dict], str | None]:
    err = None
    try:
        etfs = dm.fetch_etfs()
    except Exception as exc:
        etfs = dm.load_etfs_cache()
        err = f"Live fetch failed, using cached data: {exc}"
    holdings = dm.load_holdings()
    suggestions = dm.generate_suggestions(user, etfs, holdings)
    return etfs, suggestions, err


def ensure_state() -> None:
    if "user" not in st.session_state:
        st.session_state.user = dm.load_user()
    if "backfilled" not in st.session_state:
        added = dm.backfill_buys_from_holdings()
        st.session_state.backfilled = True
        if added:
            st.toast(f"ℹ️ Added {added} legacy holding(s) to the buy log so you can reverse them.")
    if "etfs" not in st.session_state:
        with st.spinner("Fetching latest ETF data..."):
            etfs, suggestions, err = _fetch_and_suggest(st.session_state.user)
        st.session_state.etfs = etfs
        st.session_state.suggestions = suggestions
        if err:
            st.warning(err)


def refresh_etfs() -> None:
    with st.spinner("Refreshing..."):
        etfs, suggestions, err = _fetch_and_suggest(st.session_state.user)
    st.session_state.etfs = etfs
    st.session_state.suggestions = suggestions
    if err:
        st.error(err)
    else:
        st.success(f"Fetched {len(etfs)} ETFs, {len(suggestions)} suggestions.")


ensure_state()

user: dm.UserSettings = st.session_state.user
etfs: pd.DataFrame = st.session_state.etfs


# ---------- Helpers ----------

def fmt_money(x: float, decimals: int = 0) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}₹{abs(x):,.{decimals}f}"


def fmt_pct(x: float) -> str:
    return f"{x:+.2f}%"


def pnl_class(x: float) -> str:
    return "text-green" if x >= 0 else "text-red"


def badge(text: str, kind: str) -> str:
    kind_map = {"Equity": "equity", "Jewellery": "jewellery", "Stocks": "stocks"}
    css = kind_map.get(text, kind)
    return f'<span class="badge badge-{css}">{text}</span>'


def metric_card(label: str, value: str, delta: str | None = None, delta_class: str = "") -> str:
    delta_html = f'<span class="delta {delta_class}">{delta}</span>' if delta else ""
    return (
        '<div class="metric-card">'
        f'<p class="lbl">{label}</p>'
        f'<div class="val-row"><span class="val">{value}</span>{delta_html}</div>'
        '</div>'
    )


def section(title: str) -> None:
    st.markdown(f'<div class="section-hdr">{title}</div>', unsafe_allow_html=True)


def _format_last_fetch() -> str:
    ts = dm.last_fetch_time()
    if ts is None:
        return "never"
    delta = datetime.now() - ts
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


# ---------- Sidebar ----------

with st.sidebar:
    st.markdown('<p class="app-title">🔥 FIRE</p>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Financial Independence Tracker</p>', unsafe_allow_html=True)
    st.divider()

    page = st.radio(
        "Navigate",
        ["🏠 Home", "💡 Suggestions", "📋 Listed ETFs", "🔄 Transactions", "📜 Sell History", "📊 Reports", "⚙️ Settings", "ℹ️ Info"],
        label_visibility="collapsed",
    )

    st.divider()

    if st.button("🔄 Refresh ETFs", use_container_width=True):
        refresh_etfs()

    st.markdown(
        f'<div style="margin-top:8px;color:#8B93A7;font-size:0.78rem;">'
        f'Last fetched <b style="color:#FAFAFA;">{_format_last_fetch()}</b><br>'
        f'{len(etfs)} ETFs cached'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.divider()
    section("Quick stats")
    st.markdown(metric_card("Investment", fmt_money(user.investment)), unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown(metric_card("Remaining", fmt_money(user.remainingAmount)), unsafe_allow_html=True)


# ---------- Pages ----------

def page_home() -> None:
    st.markdown('<h2 style="margin-top:0">🏠 Portfolio Overview</h2>', unsafe_allow_html=True)

    holdings = dm.load_holdings()

    # Empty state — user has no holdings yet
    if holdings.empty:
        with st.container(border=True):
            st.markdown(
                """
                ### 👋 Welcome to FIRE

                You don't have any holdings yet. Here's how to get started:

                1. Open **⚙️ Settings** → set your total investment
                2. Go to **💡 Suggestions** → pick an ETF to buy
                3. After executing the trade in Kotak, confirm it here
                4. Your portfolio will appear on this page with live P/L tracking
                """
            )
            cta = st.columns(3)
            if cta[0].button("💡 Go to Suggestions", use_container_width=True, type="primary"):
                st.toast("Click 💡 Suggestions in the sidebar", icon="👉")
            if cta[1].button("⚙️ Open Settings", use_container_width=True):
                st.toast("Click ⚙️ Settings in the sidebar", icon="👉")
            if cta[2].button("ℹ️ Read docs", use_container_width=True):
                st.toast("Click ℹ️ Info in the sidebar", icon="👉")
        _render_recent_activity()
        return

    groups = dm.classify_holdings(holdings, etfs, user)

    cost_basis = dm.holdings_total_cost(holdings)
    current_value = dm.holdings_current_value(holdings, etfs)
    pnl = current_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Holdings", f"{len(holdings)}"), unsafe_allow_html=True)
    c2.markdown(metric_card("Cost Basis", fmt_money(cost_basis)), unsafe_allow_html=True)
    c3.markdown(metric_card("Current Value", fmt_money(current_value)), unsafe_allow_html=True)
    c4.markdown(
        metric_card(
            "Unrealized P/L",
            fmt_money(pnl),
            delta=fmt_pct(pnl_pct) if cost_basis else None,
            delta_class=pnl_class(pnl),
        ),
        unsafe_allow_html=True,
    )

    if len(holdings) > 20:
        st.warning(f"⚠️ You hold {len(holdings)} ETFs — consider consolidating (>20).")

    # Allocation by type — clickable cards via invisible button overlay
    alloc = dm.holdings_by_type(holdings, etfs)
    if not alloc.empty and current_value > 0:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        section("Allocation by type")

        # selection state — list of selected types
        if "alloc_filter" not in st.session_state:
            st.session_state["alloc_filter"] = []
        active = list(st.session_state["alloc_filter"])

        type_colors = {"Equity": "b-equity", "Jewellery": "b-jewellery", "Stocks": "b-stocks"}
        cols = st.columns(len(alloc))
        for i, (_, r) in enumerate(alloc.iterrows()):
            t = str(r["etfType"])
            pct = r["currentValue"] / current_value * 100 if current_value > 0 else 0
            cls = type_colors.get(t, "b-equity")
            is_sel = t in active
            border = "2px solid #FF6B35" if is_sel else "1px solid #2A3040"
            shadow = "box-shadow:0 0 0 3px rgba(255,107,53,.15);" if is_sel else ""

            card_html = (
                f'<div class="alloc-card" data-type="{t}" style="'
                f'background:linear-gradient(145deg,#1A1F2E,#161B27);'
                f'border:{border};border-radius:12px;padding:14px 18px;{shadow}'
                f'transition:all .12s">'
                f'<div><span class="badge {cls}">{t}</span>'
                f'<span class="text-muted" style="font-size:0.75rem;margin-left:6px">{int(r["count"])} holding(s)</span></div>'
                f'<div style="font-size:1.3rem;font-weight:700;margin-top:6px">{fmt_money(r["currentValue"])}</div>'
                f'<div class="text-muted" style="font-size:0.85rem;margin-top:2px">'
                f'{pct:.1f}% of portfolio · cost {fmt_money(r["cost"])}</div>'
                f'<div class="{pnl_class(r["pnl"])}" style="font-size:0.88rem;margin-top:4px">'
                f'{fmt_money(r["pnl"])} ({fmt_pct(r["pnlPct"])})</div>'
                f'</div>'
            )
            with cols[i]:
                st.markdown(card_html, unsafe_allow_html=True)
                if st.button(" ", key=f"alloc_btn_{t}", use_container_width=True):
                    if is_sel:
                        active.remove(t)
                    else:
                        active.append(t)
                    st.session_state["alloc_filter"] = active
                    st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    selected = st.session_state.get("alloc_filter") or []

    def _filtered_count(group_df: pd.DataFrame) -> int:
        if group_df.empty:
            return 0
        if selected:
            return int(group_df["etfType"].isin(selected).sum())
        return int(len(group_df))

    sell_label  = f"🟢 Sell candidates ({_filtered_count(groups['sell'])})"
    buy_label   = f"🔴 Buy-more candidates ({_filtered_count(groups['buy'])})"
    other_label = f"⚪ Others ({_filtered_count(groups['others'])})"

    selected = st.radio(
        "Filter",
        [sell_label, buy_label, other_label],
        horizontal=True,
        label_visibility="collapsed",
        key="home_filter",
    )

    if selected == sell_label:
        st.caption(f"ETFs where CMP > avg × (1 + {user.sellProfitTarget:.2f}%) — in profit zone, sorted by |P/L %|")
        _render_holding_cards(groups["sell"], kind="sell")
    elif selected == buy_label:
        st.caption(f"ETFs where CMP < avg × (1 − {user.buyInDipThreshold:.2f}%) — in dip, sorted by |P/L %|")
        _render_holding_cards(groups["buy"], kind="buy")
    else:
        st.caption("Between thresholds — sorted by |P/L %|")
        _render_holding_cards(groups["others"], kind="others")

    _render_recent_activity()


def _render_recent_activity() -> None:
    """Show the last 3 buys + sells combined, newest first."""
    buys = dm.load_buys()
    sells = dm.load_sells()
    if buys.empty and sells.empty:
        return
    events = []
    for _, r in buys.iterrows():
        events.append({
            "when": str(r["buyDate"]),
            "kind": "Buy",
            "icon": "🛒",
            "name": str(r["etfName"]),
            "qty": int(r["quantity"]),
            "price": float(r["price"]),
            "color": "text-green",
        })
    for _, r in sells.iterrows():
        events.append({
            "when": str(r["sellDate"]),
            "kind": "Sell",
            "icon": "💰",
            "name": str(r["etfName"]),
            "qty": int(r["quantity"]),
            "price": float(r["sellPrice"]),
            "color": "text-red",
        })
    events.sort(key=lambda e: e["when"], reverse=True)
    events = events[:5]

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section("Recent activity")
    for e in events:
        when_short = e["when"][:16].replace("T", " ")
        with st.container(border=True):
            cc = st.columns([0.5, 2.5, 1, 1, 1.2])
            cc[0].markdown(f"<div style='font-size:1.2rem'>{e['icon']}</div>", unsafe_allow_html=True)
            cc[1].markdown(f"**{e['kind']}** — {e['name']}")
            cc[2].markdown(f"<span class='text-muted' style='font-size:0.75rem'>QTY</span> {e['qty']}", unsafe_allow_html=True)
            cc[3].markdown(f"<span class='text-muted' style='font-size:0.75rem'>@</span> ₹{e['price']:,.2f}", unsafe_allow_html=True)
            cc[4].markdown(f"<span class='text-muted' style='font-size:0.78rem'>{when_short}</span>", unsafe_allow_html=True)

    st.caption("Go to **🔄 Transactions** to reverse any of these.")


def _render_holding_cards(df: pd.DataFrame, kind: str) -> None:
    if df.empty:
        st.info("Nothing here.")
        return

    selected = st.session_state.get("alloc_filter") or []
    if selected:
        df = df[df["etfType"].isin(selected)]
        if df.empty:
            st.info(f"No {' / '.join(selected)} holdings here.")
            return

    df = df.copy()
    avg = df["averagePrice"].astype(float)
    cmp_f = df["cmp"].astype(float)
    has_cmp = cmp_f > 0
    df["sellTarget"] = avg * (1 + user.sellProfitTarget / 100)
    df["buyTarget"] = avg * (1 - user.buyInDipThreshold / 100)

    if kind == "sell":
        df["sortPct"] = ((cmp_f - df["sellTarget"]) / df["sellTarget"] * 100).where(has_cmp)
    elif kind == "buy":
        df["sortPct"] = ((df["buyTarget"] - cmp_f) / df["buyTarget"] * 100).where(has_cmp)
    else:
        df["toSellPct"] = ((df["sellTarget"] - cmp_f) / cmp_f * 100).where(has_cmp)
        df["toBuyPct"] = ((cmp_f - df["buyTarget"]) / cmp_f * 100).where(has_cmp)

    df["absPnlPct"] = df["pnlPct"].astype(float).abs().where(has_cmp)
    df = df.sort_values("absPnlPct", ascending=False, na_position="last")

    for _, row in df.iterrows():
        pnl = float(row["pnl"])
        pnl_pct_val = float(row["pnlPct"])
        cls = pnl_class(pnl)

        with st.container(border=True):
            top = st.columns([2.4, 0.9, 0.9, 0.7, 1.7, 1.4])
            top[0].markdown(
                f'**{row["etfName"]}** &nbsp; {badge(str(row["etfType"]), "equity")}',
                unsafe_allow_html=True,
            )
            top[1].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">AVG</div>'
                f'<div>₹{float(row["averagePrice"]):,.2f}</div>',
                unsafe_allow_html=True,
            )
            top[2].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">CMP</div>'
                f'<div>₹{float(row["cmp"]):,.2f}</div>',
                unsafe_allow_html=True,
            )
            top[3].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">QTY</div>'
                f'<div>{int(row["totalQuantity"])}</div>',
                unsafe_allow_html=True,
            )

            if kind == "sell":
                gap = row.get("sortPct")
                gap_str = (
                    f'<span class="text-green">+{float(gap):.2f}% above</span>'
                    if pd.notna(gap) else '<span class="text-muted">—</span>'
                )
                top[4].markdown(
                    f'<div class="text-muted" style="font-size:0.75rem">SELL TGT</div>'
                    f'<div>₹{float(row["sellTarget"]):,.2f}</div>'
                    f'<div style="font-size:0.78rem">{gap_str}</div>',
                    unsafe_allow_html=True,
                )
            elif kind == "buy":
                gap = row.get("sortPct")
                gap_str = (
                    f'<span class="text-red">-{float(gap):.2f}% below</span>'
                    if pd.notna(gap) else '<span class="text-muted">—</span>'
                )
                top[4].markdown(
                    f'<div class="text-muted" style="font-size:0.75rem">BUY-MORE TGT</div>'
                    f'<div>₹{float(row["buyTarget"]):,.2f}</div>'
                    f'<div style="font-size:0.78rem">{gap_str}</div>',
                    unsafe_allow_html=True,
                )
            else:
                up = row.get("toSellPct")
                down = row.get("toBuyPct")
                up_str = f'+{float(up):.2f}%' if pd.notna(up) else '—'
                down_str = f'-{float(down):.2f}%' if pd.notna(down) else '—'
                top[4].markdown(
                    f'<div style="font-size:0.78rem"><span class="text-muted">SELL @</span> '
                    f'₹{float(row["sellTarget"]):,.2f} '
                    f'<span class="text-green">({up_str})</span></div>'
                    f'<div style="font-size:0.78rem;margin-top:2px"><span class="text-muted">BUY @</span> '
                    f'₹{float(row["buyTarget"]):,.2f} '
                    f'<span class="text-red">({down_str})</span></div>',
                    unsafe_allow_html=True,
                )

            top[5].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">P/L</div>'
                f'<div class="{cls}">{fmt_money(pnl)} ({fmt_pct(pnl_pct_val)})</div>',
                unsafe_allow_html=True,
            )

            # Direct action buttons — Sell + Buy more + History. To undo a
            # mistake buy, go to 🔄 Transactions → Reverse.
            btn_cols = st.columns(3)
            show_sell = btn_cols[0].button(
                "💰 Sell", key=f"bsell_{row['id']}", use_container_width=True,
            )
            show_buy = btn_cols[1].button(
                "🛒 Buy more", key=f"bbuy_{row['id']}", use_container_width=True,
            )
            show_hist = btn_cols[2].button(
                "📜 History", key=f"bhist_{row['id']}", use_container_width=True,
            )

            active_key = f"active_{row['id']}"
            if show_sell:
                st.session_state[active_key] = "sell"
            elif show_buy:
                st.session_state[active_key] = "buy"

            if show_hist:
                _history_dialog(str(row["etfName"]), str(row["etfType"]))

            active = st.session_state.get(active_key)
            if active == "sell":
                _sell_form(row)
            elif active == "buy":
                _buy_more_form(row)


def _delete_holding_form(row: pd.Series) -> None:
    if st.button(
        f"🗑️ Delete this holding",
        key=f"del_{row['id']}",
        use_container_width=True,
        type="primary",
    ):
        _delete_dialog(
            holding_id=str(row["id"]),
            name=str(row["etfName"]),
            etf_type=str(row["etfType"]),
            avg_price=float(row["averagePrice"]),
            qty=int(row["totalQuantity"]),
        )


def _sell_form(row: pd.Series) -> None:
    c1, c2 = st.columns(2)
    default_price = float(row["cmp"]) if row["cmp"] else float(row["averagePrice"])
    sell_price = c1.number_input(
        "Sell price",
        min_value=0.0,
        value=default_price,
        step=0.05,
        key=f"sp_{row['id']}",
    )
    max_qty = int(row["totalQuantity"])
    qty = c2.number_input(
        "Quantity", min_value=1, max_value=max_qty, value=max_qty, step=1,
        key=f"sq_{row['id']}",
    )

    gross = sell_price * qty
    ch = dm.compute_kotak_charges(gross, str(row["etfType"]), side="sell")
    dividend = gross * user.dividendPercentage / 100
    net = gross - ch["brokerage"] - ch["tax"] - dividend
    realized = (sell_price - float(row["averagePrice"])) * qty - ch["brokerage"] - ch["tax"] - dividend

    _render_charge_breakdown(gross, ch, side="sell", dividend=dividend, net=net, realized=realized)

    if st.button("✅ Review & Sell", key=f"sbtn_{row['id']}", use_container_width=True, type="primary"):
        _sell_dialog(
            holding_id=str(row["id"]),
            name=str(row["etfName"]),
            etf_type=str(row["etfType"]),
            sell_price=float(sell_price),
            qty=int(qty),
            avg_price=float(row["averagePrice"]),
        )


@st.dialog("Confirm Buy")
def _buy_dialog(name: str, etf_type: str, price: float, qty: int) -> None:
    value = price * qty
    ch = dm.compute_kotak_charges(value, etf_type, side="buy")
    total_cost = value + ch["total"]
    user_obj = st.session_state.user
    remaining_after = user_obj.remainingAmount - total_cost

    st.markdown(f"**🛒 Buy {qty} × {name}**  \n<small>{etf_type} · ₹{price:,.2f} per unit</small>",
                unsafe_allow_html=True)

    s = st.columns(3)
    s[0].metric("Trade value", fmt_money(value))
    s[1].metric("+ Charges", fmt_money(ch["total"], 2))
    s[2].metric("Total cost", fmt_money(total_cost))

    st.caption(f"Remaining after: **{fmt_money(remaining_after)}**")
    if remaining_after < 0:
        st.warning("⚠️ Not enough remaining amount. You can still proceed but cash goes negative.")

    c1, c2 = st.columns(2)
    if c1.button("✅ Yes, buy it", type="primary", use_container_width=True, key="dlg_buy_yes"):
        _guard = f"_op_done_buy_{name}_{price}_{qty}"
        if st.session_state.get(_guard):
            return  # already processing — drop the duplicate click
        st.session_state[_guard] = True
        try:
            updated_user, _, _ = dm.buy_etf(
                user=st.session_state.user,
                etf_name=name, etf_type=etf_type,
                price=price, quantity=qty,
            )
            st.session_state.user = updated_user
            st.session_state.suggestions = dm.generate_suggestions(
                updated_user, etfs, dm.load_holdings()
            )
            st.toast(f"🛒 Bought {qty} × {name} — total {fmt_money(total_cost)}", icon="✅")
            st.rerun()
        except Exception as exc:
            del st.session_state[_guard]
            st.error(str(exc))
    if c2.button("❌ Cancel", use_container_width=True, key="dlg_buy_no"):
        st.rerun()


@st.dialog("Confirm Sell")
def _sell_dialog(holding_id: str, name: str, etf_type: str, sell_price: float, qty: int, avg_price: float) -> None:
    gross = sell_price * qty
    ch = dm.compute_kotak_charges(gross, etf_type, side="sell")
    dividend = gross * user.dividendPercentage / 100
    total_fees = ch["brokerage"] + ch["tax"] + dividend
    net = gross - total_fees
    realized = (sell_price - avg_price) * qty - total_fees

    st.markdown(
        f"**💰 Sell {qty} × {name}**  \n<small>{etf_type} · Sell ₹{sell_price:,.2f} · Avg buy ₹{avg_price:,.2f}</small>",
        unsafe_allow_html=True,
    )

    s = st.columns(3)
    s[0].metric("Gross", fmt_money(gross))
    s[1].metric("− Fees + Dividend", fmt_money(total_fees, 2))
    s[2].metric("Net proceeds", fmt_money(net))

    st.metric(
        "Realized P/L",
        fmt_money(realized),
        delta=("profit" if realized >= 0 else "loss"),
        delta_color=("normal" if realized >= 0 else "inverse"),
    )

    c1, c2 = st.columns(2)
    if c1.button("✅ Yes, sell it", type="primary", use_container_width=True, key="dlg_sell_yes"):
        _guard = f"_op_done_sell_{holding_id}_{sell_price}_{qty}"
        if st.session_state.get(_guard):
            return
        st.session_state[_guard] = True
        try:
            updated_user, _, _, _ = dm.sell_holding(
                user=st.session_state.user,
                holding_id=holding_id,
                sell_price=sell_price, quantity=qty,
                dividend=float(dividend),
            )
            st.session_state.user = updated_user
            st.session_state.suggestions = dm.generate_suggestions(
                updated_user, etfs, dm.load_holdings()
            )
            st.toast(f"💰 Sold {qty} × {name} — net {fmt_money(net)}", icon="✅")
            st.rerun()
        except Exception as exc:
            del st.session_state[_guard]
            st.error(str(exc))
    if c2.button("❌ Cancel", use_container_width=True, key="dlg_sell_no"):
        st.rerun()


@st.dialog("Delete Holding")
def _delete_dialog(holding_id: str, name: str, etf_type: str, avg_price: float, qty: int) -> None:
    value = avg_price * qty
    est_charges = dm.compute_kotak_charges(value, etf_type, side="buy")
    refund = value + est_charges["total"]

    st.markdown(f"**🗑️ Delete {qty} × {name}?**", unsafe_allow_html=True)
    st.warning("Use only if bought by mistake (never placed in Kotak).")

    s = st.columns(2)
    s[0].metric("Cost + charges", fmt_money(value) + f" + {fmt_money(est_charges['total'], 2)}")
    s[1].metric("Total refund", fmt_money(refund))

    c1, c2 = st.columns(2)
    if c1.button("🗑️ Yes, delete it", type="primary", use_container_width=True, key="dlg_del_yes"):
        _guard = f"_op_done_del_{holding_id}"
        if st.session_state.get(_guard):
            return
        st.session_state[_guard] = True
        try:
            updated_user, _ = dm.delete_holding(st.session_state.user, holding_id)
            st.session_state.user = updated_user
            st.session_state.suggestions = dm.generate_suggestions(
                updated_user, etfs, dm.load_holdings()
            )
            st.toast(f"🗑️ Deleted {name} — refunded {fmt_money(refund)}", icon="✅")
            st.rerun()
        except Exception as exc:
            del st.session_state[_guard]
            st.error(str(exc))
    if c2.button("❌ Cancel", use_container_width=True, key="dlg_del_no"):
        st.rerun()


@st.dialog("Reset All Data")
def _reset_all_dialog() -> None:
    u = st.session_state.user
    st.markdown("**🔥 Reset all transactions?**")
    st.error(
        "This wipes **all** holdings, buys, and sells. Cannot be undone. "
        "Your settings (investment, thresholds, dividend %) are kept."
    )
    st.caption(f"After reset: Remaining will be set to your investment = **{fmt_money(u.investment)}**")

    confirm_text = st.text_input(
        "Type **RESET** to confirm:",
        key="reset_confirm_input",
        placeholder="RESET",
    )

    c1, c2 = st.columns(2)
    is_confirmed = confirm_text.strip().upper() == "RESET"
    if c1.button("🔥 Yes, reset everything", type="primary", use_container_width=True,
                 disabled=not is_confirmed, key="dlg_reset_yes"):
        try:
            updated_user = dm.reset_all_transactions(st.session_state.user)
            st.session_state.user = updated_user
            st.session_state.suggestions = dm.generate_suggestions(
                updated_user, etfs, dm.load_holdings()
            )
            # Clear any dialog/action state
            for k in list(st.session_state.keys()):
                if k.startswith(("active_", "confirm_")):
                    del st.session_state[k]
            st.toast("🔥 All data reset", icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if c2.button("❌ Cancel", use_container_width=True, key="dlg_reset_no"):
        st.rerun()


@st.dialog("Reverse Transaction")
def _reverse_dialog(txn_id: str, kind: str, name: str, etf_type: str, summary: dict) -> None:
    st.markdown(f"**↩️ Reverse {kind} of {name}**  \n<small>{etf_type}</small>", unsafe_allow_html=True)
    st.warning(f"This restores your holdings and cash to the state before the {kind}.")

    if kind == "buy":
        s = st.columns(2)
        s[0].metric("Trade value", fmt_money(summary["value"]))
        s[1].metric("Refund on reverse", fmt_money(summary["value"] + summary["charges"]))
    else:
        s = st.columns(2)
        s[0].metric(
            f"Sold {summary['qty']} @ ₹{summary['sell_price']:,.2f}",
            fmt_money(summary["value"]),
        )
        s[1].metric(
            "Gross P/L",
            fmt_money(summary["pnl"]),
            delta=("profit" if summary["pnl"] >= 0 else "loss"),
            delta_color=("normal" if summary["pnl"] >= 0 else "inverse"),
        )

    c1, c2 = st.columns(2)
    if c1.button(f"↩️ Yes, reverse this {kind}", type="primary", use_container_width=True, key="dlg_rev_yes"):
        try:
            if kind == "buy":
                updated_user, _, _ = dm.reverse_buy(st.session_state.user, txn_id)
            else:
                updated_user, _, _ = dm.reverse_sell(st.session_state.user, txn_id)
            st.session_state.user = updated_user
            st.session_state.suggestions = dm.generate_suggestions(
                updated_user, etfs, dm.load_holdings()
            )
            st.toast(f"↩️ Reversed {kind} of {name}", icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not reverse: {exc}")
    if c2.button("❌ Cancel", use_container_width=True, key="dlg_rev_no"):
        st.rerun()


@st.dialog("📜 Transaction history", width="large")
def _history_dialog(etf_name: str, etf_type: str) -> None:
    buys = dm.load_buys()
    sells = dm.load_sells()
    bf = buys[buys["etfName"] == etf_name] if not buys.empty else buys
    sf = sells[sells["etfName"] == etf_name] if not sells.empty else sells

    events: list[dict] = []
    if bf is not None and not bf.empty:
        for _, r in bf.iterrows():
            events.append({
                "kind": "buy",
                "dt": pd.to_datetime(r["buyDate"], errors="coerce"),
                "qty": int(r["quantity"]),
                "price": float(r["price"]),
                "value": float(r["price"]) * int(r["quantity"]),
                "charges": float(r["totalCharges"]),
            })
    if sf is not None and not sf.empty:
        for _, r in sf.iterrows():
            qty = int(r["quantity"])
            sp = float(r["sellPrice"])
            ap = float(r["averagePurchasePrice"])
            fees = float(r["brokerageCharges"]) + float(r["tax"]) + float(r["dividendPaidToSelf"])
            events.append({
                "kind": "sell",
                "dt": pd.to_datetime(r["sellDate"], errors="coerce"),
                "qty": qty,
                "price": sp,
                "value": sp * qty,
                "avg": ap,
                "pnl": (sp - ap) * qty,
                "fees": fees,
            })

    events.sort(key=lambda e: (pd.Timestamp.min if pd.isna(e["dt"]) else e["dt"]), reverse=True)

    buy_count = sum(1 for e in events if e["kind"] == "buy")
    sell_count = sum(1 for e in events if e["kind"] == "sell")
    bought_qty = sum(e["qty"] for e in events if e["kind"] == "buy")
    sold_qty = sum(e["qty"] for e in events if e["kind"] == "sell")
    realized_pl = sum(e["pnl"] - e["fees"] for e in events if e["kind"] == "sell")
    net_qty = bought_qty - sold_qty

    # Header card
    st.markdown(
        f'<div class="history-hdr">'
        f'<div class="name">{etf_name}</div>'
        f'<div class="meta">{badge(etf_type, "equity")} '
        f'&nbsp;·&nbsp; {buy_count + sell_count} transactions '
        f'&nbsp;·&nbsp; net qty held <b>{net_qty}</b></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not events:
        st.info("No transactions found for this ETF.")
        return

    # Compact stats strip — reuse metric_card for theme consistency
    pnl_cls = pnl_class(realized_pl)
    s = st.columns(4)
    s[0].markdown(metric_card("🛒 Buys", str(buy_count)), unsafe_allow_html=True)
    s[1].markdown(metric_card("💰 Sells", str(sell_count)), unsafe_allow_html=True)
    s[2].markdown(metric_card("Bought / Sold", f"{bought_qty} / {sold_qty}"),
                  unsafe_allow_html=True)
    s[3].markdown(
        metric_card("Realized P/L", fmt_money(realized_pl, 2), delta_class=pnl_cls),
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    last_label = None
    for e in events:
        dt = e["dt"]
        label = _chat_date_label(dt) if pd.notna(dt) else "Unknown date"
        if label != last_label:
            _render_date_separator(label)
            last_label = label

        time_str = dt.strftime("%H:%M") if pd.notna(dt) else "—"

        if e["kind"] == "buy":
            bubble = (
                f'<div class="bubble buy">'
                f'<div class="row1"><span class="kind">🛒 Buy</span>'
                f'<span class="time">{time_str}</span></div>'
                f'<div class="main">{e["qty"]} × ₹{e["price"]:,.2f} '
                f'<span class="total">= {fmt_money(e["value"])}</span></div>'
                f'<div class="sub">Charges {fmt_money(e["charges"], 2)}</div>'
                f'</div>'
            )
            cols = st.columns([6, 1])
            with cols[0]:
                st.markdown(bubble, unsafe_allow_html=True)
        else:
            cls = pnl_class(e["pnl"])
            sign = "+" if e["pnl"] >= 0 else ""
            bubble = (
                f'<div class="bubble sell">'
                f'<div class="row1"><span class="kind">💰 Sell</span>'
                f'<span class="time">{time_str}</span></div>'
                f'<div class="main">{e["qty"]} × ₹{e["price"]:,.2f} '
                f'<span class="total">= {fmt_money(e["value"])}</span></div>'
                f'<div class="sub">Avg buy ₹{e["avg"]:,.2f} '
                f'· Gross P/L <span class="{cls}">{sign}{fmt_money(e["pnl"])}</span></div>'
                f'</div>'
            )
            cols = st.columns([1, 6])
            with cols[1]:
                st.markdown(bubble, unsafe_allow_html=True)


def _render_charge_breakdown(
    value: float,
    ch: dict,
    side: str,
    dividend: float | None = None,
    net: float | None = None,
    realized: float | None = None,
) -> None:
    with st.container(border=True):
        # Row 1
        r1 = st.columns(4)
        r1[0].metric("Gross" if side == "sell" else "Trade value", fmt_money(value))
        r1[1].metric("Brokerage", fmt_money(ch["brokerage"], 2))
        r1[2].metric("STT", fmt_money(ch["stt"], 2))
        if side == "buy":
            r1[3].metric("Stamp (0.015%)", fmt_money(ch["stamp"], 2))
        else:
            r1[3].metric(f"Dividend ({user.dividendPercentage:.2f}%)", fmt_money(dividend or 0, 2))

        # Row 2
        r2 = st.columns(4)
        r2[0].metric("Exchange", fmt_money(ch["exchangeTx"], 2))
        r2[1].metric("SEBI", fmt_money(ch["sebi"], 2))
        r2[2].metric("GST (18%)", fmt_money(ch["gst"], 2))
        if side == "buy":
            r2[3].metric("Total charges", fmt_money(ch["total"], 2))
        elif net is not None:
            r2[3].metric("Net proceeds", fmt_money(net))

        # Total row
        st.divider()
        if side == "buy":
            total_cost = value + ch["total"]
            t = st.columns(2)
            t[0].metric("Total cost", fmt_money(total_cost))
        else:
            t = st.columns(2)
            t[0].metric("Net proceeds", fmt_money(net or 0))
            if realized is not None:
                t[1].metric(
                    "Realized P/L",
                    fmt_money(realized),
                    delta=("profit" if realized >= 0 else "loss"),
                    delta_color=("normal" if realized >= 0 else "inverse"),
                )


def _buy_more_form(row: pd.Series) -> None:
    c1, c2 = st.columns(2)
    default_price = float(row["cmp"]) if row["cmp"] else float(row["averagePrice"])
    # Flutter "buy more" default qty = max(1, floor(totalQty × 0.10)) — i.e. 10% top-up
    suggested_qty = max(1, int(int(row["totalQuantity"]) * 0.10))
    price = c1.number_input(
        "Buy price", min_value=0.0, value=default_price, step=0.05, key=f"bp_{row['id']}"
    )
    qty = c2.number_input(
        "Quantity", min_value=1, value=suggested_qty, step=1, key=f"bq_{row['id']}",
        help=f"Default = 10% of your current holding ({int(row['totalQuantity'])} units) → {suggested_qty}",
    )

    value = price * qty
    ch = dm.compute_kotak_charges(value, str(row["etfType"]), side="buy")
    total_cost = value + ch["total"]
    st.caption(f"Remaining after: **{fmt_money(user.remainingAmount - total_cost)}**")
    _render_charge_breakdown(value, ch, side="buy")

    if st.button("✅ Review & Buy", key=f"bbtn_{row['id']}", use_container_width=True, type="primary"):
        _buy_dialog(
            name=str(row["etfName"]),
            etf_type=str(row["etfType"]),
            price=float(price),
            qty=int(qty),
        )


def page_suggestions() -> None:
    st.markdown('<h2 style="margin-top:0">💡 Buy Suggestions</h2>', unsafe_allow_html=True)
    st.caption("Top picks across Equity, Jewellery, and Stocks — based on greatest dip vs 20-DMA.")

    suggestions = st.session_state.get("suggestions", [])
    if not suggestions:
        st.info("No suggestions right now. Try '🔄 Refresh ETFs' in the sidebar, or set an investment amount in Settings.")
        return

    # Quick summary
    total_cost = sum(s["price"] * s["quantity"] for s in suggestions)
    types = {s["type"] for s in suggestions}
    c = st.columns(3)
    c[0].markdown(metric_card("Suggestions", f"{len(suggestions)}"), unsafe_allow_html=True)
    c[1].markdown(metric_card("Types covered", ", ".join(sorted(types))), unsafe_allow_html=True)
    c[2].markdown(metric_card("If you buy all", fmt_money(total_cost)), unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    fresh_label = f"✨ Fresh picks ({len(suggestions)})"
    back_label  = "🔁 Buy-back opportunities"
    selected = st.radio(
        "Mode",
        [fresh_label, back_label],
        horizontal=True,
        label_visibility="collapsed",
        key="sug_mode",
    )
    if selected == fresh_label:
        _render_fresh_suggestions(suggestions)
    else:
        _render_buyback_section()


def _render_buyback_section() -> None:
    st.caption(
        "ETFs you **previously sold** that are now trading **below your sell price** — "
        "you could buy them back cheaper."
    )
    holdings = dm.load_holdings()
    sells = dm.load_sells()
    opps = dm.buyback_opportunities(sells, etfs, holdings)

    if not opps:
        st.info(
            "No buy-back opportunities right now. This list fills up after you've "
            "sold an ETF and its current price drops below what you sold at."
        )
        return

    for i, s in enumerate(opps):
        with st.container(border=True):
            top = st.columns([3, 1, 1, 1])
            top[0].markdown(
                f"**{s['name']}** &nbsp; {badge(s['type'], 'equity')}",
                unsafe_allow_html=True,
            )
            top[1].markdown(
                f"<div class='text-muted' style='font-size:0.75rem'>SOLD AT (avg)</div>"
                f"<div>₹{s['avgSellPrice']:,.2f}</div>",
                unsafe_allow_html=True,
            )
            top[2].markdown(
                f"<div class='text-muted' style='font-size:0.75rem'>NOW</div>"
                f"<div>₹{s['price']:,.2f}</div>",
                unsafe_allow_html=True,
            )
            top[3].markdown(
                f"<div class='text-muted' style='font-size:0.75rem'>DISCOUNT</div>"
                f"<div class='text-green'>{s['discountPct']:+.2f}%</div>",
                unsafe_allow_html=True,
            )

            with st.expander(f"Buy back {s['name']}", expanded=False):
                cc1, cc2 = st.columns(2)
                price = cc1.number_input(
                    "Price", min_value=0.0, value=float(s["price"]), step=0.05, key=f"bbp_{i}"
                )
                qty = cc2.number_input(
                    "Quantity", min_value=1, value=int(s["qty"]), step=1, key=f"bbq_{i}"
                )
                value = price * qty
                ch = dm.compute_kotak_charges(value, s["type"], side="buy")
                total_cost = value + ch["total"]
                st.caption(f"Remaining after: **{fmt_money(user.remainingAmount - total_cost)}**")
                _render_charge_breakdown(value, ch, side="buy")
                if st.button(
                    "✅ Review & Buy back", key=f"bb_btn_{i}",
                    use_container_width=True, type="primary",
                ):
                    _buy_dialog(
                        name=s["name"], etf_type=s["type"],
                        price=float(price), qty=int(qty),
                    )


def _render_fresh_suggestions(suggestions: list[dict]) -> None:

    for i, s in enumerate(suggestions):
        with st.container(border=True):
            top = st.columns([3, 1, 1, 1])
            top[0].markdown(
                f'**{s["name"]}** &nbsp; {badge(s["type"], "equity")}',
                unsafe_allow_html=True,
            )
            top[1].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">PRICE</div>'
                f'<div>₹{s["price"]:,.2f}</div>',
                unsafe_allow_html=True,
            )
            top[2].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">SUGGESTED QTY</div>'
                f'<div>{s["quantity"]}</div>',
                unsafe_allow_html=True,
            )
            top[3].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">EST. COST</div>'
                f'<div>{fmt_money(s["price"] * s["quantity"])}</div>',
                unsafe_allow_html=True,
            )

            with st.expander(f"Buy {s['name']}", expanded=False):
                cc1, cc2 = st.columns(2)
                price = cc1.number_input(
                    "Price", min_value=0.0, value=float(s["price"]), step=0.05, key=f"p_{i}"
                )
                qty = cc2.number_input(
                    "Quantity", min_value=1, value=int(s["quantity"]), step=1, key=f"q_{i}"
                )
                value = price * qty
                ch = dm.compute_kotak_charges(value, s["type"], side="buy")
                total_cost = value + ch["total"]
                st.caption(f"Remaining after: **{fmt_money(user.remainingAmount - total_cost)}**")
                _render_charge_breakdown(value, ch, side="buy")
                if st.button(
                    "✅ Review & Buy", key=f"rev_sug_{i}", use_container_width=True, type="primary"
                ):
                    _buy_dialog(
                        name=s["name"],
                        etf_type=s["type"],
                        price=float(price),
                        qty=int(qty),
                    )


def page_listed_etfs() -> None:
    st.markdown('<h2 style="margin-top:0">📋 Listed ETFs</h2>', unsafe_allow_html=True)

    if etfs.empty:
        st.info("No ETFs cached yet. Click '🔄 Refresh ETFs' in the sidebar.")
        return

    c1, c2 = st.columns([1, 3])
    type_filter = c1.selectbox("Type", ["All"] + sorted(etfs["type"].dropna().unique().tolist()))
    search = c2.text_input("🔍 Search by name or code").strip().lower()

    view = etfs.copy()
    if type_filter != "All":
        view = view[view["type"] == type_filter]
    if search:
        view = view[
            view["name"].str.lower().str.contains(search, na=False)
            | view["etfCode"].str.lower().str.contains(search, na=False)
        ]

    view = view.sort_values("change20DmaVsCmp", ascending=True).reset_index(drop=True)

    st.caption(f"Showing {len(view)} ETFs. Sorted by dip (largest first).")

    display = view[["etfCode", "name", "type", "cmp", "the20Dma", "change20DmaVsCmp", "changePercentage"]].copy()
    display["change20DmaVsCmp"] = (display["change20DmaVsCmp"] * 100).round(2)
    display.columns = ["Code", "Name", "Type", "CMP", "20-DMA", "Δ 20-DMA %", "Change %"]
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "CMP": st.column_config.NumberColumn(format="₹%.2f"),
            "20-DMA": st.column_config.NumberColumn(format="₹%.2f"),
            "Δ 20-DMA %": st.column_config.NumberColumn(format="%.2f %%"),
            "Change %": st.column_config.NumberColumn(format="%.2f %%"),
        },
    )


def page_sell_history() -> None:
    st.markdown('<h2 style="margin-top:0">📜 Sell History</h2>', unsafe_allow_html=True)

    sells = dm.load_sells()
    if sells.empty:
        st.info("No sell transactions yet.")
        return

    view = sells.copy()
    q = view["quantity"].astype(float)
    sp = view["sellPrice"].astype(float)
    ap = view["averagePurchasePrice"].astype(float)
    view["grossPL"] = (sp - ap) * q
    view["netPL"] = (
        view["grossPL"]
        - view["brokerageCharges"].astype(float)
        - view["tax"].astype(float)
        - view["dividendPaidToSelf"].astype(float)
    )

    # Summary
    c1, c2, c3 = st.columns(3)
    c1.markdown(metric_card("Total Transactions", f"{len(view)}"), unsafe_allow_html=True)
    total_gross = float(view["grossPL"].sum())
    total_net = float(view["netPL"].sum())
    c2.markdown(
        metric_card("Gross P/L", fmt_money(total_gross), delta_class=pnl_class(total_gross)),
        unsafe_allow_html=True,
    )
    c3.markdown(
        metric_card("Net P/L", fmt_money(total_net), delta_class=pnl_class(total_net)),
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    show = view[[
        "sellDate", "etfName", "etfType", "quantity",
        "averagePurchasePrice", "sellPrice",
        "brokerageCharges", "tax", "dividendPaidToSelf",
        "grossPL", "netPL",
    ]].copy()
    show.columns = [
        "Sell Date", "ETF", "Type", "Qty",
        "Avg Buy", "Sell",
        "Brokerage", "Tax", "Dividend",
        "Gross P/L", "Net P/L",
    ]
    show = show.sort_values("Sell Date", ascending=False)

    st.dataframe(
        show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Avg Buy":   st.column_config.NumberColumn(format="₹%.2f"),
            "Sell":      st.column_config.NumberColumn(format="₹%.2f"),
            "Brokerage": st.column_config.NumberColumn(format="₹%.2f"),
            "Tax":       st.column_config.NumberColumn(format="₹%.2f"),
            "Dividend":  st.column_config.NumberColumn(format="₹%.2f"),
            "Gross P/L": st.column_config.NumberColumn(format="₹%.2f"),
            "Net P/L":   st.column_config.NumberColumn(format="₹%.2f"),
        },
    )


def page_reports() -> None:
    st.markdown('<h2 style="margin-top:0">📊 Reports</h2>', unsafe_allow_html=True)
    st.caption("How much money you used, where it went, and whether the totals add up.")

    holdings = dm.load_holdings()
    sells = dm.load_sells()
    buys = dm.load_buys()
    r = dm.compute_report(holdings, sells, etfs)
    m = dm.compute_money_summary(user, buys, sells, holdings, etfs)

    # ---- Money snapshot (4 cards) ----
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Initial deposit", fmt_money(m["initialDeposit"], 2)),
                unsafe_allow_html=True)
    c2.markdown(metric_card("Cash remaining", fmt_money(m["remainingCash"], 2)),
                unsafe_allow_html=True)
    c3.markdown(metric_card("Money in holdings", fmt_money(m["costBasis"], 2)),
                unsafe_allow_html=True)
    c4.markdown(
        metric_card("Current value", fmt_money(m["currentValue"], 2),
                    delta=fmt_pct(r["portfolioPct"]) if m["costBasis"] else None,
                    delta_class=pnl_class(m["unrealizedPL"])),
        unsafe_allow_html=True,
    )

    # ---- Money used / received / fees (one row, 4 cards) ----
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    u1, u2, u3, u4 = st.columns(4)
    u1.markdown(
        metric_card(f"Spent on buys ({m['buyCount']})", fmt_money(m["buyOutflow"], 2)),
        unsafe_allow_html=True,
    )
    u2.markdown(
        metric_card(f"Got from sells ({m['sellCount']})", fmt_money(m["sellInflow"], 2)),
        unsafe_allow_html=True,
    )
    u3.markdown(
        metric_card("Fees paid total", fmt_money(m["feesPaidTotal"], 2)),
        unsafe_allow_html=True,
    )
    u4.markdown(
        metric_card("Realized profit", fmt_money(m["sellNetPL"], 2),
                    delta_class=pnl_class(m["sellNetPL"])),
        unsafe_allow_html=True,
    )

    # ---- Verification (math always visible) ----
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section("Verify the totals")
    flow = pd.DataFrame([
        ("Initial deposit",                   m["initialDeposit"]),
        ("+ Profit from sells (gross)",       m["sellGrossPL"]),
        ("− Fees on buys",                   -m["buyTotalCharges"]),
        ("− Fees on sells",                  -m["sellFeesTotal"]),
        ("− Dividend paid to self",          -m["sellDividend"]),
        ("= Expected total",                  m["expectedBalance"]),
        ("Cash remaining + holdings cost",    m["accountBalance"]),
        ("Difference",                        m["reconcileDiff"]),
    ], columns=["Item", "Amount"])
    st.dataframe(
        flow, use_container_width=True, hide_index=True,
        column_config={"Amount": st.column_config.NumberColumn(format="₹%.4f")},
    )
    if abs(m["reconcileDiff"]) < 0.01:
        st.success(f"✅ Totals match — cash + holdings = expected total ({fmt_money(m['accountBalance'], 2)}).")
    else:
        st.error(f"⚠️ Totals off by ₹{m['reconcileDiff']:+.4f}. Investigate buy/sell history.")

    # ---- Fees breakdown (compact two-column table) ----
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section("What made up the fees")
    fees_breakdown = pd.DataFrame([
        ("Brokerage on buys",                m["buyBrokerage"]),
        ("Statutory on buys (STT/stamp/exch/SEBI/GST)", m["buyTax"]),
        ("Brokerage on sells",               m["sellBrokerage"]),
        ("Statutory on sells",               m["sellTax"]),
        ("Dividend paid to self",            m["sellDividend"]),
        ("Total money consumed",             m["moneyConsumed"]),
    ], columns=["Item", "Amount"])
    st.dataframe(
        fees_breakdown, use_container_width=True, hide_index=True,
        column_config={"Amount": st.column_config.NumberColumn(format="₹%.4f")},
    )

    # ---- Per-ETF money usage ----
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section("Where the money went (per ETF)")
    per_etf = dm.money_by_etf(buys, sells, holdings, etfs)
    if per_etf.empty:
        st.info("No transactions yet.")
    else:
        show = per_etf[[
            "etfName", "etfType",
            "buyOutflow", "sellInflow",
            "heldQty", "costBasis", "currentValue", "unrealizedPL",
            "sellNetPL", "netInvested",
        ]].copy()
        show.columns = [
            "ETF", "Type",
            "Spent (incl. fees)", "Received (after fees)",
            "Held Qty", "In holdings", "Worth now", "Unrealized P/L",
            "Realized P/L", "Net invested",
        ]
        st.dataframe(
            show, use_container_width=True, hide_index=True,
            column_config={
                "Spent (incl. fees)":    st.column_config.NumberColumn(format="₹%.2f"),
                "Received (after fees)": st.column_config.NumberColumn(format="₹%.2f"),
                "Held Qty":              st.column_config.NumberColumn(format="%.0f"),
                "In holdings":           st.column_config.NumberColumn(format="₹%.2f"),
                "Worth now":             st.column_config.NumberColumn(format="₹%.2f"),
                "Unrealized P/L":        st.column_config.NumberColumn(format="₹%.2f"),
                "Realized P/L":          st.column_config.NumberColumn(format="₹%.2f"),
                "Net invested":          st.column_config.NumberColumn(format="₹%.2f"),
            },
        )
        st.caption(
            f"Totals — spent {fmt_money(per_etf['buyOutflow'].sum(), 2)} · "
            f"received {fmt_money(per_etf['sellInflow'].sum(), 2)} · "
            f"net invested {fmt_money(per_etf['netInvested'].sum(), 2)} · "
            f"current value {fmt_money(per_etf['currentValue'].sum(), 2)}"
        )

    # ---- Allocation by type ----
    alloc = dm.holdings_by_type(holdings, etfs)
    if not alloc.empty:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        section("By type (current holdings)")
        a = alloc[["etfType", "count", "cost", "currentValue", "pnl", "pnlPct"]].copy()
        a.columns = ["Type", "# Holdings", "Cost", "Current value", "Unrealized P/L", "P/L %"]
        st.dataframe(
            a, use_container_width=True, hide_index=True,
            column_config={
                "Cost":           st.column_config.NumberColumn(format="₹%.2f"),
                "Current value":  st.column_config.NumberColumn(format="₹%.2f"),
                "Unrealized P/L": st.column_config.NumberColumn(format="₹%.2f"),
                "P/L %":          st.column_config.NumberColumn(format="%.2f %%"),
            },
        )

    # ---- Month-by-month ----
    monthly = dm.money_by_month(buys, sells)
    if not monthly.empty:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        section("Month by month")
        mv = monthly.copy()
        mv.columns = ["Month", "Spent on buys", "Buy fees",
                      "Got from sells", "Sell fees", "Dividend out", "Net flow"]
        st.dataframe(
            mv, use_container_width=True, hide_index=True,
            column_config={
                "Spent on buys":  st.column_config.NumberColumn(format="₹%.2f"),
                "Buy fees":       st.column_config.NumberColumn(format="₹%.4f"),
                "Got from sells": st.column_config.NumberColumn(format="₹%.2f"),
                "Sell fees":      st.column_config.NumberColumn(format="₹%.4f"),
                "Dividend out":   st.column_config.NumberColumn(format="₹%.2f"),
                "Net flow":       st.column_config.NumberColumn(format="₹%.2f"),
            },
        )

    if r["holdingsCount"] > 20:
        st.warning("⚠️ Holdings count exceeds 20.")


def page_settings() -> None:
    st.markdown('<h2 style="margin-top:0">⚙️ Settings</h2>', unsafe_allow_html=True)

    section("Appearance")
    st.radio(
        "Theme",
        ["🌙 Dark", "☀️ Light"],
        horizontal=True,
        key="theme",
        help="Switches instantly — no save needed. Persists for this browser session.",
    )
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    with st.form("settings"):
        section("Profile")
        name = st.text_input("Name", user.userName)

        section("Capital")
        c1, c2 = st.columns(2)
        investment = c1.number_input(
            "Total investment", min_value=0.0, value=float(user.investment), step=100.0
        )
        implied_remaining = investment - (user.investment - user.remainingAmount)
        remaining = c2.number_input(
            "Remaining amount (auto)",
            value=float(implied_remaining),
            step=100.0,
            help="Computed as investment − deployed capital. Adjust only if needed.",
        )

        section("Personal")
        dividend_pct = st.number_input(
            "Dividend % (portion of each sell you allocate to yourself)",
            min_value=0.0, value=float(user.dividendPercentage), step=0.01, format="%.2f",
        )

        section("Thresholds")
        c6, c7 = st.columns(2)
        sell_target = c6.number_input("Sell Profit Target %", min_value=0.0, value=float(user.sellProfitTarget), step=0.1, format="%.2f")
        buy_dip = c7.number_input("Buy-in-Dip Threshold %", min_value=0.0, value=float(user.buyInDipThreshold), step=0.1, format="%.2f")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        if st.form_submit_button("💾 Save", use_container_width=True, type="primary"):
            if remaining < 0:
                st.error("Remaining amount cannot be negative.")
                return
            u = dm.UserSettings(
                userName=name,
                investment=float(investment),
                remainingAmount=float(remaining),
                taxPercentage=0.0,      # auto-computed per trade
                brokeragePercentage=0.0,  # auto-computed per trade
                dividendPercentage=float(dividend_pct),
                sellProfitTarget=float(sell_target),
                buyInDipThreshold=float(buy_dip),
            )
            dm.save_user(u)
            st.session_state.user = u
            st.toast("💾 Settings saved", icon="✅")
            st.rerun()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section("Danger zone")
    with st.container(border=True):
        st.markdown("**🔥 Reset all transactions**")
        st.caption(
            "Wipes every holding, buy, and sell. Your investment amount and preferences "
            "are kept. Useful for starting fresh or clearing test data."
        )
        if st.button("🔥 Reset all transactions", type="secondary"):
            _reset_all_dialog()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section("Kotak charges (auto-applied)")
    st.markdown(
        f"""
        <div style="padding:14px; background:#12161F; border-radius:8px; border:1px solid #2A3040; font-size:0.9rem">
          Charges are computed per trade based on Kotak Trade Plan + standard statutory rates.
          You don't need to set brokerage/tax manually.
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:10px">
            <div>
              <div class="text-muted" style="font-size:0.75rem">BROKERAGE (delivery)</div>
              <div>• ETFs (Equity/Jewellery): <b>0.05%</b></div>
              <div>• Stocks: <b>0.10%</b></div>
            </div>
            <div>
              <div class="text-muted" style="font-size:0.75rem">STT</div>
              <div>• ETFs: <b>0.001%</b> sell only</div>
              <div>• Stocks: <b>0.1%</b> buy & sell</div>
            </div>
            <div>
              <div class="text-muted" style="font-size:0.75rem">OTHER STATUTORY</div>
              <div>• Stamp duty: <b>0.015%</b> on buy</div>
              <div>• Exchange: <b>0.00297%</b>, SEBI: <b>0.0001%</b></div>
            </div>
            <div>
              <div class="text-muted" style="font-size:0.75rem">GST</div>
              <div>• <b>18%</b> on (brokerage + exchange + SEBI)</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_transactions() -> None:
    st.markdown('<h2 style="margin-top:0">🔄 Transactions & Reverse</h2>', unsafe_allow_html=True)
    st.caption(
        "Made a mistake in the app? Reverse any buy or sell here — the app will restore "
        "your holdings, cash, and investment trackers to the exact state before the action."
    )

    tab_buys, tab_sells = st.tabs(["🟢 Buys", "🔴 Sells"])

    with tab_buys:
        buys = dm.load_buys()
        if buys.empty:
            st.info(
                "No buy records yet. Buys made before this feature was added can't be reversed "
                "through the log — use **Home → Sell** if you need to remove a legacy holding."
            )
        else:
            _render_transaction_list(buys, kind="buy")

    with tab_sells:
        sells = dm.load_sells()
        if sells.empty:
            st.info("No sell records yet.")
        else:
            _render_transaction_list(sells, kind="sell")


def _chat_date_label(dt: datetime) -> str:
    today = datetime.now().date()
    d = dt.date()
    if d == today:
        return "Today"
    if d == today - timedelta(days=1):
        return "Yesterday"
    if d.year == today.year:
        return f"{d.day} {dt.strftime('%B')}"
    return f"{d.day} {dt.strftime('%B %Y')}"


def _render_date_separator(label: str) -> None:
    st.markdown(
        '<div style="display:flex;justify-content:center;margin:16px 0 6px 0">'
        '<span style="background:rgba(139,147,167,0.18);color:#8B93A7;'
        'padding:4px 14px;border-radius:14px;font-size:0.78rem;'
        'font-weight:600;letter-spacing:0.3px">'
        f'{label}</span></div>',
        unsafe_allow_html=True,
    )


def _render_transaction_list(df: pd.DataFrame, kind: str) -> None:
    date_col = "buyDate" if kind == "buy" else "sellDate"
    df = df.copy()
    df["_dt"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.sort_values("_dt", ascending=False, na_position="last").reset_index(drop=True)

    df["_label"] = df["_dt"].apply(
        lambda dt: _chat_date_label(dt) if pd.notna(dt) else "Unknown date"
    )
    counts = df["_label"].value_counts().to_dict()

    last_label = None
    for _, row in df.iterrows():
        label = row["_label"]
        if label != last_label:
            n = counts.get(label, 0)
            suffix = "transaction" if n == 1 else "transactions"
            _render_date_separator(f"{label} · {n} {suffix}")
            last_label = label

        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
            c1.markdown(
                f'**{row["etfName"]}** &nbsp; {badge(str(row["etfType"]), "equity")}'
                f'<div class="text-muted" style="font-size:0.75rem;margin-top:2px">{row[date_col]}</div>',
                unsafe_allow_html=True,
            )

            if kind == "buy":
                c2.markdown(
                    f'<div class="text-muted" style="font-size:0.72rem">PRICE</div>'
                    f'<div>₹{float(row["price"]):,.2f}</div>',
                    unsafe_allow_html=True,
                )
                c3.markdown(
                    f'<div class="text-muted" style="font-size:0.72rem">QTY</div>'
                    f'<div>{int(row["quantity"])}</div>',
                    unsafe_allow_html=True,
                )
                c4.markdown(
                    f'<div class="text-muted" style="font-size:0.72rem">VALUE</div>'
                    f'<div>{fmt_money(float(row["price"]) * int(row["quantity"]))}</div>',
                    unsafe_allow_html=True,
                )
                c5.markdown(
                    f'<div class="text-muted" style="font-size:0.72rem">CHARGES</div>'
                    f'<div>{fmt_money(float(row["totalCharges"]), 2)}</div>',
                    unsafe_allow_html=True,
                )
            else:
                c2.markdown(
                    f'<div class="text-muted" style="font-size:0.72rem">SELL PRICE</div>'
                    f'<div>₹{float(row["sellPrice"]):,.2f}</div>',
                    unsafe_allow_html=True,
                )
                c3.markdown(
                    f'<div class="text-muted" style="font-size:0.72rem">QTY</div>'
                    f'<div>{int(row["quantity"])}</div>',
                    unsafe_allow_html=True,
                )
                pnl = (float(row["sellPrice"]) - float(row["averagePurchasePrice"])) * int(row["quantity"])
                c4.markdown(
                    f'<div class="text-muted" style="font-size:0.72rem">GROSS P/L</div>'
                    f'<div class="{pnl_class(pnl)}">{fmt_money(pnl)}</div>',
                    unsafe_allow_html=True,
                )
                total_charges = float(row["brokerageCharges"]) + float(row["tax"]) + float(row["dividendPaidToSelf"])
                c5.markdown(
                    f'<div class="text-muted" style="font-size:0.72rem">FEES+DIV</div>'
                    f'<div>{fmt_money(total_charges, 2)}</div>',
                    unsafe_allow_html=True,
                )

            if st.button(
                f"↩️ Reverse this {kind}",
                key=f"rev_{kind}_{row['id']}",
                use_container_width=True,
            ):
                if kind == "buy":
                    summary = {
                        "value": float(row["price"]) * int(row["quantity"]),
                        "charges": float(row["totalCharges"]),
                    }
                else:
                    val = float(row["sellPrice"]) * int(row["quantity"])
                    pnl = (float(row["sellPrice"]) - float(row["averagePurchasePrice"])) * int(row["quantity"])
                    summary = {
                        "value": val,
                        "qty": int(row["quantity"]),
                        "sell_price": float(row["sellPrice"]),
                        "pnl": pnl,
                    }
                _reverse_dialog(
                    txn_id=str(row["id"]),
                    kind=kind,
                    name=str(row["etfName"]),
                    etf_type=str(row["etfType"]),
                    summary=summary,
                )


def page_info() -> None:
    st.markdown('<h2 style="margin-top:0">ℹ️ Info & Documentation</h2>', unsafe_allow_html=True)
    doc_path = Path(__file__).parent / "DOCUMENTATION.html"
    if not doc_path.exists():
        st.error(f"Documentation file not found at {doc_path}")
        return
    html = doc_path.read_text(encoding="utf-8")
    components.html(html, height=1600, scrolling=True)
    st.caption(f"Source: {doc_path.name} — edit this file to update the in-app docs.")


# ---------- Router ----------

if page.endswith("Home"):
    page_home()
elif page.endswith("Suggestions"):
    page_suggestions()
elif page.endswith("Listed ETFs"):
    page_listed_etfs()
elif page.endswith("Sell History"):
    page_sell_history()
elif page.endswith("Reports"):
    page_reports()
elif page.endswith("Transactions"):
    page_transactions()
elif page.endswith("Settings"):
    page_settings()
elif page.endswith("Info"):
    page_info()
