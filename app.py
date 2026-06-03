"""FIRE – local Streamlit port of the Flutter investment tracker."""

from __future__ import annotations

import copy
import hashlib
import hmac
import time
from datetime import date, datetime, timedelta
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

    # Password protection disabled — let anyone in
    if not config.get("passwordEnabled", True):
        st.session_state.authenticated = True
        return

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
                dm.save_config({"passwordHash": h, "passwordEnabled": True})
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
    if "amc_checked" not in st.session_state:
        updated_user, deducted = dm.check_and_apply_amc(st.session_state.user)
        st.session_state.user = updated_user
        st.session_state.amc_checked = True
        if deducted > 0:
            st.toast(f"🏦 Auto-deducted Demat AMC ₹{deducted:.2f} — next deduction in 30 days.", icon="🏦")
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


def _fmt_hold_days(days: int) -> str:
    """Format a day count as a human-readable holding duration."""
    if days <= 0:
        return "0d"
    if days < 7:
        return f"{days}d"
    if days < 30:
        w, d = divmod(days, 7)
        return f"{w}w {d}d" if d else f"{w}w"
    if days < 365:
        m, d = divmod(days, 30)
        return f"{m}mo {d}d" if d else f"{m}mo"
    y, rem = divmod(days, 365)
    m = rem // 30
    return f"{y}y {m}mo" if m else f"{y}y"


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
        st.rerun()

    st.markdown(
        f'<div style="margin-top:8px;color:#8B93A7;font-size:0.78rem;">'
        f'Last fetched <b style="color:#FAFAFA;">{_format_last_fetch()}</b><br>'
        f'{len(etfs)} ETFs cached'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Quick stats ───────────────────────────────────────────────────────
    _sb_holdings    = dm.load_holdings()
    _sb_cost        = dm.holdings_total_cost(_sb_holdings)

    cash            = user.remainingAmount
    deposited       = user.totalDeposited           # money physically transferred in
    eff_budget      = user.investment               # deposited + realized P&L
    realized_pl     = eff_budget - deposited        # net profit/loss added so far
    cash_pct        = (cash / eff_budget * 100) if eff_budget else 0
    dep_pct         = 100 - cash_pct

    # verification: cash + cost_basis should equal effective budget
    verified        = abs((cash + _sb_cost) - eff_budget) < 1.0
    ver_color       = "#2ecc71" if verified else "#e74c3c"
    ver_icon        = "✓" if verified else "✗"
    ver_diff        = (cash + _sb_cost) - eff_budget

    def _tip(text):
        return f'<span title="{text}" style="cursor:help;opacity:0.35;font-size:0.62rem;margin-left:3px">ⓘ</span>'

    def _stat(label, value, vc="inherit", tip="", badge="", badge_color="#2ecc71"):
        badge_html = (
            f'<span style="display:inline-block;margin-left:7px;padding:1px 7px;'
            f'border-radius:10px;background:{badge_color}22;color:{badge_color};'
            f'font-size:0.68rem;font-weight:600;vertical-align:middle">{badge}</span>'
        ) if badge else ""
        return (
            f'<div style="margin-bottom:10px">'
            f'  <div style="font-size:0.72rem;opacity:0.5;margin-bottom:2px">'
            f'    {label}{_tip(tip) if tip else ""}'
            f'  </div>'
            f'  <div style="font-size:1.05rem;font-weight:700;color:{vc};line-height:1.2">'
            f'    {value}{badge_html}'
            f'  </div>'
            f'</div>'
        )

    pl_color = "#2ecc71" if realized_pl >= 0 else "#e74c3c"
    pl_sign  = "+" if realized_pl >= 0 else ""
    cash_color = "#2ecc71" if cash_pct > 10 else "#e74c3c"

    st.markdown(
        f'<div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:12px 14px 6px 14px;margin-top:4px">'
        f'<div style="font-size:0.65rem;font-weight:700;letter-spacing:.1em;opacity:0.35;margin-bottom:12px">QUICK STATS</div>'

        + _stat("You deposited",
                fmt_money(deposited, 0),
                tip="Money you actually transferred from your bank into Kotak.")

        + _stat("After profit / loss",
                fmt_money(eff_budget, 0),
                vc=pl_color,
                badge=f"{pl_sign}{fmt_money(realized_pl, 0)}",
                badge_color=pl_color,
                tip="Deposited + net realized P&L from all sells.")

        + f'<div style="border-top:1px solid rgba(255,255,255,0.07);margin:4px 0 10px"></div>'

        + _stat("Cash in hand",
                fmt_money(cash, 0),
                vc=cash_color,
                tip=f"Liquid cash available ({cash_pct:.1f}% of budget). Matches your Kotak balance.")

        + f'</div>',
        unsafe_allow_html=True,
    )


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

    # Overall avg hold days from meta/stats — no collection scan needed
    _s = dm.load_stats()
    _open_inv  = float(_s.get("openInvTotal", 0) or 0)
    _open_dsum = float(_s.get("openInvDateSum", 0) or 0)
    _today_ep  = (date.today() - date(1970, 1, 1)).days
    wavg_open_days = int(_today_ep - _open_dsum / _open_inv) if _open_inv > 0 else 0
    # Per-ETF hold times need buy lots but NOT sell history — pass empty sells DF
    ht = dm.compute_holding_time_stats(holdings, pd.DataFrame(), dm.load_buys())
    hold_time_by_etf = {op["etfName"]: op["holdingDays"] for op in ht["openPositions"]}

    c1, c2, c3, c4, c5 = st.columns(5)
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
    c5.markdown(metric_card("Avg Hold Time", _fmt_hold_days(wavg_open_days)), unsafe_allow_html=True)

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
    other_label = f"📋 All Holdings ({_filtered_count(groups['others'])})"

    selected = st.radio(
        "Filter",
        [other_label, sell_label, buy_label],
        horizontal=True,
        label_visibility="collapsed",
        key="home_filter",
    )

    if selected == sell_label:
        st.caption(f"ETFs where CMP > avg × (1 + {user.sellProfitTarget:.2f}%) — in profit zone, sorted by |P/L %|")
        _render_holding_cards(groups["sell"], kind="sell", hold_time_by_etf=hold_time_by_etf)
    elif selected == buy_label:
        st.caption(f"ETFs where CMP < avg × (1 − {user.buyInDipThreshold:.2f}%) — in dip, sorted by |P/L %|")
        _render_holding_cards(groups["buy"], kind="buy", hold_time_by_etf=hold_time_by_etf)
    else:
        st.caption("Holdings between thresholds — sorted by |P/L %|")
        _render_holding_cards(groups["others"], kind="others", hold_time_by_etf=hold_time_by_etf)

    _render_recent_activity()


def _render_recent_activity() -> None:
    """Show the last 5 buys + sells combined, newest first.
    Uses paginated fetches — never loads the full collections."""
    recent_buys, _  = dm.fetch_buys_page(5)
    recent_sells, _ = dm.fetch_sells_page(5)
    if recent_buys.empty and recent_sells.empty:
        return
    events = []
    for _, r in recent_buys.iterrows():
        events.append({
            "when": str(r["buyDate"]),
            "kind": "Buy",
            "icon": "🛒",
            "name": str(r["etfName"]),
            "qty": int(r["quantity"]),
            "price": float(r["price"]),
            "color": "text-green",
        })
    for _, r in recent_sells.iterrows():
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


def _render_holding_cards(
    df: pd.DataFrame,
    kind: str,
    hold_time_by_etf: dict | None = None,
) -> None:
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
            etf_nm = str(row["etfName"])
            if hold_time_by_etf and etf_nm in hold_time_by_etf:
                _held_d = int(hold_time_by_etf[etf_nm])
            else:
                try:
                    _buy_dt = pd.to_datetime(row["lastPurchaseDate"]).date()
                    _held_d = max(0, (date.today() - _buy_dt).days)
                except Exception:
                    _held_d = 0
            top[3].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">QTY · HELD</div>'
                f'<div>{int(row["totalQuantity"])}</div>'
                f'<div class="text-muted" style="font-size:0.78rem">{_fmt_hold_days(_held_d)}</div>',
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

            # Profit projection at sell target
            _avg   = float(row["averagePrice"])
            _qty   = int(row["totalQuantity"])
            _tgt   = float(row["sellTarget"])
            _cmp   = float(row["cmp"])
            _etype = str(row["etfType"])
            _sell_val  = _tgt * _qty
            _sell_ch   = dm.compute_kotak_charges(_sell_val, _etype, side="sell")
            _net_profit = (_tgt - _avg) * _qty - _sell_ch["total"]
            _net_pct    = (_net_profit / (_avg * _qty) * 100) if _avg * _qty > 0 else 0.0
            _p_col = "#2ecc71" if _net_profit >= 0 else "#e74c3c"
            _cmp_note = ""
            if _cmp > 0:
                _to_target_pct = (_tgt - _cmp) / _cmp * 100
                _cmp_note = (
                    f' &nbsp;·&nbsp; CMP needs <span style="color:#3b9ddd">'
                    f'{_to_target_pct:+.2f}%</span> to reach target'
                    if abs(_to_target_pct) > 0.01 else
                    f' &nbsp;·&nbsp; <span style="color:#2ecc71">At target now</span>'
                )
            st.markdown(
                f'<div style="font-size:0.78rem;opacity:0.75;margin:4px 0 6px 0">'
                f'At sell target ₹{_tgt:,.2f} (+{user.sellProfitTarget:.1f}%) → '
                f'<span style="color:{_p_col};font-weight:600">'
                f'{fmt_money(_net_profit)} net ({_net_pct:+.2f}%)</span>'
                f'{_cmp_note}</div>',
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
        "Sell price (per unit)",
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

    kotak_total = st.number_input(
        "Kotak gross total — Market Rate × Qty (optional)",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.2f",
        help="Enter Market Rate × Qty from your Kotak transaction statement "
             "(the gross value BEFORE charges are deducted). "
             "Do NOT enter the net credit amount from the ledger — "
             "that causes charges to be counted twice.",
        key=f"kt_{row['id']}",
    )

    # Use Kotak gross total if entered, otherwise fall back to price × qty
    if kotak_total > 0:
        effective_price = kotak_total / qty
        gross = kotak_total
        st.caption(f"Effective price: ₹{effective_price:.4f}/unit (gross rate)")
    else:
        effective_price = sell_price
        gross = sell_price * qty

    ch = dm.compute_kotak_charges(gross, str(row["etfType"]), side="sell")
    dividend = gross * user.dividendPercentage / 100
    net = gross - ch["brokerage"] - ch["tax"] - dividend
    realized = (effective_price - float(row["averagePrice"])) * qty - ch["brokerage"] - ch["tax"] - dividend

    _render_charge_breakdown(gross, ch, side="sell", dividend=dividend, net=net, realized=realized)

    if st.button("✅ Review & Sell", key=f"sbtn_{row['id']}", use_container_width=True, type="primary"):
        _sell_dialog(
            holding_id=str(row["id"]),
            name=str(row["etfName"]),
            etf_type=str(row["etfType"]),
            sell_price=float(effective_price),
            qty=int(qty),
            avg_price=float(row["averagePrice"]),
        )


def _clear_txn_cache() -> None:
    """Evict paginated Transactions and Sell History session caches after any write."""
    for k in list(st.session_state.keys()):
        if (k.startswith("txn_df_") or k.startswith("txn_cursor_")
                or k.startswith("sh_df") or k.startswith("sh_cursor")):
            del st.session_state[k]


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
            del st.session_state[_guard]
            _clear_txn_cache()
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
            del st.session_state[_guard]
            _clear_txn_cache()
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
            del st.session_state[_guard]
            _clear_txn_cache()
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
        _guard = f"_op_done_rev_{txn_id}"
        if not st.session_state.get(_guard):
            st.session_state[_guard] = True
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
                del st.session_state[_guard]
                _clear_txn_cache()
                st.rerun()
            except Exception as exc:
                del st.session_state[_guard]
                st.error(f"Could not reverse: {exc}")
    if c2.button("❌ Cancel", use_container_width=True, key="dlg_rev_no"):
        st.rerun()


@st.dialog("📜 Transaction history", width="large")
def _history_dialog(etf_name: str, etf_type: str) -> None:
    bf = dm.fetch_buys_for_etf(etf_name)
    sf = dm.fetch_sells_for_etf(etf_name)

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
    suggested_qty = max(1, int(int(row["totalQuantity"]) * 0.10))
    price = c1.number_input(
        "Buy price (per unit)", min_value=0.0, value=default_price, step=0.05, key=f"bp_{row['id']}"
    )
    qty = c2.number_input(
        "Quantity", min_value=1, value=suggested_qty, step=1, key=f"bq_{row['id']}",
        help=f"Default = 10% of your current holding ({int(row['totalQuantity'])} units) → {suggested_qty}",
    )
    kotak_total = st.number_input(
        "Total paid to Kotak (₹) — optional",
        min_value=0.0, value=0.0, step=0.01, format="%.2f",
        help="Paste the exact amount Kotak debited for this trade (without charges). "
             "Overrides per-unit price.",
        key=f"bkt_{row['id']}",
    )
    effective_price = (kotak_total / qty) if kotak_total > 0 else price
    if kotak_total > 0:
        st.caption(f"Effective price: ₹{effective_price:.4f}/unit")

    value = effective_price * qty
    ch = dm.compute_kotak_charges(value, str(row["etfType"]), side="buy")
    total_cost = value + ch["total"]
    st.caption(f"Remaining after: **{fmt_money(user.remainingAmount - total_cost)}**")
    _render_charge_breakdown(value, ch, side="buy")

    if st.button("✅ Review & Buy", key=f"bbtn_{row['id']}", use_container_width=True, type="primary"):
        _buy_dialog(
            name=str(row["etfName"]),
            etf_type=str(row["etfType"]),
            price=float(effective_price),
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

    for s in suggestions:
        with st.container(border=True):
            top = st.columns([3, 1, 1, 1, 1])
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
            dip = s.get("dip", 0.0)
            dip_color = "#2ecc71" if dip >= 0 else "#e74c3c"
            top[4].markdown(
                f'<div class="text-muted" style="font-size:0.75rem">DIP vs 20-DMA</div>'
                f'<div style="color:{dip_color}">{dip:+.2f}%</div>',
                unsafe_allow_html=True,
            )

            with st.expander(f"Buy {s['name']}", expanded=False):
                cc1, cc2 = st.columns(2)
                price = cc1.number_input(
                    "Price", min_value=0.0, value=float(s["price"]), step=0.05, key=f"sug_p_{s['name']}"
                )
                qty = cc2.number_input(
                    "Quantity", min_value=1, value=int(s["quantity"]), step=1, key=f"sug_q_{s['name']}"
                )
                value = price * qty
                ch = dm.compute_kotak_charges(value, s["type"], side="buy")
                total_cost = value + ch["total"]
                st.caption(f"Remaining after: **{fmt_money(user.remainingAmount - total_cost)}**")
                _render_charge_breakdown(value, ch, side="buy")

                # ── Profit projection ────────────────────────────────────────
                target_pct   = user.sellProfitTarget
                sell_target  = price * (1 + target_pct / 100)
                sell_value   = sell_target * qty
                sell_ch      = dm.compute_kotak_charges(sell_value, s["type"], side="sell")
                gross_profit = (sell_target - price) * qty
                net_profit   = gross_profit - sell_ch["total"]
                net_pct      = (net_profit / total_cost * 100) if total_cost else 0.0
                p_col = "#2ecc71" if net_profit >= 0 else "#e74c3c"
                st.markdown(
                    f'<div style="background:var(--secondary-background-color);'
                    f'border-radius:8px;padding:10px 14px;margin:8px 0">'
                    f'<div style="font-size:0.72rem;opacity:0.5;text-transform:uppercase;'
                    f'letter-spacing:.07em;margin-bottom:6px">'
                    f'If sold at +{target_pct:.1f}% target (₹{sell_target:,.2f}/unit)</div>'
                    f'<div style="display:flex;gap:24px">'
                    f'<div><div style="font-size:0.72rem;opacity:0.5">Gross profit</div>'
                    f'<div>{fmt_money(gross_profit)}</div></div>'
                    f'<div><div style="font-size:0.72rem;opacity:0.5">Sell charges</div>'
                    f'<div>−{fmt_money(sell_ch["total"])}</div></div>'
                    f'<div><div style="font-size:0.72rem;opacity:0.5">Net profit</div>'
                    f'<div style="color:{p_col};font-weight:600">{fmt_money(net_profit)} '
                    f'({net_pct:+.2f}%)</div></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

                if st.button(
                    "✅ Review & Buy", key=f"sug_buy_{s['name']}", use_container_width=True, type="primary"
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


_SH_BATCH = 50


def page_sell_history() -> None:
    st.markdown('<h2 style="margin-top:0">📜 Sell History</h2>', unsafe_allow_html=True)

    # ── Date filter + page size ───────────────────────────────────────────────
    if "sh_filter_gen" not in st.session_state:
        st.session_state["sh_filter_gen"] = 0
    _gen = st.session_state["sh_filter_gen"]

    fc1, fc2, fc3, fc4 = st.columns([2, 2, 1, 1])
    sh_from = fc1.date_input("From", value=None, key=f"sh_filter_from_{_gen}",
                             label_visibility="collapsed", help="Filter from date")
    sh_to   = fc2.date_input("To",   value=None, key=f"sh_filter_to_{_gen}",
                             label_visibility="collapsed", help="Filter to date")
    fc1.caption("From date")
    fc2.caption("To date")

    _SH_PAGE_OPTIONS = [10, 20, 50, 100]
    _sh_default = int(user.defaultPageSize) if int(user.defaultPageSize) in _SH_PAGE_OPTIONS else _SH_BATCH
    sh_batch = fc4.selectbox("Page size", _SH_PAGE_OPTIONS,
                             index=_SH_PAGE_OPTIONS.index(st.session_state.get("sh_batch", _sh_default)),
                             key="sh_batch_sel", label_visibility="collapsed",
                             help="Records per page")
    fc4.caption("Page size")
    if sh_batch != st.session_state.get("sh_batch", _sh_default):
        st.session_state["sh_batch"] = sh_batch
        for k in list(st.session_state.keys()):
            if k.startswith("sh_df") or k.startswith("sh_cursor") \
                    or k.startswith("sh_has_more") or k.startswith("sh_total"):
                st.session_state.pop(k)
        st.rerun()
    sh_batch = st.session_state.get("sh_batch", _sh_default)

    sh_filter_active = sh_from is not None or sh_to is not None
    if fc3.button("✕ Clear", key="sh_filter_clear", disabled=not sh_filter_active, use_container_width=True):
        st.session_state["sh_filter_gen"] += 1
        for k in list(st.session_state.keys()):
            if k.startswith("sh_df") or k.startswith("sh_cursor") \
                    or k.startswith("sh_has_more") or k.startswith("sh_total") \
                    or k == "sh_filter_key":
                del st.session_state[k]
        st.rerun()

    if sh_filter_active:
        from_s = sh_from.isoformat() if sh_from else "1900-01-01"
        to_s   = sh_to.isoformat()   if sh_to   else "2999-12-31"
        fkey   = f"{from_s}_{to_s}"
        if st.session_state.get("sh_filter_key") != fkey:
            for k in list(st.session_state.keys()):
                if k.startswith("sh_df") or k.startswith("sh_cursor") \
                        or k.startswith("sh_has_more") or k.startswith("sh_total"):
                    del st.session_state[k]
            st.session_state["sh_filter_key"] = fkey
    else:
        from_s = to_s = None
        if st.session_state.get("sh_filter_key") is not None:
            st.session_state.pop("sh_filter_key", None)
            for k in list(st.session_state.keys()):
                if k.startswith("sh_df") or k.startswith("sh_cursor") \
                        or k.startswith("sh_has_more") or k.startswith("sh_total"):
                    st.session_state.pop(k)

    # ── Load first page if not cached ────────────────────────────────────────
    if "sh_df" not in st.session_state:
        if from_s and to_s:
            df, cursor = dm.fetch_sells_in_range(from_s, to_s, sh_batch)
            total = dm.count_in_range("sells", "sellDate", from_s, to_s)
        else:
            df, cursor = dm.fetch_sells_page(sh_batch)
            total = dm.count_collection("sells")
        st.session_state["sh_df"]       = df
        st.session_state["sh_cursor"]   = cursor
        st.session_state["sh_has_more"] = cursor is not None
        st.session_state["sh_total"]    = total

    sells    = st.session_state["sh_df"]
    loaded   = len(sells)
    total    = st.session_state.get("sh_total", loaded)
    has_more = st.session_state.get("sh_has_more", False)

    if sells.empty:
        st.info("No sell transactions found." if sh_filter_active else "No sell transactions yet.")
        return

    view = sells.copy()
    q  = view["quantity"].astype(float)
    sp = view["sellPrice"].astype(float)
    ap = view["averagePurchasePrice"].astype(float)
    view["grossPL"] = (sp - ap) * q
    view["netPL"] = (
        view["grossPL"]
        - view["brokerageCharges"].astype(float)
        - view["tax"].astype(float)
        - view["dividendPaidToSelf"].astype(float)
    )

    # ── Summary cards ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    label_sfx = f" (of {total})" if has_more else ""
    c1.markdown(metric_card("Transactions shown", f"{loaded}{label_sfx}"), unsafe_allow_html=True)
    total_gross = float(view["grossPL"].sum())
    total_net   = float(view["netPL"].sum())
    c2.markdown(
        metric_card("Gross P/L" + (" ↗" if has_more else ""), fmt_money(total_gross), delta_class=pnl_class(total_gross)),
        unsafe_allow_html=True,
    )
    c3.markdown(
        metric_card("Net P/L" + (" ↗" if has_more else ""), fmt_money(total_net), delta_class=pnl_class(total_net)),
        unsafe_allow_html=True,
    )
    # Weighted avg holding time — from stamped holdingDays, weighted by investment
    _inv  = view["averagePurchasePrice"].astype(float) * view["quantity"].astype(float)
    _hd   = pd.to_numeric(view.get("holdingDays", pd.Series(dtype=float)), errors="coerce")
    _mask = _hd.notna()
    _sh_wavg = int((_hd[_mask] * _inv[_mask]).sum() / _inv[_mask].sum()) if _mask.any() and _inv[_mask].sum() > 0 else 0
    c4.markdown(metric_card("Avg Hold Time" + (" ↗" if has_more else ""), _fmt_hold_days(_sh_wavg)), unsafe_allow_html=True)
    if has_more:
        st.caption(f"↗ Showing {loaded} of {total} sells — load more below to include all records in the totals.")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Cards ────────────────────────────────────────────────────────────────
    view["_dt"] = pd.to_datetime(view["sellDate"], errors="coerce")
    view = view.sort_values("_dt", ascending=False, na_position="last").reset_index(drop=True)
    view["_label"] = view["_dt"].apply(
        lambda dt: _chat_date_label(dt) if pd.notna(dt) else "Unknown date"
    )
    counts = view["_label"].value_counts().to_dict()

    if sh_filter_active:
        st.caption(f"{loaded} sells in selected date range")
    else:
        st.caption(f"Showing {loaded} of {total} sells (newest first)")

    last_label = None
    for _, row in view.iterrows():
        label = row["_label"]
        if label != last_label:
            n = counts.get(label, 0)
            _render_date_separator(f"{label} · {n} {'sell' if n == 1 else 'sells'}")
            last_label = label

        gross = float(row["grossPL"])
        net   = float(row["netPL"])
        brok  = float(row["brokerageCharges"])
        tax   = float(row["tax"])
        div   = float(row["dividendPaidToSelf"])
        qty        = int(row["quantity"])
        avg_buy    = float(row["averagePurchasePrice"])
        sell_p     = float(row["sellPrice"])
        invested   = avg_buy * qty
        sell_val   = sell_p * qty
        fees_total = brok + tax + div
        try:
            _held_days = int(float(row["holdingDays"]))
        except Exception:
            try:
                _sell_dt = pd.to_datetime(row["sellDate"]).date()
                _buy_dt  = pd.to_datetime(row["lastPurchaseDate"]).date()
                _held_days = max(0, (_sell_dt - _buy_dt).days)
            except Exception:
                _held_days = 0

        with st.container(border=True):
            # ── Header ────────────────────────────────────────────────────
            hc1, hc2 = st.columns([4, 1])
            hc1.markdown(
                f'**{row["etfName"]}** &nbsp; {badge(str(row["etfType"]), "equity")}'
                f' &nbsp;<span class="text-muted" style="font-size:0.78rem">held {_fmt_hold_days(_held_days)}</span>',
                unsafe_allow_html=True,
            )
            hc2.markdown(
                f'<div class="text-muted" style="font-size:0.8rem;text-align:right">{row["sellDate"]}</div>',
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            # ── Formula: INVESTED → RECEIVED − CHARGES = NET ─────────────
            b, arr1, s, arr2, c, arr3, n = st.columns([4, 1, 4, 1, 3, 1, 3])

            b.markdown(
                f'<div style="background:var(--secondary-background-color);border-radius:10px;padding:12px 14px">'
                f'<div class="text-muted" style="font-size:0.7rem;letter-spacing:.06em;margin-bottom:4px">INVESTED</div>'
                f'<div style="font-size:0.85rem">{qty} units &times; ₹{avg_buy:,.2f}</div>'
                f'<div style="font-size:1.15rem;font-weight:700;margin-top:2px">{fmt_money(invested)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            arr1.markdown(
                '<div style="text-align:center;font-size:1.4rem;padding-top:22px;opacity:0.4">→</div>',
                unsafe_allow_html=True,
            )
            s.markdown(
                f'<div style="background:var(--secondary-background-color);border-radius:10px;padding:12px 14px">'
                f'<div class="text-muted" style="font-size:0.7rem;letter-spacing:.06em;margin-bottom:4px">RECEIVED</div>'
                f'<div style="font-size:0.85rem">{qty} units &times; ₹{sell_p:,.2f}</div>'
                f'<div style="font-size:1.15rem;font-weight:700;margin-top:2px">{fmt_money(sell_val)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            arr2.markdown(
                '<div style="text-align:center;font-size:1.4rem;padding-top:22px;opacity:0.4">−</div>',
                unsafe_allow_html=True,
            )
            c.markdown(
                f'<div style="background:var(--secondary-background-color);border-radius:10px;padding:12px 14px">'
                f'<div class="text-muted" style="font-size:0.7rem;letter-spacing:.06em;margin-bottom:4px">CHARGES</div>'
                f'<div style="font-size:0.78rem;line-height:1.6">'
                f'Brok {fmt_money(brok,2)} &nbsp;·&nbsp; Tax {fmt_money(tax,2)} &nbsp;·&nbsp; Div {fmt_money(div,2)}</div>'
                f'<div style="font-size:1.15rem;font-weight:700;margin-top:2px">{fmt_money(fees_total)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            net_color = "#2ecc71" if net >= 0 else "#e74c3c"
            arr3.markdown(
                '<div style="text-align:center;font-size:1.4rem;padding-top:22px;opacity:0.4">=</div>',
                unsafe_allow_html=True,
            )
            n.markdown(
                f'<div style="border:2px solid {net_color};border-radius:10px;padding:12px 14px">'
                f'<div class="text-muted" style="font-size:0.7rem;letter-spacing:.06em;margin-bottom:4px">NET P/L</div>'
                f'<div style="font-size:0.85rem;opacity:0.6">gross {fmt_money(gross)}</div>'
                f'<div style="font-size:1.25rem;font-weight:700;color:{net_color};margin-top:2px">{fmt_money(net)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    if has_more:
        remaining  = total - loaded
        next_batch = min(sh_batch, remaining)
        if st.button(f"⬇ Load {next_batch} more  ({loaded} of {total})", key="sh_load_more", use_container_width=True):
            cursor = st.session_state.get("sh_cursor")
            if from_s and to_s:
                new_df, new_cursor = dm.fetch_sells_in_range(from_s, to_s, sh_batch, cursor)
            else:
                new_df, new_cursor = dm.fetch_sells_page(sh_batch, cursor)
            st.session_state["sh_df"] = pd.concat(
                [st.session_state["sh_df"], new_df], ignore_index=True
            )
            st.session_state["sh_cursor"]   = new_cursor
            st.session_state["sh_has_more"] = new_cursor is not None
            st.rerun()


def page_reports() -> None:
    st.markdown('<h2 style="margin-top:0">📊 Reports</h2>', unsafe_allow_html=True)

    holdings = dm.load_holdings()
    _s = dm.load_stats()  # load once — reused for summary and avg hold days
    m = dm.compute_money_summary_from_stats(user, holdings, etfs, _stats=_s)

    # Derive avg hold days from the same stats doc — no second Firestore read
    _open_inv   = float(_s.get("openInvTotal", 0) or 0)
    _open_dsum  = float(_s.get("openInvDateSum", 0) or 0)
    _today_ep   = (date.today() - date(1970, 1, 1)).days
    avg_hold_days = int(_today_ep - _open_dsum / _open_inv) if _open_inv > 0 else 0

    # ── Chapter 1 — The headline ──────────────────────────────────────────
    deployed      = m["costBasis"] + m["buyTotalCharges"]
    total_return  = m["unrealizedPL"] + m["sellNetPL"]
    total_ret_pct = (total_return / deployed * 100) if deployed else 0.0
    pnl_col_h     = "#2ecc71" if total_return >= 0 else "#e74c3c"
    direction     = "up" if total_return >= 0 else "down"
    ret_sign      = "+" if total_return >= 0 else "−"

    st.markdown(
        f'<div style="background:var(--secondary-background-color);border-radius:12px;'
        f'padding:24px 28px;margin-bottom:4px">'
        f'<div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.09em;'
        f'opacity:0.5;margin-bottom:8px">Your portfolio</div>'
        f'<div style="font-size:1.55rem;font-weight:700;line-height:1.3">'
        f'You\'ve deployed <span style="color:#3b9ddd">{fmt_money(deployed, 0)}</span> '
        f'into the market. Currently <span style="color:{pnl_col_h}">{direction}: '
        f'{ret_sign}₹{abs(total_return):,.0f} ({abs(total_ret_pct):.2f}%)</span>'
        f'</div>'
        f'<div style="margin-top:10px;font-size:0.85rem;opacity:0.6">'
        f'{fmt_money(m["costBasis"], 0)} in holdings &nbsp;·&nbsp; '
        f'{fmt_money(m["remainingCash"], 0)} cash remaining &nbsp;·&nbsp; '
        f'avg hold {avg_hold_days}d'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Chapter 2 — How the money is working ─────────────────────────────
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    unreal_sign = "+" if m["unrealizedPL"] >= 0 else "−"
    unreal_pct  = (m["unrealizedPL"] / m["costBasis"] * 100) if m["costBasis"] else 0.0
    real_sign   = "+" if m["sellNetPL"] >= 0 else "−"

    col_left, col_right = st.columns(2)
    with col_left:
        with st.container(border=True):
            st.markdown(
                '<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:.09em;'
                'opacity:0.45;margin-bottom:10px">Still in market</div>',
                unsafe_allow_html=True,
            )
            st.markdown(metric_card("Cost basis", fmt_money(m["costBasis"], 2)), unsafe_allow_html=True)
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            st.markdown(
                metric_card(
                    "Worth now", fmt_money(m["currentValue"], 2),
                    delta=f"{unreal_sign}₹{abs(m['unrealizedPL']):,.2f} ({abs(unreal_pct):.2f}%)",
                    delta_class=pnl_class(m["unrealizedPL"]),
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="margin-top:8px;font-size:0.8rem;opacity:0.55">'
                f'{len(holdings)} open position{"s" if len(holdings) != 1 else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_right:
        with st.container(border=True):
            st.markdown(
                '<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:.09em;'
                'opacity:0.45;margin-bottom:10px">Already sold</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                metric_card(f"Gross sold ({m['sellCount']} sells)", fmt_money(m["sellGross"], 2)),
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            st.markdown(
                metric_card(
                    "Net profit after fees", fmt_money(m["sellNetPL"], 2),
                    delta=f"{real_sign}₹{abs(m['sellNetPL']):,.2f}",
                    delta_class=pnl_class(m["sellNetPL"]),
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="margin-top:8px;font-size:0.8rem;opacity:0.55">'
                f'Cash received back: {fmt_money(m["sellInflow"], 2)}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Chapter 3 — What it cost you ─────────────────────────────────────
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section("What it cost you")

    total_fees   = m["feesPaidTotal"] + m["chargesTotal"]
    fee_drag_pct = (total_fees / deployed * 100) if deployed else 0.0

    st.markdown(
        f'<div style="font-size:1rem;margin-bottom:14px;line-height:1.6">'
        f'You paid <b>{fmt_money(total_fees, 2)}</b> in total fees — '
        f'<b>{fee_drag_pct:.2f}%</b> of deployed capital. '
        f'Break-even on a round-trip trade: <b>~0.33%</b>.'
        f'</div>',
        unsafe_allow_html=True,
    )
    f1, f2, f3 = st.columns(3)
    f1.markdown(
        metric_card(f"Buy fees ({m['buyCount']} buys)", fmt_money(m["buyTotalCharges"], 2)),
        unsafe_allow_html=True,
    )
    f2.markdown(
        metric_card(f"Sell fees ({m['sellCount']} sells)", fmt_money(m["sellFeesTotal"], 2)),
        unsafe_allow_html=True,
    )
    f3.markdown(
        metric_card("Demat AMC & charges", fmt_money(m["chargesTotal"], 2)),
        unsafe_allow_html=True,
    )
    with st.expander("Fee breakdown detail"):
        fees_detail = [
            ("Brokerage on buys",     m["buyBrokerage"]),
            ("Statutory on buys",     m["buyTax"]),
            ("Brokerage on sells",    m["sellBrokerage"]),
            ("Statutory on sells",    m["sellTax"]),
            ("Dividend paid to self", m["sellDividend"]),
            ("Demat AMC & charges",   m["chargesTotal"]),
        ]
        dc = st.columns(len(fees_detail))
        for col, (label, val) in zip(dc, fees_detail):
            col.markdown(metric_card(label, fmt_money(val, 2)), unsafe_allow_html=True)

    # ── Chapter 4 — Verify the totals ────────────────────────────────────
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    section("Verify the totals")

    def _lrow(label, amount, bold=False, indent=False, separator=False):
        prefix = "&nbsp;&nbsp;&nbsp;" if indent else ""
        w      = "700" if bold else "400"
        sign   = "−" if amount < 0 else ("+" if amount > 0 and not bold else "")
        color  = "inherit"
        if bold and abs(amount) > 0:
            color = "#2ecc71" if amount > 0 else "#e74c3c"
        top = "border-top:1px solid var(--secondary-background-color);margin-top:6px;padding-top:6px;" if separator else ""
        return (
            f'<div style="display:flex;justify-content:space-between;padding:3px 0;{top}">'
            f'<span style="font-weight:{w};opacity:{"1" if bold else "0.85"}">{prefix}{label}</span>'
            f'<span style="font-weight:{w};color:{color};font-variant-numeric:tabular-nums">'
            f'{sign}₹{abs(amount):,.4f}</span></div>'
        )

    diff      = m["reconcileDiff"]
    diff_sign = "+" if diff >= 0 else "−"
    diff_col  = "#2ecc71" if abs(diff) < 0.01 else "#e74c3c"
    diff_icon = "✓" if abs(diff) < 0.01 else "✗"

    with st.container(border=True):
        st.markdown(
            _lrow("Initial deposit",             m["initialDeposit"])
            + _lrow("+ Profit from sells (gross)", m["sellGrossPL"],    indent=True)
            + _lrow("− Fees on buys",             -m["buyTotalCharges"], indent=True)
            + _lrow("− Fees on sells",            -m["sellFeesTotal"],   indent=True)
            + _lrow("− Dividend paid to self",    -m["sellDividend"],    indent=True)
            + _lrow("= Expected total",            m["expectedBalance"],  bold=True, separator=True)
            + _lrow("Cash remaining + holdings",   m["accountBalance"],  indent=True)
            + f'<div style="display:flex;justify-content:space-between;padding:3px 0;'
              f'border-top:1px solid var(--secondary-background-color);margin-top:6px;padding-top:6px;">'
              f'<span style="font-weight:700">Difference</span>'
              f'<span style="font-weight:700;color:{diff_col};font-variant-numeric:tabular-nums">'
              f'{diff_sign}₹{abs(diff):,.4f} &nbsp;{diff_icon}</span></div>',
            unsafe_allow_html=True,
        )

    if abs(diff) < 0.01:
        st.success(f"✅ Totals match — cash + holdings = expected ({fmt_money(m['accountBalance'], 2)}).")
    else:
        st.error(
            f"⚠️ Totals off by ₹{diff:+.4f}. "
            "Legacy holdings may have been backfilled with charges never deducted from Remaining Amount."
        )
        if st.button("🔧 Fix reconciliation drift", key="fix_reconcile_btn"):
            _guard = "_op_done_fix_reconcile"
            if not st.session_state.get(_guard):
                st.session_state[_guard] = True
                adj = m["reconcileDiff"]
                updated_user = copy.copy(st.session_state.user)
                updated_user.remainingAmount -= adj
                dm.save_user(updated_user)
                st.session_state.user = updated_user
                st.toast(f"✅ Remaining Amount adjusted by ₹{-adj:+.4f} — books balanced.", icon="🔧")
                del st.session_state[_guard]
                st.rerun()

    # ── Chapter 5 — Month by month ───────────────────────────────────────
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    with st.expander("Month by month"):
        monthly = dm.money_by_month(dm.load_buys(), dm.load_sells())
        if monthly.empty:
            st.info("No transactions yet.")
        else:
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

    if len(holdings) > 20:
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

        section("Display")
        _PS_OPTIONS = [10, 20, 50, 100]
        default_page_size = st.selectbox(
            "Default page size (Transactions & Sell History)",
            _PS_OPTIONS,
            index=_PS_OPTIONS.index(int(user.defaultPageSize)) if int(user.defaultPageSize) in _PS_OPTIONS else 1,
            help="How many records to load per page by default. You can still change it on each page.",
        )

        section("Demat AMC (Auto-deduction)")
        amc_amount = st.number_input(
            "Monthly AMC charge (₹)",
            min_value=0.0, value=float(user.amcAmount), step=0.01, format="%.2f",
            help="Auto-deducted from investment + remaining every 30 days. Set to 0 to disable.",
        )
        if user.lastAmcDate:
            st.caption(f"Last deducted: **{user.lastAmcDate}** · Next: 30 days after that")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        if st.form_submit_button("💾 Save", use_container_width=True, type="primary"):
            if remaining < 0:
                st.error("Remaining amount cannot be negative.")
                return
            u = dm.UserSettings(
                userName=name,
                investment=float(investment),
                remainingAmount=float(remaining),
                taxPercentage=0.0,
                brokeragePercentage=0.0,
                dividendPercentage=float(dividend_pct),
                sellProfitTarget=float(sell_target),
                buyInDipThreshold=float(buy_dip),
                amcAmount=float(amc_amount),
                lastAmcDate=user.lastAmcDate,
                totalDeposited=user.totalDeposited,
                defaultPageSize=int(default_page_size),
            )
            dm.save_user(u)
            st.session_state.user = u
            st.toast("💾 Settings saved", icon="✅")
            st.rerun()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    section("Deposit / Withdraw / Charges")
    tab_dep, tab_wd, tab_ch = st.tabs(["➕ Deposit", "➖ Withdraw", "🏦 Kotak Charges"])

    # Reset flags are set on successful submit, applied on the NEXT run before widgets render
    if st.session_state.pop("_reset_dep", False):
        st.session_state.dep_amt = 0.0
    if st.session_state.pop("_reset_wd", False):
        st.session_state.wd_amt = 0.0
    if st.session_state.pop("_reset_ch", False):
        st.session_state.ch_amt = 0.0
    if "dep_amt" not in st.session_state:
        st.session_state.dep_amt = 0.0
    if "wd_amt" not in st.session_state:
        st.session_state.wd_amt = 0.0
    if "ch_amt" not in st.session_state:
        st.session_state.ch_amt = 0.0

    with tab_dep:
        with st.form("deposit_form"):
            amount = st.number_input(
                "Amount to deposit (₹)", min_value=0.0, step=100.0, format="%.2f",
                help="Added to both total investment and remaining cash.",
                key="dep_amt",
            )
            if amount > 0:
                st.info(
                    f"₹{user.investment:,.2f} → **₹{user.investment + amount:,.2f}** (investment)  \n"
                    f"₹{user.remainingAmount:,.2f} → **₹{user.remainingAmount + amount:,.2f}** (remaining cash)"
                )
            if st.form_submit_button("➕ Deposit", use_container_width=True, type="primary"):
                if amount <= 0:
                    st.error("Enter an amount greater than ₹0.")
                else:
                    u = dm.UserSettings(
                        userName=user.userName,
                        investment=user.investment + amount,
                        remainingAmount=user.remainingAmount + amount,
                        taxPercentage=user.taxPercentage,
                        brokeragePercentage=user.brokeragePercentage,
                        dividendPercentage=user.dividendPercentage,
                        sellProfitTarget=user.sellProfitTarget,
                        buyInDipThreshold=user.buyInDipThreshold,
                        amcAmount=user.amcAmount,
                        lastAmcDate=user.lastAmcDate,
                        totalDeposited=user.totalDeposited + amount,
                        defaultPageSize=user.defaultPageSize,
                    )
                    dm.save_user(u)
                    dm.save_cashflow("deposit", amount)
                    st.session_state.user = u
                    st.session_state["_reset_dep"] = True  # cleared next run, before widget renders
                    st.toast(f"✅ ₹{amount:,.2f} deposited — investment now ₹{u.investment:,.2f}", icon="💰")
                    st.rerun()

    with tab_wd:
        with st.form("withdraw_form"):
            max_wd = float(user.remainingAmount)
            st.caption(f"Available to withdraw: **₹{max_wd:,.2f}** (cash not deployed in market)")
            amount = st.number_input(
                "Amount to withdraw (₹)", min_value=0.0, max_value=max_wd,
                step=100.0, format="%.2f",
                help="Deducted from both total investment and remaining cash. Cannot exceed available cash.",
                key="wd_amt",
            )
            if amount > 0:
                st.info(
                    f"₹{user.investment:,.2f} → **₹{user.investment - amount:,.2f}** (investment)  \n"
                    f"₹{user.remainingAmount:,.2f} → **₹{user.remainingAmount - amount:,.2f}** (remaining cash)"
                )
            if st.form_submit_button("➖ Withdraw", use_container_width=True, type="primary"):
                if amount <= 0:
                    st.error("Enter an amount greater than ₹0.")
                elif amount > max_wd:
                    st.error(f"Cannot withdraw ₹{amount:,.2f} — only ₹{max_wd:,.2f} is available as cash.")
                else:
                    u = dm.UserSettings(
                        userName=user.userName,
                        investment=user.investment - amount,
                        remainingAmount=user.remainingAmount - amount,
                        taxPercentage=user.taxPercentage,
                        brokeragePercentage=user.brokeragePercentage,
                        dividendPercentage=user.dividendPercentage,
                        sellProfitTarget=user.sellProfitTarget,
                        buyInDipThreshold=user.buyInDipThreshold,
                        amcAmount=user.amcAmount,
                        lastAmcDate=user.lastAmcDate,
                        totalDeposited=user.totalDeposited - amount,
                        defaultPageSize=user.defaultPageSize,
                    )
                    dm.save_user(u)
                    dm.save_cashflow("withdrawal", amount)
                    st.session_state.user = u
                    st.session_state["_reset_wd"] = True  # cleared next run, before widget renders
                    st.toast(f"✅ ₹{amount:,.2f} withdrawn — investment now ₹{u.investment:,.2f}", icon="🏦")
                    st.rerun()

    with tab_ch:
        st.caption(
            "Record charges already deducted by Kotak — Demat AMC, or any other platform fee. "
            "Use the date field to backfill past charges."
        )
        with st.form("charges_form"):
            ca, cb = st.columns(2)
            amount = ca.number_input(
                "Charge amount (₹)", min_value=0.0, step=1.0, format="%.2f",
                help="e.g. ₹18.88 for monthly Demat AMC.",
                key="ch_amt",
            )
            charge_date = cb.date_input(
                "Date debited",
                value=datetime.today().date(),
                help="Use the actual date Kotak debited the charge.",
                key="ch_date",
            )
            cr, cd = st.columns(2)
            charge_type = cr.selectbox(
                "Charge type",
                ["AMC", "DP Charge", "Other"],
                key="ch_type",
            )
            description = cd.text_input(
                "Description (optional)",
                placeholder="e.g. Demat AMC for April 2026",
                key="ch_desc",
            )
            if amount > 0:
                st.info(
                    f"₹{user.investment:,.2f} → **₹{user.investment - amount:,.2f}** (investment)  \n"
                    f"₹{user.remainingAmount:,.2f} → **₹{user.remainingAmount - amount:,.2f}** (remaining cash)"
                )
            if st.form_submit_button("💸 Record Charge", use_container_width=True, type="primary"):
                if amount <= 0:
                    st.error("Enter an amount greater than ₹0.")
                else:
                    desc = description.strip() or f"Demat AMC — {charge_date.isoformat()}"
                    u = dm.UserSettings(
                        userName=user.userName,
                        investment=user.investment - amount,
                        remainingAmount=user.remainingAmount - amount,
                        taxPercentage=user.taxPercentage,
                        brokeragePercentage=user.brokeragePercentage,
                        dividendPercentage=user.dividendPercentage,
                        sellProfitTarget=user.sellProfitTarget,
                        buyInDipThreshold=user.buyInDipThreshold,
                        amcAmount=user.amcAmount,
                        lastAmcDate=user.lastAmcDate,
                        totalDeposited=user.totalDeposited,
                        defaultPageSize=user.defaultPageSize,
                    )
                    dm.save_user(u)
                    dm.save_charge(charge_type, amount, desc, charge_date.isoformat())
                    st.session_state.user = u
                    st.session_state["_reset_ch"] = True
                    st.toast(f"✅ ₹{amount:.2f} on {charge_date.isoformat()} recorded.", icon="💸")
                    st.rerun()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    section("Password")
    _cfg = dm.load_config()
    _pwd_on = _cfg.get("passwordEnabled", True)
    _has_pwd = bool(_cfg.get("passwordHash", ""))

    if _pwd_on and _has_pwd:
        st.success("🔒 Password protection is **enabled**")
        col_a, col_b = st.columns(2)

        with col_a.popover("🔓 Disable password", use_container_width=True):
            st.warning("Anyone with the URL will be able to open the app.")
            if st.button("Confirm — disable password", type="primary", key="confirm_disable_pwd"):
                dm.save_config({"passwordEnabled": False, "passwordHash": ""})
                st.session_state.pop(_SESSION_PARAM, None)
                if _SESSION_PARAM in st.query_params:
                    del st.query_params[_SESSION_PARAM]
                st.toast("🔓 Password disabled", icon="✅")
                st.rerun()

        with col_b.popover("🔑 Change password", use_container_width=True):
            new_pwd = st.text_input("New password", type="password", key="chg_pwd_new")
            cfm_pwd = st.text_input("Confirm", type="password", key="chg_pwd_cfm")
            if st.button("Save new password", type="primary", key="chg_pwd_save"):
                if not new_pwd:
                    st.error("Password cannot be empty.")
                elif new_pwd != cfm_pwd:
                    st.error("Passwords do not match.")
                else:
                    h = hashlib.sha256(new_pwd.encode()).hexdigest()
                    dm.save_config({"passwordHash": h, "passwordEnabled": True})
                    _set_session_token(h)
                    st.toast("🔑 Password changed", icon="✅")
                    st.rerun()
    else:
        st.warning("🔓 Password protection is **disabled** — anyone with the URL can access the app.")
        with st.form("enable_pwd_form"):
            st.markdown("Set a password to re-enable protection:")
            new_pwd = st.text_input("New password", type="password")
            cfm_pwd = st.text_input("Confirm", type="password")
            if st.form_submit_button("🔒 Enable password", type="primary", use_container_width=True):
                if not new_pwd:
                    st.error("Password cannot be empty.")
                elif new_pwd != cfm_pwd:
                    st.error("Passwords do not match.")
                else:
                    h = hashlib.sha256(new_pwd.encode()).hexdigest()
                    dm.save_config({"passwordHash": h, "passwordEnabled": True})
                    _set_session_token(h)
                    st.toast("🔒 Password enabled", icon="✅")
                    st.rerun()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section("Maintenance")
    with st.container(border=True):
        st.markdown("**🔄 Rebuild summary stats**")
        st.caption(
            "Recomputes the `meta/stats` aggregate from all transactions. "
            "Run this once after upgrading, or if the Avg Hold Time metric looks wrong."
        )
        if st.button("🔄 Rebuild stats", type="secondary", key="rebuild_stats_btn"):
            with st.spinner("Scanning all transactions…"):
                s = dm.rebuild_stats()
            st.success(
                f"Done — {s['buyCount']} buys · {s['sellCount']} sells · "
                f"openInvTotal ₹{s['openInvTotal']:,.0f}"
            )

    with st.container(border=True):
        st.markdown("**📅 Backfill sell holding days**")
        st.caption(
            "Computes the exact weighted-avg holding time for all existing sell records "
            "and stamps it permanently. Run once after upgrading."
        )
        if st.button("📅 Backfill holding days", type="secondary", key="backfill_hd_btn"):
            with st.spinner("Computing holding days for existing sells…"):
                n = dm.backfill_sell_holding_days()
            st.success(f"Done — updated {n} sell record(s).")

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


@st.dialog("Edit Sell Price")
def _edit_sell_dialog(sell_id: str, name: str, qty: int, old_price: float) -> None:
    old_total = old_price * qty
    st.markdown(f"**✏️ {name}** — {qty} units", unsafe_allow_html=True)
    st.caption(f"Current recorded price: ₹{old_price:,.4f}/unit  |  Total: ₹{old_total:,.2f}")
    st.markdown("---")
    new_price = st.number_input(
        "Sell price per unit (₹)",
        min_value=0.0001,
        value=round(old_price, 4),
        step=0.0001,
        format="%.4f",
        help="Enter the exact per-unit sell price. The app will compute total and recalculate charges.",
    )
    new_total = new_price * qty
    if abs(new_price - old_price) > 0.00001:
        st.info(f"New total: ₹{new_total:,.2f}  |  Difference: ₹{new_total - old_total:+.2f}")
    c1, c2 = st.columns(2)
    if c1.button("💾 Save", type="primary", use_container_width=True, key="edit_sell_save"):
        _guard = f"_edit_sell_{sell_id}"
        if not st.session_state.get(_guard):
            st.session_state[_guard] = True
            try:
                dm.update_sell_price(sell_id, new_total)
                st.toast(f"✅ Updated to ₹{new_price:.4f}/unit", icon="✏️")
                del st.session_state[_guard]
                st.rerun()
            except Exception as e:
                del st.session_state[_guard]
                st.error(str(e))
    if c2.button("Cancel", use_container_width=True, key="edit_sell_cancel"):
        st.rerun()


@st.dialog("Edit Buy Price")
def _edit_buy_dialog(buy_id: str, name: str, qty: int, old_price: float) -> None:
    old_total = old_price * qty
    st.markdown(f"**✏️ {name}** — {qty} units", unsafe_allow_html=True)
    st.caption(f"Current recorded price: ₹{old_price:,.4f}/unit  |  Total: ₹{old_total:,.2f}")
    st.markdown("---")
    new_price = st.number_input(
        "Buy price per unit (₹)",
        min_value=0.0001,
        value=round(old_price, 4),
        step=0.0001,
        format="%.4f",
        help="Enter the exact per-unit buy price. The app will compute total, recalculate charges, and adjust your balance.",
    )
    new_total = new_price * qty
    if abs(new_price - old_price) > 0.00001:
        st.info(f"New total: ₹{new_total:,.2f}  |  Difference: ₹{new_total - old_total:+.2f}")
    c1, c2 = st.columns(2)
    if c1.button("💾 Save", type="primary", use_container_width=True, key="edit_buy_save"):
        _guard = f"_edit_buy_{buy_id}"
        if not st.session_state.get(_guard):
            st.session_state[_guard] = True
            try:
                updated_user = dm.update_buy_price(st.session_state.user, buy_id, new_total)
                st.session_state.user = updated_user
                st.toast(f"✅ Updated to ₹{new_price:.4f}/unit", icon="✏️")
                del st.session_state[_guard]
                st.rerun()
            except Exception as e:
                del st.session_state[_guard]
                st.error(str(e))
    if c2.button("Cancel", use_container_width=True, key="edit_buy_cancel"):
        st.rerun()


_TXN_COL      = {"buy": "buys",    "sell": "sells",   "charge": "charges", "cash": "cashflow"}
_TXN_DATE_COL = {"buy": "buyDate", "sell": "sellDate","charge": "chargeDate","cash": "date"}


def _ensure_txn_cache(kind: str, from_str: str | None = None, to_str: str | None = None, batch: int = 20) -> None:
    """Load first page + total count into session state if not already loaded."""
    df_key       = f"txn_df_{kind}"
    cursor_key   = f"txn_cursor_{kind}"
    has_more_key = f"txn_has_more_{kind}"
    total_key    = f"txn_total_{kind}"
    col        = _TXN_COL[kind]
    date_field = _TXN_DATE_COL[kind]
    if df_key not in st.session_state:
        if from_str and to_str:
            fetch_range = {
                "buy":    dm.fetch_buys_in_range,
                "sell":   dm.fetch_sells_in_range,
                "charge": dm.fetch_charges_in_range,
                "cash":   dm.fetch_cashflow_in_range,
            }[kind]
            df, cursor = fetch_range(from_str, to_str, batch)
            total = dm.count_in_range(col, date_field, from_str, to_str)
        else:
            fetch_page = {
                "buy":    dm.fetch_buys_page,
                "sell":   dm.fetch_sells_page,
                "charge": dm.fetch_charges_page,
                "cash":   dm.fetch_cashflow_page,
            }[kind]
            df, cursor = fetch_page(batch)
            total = dm.count_collection(col)
        st.session_state[df_key]       = df
        st.session_state[cursor_key]   = cursor
        st.session_state[has_more_key] = cursor is not None
        st.session_state[total_key]    = total


def page_transactions() -> None:
    components.html(
        "<script>window.parent.document.querySelector('[data-testid=\"stMain\"]').scrollTo(0, 0);</script>",
        height=0,
    )
    st.markdown('<h2 style="margin-top:0">🔄 Transactions & Reverse</h2>', unsafe_allow_html=True)
    st.caption(
        "Made a mistake in the app? Reverse any buy or sell here — the app will restore "
        "your holdings, cash, and investment trackers to the exact state before the action."
    )

    # ── Date filter + page size ───────────────────────────────────────────────
    if "txn_filter_gen" not in st.session_state:
        st.session_state["txn_filter_gen"] = 0
    _gen = st.session_state["txn_filter_gen"]

    fc1, fc2, fc3, fc4 = st.columns([2, 2, 1, 1])
    filter_from = fc1.date_input("From", value=None, key=f"txn_filter_from_{_gen}",
                                 label_visibility="collapsed", help="Filter from date")
    filter_to   = fc2.date_input("To",   value=None, key=f"txn_filter_to_{_gen}",
                                 label_visibility="collapsed", help="Filter to date")
    fc1.caption("From date")
    fc2.caption("To date")

    _TXN_PAGE_OPTIONS = [10, 20, 50, 100]
    _txn_default = int(user.defaultPageSize) if int(user.defaultPageSize) in _TXN_PAGE_OPTIONS else _TXN_BATCH
    txn_batch = fc4.selectbox("Page size", _TXN_PAGE_OPTIONS,
                              index=_TXN_PAGE_OPTIONS.index(st.session_state.get("txn_batch", _txn_default)),
                              key="txn_batch_sel", label_visibility="collapsed",
                              help="Records per page")
    fc4.caption("Page size")
    if txn_batch != st.session_state.get("txn_batch", _txn_default):
        st.session_state["txn_batch"] = txn_batch
        for k in list(st.session_state.keys()):
            if k.startswith("txn_df_") or k.startswith("txn_cursor_") \
                    or k.startswith("txn_has_more_") or k.startswith("txn_total_"):
                st.session_state.pop(k)
        st.rerun()
    txn_batch = st.session_state.get("txn_batch", _txn_default)

    date_filter_active = filter_from is not None or filter_to is not None
    if fc3.button("✕ Clear", key="txn_filter_clear", disabled=not date_filter_active, use_container_width=True):
        st.session_state["txn_filter_gen"] += 1
        # Also clear the txn cache so unfiltered data reloads fresh
        for k in list(st.session_state.keys()):
            if k.startswith("txn_df_") or k.startswith("txn_cursor_") \
                    or k.startswith("txn_has_more_") or k.startswith("txn_total_") \
                    or k == "txn_filter_key":
                del st.session_state[k]
        st.rerun()

    if date_filter_active:
        from_str = filter_from.isoformat() if filter_from else "1900-01-01"
        to_str   = filter_to.isoformat()   if filter_to   else "2999-12-31"
        filter_key = f"{from_str}_{to_str}"
        # Reset filtered cache when the date range changes
        if st.session_state.get("txn_filter_key") != filter_key:
            for k in list(st.session_state.keys()):
                if k.startswith("txn_df_") or k.startswith("txn_cursor_") \
                        or k.startswith("txn_has_more_") or k.startswith("txn_total_"):
                    del st.session_state[k]
            st.session_state["txn_filter_key"] = filter_key
    else:
        from_str = to_str = filter_key = None
        if st.session_state.get("txn_filter_key") is not None:
            st.session_state.pop("txn_filter_key", None)
            for k in list(st.session_state.keys()):
                if k.startswith("txn_df_") or k.startswith("txn_cursor_") \
                        or k.startswith("txn_has_more_") or k.startswith("txn_total_"):
                    st.session_state.pop(k)

    tab_buys, tab_sells, tab_charges, tab_cash = st.tabs(["🟢 Buys", "🔴 Sells", "🏦 Charges", "💰 Deposits & Withdrawals"])

    with tab_buys:
        if date_filter_active:
            _ensure_txn_cache("buy", from_str=from_str, to_str=to_str, batch=txn_batch)
        else:
            _ensure_txn_cache("buy", batch=txn_batch)
        buys = st.session_state["txn_df_buy"]
        if buys.empty:
            st.info(
                "No buy records found." if date_filter_active else
                "No buy records yet. Buys made before this feature was added can't be reversed "
                "through the log — use **Home → Sell** if you need to remove a legacy holding."
            )
        else:
            _render_transaction_list(buys, kind="buy", filtered=date_filter_active)

    with tab_sells:
        if date_filter_active:
            _ensure_txn_cache("sell", from_str=from_str, to_str=to_str, batch=txn_batch)
        else:
            _ensure_txn_cache("sell", batch=txn_batch)
        sells = st.session_state["txn_df_sell"]
        if sells.empty:
            st.info("No sell records found." if date_filter_active else "No sell records yet.")
        else:
            _render_transaction_list(sells, kind="sell", filtered=date_filter_active)

    with tab_charges:
        if date_filter_active:
            _ensure_txn_cache("charge", from_str=from_str, to_str=to_str, batch=txn_batch)
        else:
            _ensure_txn_cache("charge", batch=txn_batch)
        charges = st.session_state["txn_df_charge"]
        if charges.empty:
            st.info("No charge records found." if date_filter_active else "No charge records yet. Demat AMC will appear here once auto-deducted.")
        else:
            ch = charges.copy()
            ch["_dt"] = pd.to_datetime(ch["chargeDate"], errors="coerce")
            ch = ch.sort_values("_dt", ascending=False).reset_index(drop=True)
            loaded_ch  = len(ch)
            total_ch   = st.session_state.get("txn_total_charge", loaded_ch)
            has_more_ch = st.session_state.get("txn_has_more_charge", False)
            st.caption(f"Showing {loaded_ch} of {total_ch} charges (newest first)")
            counts_ch = ch["_dt"].apply(
                lambda dt: _chat_date_label(dt) if pd.notna(dt) else "Unknown date"
            ).value_counts().to_dict()
            last_label = None
            for _, row in ch.iterrows():
                dt = row["_dt"]
                label = _chat_date_label(dt) if pd.notna(dt) else "Unknown date"
                if label != last_label:
                    n = counts_ch.get(label, 0)
                    s = "charge" if n == 1 else "charges"
                    _render_date_separator(f"{label} · {n} {s}")
                    last_label = label
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 2])
                    c1.markdown(
                        f'**{row["description"]}**'
                        f'<div class="text-muted" style="font-size:0.75rem;margin-top:2px">{row["chargeDate"]}</div>',
                        unsafe_allow_html=True,
                    )
                    c2.markdown(
                        f'<div class="text-muted" style="font-size:0.72rem">TYPE</div>'
                        f'<div>{row["chargeType"]}</div>',
                        unsafe_allow_html=True,
                    )
                    c3.markdown(
                        f'<div class="text-muted" style="font-size:0.72rem">AMOUNT</div>'
                        f'<div style="font-weight:600">−₹{float(row["amount"]):,.2f}</div>',
                        unsafe_allow_html=True,
                    )
            st.caption(f"Total shown: **₹{ch['amount'].astype(float).sum():,.2f}**")
            if has_more_ch:
                rem_ch = total_ch - loaded_ch
                nb_ch  = min(txn_batch, rem_ch)
                if st.button(f"⬇ Load {nb_ch} more  ({loaded_ch} of {total_ch})", key="load_more_charge", use_container_width=True):
                    cursor   = st.session_state.get("txn_cursor_charge")
                    f_s = from_str if date_filter_active else None
                    t_s = to_str   if date_filter_active else None
                    if f_s and t_s:
                        new_df, new_cursor = dm.fetch_charges_in_range(f_s, t_s, txn_batch, cursor)
                    else:
                        new_df, new_cursor = dm.fetch_charges_page(txn_batch, cursor)
                    st.session_state["txn_df_charge"] = pd.concat(
                        [st.session_state["txn_df_charge"], new_df], ignore_index=True
                    )
                    st.session_state["txn_cursor_charge"]   = new_cursor
                    st.session_state["txn_has_more_charge"] = new_cursor is not None
                    st.rerun()

    with tab_cash:
        if date_filter_active:
            _ensure_txn_cache("cash", from_str=from_str, to_str=to_str, batch=txn_batch)
        else:
            _ensure_txn_cache("cash", batch=txn_batch)
        cf = st.session_state["txn_df_cash"]
        if cf.empty:
            st.info("No records found." if date_filter_active else "No deposit or withdrawal history yet.")
        else:
            cf = cf.copy()
            cf["_dt"] = pd.to_datetime(cf["date"], errors="coerce")
            cf = cf.sort_values("_dt", ascending=False).reset_index(drop=True)
            loaded_cf   = len(cf)
            total_cf    = st.session_state.get("txn_total_cash", loaded_cf)
            has_more_cf = st.session_state.get("txn_has_more_cash", False)

            total_dep = cf[cf["type"] == "deposit"]["amount"].astype(float).sum()
            total_wd  = cf[cf["type"] == "withdrawal"]["amount"].astype(float).sum()
            net       = total_dep - total_wd
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Total deposited", f"₹{total_dep:,.2f}")
            mc2.metric("Total withdrawn",  f"₹{total_wd:,.2f}")
            mc3.metric("Net invested",     f"₹{net:,.2f}")
            if date_filter_active:
                st.caption("Totals reflect the loaded records in the selected date range.")
            st.markdown("---")
            st.caption(f"Showing {loaded_cf} of {total_cf} entries (newest first)")

            counts_cf = cf["_dt"].apply(
                lambda dt: _chat_date_label(dt) if pd.notna(dt) else "Unknown date"
            ).value_counts().to_dict()
            last_label = None
            for _, row in cf.iterrows():
                dt = row["_dt"]
                label = _chat_date_label(dt) if pd.notna(dt) else "Unknown date"
                if label != last_label:
                    n = counts_cf.get(label, 0)
                    s = "transaction" if n == 1 else "transactions"
                    _render_date_separator(f"{label} · {n} {s}")
                    last_label = label
                is_dep = str(row["type"]) == "deposit"
                color  = "text-green" if is_dep else "text-red"
                note   = str(row.get("note", "") or "").strip()
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 2])
                    c1.markdown(
                        f'**{"➕ Deposit" if is_dep else "➖ Withdrawal"}**'
                        + (f'<div class="text-muted" style="font-size:0.75rem;margin-top:2px">{note}</div>' if note else "")
                        + f'<div class="text-muted" style="font-size:0.75rem;margin-top:2px">{str(row["date"])}</div>',
                        unsafe_allow_html=True,
                    )
                    c2.markdown(
                        f'<div class="text-muted" style="font-size:0.72rem">TYPE</div>'
                        f'<div>{"Deposit" if is_dep else "Withdrawal"}</div>',
                        unsafe_allow_html=True,
                    )
                    c3.markdown(
                        f'<div class="text-muted" style="font-size:0.72rem">AMOUNT</div>'
                        f'<div class="{color}" style="font-weight:600">{"+" if is_dep else "−"}₹{float(row["amount"]):,.2f}</div>',
                        unsafe_allow_html=True,
                    )
            if has_more_cf:
                rem_cf = total_cf - loaded_cf
                nb_cf  = min(txn_batch, rem_cf)
                if st.button(f"⬇ Load {nb_cf} more  ({loaded_cf} of {total_cf})", key="load_more_cash", use_container_width=True):
                    cursor   = st.session_state.get("txn_cursor_cash")
                    f_s = from_str if date_filter_active else None
                    t_s = to_str   if date_filter_active else None
                    if f_s and t_s:
                        new_df, new_cursor = dm.fetch_cashflow_in_range(f_s, t_s, txn_batch, cursor)
                    else:
                        new_df, new_cursor = dm.fetch_cashflow_page(txn_batch, cursor)
                    st.session_state["txn_df_cash"] = pd.concat(
                        [st.session_state["txn_df_cash"], new_df], ignore_index=True
                    )
                    st.session_state["txn_cursor_cash"]   = new_cursor
                    st.session_state["txn_has_more_cash"] = new_cursor is not None
                    st.rerun()


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


_TXN_BATCH = 20


def _render_transaction_list(df: pd.DataFrame, kind: str, filtered: bool = False) -> None:
    date_col = "buyDate" if kind == "buy" else "sellDate"
    df = df.copy()
    df["_dt"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.sort_values("_dt", ascending=False, na_position="last").reset_index(drop=True)
    df["_label"] = df["_dt"].apply(
        lambda dt: _chat_date_label(dt) if pd.notna(dt) else "Unknown date"
    )
    counts = df["_label"].value_counts().to_dict()

    loaded   = len(df)
    total    = st.session_state.get(f"txn_total_{kind}", loaded)
    has_more = st.session_state.get(f"txn_has_more_{kind}", False)
    if filtered:
        st.caption(f"{loaded} transactions in selected date range")
    else:
        st.caption(f"Showing {loaded} of {total} transactions (newest first)")

    last_label = None
    for _, row in df.iterrows():
        label = row["_label"]
        if label != last_label:
            n = counts.get(label, 0)
            s = "transaction" if n == 1 else "transactions"
            _render_date_separator(f"{label} · {n} {s}")
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

            if kind == "sell":
                ec1, ec2 = st.columns(2)
                edit_clicked = ec1.button("✏️ Edit price", key=f"edit_{row['id']}", use_container_width=True)
                rev_clicked  = ec2.button("↩️ Reverse", key=f"rev_{kind}_{row['id']}", use_container_width=True)
                if edit_clicked:
                    _edit_sell_dialog(
                        sell_id=str(row["id"]),
                        name=str(row["etfName"]),
                        qty=int(row["quantity"]),
                        old_price=float(row["sellPrice"]),
                    )
            else:
                ec1, ec2 = st.columns(2)
                edit_clicked = ec1.button("✏️ Edit price", key=f"edit_{row['id']}", use_container_width=True)
                rev_clicked  = ec2.button("↩️ Reverse", key=f"rev_{kind}_{row['id']}", use_container_width=True)
                if edit_clicked:
                    _edit_buy_dialog(
                        buy_id=str(row["id"]),
                        name=str(row["etfName"]),
                        qty=int(row["quantity"]),
                        old_price=float(row["price"]),
                    )

            if rev_clicked:
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

    if has_more:
        remaining  = total - loaded
        _batch     = st.session_state.get("txn_batch", _TXN_BATCH)
        next_batch = min(_batch, remaining)
        if st.button(f"⬇ Load {next_batch} more  ({loaded} of {total})", key=f"load_more_{kind}", use_container_width=True):
            cursor     = st.session_state.get(f"txn_cursor_{kind}")
            filter_key = st.session_state.get("txn_filter_key")
            if filter_key:
                parts = filter_key.split("_", 1)
                f_str, t_str = (parts[0], parts[1]) if len(parts) == 2 else (None, None)
            else:
                f_str = t_str = None
            if f_str or t_str:
                f_str = f_str or "1900-01-01"
                t_str = t_str or "2999-12-31"
                if kind == "buy":
                    new_df, new_cursor = dm.fetch_buys_in_range(f_str, t_str, _batch, cursor)
                else:
                    new_df, new_cursor = dm.fetch_sells_in_range(f_str, t_str, _batch, cursor)
            else:
                if kind == "buy":
                    new_df, new_cursor = dm.fetch_buys_page(_batch, cursor)
                else:
                    new_df, new_cursor = dm.fetch_sells_page(_batch, cursor)
            st.session_state[f"txn_df_{kind}"] = pd.concat(
                [st.session_state[f"txn_df_{kind}"], new_df], ignore_index=True
            )
            st.session_state[f"txn_cursor_{kind}"]   = new_cursor
            st.session_state[f"txn_has_more_{kind}"] = new_cursor is not None
            st.rerun()


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
