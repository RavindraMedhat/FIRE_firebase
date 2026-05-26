"""Firestore-backed data layer + ETF API fetching for the FIRE Python app."""

from __future__ import annotations

import math
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import firestore
import pandas as pd
import requests

# ── Firebase init ────────────────────────────────────────────────────────────
_KEY_FILE = Path(__file__).parent / "serviceAccountKey.json"


def _firebase_credential():
    # Local development: use the JSON key file
    if _KEY_FILE.exists():
        return firebase_admin.credentials.Certificate(str(_KEY_FILE))
    # Streamlit Cloud: credentials stored in st.secrets["gcp_service_account"]
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

# ── In-process data cache ────────────────────────────────────────────────────
# Holds full DataFrames for holdings/buys/sells/charges/cashflow so multiple
# pages in the same Streamlit session share one Firestore round-trip.
# Cleared automatically by every save_* function after any write.
_DATA_CACHE: dict = {}


def clear_data_cache() -> None:
    """Invalidate all cached collection DataFrames. Called by every write."""
    _DATA_CACHE.clear()


# ── ETF cache stays local ────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
ETFS_CACHE_CSV = DATA_DIR / "etfs_cache.csv"

API_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzziniyDaACjDKiFLcTMepDdEtfswFtbGVWbYJnwJrPOhgO4z5WKfKosiPZwNcYxbI/exec"
)

USER_COLUMNS = [
    "userName",
    "investment",
    "remainingAmount",
    "taxPercentage",
    "brokeragePercentage",
    "dividendPercentage",
    "sellProfitTarget",
    "buyInDipThreshold",
    "amcAmount",
    "lastAmcDate",
    "totalDeposited",
    "defaultPageSize",
]

# ---- Kotak Securities charges (Kotak Trade Plan, delivery, 2025) ----
KOTAK_RATES = {
    "Equity":    {"brokerage_pct": 0.05, "stt_buy_pct": 0.0,  "stt_sell_pct": 0.001},
    "Jewellery": {"brokerage_pct": 0.05, "stt_buy_pct": 0.0,  "stt_sell_pct": 0.001},
    "Stocks":    {"brokerage_pct": 0.10, "stt_buy_pct": 0.1,  "stt_sell_pct": 0.1},
}
EXCHANGE_TX_PCT = 0.00297
SEBI_PCT = 0.0001
STAMP_DUTY_PCT_BUY = 0.015
GST_PCT = 18.0


def compute_kotak_charges(value: float, etf_type: str, side: str) -> dict:
    rates = KOTAK_RATES.get(etf_type, KOTAK_RATES["Equity"])
    brokerage = value * rates["brokerage_pct"] / 100
    if side == "buy":
        stt = value * rates["stt_buy_pct"] / 100
        stamp = value * STAMP_DUTY_PCT_BUY / 100
    else:
        stt = value * rates["stt_sell_pct"] / 100
        stamp = 0.0
    exchange_tx = value * EXCHANGE_TX_PCT / 100
    sebi = value * SEBI_PCT / 100
    gst = (brokerage + exchange_tx + sebi) * GST_PCT / 100
    total = brokerage + stt + stamp + exchange_tx + sebi + gst
    return {
        "brokerage": brokerage,
        "stt": stt,
        "stamp": stamp,
        "exchangeTx": exchange_tx,
        "sebi": sebi,
        "gst": gst,
        "total": total,
        "tax": stt + stamp + exchange_tx + sebi + gst,
    }


HOLDING_COLUMNS = [
    "id",
    "etfName",
    "etfType",
    "averagePrice",
    "lastPurchasePrice",
    "totalQuantity",
    "lastPurchaseDate",
]

SELL_COLUMNS = [
    "id",
    "etfName",
    "etfType",
    "quantity",
    "averagePurchasePrice",
    "sellPrice",
    "brokerageCharges",
    "tax",
    "dividendPaidToSelf",
    "lastPurchaseDate",
    "sellDate",
    "holdingDays",   # weighted avg hold days across all buy lots — stamped at sell time
]

BUY_COLUMNS = [
    "id",
    "holdingId",
    "etfName",
    "etfType",
    "quantity",
    "price",
    "brokerageCharges",
    "tax",
    "totalCharges",
    "buyDate",
]

CHARGE_COLUMNS = [
    "id",
    "chargeType",
    "amount",
    "description",
    "chargeDate",
]

CASHFLOW_COLUMNS = [
    "id",
    "type",       # "deposit" | "withdrawal"
    "amount",
    "date",
    "note",
]

ETF_COLUMNS = [
    "etfCode",
    "name",
    "cmp",
    "the20Dma",
    "change20DmaVsCmp",
    "changePercentage",
    "dailyAverageVolumeInLast30Days",
    "dailyAverageVolumeInLast90Days",
    "dailyAverageVolumeInLast365Days",
    "type",
]


# ── Firestore helpers ────────────────────────────────────────────────────────

def _clean(v):
    """Replace NaN/None with None so Firestore accepts it."""
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
    """Delete all existing docs then write every row in df.
    Only used for small collections (holdings, ≤30 docs) where full replace is safe."""
    col_ref = db.collection(col_name)
    existing = list(col_ref.stream())
    batch = db.batch()
    for doc in existing:
        batch.delete(doc.reference)
    for _, row in df.iterrows():
        data = _clean_row(row.to_dict())
        batch.set(col_ref.document(str(data[id_field])), data)
    batch.commit()
    _DATA_CACHE.pop(col_name, None)


def _add_document(col_name: str, row: dict) -> None:
    """Write one new document. O(1) — always one Firestore write regardless of collection size."""
    db.collection(col_name).document(str(row["id"])).set(_clean_row(row))
    # Append to in-memory cache if it exists so the next read doesn't need a round-trip
    if col_name in _DATA_CACHE:
        _DATA_CACHE[col_name] = pd.concat(
            [_DATA_CACHE[col_name], pd.DataFrame([row])], ignore_index=True
        )


def _delete_document(col_name: str, doc_id: str) -> None:
    """Delete one document by ID. O(1) — always one Firestore delete."""
    db.collection(col_name).document(doc_id).delete()
    if col_name in _DATA_CACHE:
        cache = _DATA_CACHE[col_name]
        _DATA_CACHE[col_name] = cache[cache["id"] != doc_id].reset_index(drop=True)


def _delete_where(col_name: str, field: str, value: str) -> None:
    """Delete all documents where field == value."""
    docs = list(db.collection(col_name).where(field, "==", value).stream())
    if docs:
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
    if col_name in _DATA_CACHE:
        cache = _DATA_CACHE[col_name]
        _DATA_CACHE[col_name] = cache[cache[field] != value].reset_index(drop=True)


def _clear_collection(col_name: str) -> None:
    """Delete every document in a collection in batches of 400."""
    col_ref = db.collection(col_name)
    while True:
        docs = list(col_ref.limit(400).stream())
        if not docs:
            break
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
    _DATA_CACHE.pop(col_name, None)


# ── Running stats (meta/stats) ────────────────────────────────────────────────
# Precomputed aggregates so the home page never needs to load buys/sells in full.
# Updated incrementally on every write; rebuilt from scratch on first use.

STATS_DEFAULTS: dict = {
    "buyCount": 0,
    "buyGross": 0.0,          # Σ(price × qty)
    "buyBrokerage": 0.0,      # Σ(brokerage) on buys
    "buyTotalCharges": 0.0,   # Σ(totalCharges) on buys
    "sellCount": 0,
    "sellGross": 0.0,         # Σ(sellPrice × qty)
    "sellBrokerage": 0.0,     # Σ(brokerage) on sells
    "sellNetPL": 0.0,
    "sellTotalCharges": 0.0,  # Σ(brokerage + tax) on sells
    "sellDividend": 0.0,
    "chargesTotal": 0.0,      # Σ(charges.amount)
    # For weighted-avg hold days without loading all buys:
    # avgHoldDays ≈ today_epoch_days − openInvDateSum / openInvTotal
    "openInvTotal": 0.0,      # Σ(price × qty) for all open buy lots
    "openInvDateSum": 0.0,    # Σ(price × qty × epoch_days_of_buyDate)
}


def load_stats() -> dict:
    doc = db.collection("meta").document("stats").get()
    if not doc.exists:
        return rebuild_stats()
    d = doc.to_dict() or {}
    return {k: d.get(k, v) for k, v in STATS_DEFAULTS.items()}


def _update_stats(delta: dict) -> None:
    doc_ref = db.collection("meta").document("stats")
    existing = doc_ref.get()
    current = existing.to_dict() if existing.exists else dict(STATS_DEFAULTS)
    for k, v in delta.items():
        current[k] = float(current.get(k, 0.0)) + float(v)
    doc_ref.set(current)


