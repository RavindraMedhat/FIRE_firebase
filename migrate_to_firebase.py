"""One-time migration: CSV → Firebase Firestore.

Run ONCE (after placing serviceAccountKey.json in the project folder):

    python migrate_to_firebase.py

Reads data from ./data/*.csv and writes it to your Firebase project.
Safe to re-run — it will overwrite existing documents with the same IDs.
"""

import math
import sys
from pathlib import Path

import pandas as pd

import firebase_admin
from firebase_admin import credentials, firestore

KEY_FILE = Path(__file__).parent / "serviceAccountKey.json"

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(str(KEY_FILE)))
db = firestore.client()

DATA_DIR = Path(__file__).parent / "data"


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _clean_row(d: dict) -> dict:
    return {k: _clean(v) for k, v in d.items()}


def migrate_collection(csv_path: Path, col_name: str, id_field: str, columns: list[str]) -> int:
    if not csv_path.exists():
        print(f"  ⚠  {csv_path.name} not found — skipping.")
        return 0
    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"  ⚠  {csv_path.name} is empty — skipping.")
        return 0
    col_ref = db.collection(col_name)
    batch = db.batch()
    count = 0
    for _, row in df[columns].iterrows():
        data = _clean_row(row.to_dict())
        doc_ref = col_ref.document(str(data[id_field]))
        batch.set(doc_ref, data)
        count += 1
    batch.commit()
    return count


def migrate_user(csv_path: Path) -> bool:
    if not csv_path.exists():
        print(f"  ⚠  {csv_path.name} not found — skipping.")
        return False
    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"  ⚠  {csv_path.name} is empty — skipping.")
        return False
    row = df.iloc[0].to_dict()
    data = _clean_row(row)
    db.collection("meta").document("user").set(data)
    return True


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


def main():
    print("🔥 FIRE — CSV → Firebase Firestore migration")
    print(f"   Data dir: {DATA_DIR}\n")

    # Test connectivity
    try:
        db.collection("meta").document("_ping").set({"ok": True})
        db.collection("meta").document("_ping").delete()
    except Exception as e:
        print(f"✗ Cannot reach Firebase: {e}")
        print("  Check that serviceAccountKey.json is present and valid.")
        sys.exit(1)

    print("user.csv →  meta/user")
    ok = migrate_user(DATA_DIR / "user.csv")
    print(f"  {'✓ migrated' if ok else 'skipped'}")

    print("holdings.csv → holdings/")
    n = migrate_collection(DATA_DIR / "holdings.csv", "holdings", "id", HOLDING_COLUMNS)
    print(f"  ✓ {n} docs")

    print("buys.csv → buys/")
    n = migrate_collection(DATA_DIR / "buys.csv", "buys", "id", BUY_COLUMNS)
    print(f"  ✓ {n} docs")

    print("sells.csv → sells/")
    n = migrate_collection(DATA_DIR / "sells.csv", "sells", "id", SELL_COLUMNS)
    print(f"  ✓ {n} docs")

    print("\n✅ Migration complete. You can now start the Streamlit app.")


if __name__ == "__main__":
    main()
