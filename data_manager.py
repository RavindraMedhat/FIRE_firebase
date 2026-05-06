"""Firestore-backed data layer + ETF API fetching for the FIRE Python app."""

from __future__ import annotations

import math
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
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
    """Delete all existing docs then write every row in df."""
    col_ref = db.collection(col_name)
    existing = list(col_ref.stream())
    batch = db.batch()
    for doc in existing:
        batch.delete(doc.reference)
    for _, row in df.iterrows():
        data = _clean_row(row.to_dict())
        batch.set(col_ref.document(str(data[id_field])), data)
    batch.commit()


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


# ── Sells ────────────────────────────────────────────────────────────────────

def load_sells() -> pd.DataFrame:
    return _collection_to_df("sells", SELL_COLUMNS)


def save_sells(df: pd.DataFrame) -> None:
    _replace_collection("sells", df[SELL_COLUMNS], "id")


# ── Buys ─────────────────────────────────────────────────────────────────────

def load_buys() -> pd.DataFrame:
    return _collection_to_df("buys", BUY_COLUMNS)


def save_buys(df: pd.DataFrame) -> None:
    _replace_collection("buys", df[BUY_COLUMNS], "id")


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
        value = price * qty
        charges = compute_kotak_charges(value, str(h["etfType"]), side="buy")
        new_rows.append({
            "id": str(uuid.uuid4()),
            "holdingId": hid,
            "etfName": str(h["etfName"]),
            "etfType": str(h["etfType"]),
            "quantity": qty,
            "price": price,
            "brokerageCharges": charges["brokerage"],
            "tax": charges["tax"],
            "totalCharges": charges["total"],
            "buyDate": str(h["lastPurchaseDate"]) if pd.notna(h.get("lastPurchaseDate")) else _now_iso(),
        })
    if new_rows:
        buys = pd.concat([buys, pd.DataFrame(new_rows)], ignore_index=True)
        save_buys(buys)
    return len(new_rows)


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

    buys = load_buys()
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
    buys = pd.concat([buys, pd.DataFrame([buy_row])], ignore_index=True)
    save_buys(buys)

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
    sells = load_sells()

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
    }
    sells = pd.concat([sells, pd.DataFrame([sell_row])], ignore_index=True)
    save_sells(sells)

    if remaining_qty == 0:
        holdings = holdings.drop(idx).reset_index(drop=True)
    else:
        new_avg = (old_avg * old_qty - sell_price * quantity) / remaining_qty
        holdings.at[idx, "averagePrice"] = new_avg
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

    return user, holdings, sells, charges


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
    save_sells(pd.DataFrame(columns=SELL_COLUMNS))
    save_buys(pd.DataFrame(columns=BUY_COLUMNS))
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

    buys = load_buys()
    if not buys.empty:
        buys = buys[buys["holdingId"] != holding_id].reset_index(drop=True)
        save_buys(buys)

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

    buys = buys.drop(match.index).reset_index(drop=True)
    save_buys(buys)

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
        restored_avg = (cur_avg * cur_qty + sell_price * qty) / (cur_qty + qty)
        holdings.at[idx, "averagePrice"] = restored_avg
        holdings.at[idx, "totalQuantity"] = cur_qty + qty
    save_holdings(holdings)

    sells = sells.drop(match.index).reset_index(drop=True)
    save_sells(sells)

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


def compute_money_summary(
    user: "UserSettings",
    buys: pd.DataFrame,
    sells: pd.DataFrame,
    holdings: pd.DataFrame,
    etfs: pd.DataFrame,
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
    initial_deposit = current_investment - sell_net_pl
    remaining_cash = float(user.remainingAmount)

    fees_paid_total = buy_total_charges + sell_fees_total
    money_consumed = fees_paid_total + sell_dividend

    account_balance = remaining_cash + cost_basis
    expected_balance = initial_deposit + sell_gross_pl - money_consumed
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