def rebuild_stats() -> dict:
    """Full rescan of all collections to recompute stats. Called on first use or to repair."""
    buys = _collection_to_df("buys", BUY_COLUMNS)
    sells = _collection_to_df("sells", SELL_COLUMNS)
    charges_df = _collection_to_df("charges", CHARGE_COLUMNS)
    holdings = _collection_to_df("holdings", HOLDING_COLUMNS)

    stats = dict(STATS_DEFAULTS)
    epoch = date(1970, 1, 1)
    today = date.today()

    if not buys.empty:
        stats["buyCount"] = len(buys)
        stats["buyGross"] = float((buys["price"].astype(float) * buys["quantity"].astype(float)).sum())
        stats["buyBrokerage"] = float(buys["brokerageCharges"].astype(float).sum())
        stats["buyTotalCharges"] = float(buys["totalCharges"].astype(float).sum())

    # openInvTotal / openInvDateSum: always computed from holdings regardless of whether
    # buys exist (e.g. legacy data before backfill). Uses remaining qty × avg price so
    # partial sells don't overcount.
    if not holdings.empty:
        active_ids = set(holdings["id"].astype(str).tolist())
        lot_by_holding: dict[str, list] = {}
        if not buys.empty:
            for _, b in buys[buys["holdingId"].isin(active_ids)].iterrows():
                hid = str(b["holdingId"])
                lot_by_holding.setdefault(hid, []).append(b)

        for _, h in holdings.iterrows():
            hid = str(h["id"])
            remaining_inv = float(h["averagePrice"]) * float(h["totalQuantity"])
            stats["openInvTotal"] += remaining_inv

            lots = lot_by_holding.get(hid, [])
            if lots:
                lot_inv_total = lot_date_sum = 0.0
                for b in lots:
                    lot_inv = float(b["price"]) * float(b["quantity"])
                    try:
                        ep = (pd.to_datetime(b["buyDate"]).date() - epoch).days
                    except Exception:
                        ep = (today - epoch).days
                    lot_inv_total += lot_inv
                    lot_date_sum  += lot_inv * ep
                weighted_ep = lot_date_sum / lot_inv_total if lot_inv_total > 0 else (today - epoch).days
            else:
                try:
                    weighted_ep = (pd.to_datetime(h["lastPurchaseDate"]).date() - epoch).days
                except Exception:
                    weighted_ep = (today - epoch).days

            stats["openInvDateSum"] += remaining_inv * weighted_ep

    if not sells.empty:
        q  = sells["quantity"].astype(float)
        sp = sells["sellPrice"].astype(float)
        ap = sells["averagePurchasePrice"].astype(float)
        br = sells["brokerageCharges"].astype(float)
        tx = sells["tax"].astype(float)
        dv = sells["dividendPaidToSelf"].astype(float)
        stats["sellCount"] = len(sells)
        stats["sellGross"] = float((sp * q).sum())
        stats["sellBrokerage"] = float(br.sum())
        stats["sellNetPL"] = float(((sp - ap) * q - br - tx - dv).sum())
        stats["sellTotalCharges"] = float((br + tx).sum())
        stats["sellDividend"] = float(dv.sum())

    if not charges_df.empty:
        stats["chargesTotal"] = float(charges_df["amount"].astype(float).sum())

    db.collection("meta").document("stats").set(stats)
    return stats


# ── Config (password) ────────────────────────────────────────────────────────

def load_config() -> dict:
    doc = db.collection("meta").document("config").get()
    if not doc.exists:
        return {}
    return doc.to_dict() or {}


def save_config(data: dict) -> None:
    db.collection("meta").document("config").set(data, merge=True)


# ── User ─────────────────────────────────────────────────────────────────────

@dataclass
class UserSettings:
    userName: str = ""
    investment: float = 0.0
    remainingAmount: float = 0.0
    taxPercentage: float = 0.0
    brokeragePercentage: float = 0.0
    dividendPercentage: float = 0.0
    sellProfitTarget: float = 3.0
    buyInDipThreshold: float = 2.5
    amcAmount: float = 18.88
    lastAmcDate: str = ""
    totalDeposited: float = 0.0
    defaultPageSize: int = 20


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
        amcAmount=float(row.get("amcAmount", 18.88) or 18.88),
        lastAmcDate=str(row.get("lastAmcDate", "") or ""),
        totalDeposited=float(row.get("totalDeposited", 0) or 0),
        defaultPageSize=int(row.get("defaultPageSize", 20) or 20),
    )


def save_user(u: UserSettings) -> None:
    data = {col: getattr(u, col) for col in USER_COLUMNS}
    db.collection("meta").document("user").set(data)


def load_charges() -> pd.DataFrame:
    if "charges" not in _DATA_CACHE:
        _DATA_CACHE["charges"] = _collection_to_df("charges", CHARGE_COLUMNS)
    return _DATA_CACHE["charges"]


def fetch_charges_page(page_size: int, cursor=None) -> tuple[pd.DataFrame, object]:
    q = db.collection("charges").order_by("chargeDate", direction=firestore.Query.DESCENDING)
    if cursor is not None:
        q = q.start_after(cursor)
    docs = list(q.limit(page_size).stream())
    if not docs:
        return pd.DataFrame(columns=CHARGE_COLUMNS), None
    rows = [d.to_dict() for d in docs]
    df = pd.DataFrame(rows)
    for col in CHARGE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[CHARGE_COLUMNS], docs[-1]


def fetch_charges_in_range(date_from: str, date_to: str, page_size: int = 20, cursor=None) -> tuple[pd.DataFrame, object]:
    date_to_end = date_to if "T" in date_to else date_to + "T23:59:59"
    q = (
        db.collection("charges")
        .where("chargeDate", ">=", date_from)
        .where("chargeDate", "<=", date_to_end)
        .order_by("chargeDate", direction=firestore.Query.DESCENDING)
    )
    if cursor is not None:
        q = q.start_after(cursor)
    docs = list(q.limit(page_size).stream())
    if not docs:
        return pd.DataFrame(columns=CHARGE_COLUMNS), None
    rows = [d.to_dict() for d in docs]
    df = pd.DataFrame(rows)
    for col in CHARGE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[CHARGE_COLUMNS], docs[-1]


def save_charge(charge_type: str, amount: float, description: str, charge_date: str | None = None) -> None:
    row = {
        "id": str(uuid.uuid4()),
        "chargeType": charge_type,
        "amount": amount,
        "description": description,
        "chargeDate": charge_date or _now_iso(),
    }
    db.collection("charges").document(row["id"]).set(row)
    _update_stats({"chargesTotal": amount})
    _DATA_CACHE.pop("charges", None)


def load_cashflow() -> pd.DataFrame:
    if "cashflow" not in _DATA_CACHE:
        _DATA_CACHE["cashflow"] = _collection_to_df("cashflow", CASHFLOW_COLUMNS)
    return _DATA_CACHE["cashflow"]


def fetch_cashflow_page(page_size: int, cursor=None) -> tuple[pd.DataFrame, object]:
    q = db.collection("cashflow").order_by("date", direction=firestore.Query.DESCENDING)
    if cursor is not None:
        q = q.start_after(cursor)
    docs = list(q.limit(page_size).stream())
    if not docs:
        return pd.DataFrame(columns=CASHFLOW_COLUMNS), None
    rows = [d.to_dict() for d in docs]
    df = pd.DataFrame(rows)
    for col in CASHFLOW_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[CASHFLOW_COLUMNS], docs[-1]


def fetch_cashflow_in_range(date_from: str, date_to: str, page_size: int = 20, cursor=None) -> tuple[pd.DataFrame, object]:
    date_to_end = date_to if "T" in date_to else date_to + "T23:59:59"
    q = (
        db.collection("cashflow")
        .where("date", ">=", date_from)
        .where("date", "<=", date_to_end)
        .order_by("date", direction=firestore.Query.DESCENDING)
    )
    if cursor is not None:
        q = q.start_after(cursor)
    docs = list(q.limit(page_size).stream())
    if not docs:
        return pd.DataFrame(columns=CASHFLOW_COLUMNS), None
    rows = [d.to_dict() for d in docs]
    df = pd.DataFrame(rows)
    for col in CASHFLOW_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[CASHFLOW_COLUMNS], docs[-1]


def save_cashflow(txn_type: str, amount: float, txn_date: str | None = None, note: str = "") -> None:
    row = {
        "id": str(uuid.uuid4()),
        "type": txn_type,
        "amount": amount,
        "date": txn_date or _now_iso()[:10],
        "note": note,
    }
    db.collection("cashflow").document(row["id"]).set(row)
    _DATA_CACHE.pop("cashflow", None)


def check_and_apply_amc(user: UserSettings) -> tuple[UserSettings, float]:
    """Deduct monthly Demat AMC if 30+ days have passed since last deduction.
    Re-reads lastAmcDate fresh from Firestore so a second browser tab that opens
    after the first already ran the deduction will see the updated date and skip."""
    if user.amcAmount <= 0:
        return user, 0.0

    today = date.today()

    # Bypass cache: get the current lastAmcDate directly from Firestore.
    fresh = (db.collection("meta").document("user").get().to_dict() or {})
    last_str = str(fresh.get("lastAmcDate", "") or "")

    if not last_str:
        user.lastAmcDate = today.isoformat()
        save_user(user)
        return user, 0.0

    try:
        last = date.fromisoformat(last_str)
    except ValueError:
        user.lastAmcDate = today.isoformat()
        save_user(user)
        return user, 0.0

    if (today - last) < timedelta(days=30):
        user.lastAmcDate = last_str  # keep local object in sync with Firestore
        return user, 0.0

    amount = user.amcAmount
    user.investment -= amount
    user.remainingAmount -= amount
    user.lastAmcDate = today.isoformat()
    save_user(user)
    save_charge("AMC", amount, f"Demat AMC auto-deduction ({today.isoformat()})")
    return user, amount


