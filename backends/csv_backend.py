"""CSV-backed I/O — stores all data as local CSV files in ./data/"""

from __future__ import annotations

import json
import math

import pandas as pd

from models import (
    DATA_DIR,
    UserSettings,
    USER_COLUMNS,
    HOLDING_COLUMNS,
    SELL_COLUMNS,
    BUY_COLUMNS,
)

USER_CSV     = DATA_DIR / "user.csv"
HOLDINGS_CSV = DATA_DIR / "holdings.csv"
SELLS_CSV    = DATA_DIR / "sells.csv"
BUYS_CSV     = DATA_DIR / "buys.csv"
CONFIG_JSON  = DATA_DIR / "config.json"


# ── Config (password) ─────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_JSON.exists():
        return {}
    return json.loads(CONFIG_JSON.read_text())


def save_config(data: dict) -> None:
    existing = load_config()
    existing.update(data)
    CONFIG_JSON.write_text(json.dumps(existing))


# ── User ──────────────────────────────────────────────────────────────────────

def load_user() -> UserSettings:
    if not USER_CSV.exists():
        u = UserSettings()
        save_user(u)
        return u
    df = pd.read_csv(USER_CSV)
    if df.empty:
        return UserSettings()
    row = df.iloc[0].to_dict()
    raw_name = row.get("userName", "")
    if raw_name is None or (isinstance(raw_name, float) and math.isnan(raw_name)):
        raw_name = ""
    return UserSettings(
        userName=str(raw_name),
        investment=float(row.get("investment", 0) or 0),
        remainingAmount=float(row.get("remainingAmount", 0) or 0),
        taxPercentage=float(row.get("taxPercentage", 0) or 0),
        brokeragePercentage=float(row.get("brokeragePercentage", 0) or 0),
        dividendPercentage=float(row.get("dividendPercentage", 0) or 0),
        sellProfitTarget=float(row.get("sellProfitTarget", 3) or 3),
        buyInDipThreshold=float(row.get("buyInDipThreshold", 2.5) or 2.5),
    )


def save_user(u: UserSettings) -> None:
    df = pd.DataFrame([{col: getattr(u, col) for col in USER_COLUMNS}])
    df.to_csv(USER_CSV, index=False)


# ── Holdings ──────────────────────────────────────────────────────────────────

def load_holdings() -> pd.DataFrame:
    if not HOLDINGS_CSV.exists():
        return pd.DataFrame(columns=HOLDING_COLUMNS)
    df = pd.read_csv(HOLDINGS_CSV)
    for col in HOLDING_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[HOLDING_COLUMNS]


def save_holdings(df: pd.DataFrame) -> None:
    df[HOLDING_COLUMNS].to_csv(HOLDINGS_CSV, index=False)


# ── Sells ─────────────────────────────────────────────────────────────────────

def load_sells() -> pd.DataFrame:
    if not SELLS_CSV.exists():
        return pd.DataFrame(columns=SELL_COLUMNS)
    df = pd.read_csv(SELLS_CSV)
    for col in SELL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[SELL_COLUMNS]


def save_sells(df: pd.DataFrame) -> None:
    df[SELL_COLUMNS].to_csv(SELLS_CSV, index=False)


# ── Buys ──────────────────────────────────────────────────────────────────────

def load_buys() -> pd.DataFrame:
    if not BUYS_CSV.exists():
        return pd.DataFrame(columns=BUY_COLUMNS)
    df = pd.read_csv(BUYS_CSV)
    for col in BUY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[BUY_COLUMNS]


def save_buys(df: pd.DataFrame) -> None:
    df[BUY_COLUMNS].to_csv(BUYS_CSV, index=False)
