"""Export Firebase Firestore data back to CSV files.

Run any time you want a local CSV backup:

    python export_from_firebase.py

Saves files to ./data/  (same location the old CSV app used).
Safe to re-run — existing CSVs are overwritten.
"""

import sys
from pathlib import Path

import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

# ── Firebase init ─────────────────────────────────────────────────────────────
KEY_FILE = Path(__file__).parent / "serviceAccountKey.json"

if not firebase_admin._apps:
    if not KEY_FILE.exists():
        print("✗ serviceAccountKey.json not found.")
        sys.exit(1)
    firebase_admin.initialize_app(credentials.Certificate(str(KEY_FILE)))

db = firestore.client()

# ── Column order (matches original CSV schema) ────────────────────────────────
USER_COLUMNS = [
    "userName", "investment", "remainingAmount", "taxPercentage",
    "brokeragePercentage", "dividendPercentage", "sellProfitTarget", "buyInDipThreshold",
]
HOLDING_COLUMNS = [
    "id", "etfName", "etfType", "averagePrice", "lastPurchasePrice",
    "totalQuantity", "lastPurchaseDate",
]
SELL_COLUMNS = [
    "id", "etfName", "etfType", "quantity", "averagePurchasePrice", "sellPrice",
    "brokerageCharges", "tax", "dividendPaidToSelf", "lastPurchaseDate", "sellDate",
]
BUY_COLUMNS = [
    "id", "holdingId", "etfName", "etfType", "quantity", "price",
    "brokerageCharges", "tax", "totalCharges", "buyDate",
]

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def export_user() -> bool:
    doc = db.collection("meta").document("user").get()
    if not doc.exists:
        print("  ⚠  meta/user not found — skipping.")
        return False
    row = doc.to_dict()
    df = pd.DataFrame([[row.get(c) for c in USER_COLUMNS]], columns=USER_COLUMNS)
    df.to_csv(DATA_DIR / "user.csv", index=False)
    return True


def export_collection(col_name: str, columns: list[str], filename: str) -> int:
    docs = db.collection(col_name).stream()
    rows = [doc.to_dict() for doc in docs]
    if not rows:
        df = pd.DataFrame(columns=columns)
    else:
        df = pd.DataFrame(rows)
        for col in columns:
            if col not in df.columns:
                df[col] = None
        df = df[columns]
    df.to_csv(DATA_DIR / filename, index=False)
    return len(rows)


def main():
    print("🔥 FIRE — Firebase → CSV export")
    print(f"   Output: {DATA_DIR}\n")

    # Test connectivity
    try:
        db.collection("meta").document("_ping").set({"ok": True})
        db.collection("meta").document("_ping").delete()
    except Exception as e:
        print(f"✗ Cannot reach Firebase: {e}")
        sys.exit(1)

    print("meta/user  →  user.csv")
    ok = export_user()
    print(f"  {'✓ exported' if ok else 'skipped'}")

    print("holdings/  →  holdings.csv")
    n = export_collection("holdings", HOLDING_COLUMNS, "holdings.csv")
    print(f"  ✓ {n} rows")

    print("buys/      →  buys.csv")
    n = export_collection("buys", BUY_COLUMNS, "buys.csv")
    print(f"  ✓ {n} rows")

    print("sells/     →  sells.csv")
    n = export_collection("sells", SELL_COLUMNS, "sells.csv")
    print(f"  ✓ {n} rows")

    print(f"\n✅ Export complete. Files saved to {DATA_DIR}/")


if __name__ == "__main__":
    main()