# ── Holdings ──────────────────────────────────────────────────────────────────

def load_holdings() -> pd.DataFrame:
    if "holdings" not in _DATA_CACHE:
        _DATA_CACHE["holdings"] = _collection_to_df("holdings", HOLDING_COLUMNS)
    return _DATA_CACHE["holdings"]


def save_holdings(df: pd.DataFrame) -> None:
    _replace_collection("holdings", df[HOLDING_COLUMNS], "id")


# ── Sells ────────────────────────────────────────────────────────────────────

def load_sells() -> pd.DataFrame:
    if "sells" not in _DATA_CACHE:
        _DATA_CACHE["sells"] = _collection_to_df("sells", SELL_COLUMNS)
    return _DATA_CACHE["sells"]


def fetch_sells_page(page_size: int, cursor=None) -> tuple[pd.DataFrame, object]:
    """Fetch one page of sells ordered newest-first.
    Pass cursor=last_doc from a previous call to get the next page.
    Returns (df, last_doc) — last_doc is None when no more records exist."""
    q = db.collection("sells").order_by("sellDate", direction=firestore.Query.DESCENDING)
    if cursor is not None:
        q = q.start_after(cursor)
    docs = list(q.limit(page_size).stream())
    if not docs:
        return pd.DataFrame(columns=SELL_COLUMNS), None
    rows = [d.to_dict() for d in docs]
    df = pd.DataFrame(rows)
    for col in SELL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[SELL_COLUMNS], docs[-1]


def save_sells(df: pd.DataFrame) -> None:
    _replace_collection("sells", df[SELL_COLUMNS], "id")


def fetch_sells_for_etf(etf_name: str) -> pd.DataFrame:
    """Return all sell records for a specific ETF without loading the full collection."""
    docs = list(db.collection("sells").where("etfName", "==", etf_name).stream())
    if not docs:
        return pd.DataFrame(columns=SELL_COLUMNS)
    df = pd.DataFrame([d.to_dict() for d in docs])
    for col in SELL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[SELL_COLUMNS]


# ── Buys ─────────────────────────────────────────────────────────────────────

def load_buys() -> pd.DataFrame:
    if "buys" not in _DATA_CACHE:
        _DATA_CACHE["buys"] = _collection_to_df("buys", BUY_COLUMNS)
    return _DATA_CACHE["buys"]


def fetch_buys_page(page_size: int, cursor=None) -> tuple[pd.DataFrame, object]:
    """Fetch one page of buys ordered newest-first.
    Pass cursor=last_doc from a previous call to get the next page.
    Returns (df, last_doc) — last_doc is None when no more records exist."""
    q = db.collection("buys").order_by("buyDate", direction=firestore.Query.DESCENDING)
    if cursor is not None:
        q = q.start_after(cursor)
    docs = list(q.limit(page_size).stream())
    if not docs:
        return pd.DataFrame(columns=BUY_COLUMNS), None
    rows = [d.to_dict() for d in docs]
    df = pd.DataFrame(rows)
    for col in BUY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[BUY_COLUMNS], docs[-1]


def save_buys(df: pd.DataFrame) -> None:
    _replace_collection("buys", df[BUY_COLUMNS], "id")


def fetch_buys_for_etf(etf_name: str) -> pd.DataFrame:
    """Return all buy records for a specific ETF without loading the full collection."""
    docs = list(db.collection("buys").where("etfName", "==", etf_name).stream())
    if not docs:
        return pd.DataFrame(columns=BUY_COLUMNS)
    df = pd.DataFrame([d.to_dict() for d in docs])
    for col in BUY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[BUY_COLUMNS]


def count_collection(col_name: str) -> int:
    result = db.collection(col_name).count().get()
    return result[0][0].value


def fetch_buys_in_range(date_from: str, date_to: str, page_size: int = 20, cursor=None) -> tuple[pd.DataFrame, object]:
    """Fetch one page of buys in a date range, newest first. Returns (df, last_doc)."""
    # Append end-of-day time so ISO-timestamped records (e.g. "2026-05-25T14:32:00")
    # are not excluded by the <= upper bound when date_to is a plain "YYYY-MM-DD" string.
    date_to_end = date_to if "T" in date_to else date_to + "T23:59:59"
    q = (
        db.collection("buys")
        .where("buyDate", ">=", date_from)
        .where("buyDate", "<=", date_to_end)
        .order_by("buyDate", direction=firestore.Query.DESCENDING)
    )
    if cursor is not None:
        q = q.start_after(cursor)
    docs = list(q.limit(page_size).stream())
    if not docs:
        return pd.DataFrame(columns=BUY_COLUMNS), None
    rows = [d.to_dict() for d in docs]
    df = pd.DataFrame(rows)
    for col in BUY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[BUY_COLUMNS], docs[-1]


def fetch_sells_in_range(date_from: str, date_to: str, page_size: int = 20, cursor=None) -> tuple[pd.DataFrame, object]:
    """Fetch one page of sells in a date range, newest first. Returns (df, last_doc)."""
    date_to_end = date_to if "T" in date_to else date_to + "T23:59:59"
    q = (
        db.collection("sells")
        .where("sellDate", ">=", date_from)
        .where("sellDate", "<=", date_to_end)
        .order_by("sellDate", direction=firestore.Query.DESCENDING)
    )
    if cursor is not None:
        q = q.start_after(cursor)
    docs = list(q.limit(page_size).stream())
    if not docs:
        return pd.DataFrame(columns=SELL_COLUMNS), None
    rows = [d.to_dict() for d in docs]
    df = pd.DataFrame(rows)
    for col in SELL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[SELL_COLUMNS], docs[-1]


def count_in_range(col_name: str, date_field: str, date_from: str, date_to: str) -> int:
    date_to_end = date_to if "T" in date_to else date_to + "T23:59:59"
    result = (
        db.collection(col_name)
        .where(date_field, ">=", date_from)
        .where(date_field, "<=", date_to_end)
        .count()
        .get()
    )
    return result[0][0].value


def backfill_buys_from_holdings() -> int:
    holdings = load_holdings()
    if holdings.empty:
        return 0
    buys = load_buys()
    existing_holding_ids = (
        set() if buys.empty else set(buys["holdingId"].astype(str).tolist())
    )
    new_rows = []
    for _, h in holdings.iterrows():
        hid = str(h["id"])
        if hid in existing_holding_ids:
            continue
        qty = int(h["totalQuantity"])
        price = float(h["averagePrice"])
        value = price * qty  # noqa: F841 – kept for clarity
        new_rows.append({
            "id": str(uuid.uuid4()),
            "holdingId": hid,
            "etfName": str(h["etfName"]),
            "etfType": str(h["etfType"]),
            "quantity": qty,
            "price": price,
            # Charges are unknown for legacy holdings — setting to 0 keeps the
            # reconciliation formula correct (charges were embedded in the original
            # remainingAmount adjustment, not tracked separately).
            "brokerageCharges": 0.0,
            "tax": 0.0,
            "totalCharges": 0.0,
            "buyDate": str(h["lastPurchaseDate"]) if pd.notna(h.get("lastPurchaseDate")) else _now_iso(),
        })
    for row in new_rows:
        _add_document("buys", row)
    if new_rows:
        # Resync meta/stats — backfill adds buy docs that weren't counted before.
        rebuild_stats()
    return len(new_rows)


def backfill_sell_holding_days() -> int:
    """Compute and stamp holdingDays into every sell record that is missing it.
    Uses only buy lots from the same ownership cycle (buys since the last time
    qty reached zero), matching the formula sell_holding() uses going forward."""
    sells = _collection_to_df("sells", SELL_COLUMNS)
    if sells.empty:
        return 0
    buys = _collection_to_df("buys", BUY_COLUMNS)
    epoch = date(1970, 1, 1)
    count = 0

    for _, s in sells.iterrows():
        existing = s.get("holdingDays")
        if existing is not None and not (isinstance(existing, float) and math.isnan(existing)):
            continue  # already stamped

        etf_name = str(s["etfName"])
        try:
            sell_dt = pd.to_datetime(s["sellDate"]).date()
            sell_ep = (sell_dt - epoch).days
        except Exception:
            continue

        # Find the start of the current ownership cycle: walk all prior
        # transactions for this ETF chronologically and find the last date when
        # cumulative qty reached zero. Buy lots before that date belong to a
        # previous ownership cycle and must be excluded.
        cycle_start_dt = epoch
        txns: list[tuple[str, date, int]] = []
        if not buys.empty:
            for _, b in buys[buys["etfName"] == etf_name].iterrows():
                try:
                    bdt = pd.to_datetime(b["buyDate"]).date()
                    if bdt < sell_dt:
                        txns.append(("buy", bdt, int(b["quantity"])))
                except Exception:
                    pass
        prior_sells = sells[sells["etfName"] == etf_name]
        for _, ps in prior_sells.iterrows():
            try:
                sdt = pd.to_datetime(ps["sellDate"]).date()
                if sdt < sell_dt:
                    txns.append(("sell", sdt, int(ps["quantity"])))
            except Exception:
                pass
        txns.sort(key=lambda t: t[1])
        running_qty = 0
        for kind, dt, qty in txns:
            if kind == "buy":
                running_qty += qty
            else:
                running_qty = max(0, running_qty - qty)
                if running_qty == 0:
                    cycle_start_dt = dt

        valid_lots = []
        if not buys.empty:
            for _, b in buys[buys["etfName"] == etf_name].iterrows():
                try:
                    bdt = pd.to_datetime(b["buyDate"]).date()
                    if cycle_start_dt < bdt <= sell_dt:
                        valid_lots.append(b)
                except Exception:
                    pass

        if valid_lots:
            inv_total = inv_date_sum = 0.0
            for b in valid_lots:
                inv = float(b["price"]) * float(b["quantity"])
                ep  = (pd.to_datetime(b["buyDate"]).date() - epoch).days
                inv_total    += inv
                inv_date_sum += inv * ep
            holding_days = round((sell_ep - inv_date_sum / inv_total) if inv_total > 0 else 0.0, 1)
        else:
            try:
                buy_dt = pd.to_datetime(s["lastPurchaseDate"]).date()
                holding_days = round(max(0.0, float((sell_dt - buy_dt).days)), 1)
            except Exception:
                holding_days = 0.0

        db.collection("sells").document(str(s["id"])).update({"holdingDays": holding_days})
        count += 1

    clear_data_cache()
    return count


