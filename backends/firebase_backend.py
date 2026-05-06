"""Firebase Firestore-backed I/O — stores all data in the cloud."""

from __future__ import annotations

import math
from pathlib import Path

import firebase_admin
from firebase_admin import firestore
import pandas as pd

from models import (
    UserSettings,
    USER_COLUMNS,
    HOLDING_COLUMNS,
    SELL_COLUMNS,
    BUY_COLUMNS,
)

# ── Firebase init ─────────────────────────────────────────────────────────────
_KEY_FILE = Path(__file__).parent.parent / "serviceAccountKey.json"


def _firebase_credential():
    if _KEY_FILE.exists():
        return firebase_admin.credentials.Certificate(str(_KEY_FILE))
    try:
        import streamlit as st
        return firebase_admin.credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    except Exception:
        raise FileNotFoundError(
            "Firebase credentials not found. "
            "Add serviceAccountKey.json locally or configure Streamlit secrets."
        )


if not firebase_admin._apps:
    firebase_admin.initialize_app(_firebase_credential())

db: firestore.Client = firestore.client()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _clean_row(d: dict) -> dict:
    return {k: _clean(v) for k, v in d.items()}


def _collection_to_df(col_name: str, columns: list[str]) -> pd.DataFrame:
    docs = db.collection(col_name).stream()
    rows = [doc.to_dict() for doc in docs]
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def _replace_collection(col_name: str, df: pd.DataFrame, id_field: str) -> None:
    col_ref = db.collection(col_name)
    existing = list(col_ref.stream())
    batch = db.batch()
    for doc in existing:
        batch.delete(doc.reference)
    for _, row in df.iterrows():
        data = _clean_row(row.to_dict())
        batch.set(col_ref.document(str(data[id_field])), data)
    batch.commit()


# ── Config (password) ─────────────────────────────────────────────────────────

def load_config() -> dict:
    doc = db.collection("meta").document("config").get()
    if not doc.exists:
        return {}
    return doc.to_dict() or {}


def save_config(data: dict) -> None:
    db.collection("meta").document("config").set(data, merge=True)


# ── User ──────────────────────────────────────────────────────────────────────

def load_user() -> UserSettings:
    doc = db.collection("meta").document("user").get()
    if not doc.exists:
        u = UserSettings()
        save_user(u)
        return u
    row = doc.to_dict() or {}
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
    data = {col: getattr(u, col) for col in USER_COLUMNS}
    db.collection("meta").document("user").set(data)


# ── Holdings ──────────────────────────────────────────────────────────────────

def load_holdings() -> pd.DataFrame:
    return _collection_to_df("holdings", HOLDING_COLUMNS)


def save_holdings(df: pd.DataFrame) -> None:
    _replace_collection("holdings", df[HOLDING_COLUMNS], "id")


# ── Sells ─────────────────────────────────────────────────────────────────────

def load_sells() -> pd.DataFrame:
    return _collection_to_df("sells", SELL_COLUMNS)


def save_sells(df: pd.DataFrame) -> None:
    _replace_collection("sells", df[SELL_COLUMNS], "id")


# ── Buys ──────────────────────────────────────────────────────────────────────

def load_buys() -> pd.DataFrame:
    return _collection_to_df("buys", BUY_COLUMNS)


def save_buys(df: pd.DataFrame) -> None:
    _replace_collection("buys", df[BUY_COLUMNS], "id")