# ── ETFs (local CSV cache) ────────────────────────────────────────────────────

def load_etfs_cache() -> pd.DataFrame:
    if not ETFS_CACHE_CSV.exists():
        return pd.DataFrame(columns=ETF_COLUMNS)
    df = pd.read_csv(ETFS_CACHE_CSV)
    for col in ETF_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[ETF_COLUMNS]


def _to_float(v) -> float:
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def fetch_etfs(timeout: int = 30) -> pd.DataFrame:
    resp = requests.get(API_URL, timeout=timeout)
    resp.raise_for_status()
    raw = resp.json()
    rows = []
    for item in raw:
        rows.append({
            "etfCode": item.get("ETF Code", "") or "",
            "name": item.get("Name", "") or "",
            "cmp": _to_float(item.get("CMP")),
            "the20Dma": _to_float(item.get("20 DMA")),
            "change20DmaVsCmp": _to_float(item.get("Change 20 DMA Vs CMP")),
            "changePercentage": _to_float(item.get("Changes %")),
            "dailyAverageVolumeInLast30Days": _to_float(item.get("Daily average volume in last 30 days")),
            "dailyAverageVolumeInLast90Days": _to_float(item.get("Daily average volume in last 90 days")),
            "dailyAverageVolumeInLast365Days": _to_float(item.get("Daily average volume in last 365 days")),
            "type": item.get("Type", "") or "",
        })
    df = pd.DataFrame(rows, columns=ETF_COLUMNS)
    df = df[df["cmp"] > 0].reset_index(drop=True)
    df.to_csv(ETFS_CACHE_CSV, index=False)
    return df


def last_fetch_time() -> Optional[datetime]:
    if not ETFS_CACHE_CSV.exists():
        return None
    return datetime.fromtimestamp(ETFS_CACHE_CSV.stat().st_mtime)


def get_etfs(refresh: bool = False) -> pd.DataFrame:
    if refresh or not ETFS_CACHE_CSV.exists():
        try:
            return fetch_etfs()
        except Exception:
            return load_etfs_cache()
    return load_etfs_cache()


# ── Business logic ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now().isoformat()


def holdings_total_cost(holdings: pd.DataFrame) -> float:
    if holdings.empty:
        return 0.0
    return float((holdings["averagePrice"] * holdings["totalQuantity"]).sum())


def holdings_current_value(holdings: pd.DataFrame, etfs: pd.DataFrame) -> float:
    if holdings.empty or etfs.empty:
        return 0.0
    merged = holdings.merge(
        etfs[["name", "cmp"]], left_on="etfName", right_on="name", how="left"
    )
    merged["cmp"] = merged["cmp"].fillna(0)
    return float((merged["cmp"] * merged["totalQuantity"]).sum())


def buy_etf(
    user: UserSettings,
    etf_name: str,
    etf_type: str,
    price: float,
    quantity: int,
) -> tuple[UserSettings, pd.DataFrame, dict]:
    holdings = load_holdings()
    value = price * quantity
    charges = compute_kotak_charges(value, etf_type, side="buy")

    match = holdings[holdings["etfName"] == etf_name]
    if not match.empty:
        idx = match.index[0]
        old_avg = float(holdings.at[idx, "averagePrice"])
        old_qty = int(holdings.at[idx, "totalQuantity"])
        new_qty = old_qty + quantity
        new_avg = (old_avg * old_qty + price * quantity) / new_qty
        holdings.at[idx, "averagePrice"] = new_avg
        holdings.at[idx, "lastPurchasePrice"] = price
        holdings.at[idx, "totalQuantity"] = new_qty
        holdings.at[idx, "lastPurchaseDate"] = _now_iso()
        holding_id = str(holdings.at[idx, "id"])
    else:
        holding_id = str(uuid.uuid4())
        new_row = {
            "id": holding_id,
            "etfName": etf_name,
            "etfType": etf_type,
            "averagePrice": price,
            "lastPurchasePrice": price,
            "totalQuantity": quantity,
            "lastPurchaseDate": _now_iso(),
        }
        holdings = pd.concat([holdings, pd.DataFrame([new_row])], ignore_index=True)

    save_holdings(holdings)

    buy_row = {
        "id": str(uuid.uuid4()),
        "holdingId": holding_id,
        "etfName": etf_name,
        "etfType": etf_type,
        "quantity": quantity,
        "price": price,
        "brokerageCharges": charges["brokerage"],
        "tax": charges["tax"],
        "totalCharges": charges["total"],
        "buyDate": _now_iso(),
    }
    _add_document("buys", buy_row)

    epoch_days = (date.today() - date(1970, 1, 1)).days
    _update_stats({
        "buyCount": 1,
        "buyGross": value,
        "buyBrokerage": charges["brokerage"],
        "buyTotalCharges": charges["total"],
        "openInvTotal": value,
        "openInvDateSum": value * epoch_days,
    })

    user.remainingAmount = user.remainingAmount - value - charges["total"]
    save_user(user)
    return user, holdings, charges


def sell_holding(
    user: UserSettings,
    holding_id: str,
    sell_price: float,
    quantity: int,
    dividend: float,
) -> tuple[UserSettings, pd.DataFrame, pd.DataFrame, dict]:
    holdings = load_holdings()

    row = holdings[holdings["id"] == holding_id]
    if row.empty:
        raise ValueError(f"Holding {holding_id} not found")
    idx = row.index[0]

    old_avg = float(holdings.at[idx, "averagePrice"])
    old_qty = int(holdings.at[idx, "totalQuantity"])
    etf_name = str(holdings.at[idx, "etfName"])
    etf_type = str(holdings.at[idx, "etfType"])
    last_purchase_date = holdings.at[idx, "lastPurchaseDate"]

    if quantity > old_qty:
        raise ValueError("Sell quantity exceeds holding quantity")

    value = sell_price * quantity
    charges = compute_kotak_charges(value, etf_type, side="sell")
    brokerage = charges["brokerage"]
    tax = charges["tax"]

    remaining_qty = old_qty - quantity

    # Compute exact weighted-avg holding days from buy lots for this holding
    epoch = date(1970, 1, 1)
    sell_epoch = (date.today() - epoch).days
    if "buys" in _DATA_CACHE and not _DATA_CACHE["buys"].empty:
        holding_lots = _DATA_CACHE["buys"][_DATA_CACHE["buys"]["holdingId"] == holding_id]
    else:
        raw = list(db.collection("buys").where("holdingId", "==", holding_id).stream())
        holding_lots = pd.DataFrame([d.to_dict() for d in raw]) if raw else pd.DataFrame()
    if holding_lots.empty:
        holding_days = 0.0
    else:
        inv_total = inv_date_sum = 0.0
        for _, b in holding_lots.iterrows():
            inv = float(b["price"]) * float(b["quantity"])
            try:
                ep = (pd.to_datetime(b["buyDate"]).date() - epoch).days
            except Exception:
                ep = sell_epoch
            inv_total += inv
            inv_date_sum += inv * ep
        holding_days = round((sell_epoch - inv_date_sum / inv_total) if inv_total > 0 else 0.0, 1)

    sell_row = {
        "id": str(uuid.uuid4()),
        "etfName": etf_name,
        "etfType": etf_type,
        "quantity": quantity,
        "averagePurchasePrice": old_avg,
        "sellPrice": sell_price,
        "brokerageCharges": brokerage,
        "tax": tax,
        "dividendPaidToSelf": dividend,
        "lastPurchaseDate": last_purchase_date,
        "sellDate": _now_iso(),
        "holdingDays": holding_days,
    }
    _add_document("sells", sell_row)

    sold_inv = old_avg * quantity
    # Use the weighted buy epoch already derived from buy lots above.
    # holding_days = sell_epoch − weighted_buy_epoch  →  weighted_buy_epoch = sell_epoch − holding_days
    sold_ep_days = sell_epoch - holding_days
    _update_stats({
        "sellCount": 1,
        "sellGross": value,
        "sellBrokerage": brokerage,
        "sellNetPL": (sell_price - old_avg) * quantity - brokerage - tax - dividend,
        "sellTotalCharges": brokerage + tax,
        "sellDividend": dividend,
        "openInvTotal": -sold_inv,
        "openInvDateSum": -sold_inv * sold_ep_days,
    })

    if remaining_qty == 0:
        holdings = holdings.drop(idx).reset_index(drop=True)
    else:
        # Average purchase price is unchanged when selling — only quantity reduces
        holdings.at[idx, "averagePrice"] = old_avg
        holdings.at[idx, "totalQuantity"] = remaining_qty
    save_holdings(holdings)

    user.remainingAmount = (
        user.remainingAmount + value - brokerage - dividend - tax
    )
    user.investment = (
        user.investment
        + (quantity * (sell_price - old_avg))
        - brokerage
        - dividend
        - tax
    )
    save_user(user)

    return user, holdings, pd.DataFrame([sell_row]), charges


def update_buy_price(user: UserSettings, buy_id: str, new_exec_value: float) -> UserSettings:
    """Update buy price using exact execution value (price × qty, without charges).
    Recalculates holding avg price and adjusts user balance."""
    buys = load_buys()
    row = buys[buys["id"] == buy_id]
    if row.empty:
        raise ValueError(f"Buy {buy_id} not found")
    r = row.iloc[0]
    qty        = int(r["quantity"])
    etf_type   = str(r["etfType"])
    etf_name   = str(r["etfName"])
    holding_id = str(r["holdingId"])

    old_price      = float(r["price"])
    old_value      = old_price * qty
    old_charges    = compute_kotak_charges(old_value, etf_type, side="buy")
    old_total_cost = old_value + old_charges["total"]

    new_price      = new_exec_value / qty
    new_charges    = compute_kotak_charges(new_exec_value, etf_type, side="buy")
    new_total_cost = new_exec_value + new_charges["total"]

    # Update buy record
    db.collection("buys").document(buy_id).update({
        "price":            new_price,
        "brokerageCharges": new_charges["brokerage"],
        "tax":              new_charges["tax"],
        "totalCharges":     new_charges["total"],
    })

    # Recalculate holding avg price from all buys for this ETF (weighted average)
    buys.at[buys[buys["id"] == buy_id].index[0], "price"] = new_price
    etf_buys = buys[buys["holdingId"] == holding_id]
    if not etf_buys.empty:
        total_val = (etf_buys["price"].astype(float) * etf_buys["quantity"].astype(int)).sum()
        total_qty = etf_buys["quantity"].astype(int).sum()
        new_avg = total_val / total_qty if total_qty > 0 else new_price
        holdings = load_holdings()
        hold_row = holdings[holdings["id"] == holding_id]
        if not hold_row.empty:
            holdings.at[hold_row.index[0], "averagePrice"] = new_avg
            save_holdings(holdings)

    # Adjust user balance by cost difference
    diff = new_total_cost - old_total_cost
    user.remainingAmount -= diff
    save_user(user)

    # Resync meta/stats and bust cache (price edit changes buyGross, charges, openInv)
    _DATA_CACHE.pop("buys", None)
    rebuild_stats()
    return user


def update_sell_price(sell_id: str, kotak_total: float) -> dict:
    """Update sellPrice + charges for a sell record using the exact Kotak total.
    Does NOT adjust remainingAmount — call only when balance is already correct."""
    sells = load_sells()
    row = sells[sells["id"] == sell_id]
    if row.empty:
        raise ValueError(f"Sell {sell_id} not found")
    r = row.iloc[0]
    qty = int(r["quantity"])
    etf_type = str(r["etfType"])
    new_price = kotak_total / qty
    charges = compute_kotak_charges(kotak_total, etf_type, side="sell")
    db.collection("sells").document(sell_id).update({
        "sellPrice":        new_price,
        "brokerageCharges": charges["brokerage"],
        "tax":              charges["tax"],
    })
    # Resync meta/stats and bust cache (price edit changes sellGross, charges, sellNetPL)
    _DATA_CACHE.pop("sells", None)
    rebuild_stats()
    return {"newPrice": new_price, "charges": charges}


def generate_suggestions(
    user: UserSettings,
    etfs: pd.DataFrame,
    holdings: pd.DataFrame,
) -> list[dict]:
    if etfs.empty:
        return []

    def top_n(etf_type: str, n: int) -> pd.DataFrame:
        sub = etfs[(etfs["type"] == etf_type) & (etfs["cmp"] > 0)].copy()
        sub = sub.sort_values("change20DmaVsCmp", ascending=True)
        return sub.head(n)

    top = pd.concat(
        [top_n("Equity", 5), top_n("Jewellery", 3), top_n("Stocks", 3)],
        ignore_index=True,
    )

    if not holdings.empty:
        held = set(holdings["etfName"].astype(str).tolist())
        top = top[~top["name"].isin(held)]

    suggestions = []
    for etf_type, group in top.groupby("type"):
        if group.empty:
            continue
        best = group.sort_values("change20DmaVsCmp", ascending=True).iloc[0]
        cmp_val = float(best["cmp"])
        if cmp_val <= 0:
            continue
        qty = max(1, math.ceil(user.investment / 25 / cmp_val)) if user.investment > 0 else 1
        suggestions.append({
            "type": str(best["type"]),
            "name": str(best["name"]),
            "price": cmp_val,
            "quantity": qty,
        })
    return suggestions


def classify_holdings(
    holdings: pd.DataFrame,
    etfs: pd.DataFrame,
    user: UserSettings,
) -> dict:
    if holdings.empty:
        return {"sell": pd.DataFrame(), "buy": pd.DataFrame(), "others": pd.DataFrame()}

    merged = holdings.merge(
        etfs[["name", "cmp"]], left_on="etfName", right_on="name", how="left"
    )
    merged["cmp"] = merged["cmp"].fillna(0).astype(float)
    merged["averagePrice"] = merged["averagePrice"].astype(float)
    merged["totalQuantity"] = merged["totalQuantity"].astype(int)
    merged["currentValue"] = merged["cmp"] * merged["totalQuantity"]
    merged["costValue"] = merged["averagePrice"] * merged["totalQuantity"]
    merged["pnl"] = merged["currentValue"] - merged["costValue"]
    merged["pnlPct"] = (
        (merged["cmp"] - merged["averagePrice"]) / merged["averagePrice"] * 100
    ).where(merged["averagePrice"] > 0, 0.0)

    sell_threshold = 1 + (user.sellProfitTarget / 100)
    buy_threshold = 1 - (user.buyInDipThreshold / 100)

    sell_mask = merged["cmp"] > merged["averagePrice"] * sell_threshold
    buy_mask = merged["cmp"] < merged["averagePrice"] * buy_threshold
    other_mask = ~(sell_mask | buy_mask)

    return {
        "sell": merged[sell_mask].reset_index(drop=True),
        "buy": merged[buy_mask].reset_index(drop=True),
        "others": merged[other_mask].reset_index(drop=True),
    }


def reset_all_transactions(user: UserSettings) -> UserSettings:
    save_holdings(pd.DataFrame(columns=HOLDING_COLUMNS))
    _clear_collection("sells")
    _clear_collection("buys")
    _clear_collection("charges")
    _clear_collection("cashflow")
    db.collection("meta").document("stats").set(dict(STATS_DEFAULTS))
    user.remainingAmount = user.investment
    save_user(user)
    return user


def delete_holding(user: UserSettings, holding_id: str) -> tuple[UserSettings, pd.DataFrame]:
    holdings = load_holdings()
    match = holdings[holdings["id"] == holding_id]
    if match.empty:
        raise ValueError(f"Holding {holding_id} not found")
    row = match.iloc[0]

    etf_type = str(row["etfType"])
    avg_price = float(row["averagePrice"])
    qty = int(row["totalQuantity"])
    value = avg_price * qty
    est_charges = compute_kotak_charges(value, etf_type, side="buy")

    holdings = holdings.drop(match.index).reset_index(drop=True)
    save_holdings(holdings)

    _delete_where("buys", "holdingId", holding_id)
    rebuild_stats()  # rare operation — full rescan is acceptable

    user.remainingAmount = user.remainingAmount + value + est_charges["total"]
    save_user(user)
    return user, holdings


def reverse_buy(user: UserSettings, buy_id: str) -> tuple[UserSettings, pd.DataFrame, pd.DataFrame]:
    buys = load_buys()
    match = buys[buys["id"] == buy_id]
    if match.empty:
        raise ValueError(f"Buy record {buy_id} not found")
    row = match.iloc[0]

    etf_name = str(row["etfName"])
    qty_to_remove = int(row["quantity"])
    price = float(row["price"])
    total_charges = float(row["totalCharges"])
    value = price * qty_to_remove

    holdings = load_holdings()
    hmatch = holdings[holdings["etfName"] == etf_name]
    if hmatch.empty:
        raise ValueError(
            f"Cannot reverse: no current holding for '{etf_name}'. "
            "It may have been sold or deleted after the buy."
        )
    idx = hmatch.index[0]
    cur_avg = float(holdings.at[idx, "averagePrice"])
    cur_qty = int(holdings.at[idx, "totalQuantity"])

    if qty_to_remove > cur_qty:
        raise ValueError(
            f"Cannot reverse: current holding is only {cur_qty} units but buy was {qty_to_remove}. "
            "Some units were probably sold after this buy."
        )

    new_qty = cur_qty - qty_to_remove
    if new_qty == 0:
        holdings = holdings.drop(idx).reset_index(drop=True)
    else:
        new_avg = (cur_avg * cur_qty - price * qty_to_remove) / new_qty
        holdings.at[idx, "averagePrice"] = new_avg
        holdings.at[idx, "totalQuantity"] = new_qty
    save_holdings(holdings)

    _delete_document("buys", buy_id)
    buys = buys.drop(match.index).reset_index(drop=True)

    epoch = date(1970, 1, 1)
    try:
        buy_ep_days = (pd.to_datetime(row["buyDate"]).date() - epoch).days
    except Exception:
        buy_ep_days = (date.today() - epoch).days
    _update_stats({
        "buyCount": -1,
        "buyGross": -value,
        "buyBrokerage": -float(row["brokerageCharges"]),
        "buyTotalCharges": -total_charges,
        "openInvTotal": -value,
        "openInvDateSum": -value * buy_ep_days,
    })

    user.remainingAmount = user.remainingAmount + value + total_charges
    save_user(user)

    return user, holdings, buys


def reverse_sell(user: UserSettings, sell_id: str) -> tuple[UserSettings, pd.DataFrame, pd.DataFrame]:
    sells = load_sells()
    match = sells[sells["id"] == sell_id]
    if match.empty:
        raise ValueError(f"Sell record {sell_id} not found")
    row = match.iloc[0]

    etf_name = str(row["etfName"])
    etf_type = str(row["etfType"])
    qty = int(row["quantity"])
    sell_price = float(row["sellPrice"])
    original_avg = float(row["averagePurchasePrice"])
    brokerage = float(row["brokerageCharges"])
    tax = float(row["tax"])
    dividend = float(row["dividendPaidToSelf"])
    last_purchase_date = row["lastPurchaseDate"]

    value = sell_price * qty

    holdings = load_holdings()
    hmatch = holdings[holdings["etfName"] == etf_name]

    if hmatch.empty:
        new_row = {
            "id": str(uuid.uuid4()),
            "etfName": etf_name,
            "etfType": etf_type,
            "averagePrice": original_avg,
            "lastPurchasePrice": original_avg,
            "totalQuantity": qty,
            "lastPurchaseDate": last_purchase_date if pd.notna(last_purchase_date) else _now_iso(),
        }
        holdings = pd.concat([holdings, pd.DataFrame([new_row])], ignore_index=True)
    else:
        idx = hmatch.index[0]
        cur_avg = float(holdings.at[idx, "averagePrice"])
        cur_qty = int(holdings.at[idx, "totalQuantity"])
        restored_avg = (cur_avg * cur_qty + original_avg * qty) / (cur_qty + qty)
        holdings.at[idx, "averagePrice"] = restored_avg
        holdings.at[idx, "totalQuantity"] = cur_qty + qty
    save_holdings(holdings)

    _delete_document("sells", sell_id)
    sells = sells.drop(match.index).reset_index(drop=True)

    # Undo the sell's stats contribution; restore open inv using the stamped holdingDays
    # to recover the exact weighted buy epoch used at sell time.
    restored_inv = original_avg * qty
    epoch = date(1970, 1, 1)
    try:
        sell_ep_days = (pd.to_datetime(row["sellDate"]).date() - epoch).days
        hd = float(row.get("holdingDays", 0) or 0)
        restore_ep_days = sell_ep_days - hd  # mirrors: holding_days = sell_epoch - weighted_buy_epoch
    except Exception:
        restore_ep_days = (date.today() - epoch).days
    net_pl = (sell_price - original_avg) * qty - brokerage - tax - dividend
    _update_stats({
        "sellCount": -1,
        "sellGross": -value,
        "sellBrokerage": -brokerage,
        "sellNetPL": -net_pl,
        "sellTotalCharges": -(brokerage + tax),
        "sellDividend": -dividend,
        "openInvTotal": restored_inv,
        "openInvDateSum": restored_inv * restore_ep_days,
    })

    user.remainingAmount = (
        user.remainingAmount - value + brokerage + dividend + tax
    )
    user.investment = (
        user.investment
        - qty * (sell_price - original_avg)
        + brokerage
        + dividend
        + tax
    )
    save_user(user)

    return user, holdings, sells


def holdings_by_type(holdings: pd.DataFrame, etfs: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame(columns=["etfType", "count", "cost", "currentValue", "pnl", "pnlPct"])
    merged = holdings.merge(
        etfs[["name", "cmp"]], left_on="etfName", right_on="name", how="left"
    )
    merged["cmp"] = merged["cmp"].fillna(0).astype(float)
    merged["cost"] = merged["averagePrice"].astype(float) * merged["totalQuantity"].astype(int)
    merged["currentValue"] = merged["cmp"] * merged["totalQuantity"].astype(int)
    grp = merged.groupby("etfType").agg(
        count=("id", "count"),
        cost=("cost", "sum"),
        currentValue=("currentValue", "sum"),
    ).reset_index()
    grp["pnl"] = grp["currentValue"] - grp["cost"]
    grp["pnlPct"] = grp.apply(
        lambda r: ((r["currentValue"] - r["cost"]) / r["cost"] * 100) if r["cost"] > 0 else 0.0,
        axis=1,
    )
    return grp


def fees_by_type(sells: pd.DataFrame) -> pd.DataFrame:
    if sells.empty:
        return pd.DataFrame(
            columns=["etfType", "count", "brokerage", "tax", "dividend", "grossPL", "netPL"]
        )
    df = sells.copy()
    df["brokerageCharges"] = df["brokerageCharges"].astype(float)
    df["tax"] = df["tax"].astype(float)
    df["dividendPaidToSelf"] = df["dividendPaidToSelf"].astype(float)
    df["grossPL"] = (df["sellPrice"].astype(float) - df["averagePurchasePrice"].astype(float)) \
                   * df["quantity"].astype(float)
    df["netPL"] = df["grossPL"] - df["brokerageCharges"] - df["tax"] - df["dividendPaidToSelf"]
    grp = df.groupby("etfType").agg(
        count=("id", "count"),
        brokerage=("brokerageCharges", "sum"),
        tax=("tax", "sum"),
        dividend=("dividendPaidToSelf", "sum"),
        grossPL=("grossPL", "sum"),
        netPL=("netPL", "sum"),
    ).reset_index()
    return grp


def buyback_opportunities(
    sells: pd.DataFrame, etfs: pd.DataFrame, holdings: pd.DataFrame,
) -> list[dict]:
    if sells.empty or etfs.empty:
        return []

    held = set() if holdings.empty else set(holdings["etfName"].astype(str).tolist())

    df = sells.copy()
    df["quantity"] = df["quantity"].astype(float)
    df["sellPrice"] = df["sellPrice"].astype(float)
    df["value"] = df["quantity"] * df["sellPrice"]
    agg = df.groupby(["etfName", "etfType"]).agg(
        qtySold=("quantity", "sum"),
        valSold=("value", "sum"),
    ).reset_index()
    agg["avgSellPrice"] = agg["valSold"] / agg["qtySold"]

    m = agg.merge(
        etfs[["name", "cmp"]], left_on="etfName", right_on="name", how="left"
    )
    m["cmp"] = m["cmp"].fillna(0).astype(float)
    m = m[(m["cmp"] > 0) & (~m["etfName"].isin(held))]
    m["discountPct"] = (m["avgSellPrice"] - m["cmp"]) / m["avgSellPrice"] * 100
    m = m[m["discountPct"] > 0]
    m = m.sort_values("discountPct", ascending=False)

    return [
        {
            "name": str(r["etfName"]),
            "type": str(r["etfType"]),
            "price": float(r["cmp"]),
            "avgSellPrice": float(r["avgSellPrice"]),
            "discountPct": float(r["discountPct"]),
            "qty": 1,
        }
        for _, r in m.iterrows()
    ]


def compute_report(
    holdings: pd.DataFrame,
    sells: pd.DataFrame,
    etfs: pd.DataFrame,
) -> dict:
    total_profit = 0.0
    total_growth = 0.0
    total_tax = 0.0
    total_brokerage = 0.0
    total_dividend = 0.0

    if not sells.empty:
        q = sells["quantity"].astype(float)
        sp = sells["sellPrice"].astype(float)
        ap = sells["averagePurchasePrice"].astype(float)
        br = sells["brokerageCharges"].astype(float)
        tx = sells["tax"].astype(float)
        dv = sells["dividendPaidToSelf"].astype(float)
        gross = (sp - ap) * q
        total_profit = float(gross.sum())
        total_growth = float((gross - br - tx - dv).sum())
        total_tax = float(tx.sum())
        total_brokerage = float(br.sum())
        total_dividend = float(dv.sum())

    cost_basis = 0.0
    current_value = 0.0
    if not holdings.empty and not etfs.empty:
        m = holdings.merge(
            etfs[["name", "cmp"]], left_on="etfName", right_on="name", how="left"
        )
        m["cmp"] = m["cmp"].fillna(0).astype(float)
        cost_basis = float((m["averagePrice"].astype(float) * m["totalQuantity"].astype(int)).sum())
        current_value = float((m["cmp"] * m["totalQuantity"].astype(int)).sum())

    portfolio_pct = (
        ((current_value - cost_basis) / cost_basis) * 100 if cost_basis > 0 else 0.0
    )

    return {
        "totalProfit": total_profit,
        "totalGrowth": total_growth,
        "totalTax": total_tax,
        "totalBrokerage": total_brokerage,
        "totalDividend": total_dividend,
        "holdingsCount": int(len(holdings)),
        "holdingAmount": float(math.floor(cost_basis)),
        "currentValue": current_value,
        "portfolioPct": portfolio_pct,
    }


def compute_money_summary_from_stats(
    user: "UserSettings",
    holdings: pd.DataFrame,
    etfs: pd.DataFrame,
    _stats: dict | None = None,
) -> dict:
    """Fast version of compute_money_summary — reads meta/stats (1 doc) instead of
    scanning all buys/sells/charges. Returns the same dict shape.
    Pass _stats to reuse an already-loaded stats dict and avoid a second Firestore read."""
    s = _stats if _stats is not None else load_stats()

    buy_count        = int(s["buyCount"])
    buy_gross        = float(s["buyGross"])
    buy_brokerage    = float(s["buyBrokerage"])
    buy_total_chg    = float(s["buyTotalCharges"])
    buy_tax          = buy_total_chg - buy_brokerage
    buy_outflow      = buy_gross + buy_total_chg

    sell_count       = int(s["sellCount"])
    sell_gross       = float(s["sellGross"])
    sell_brokerage   = float(s["sellBrokerage"])
    sell_net_pl      = float(s["sellNetPL"])
    sell_total_chg   = float(s["sellTotalCharges"])
    sell_tax         = sell_total_chg - sell_brokerage
    sell_dividend    = float(s["sellDividend"])
    sell_gross_pl    = sell_net_pl + sell_total_chg + sell_dividend
    sell_inflow      = sell_gross - sell_total_chg - sell_dividend
    charges_total    = float(s["chargesTotal"])

    cost_basis = current_value = 0.0
    if not holdings.empty:
        cost_basis = float(
            (holdings["averagePrice"].astype(float) * holdings["totalQuantity"].astype(int)).sum()
        )
        if not etfs.empty:
            m = holdings.merge(etfs[["name", "cmp"]], left_on="etfName", right_on="name", how="left")
            m["cmp"] = m["cmp"].fillna(0).astype(float)
            current_value = float((m["cmp"] * m["totalQuantity"].astype(int)).sum())

    initial_deposit  = float(user.totalDeposited) if user.totalDeposited > 0 else float(user.investment) - sell_net_pl
    remaining_cash   = float(user.remainingAmount)
    account_balance  = remaining_cash + cost_basis
    expected_balance = initial_deposit + sell_net_pl - buy_total_chg - charges_total
    fees_paid_total  = buy_total_chg + sell_total_chg

    return {
        "initialDeposit":    initial_deposit,
        "currentInvestment": float(user.investment),
        "remainingCash":     remaining_cash,
        "costBasis":         cost_basis,
        "currentValue":      current_value,
        "unrealizedPL":      current_value - cost_basis,
        "buyCount":          buy_count,
        "buyGross":          buy_gross,
        "buyBrokerage":      buy_brokerage,
        "buyTax":            buy_tax,
        "buyTotalCharges":   buy_total_chg,
        "buyOutflow":        buy_outflow,
        "sellCount":         sell_count,
        "sellGross":         sell_gross,
        "sellBrokerage":     sell_brokerage,
        "sellTax":           sell_tax,
        "sellDividend":      sell_dividend,
        "sellFeesTotal":     sell_total_chg,
        "sellInflow":        sell_inflow,
        "sellGrossPL":       sell_gross_pl,
        "sellNetPL":         sell_net_pl,
        "sellCostAtSale":    sell_gross - sell_gross_pl,  # Σ(avgPrice × qty) at time of sell
        "feesPaidTotal":     fees_paid_total,
        "moneyConsumed":     fees_paid_total + sell_dividend,
        "chargesTotal":      charges_total,
        "accountBalance":    account_balance,
        "expectedBalance":   expected_balance,
        "reconcileDiff":     account_balance - expected_balance,
    }


def compute_money_summary(
    user: "UserSettings",
    buys: pd.DataFrame,
    sells: pd.DataFrame,
    holdings: pd.DataFrame,
    etfs: pd.DataFrame,
    charges: pd.DataFrame | None = None,
) -> dict:
    buy_count = 0
    buy_gross = 0.0
    buy_brokerage = 0.0
    buy_tax = 0.0
    buy_total_charges = 0.0
    buy_outflow = 0.0
    if not buys.empty:
        b = buys.copy()
        q = b["quantity"].astype(float)
        p = b["price"].astype(float)
        br = b["brokerageCharges"].astype(float)
        tx = b["tax"].astype(float)
        tc = b["totalCharges"].astype(float)
        gross = p * q
        buy_count = int(len(b))
        buy_gross = float(gross.sum())
        buy_brokerage = float(br.sum())
        buy_tax = float(tx.sum())
        buy_total_charges = float(tc.sum())
        buy_outflow = float((gross + tc).sum())

    sell_count = 0
    sell_gross = 0.0
    sell_cost_at_sale = 0.0
    sell_brokerage = 0.0
    sell_tax = 0.0
    sell_dividend = 0.0
    sell_fees_total = 0.0
    sell_inflow = 0.0
    sell_gross_pl = 0.0
    sell_net_pl = 0.0
    if not sells.empty:
        s = sells.copy()
        q = s["quantity"].astype(float)
        sp = s["sellPrice"].astype(float)
        ap = s["averagePurchasePrice"].astype(float)
        br = s["brokerageCharges"].astype(float)
        tx = s["tax"].astype(float)
        dv = s["dividendPaidToSelf"].astype(float)
        gross = sp * q
        cost_at_sale = ap * q
        sell_count = int(len(s))
        sell_gross = float(gross.sum())
        sell_cost_at_sale = float(cost_at_sale.sum())
        sell_brokerage = float(br.sum())
        sell_tax = float(tx.sum())
        sell_dividend = float(dv.sum())
        sell_fees_total = sell_brokerage + sell_tax
        sell_inflow = float((gross - br - tx - dv).sum())
        sell_gross_pl = float((gross - cost_at_sale).sum())
        sell_net_pl = float((gross - cost_at_sale - br - tx - dv).sum())

    cost_basis = 0.0
    current_value = 0.0
    if not holdings.empty:
        cost_basis = float(
            (holdings["averagePrice"].astype(float)
             * holdings["totalQuantity"].astype(int)).sum()
        )
        if not etfs.empty:
            m = holdings.merge(
                etfs[["name", "cmp"]], left_on="etfName", right_on="name", how="left"
            )
            m["cmp"] = m["cmp"].fillna(0).astype(float)
            current_value = float((m["cmp"] * m["totalQuantity"].astype(int)).sum())

    unrealized_pl = current_value - cost_basis

    current_investment = float(user.investment)
    initial_deposit = float(user.totalDeposited) if user.totalDeposited > 0 else current_investment - sell_net_pl
    remaining_cash = float(user.remainingAmount)

    charges_total = 0.0
    if charges is not None and not charges.empty:
        charges_total = float(charges["amount"].astype(float).sum())

    fees_paid_total = buy_total_charges + sell_fees_total
    money_consumed = fees_paid_total + sell_dividend

    account_balance = remaining_cash + cost_basis
    # Formula derived from first principles — independent of investment field:
    # remaining + cost_basis = totalDeposited + sell_net_pl − buy_charges − charges_total
    expected_balance = initial_deposit + sell_net_pl - buy_total_charges - charges_total
    diff = account_balance - expected_balance

    return {
        "initialDeposit": initial_deposit,
        "currentInvestment": current_investment,
        "remainingCash": remaining_cash,
        "costBasis": cost_basis,
        "currentValue": current_value,
        "unrealizedPL": unrealized_pl,
        "buyCount": buy_count,
        "buyGross": buy_gross,
        "buyBrokerage": buy_brokerage,
        "buyTax": buy_tax,
        "buyTotalCharges": buy_total_charges,
        "buyOutflow": buy_outflow,
        "sellCount": sell_count,
        "sellGross": sell_gross,
        "sellCostAtSale": sell_cost_at_sale,
        "sellBrokerage": sell_brokerage,
        "sellTax": sell_tax,
        "sellDividend": sell_dividend,
        "sellFeesTotal": sell_fees_total,
        "sellInflow": sell_inflow,
        "sellGrossPL": sell_gross_pl,
        "sellNetPL": sell_net_pl,
        "feesPaidTotal": fees_paid_total,
        "moneyConsumed": money_consumed,
        "chargesTotal": charges_total,
        "accountBalance": account_balance,
        "expectedBalance": expected_balance,
        "reconcileDiff": diff,
    }


def money_by_etf(
    buys: pd.DataFrame,
    sells: pd.DataFrame,
    holdings: pd.DataFrame,
    etfs: pd.DataFrame,
) -> pd.DataFrame:
    rows: dict[str, dict] = {}

    def _row(name: str, etf_type: str) -> dict:
        if name not in rows:
            rows[name] = {
                "etfName": name, "etfType": etf_type,
                "buyQty": 0.0, "buyValue": 0.0, "buyFees": 0.0, "buyOutflow": 0.0,
                "sellQty": 0.0, "sellGross": 0.0, "sellFees": 0.0,
                "sellInflow": 0.0, "sellNetPL": 0.0,
                "heldQty": 0, "costBasis": 0.0, "currentValue": 0.0,
                "unrealizedPL": 0.0,
            }
        return rows[name]

    if not buys.empty:
        for _, b in buys.iterrows():
            r = _row(str(b["etfName"]), str(b["etfType"]))
            q = float(b["quantity"]); p = float(b["price"])
            tc = float(b["totalCharges"])
            r["buyQty"] += q
            r["buyValue"] += p * q
            r["buyFees"] += tc
            r["buyOutflow"] += p * q + tc

    if not sells.empty:
        for _, s in sells.iterrows():
            r = _row(str(s["etfName"]), str(s["etfType"]))
            q = float(s["quantity"]); sp = float(s["sellPrice"])
            ap = float(s["averagePurchasePrice"])
            br = float(s["brokerageCharges"]); tx = float(s["tax"])
            dv = float(s["dividendPaidToSelf"])
            gross = sp * q
            r["sellQty"] += q
            r["sellGross"] += gross
            r["sellFees"] += br + tx
            r["sellInflow"] += gross - br - tx - dv
            r["sellNetPL"] += (sp - ap) * q - br - tx - dv

    cmp_map: dict[str, float] = {}
    if not etfs.empty:
        cmp_map = dict(zip(etfs["name"].astype(str), etfs["cmp"].astype(float)))

    if not holdings.empty:
        for _, h in holdings.iterrows():
            name = str(h["etfName"])
            r = _row(name, str(h["etfType"]))
            qty = int(h["totalQuantity"])
            avg = float(h["averagePrice"])
            cmp_v = float(cmp_map.get(name, 0.0))
            r["heldQty"] = qty
            r["costBasis"] = avg * qty
            r["currentValue"] = cmp_v * qty
            r["unrealizedPL"] = (cmp_v - avg) * qty

    if not rows:
        return pd.DataFrame(columns=[
            "etfName", "etfType", "buyQty", "buyValue", "buyFees", "buyOutflow",
            "sellQty", "sellGross", "sellFees", "sellInflow", "sellNetPL",
            "heldQty", "costBasis", "currentValue", "unrealizedPL", "netInvested",
        ])

    df = pd.DataFrame(rows.values())
    df["netInvested"] = df["buyOutflow"] - df["sellInflow"]
    df = df.sort_values("buyOutflow", ascending=False).reset_index(drop=True)
    return df


def fix_reconciliation_drift(
    user: "UserSettings",
    buys: pd.DataFrame,
    sells: pd.DataFrame,
    holdings: pd.DataFrame,
    etfs: pd.DataFrame,
    charges: pd.DataFrame | None = None,
) -> tuple["UserSettings", float]:
    """Eliminate reconciliation drift by adjusting remainingAmount.

    Subtracting the diff from remainingAmount re-aligns the books.
    Returns (updated_user, adjustment_applied).
    """
    m = compute_money_summary(user, buys, sells, holdings, etfs, charges)
    diff = m["reconcileDiff"]
    if abs(diff) < 0.001:
        return user, 0.0
    user.remainingAmount = user.remainingAmount - diff
    save_user(user)
    return user, diff


def compute_holding_time_stats(
    holdings: pd.DataFrame,
    sells: pd.DataFrame,
    buys: pd.DataFrame | None = None,
) -> dict:
    """Weighted-average holding time across open and closed positions.

    Formula: Σ(Investment Amount × Holding Days) ÷ Total Investment Amount
    For open positions each individual buy lot is used (price × qty × days since that buy).
    For closed positions sellDate − lastPurchaseDate is used per sell record.
    """
    today = date.today()

    def _wavg(rows: list[dict]) -> float:
        total = sum(r["costBasis"] for r in rows)
        if total <= 0:
            return 0.0
        return sum(r["holdingDays"] * r["costBasis"] for r in rows) / total

    # ── Open positions — per buy-lot ──────────────────────────────────────
    open_rows: list[dict] = []
    if not holdings.empty:
        active_ids = set(holdings["id"].astype(str).tolist())

        if buys is not None and not buys.empty:
            # Per-lot: buy lots whose holdingId is still active (excludes prior ownership cycles)
            for _, b in buys[buys["holdingId"].isin(active_ids)].iterrows():
                try:
                    buy_dt = pd.to_datetime(b["buyDate"]).date()
                    days   = max(0, (today - buy_dt).days)
                except Exception:
                    days = 0
                lot_inv = float(b["price"]) * float(b["quantity"])
                open_rows.append({"etfName": str(b["etfName"]), "holdingDays": days, "costBasis": lot_inv})
        else:
            # Fallback when buys not provided: use lastPurchaseDate + total cost basis
            for _, row in holdings.iterrows():
                try:
                    buy_dt = pd.to_datetime(row["lastPurchaseDate"]).date()
                    days   = max(0, (today - buy_dt).days)
                except Exception:
                    days = 0
                cost_basis = float(row["averagePrice"]) * int(row["totalQuantity"])
                open_rows.append({"etfName": str(row["etfName"]), "holdingDays": days, "costBasis": cost_basis})

    # Per-ETF rollup for the table display
    etf_wavg: dict[str, dict] = {}
    for r in open_rows:
        e = r["etfName"]
        if e not in etf_wavg:
            etf_wavg[e] = {"etfName": e, "_num": 0.0, "_den": 0.0}
        etf_wavg[e]["_num"] += r["holdingDays"] * r["costBasis"]
        etf_wavg[e]["_den"] += r["costBasis"]
    open_summary: list[dict] = []
    for e, v in etf_wavg.items():
        wavg_d = v["_num"] / v["_den"] if v["_den"] > 0 else 0.0
        open_summary.append({"etfName": e, "holdingDays": round(wavg_d, 1), "costBasis": v["_den"]})

    # ── Closed positions — per sell record ────────────────────────────────
    closed_rows: list[dict] = []
    if not sells.empty:
        for _, row in sells.iterrows():
            try:
                stamped = float(row.get("holdingDays") or 0)
                if stamped > 0:
                    # Use the precise weighted-avg buy-lot value stamped at sell time
                    days = stamped
                else:
                    # Legacy record: fall back to simple sellDate − lastPurchaseDate
                    sell_dt = pd.to_datetime(row["sellDate"]).date()
                    buy_dt  = pd.to_datetime(row["lastPurchaseDate"]).date()
                    days    = max(0, (sell_dt - buy_dt).days)
            except Exception:
                days = 0
            cost_basis = float(row["averagePurchasePrice"]) * float(row["quantity"])
            closed_rows.append({"etfName": str(row["etfName"]), "holdingDays": days, "costBasis": cost_basis})

    return {
        "openPositions":         open_summary,
        "closedPositions":       closed_rows,
        "weightedAvgDaysOpen":   _wavg(open_rows),
        "weightedAvgDaysClosed": _wavg(closed_rows),
        "weightedAvgDaysAll":    _wavg(open_rows + closed_rows),
    }


def money_by_month(buys: pd.DataFrame, sells: pd.DataFrame) -> pd.DataFrame:
    parts = []
    if not buys.empty:
        b = buys.copy()
        b["month"] = pd.to_datetime(b["buyDate"], errors="coerce").dt.strftime("%Y-%m")
        b["buyOutflow"] = b["price"].astype(float) * b["quantity"].astype(float) \
                        + b["totalCharges"].astype(float)
        b["buyFees"] = b["totalCharges"].astype(float)
        parts.append(b.groupby("month").agg(
            buyOutflow=("buyOutflow", "sum"),
            buyFees=("buyFees", "sum"),
        ).reset_index())
    if not sells.empty:
        s = sells.copy()
        s["month"] = pd.to_datetime(s["sellDate"], errors="coerce").dt.strftime("%Y-%m")
        s["sellGross"] = s["sellPrice"].astype(float) * s["quantity"].astype(float)
        s["sellFeesAll"] = s["brokerageCharges"].astype(float) + s["tax"].astype(float)
        s["sellInflow"] = s["sellGross"] - s["sellFeesAll"] - s["dividendPaidToSelf"].astype(float)
        parts.append(s.groupby("month").agg(
            sellInflow=("sellInflow", "sum"),
            sellFees=("sellFeesAll", "sum"),
            dividend=("dividendPaidToSelf", "sum"),
        ).reset_index())

    if not parts:
        return pd.DataFrame(columns=[
            "month", "buyOutflow", "buyFees", "sellInflow", "sellFees", "dividend",
            "netCashFlow",
        ])

    out = parts[0]
    for p in parts[1:]:
        out = out.merge(p, on="month", how="outer")
    for col in ("buyOutflow", "buyFees", "sellInflow", "sellFees", "dividend"):
        if col not in out.columns:
            out[col] = 0.0
    out = out.fillna(0.0).sort_values("month").reset_index(drop=True)
    out["netCashFlow"] = out["sellInflow"] - out["buyOutflow"]
    return out[["month", "buyOutflow", "buyFees", "sellInflow", "sellFees",
                "dividend", "netCashFlow"]]
