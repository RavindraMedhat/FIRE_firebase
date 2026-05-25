# 🔥 FIRE — Financial Independence Investment Tracker

A personal ETF/stock investment tracker built with **Python + Streamlit**.  
Data is stored in **Firebase Firestore** — visible live at [console.firebase.google.com](https://console.firebase.google.com/project/myfire-1783b/firestore).

> **Other branches**
> - `master` — original version, CSV file storage, no login
> - `feature/firebase-firestore-csv` — hybrid version supporting both Firebase and CSV backends

---

## Features

- **8-page app**: Home, Suggestions, Listed ETFs, Transactions, Sell History, Reports, Settings, Info
- Track ETF and stock holdings with weighted-average price, quantity, and P&L
- **Per-lot weighted-average holding time** on every holding card — computed from actual buy records, not just last purchase date
- Log every buy and sell with automatic Kotak Securities charge calculation
- Portfolio dashboard: allocation cards, 3-tab holdings filter, recent activity (paginated — 5 docs, no full scan)
- Buy/sell suggestions based on 20-DMA dip — fresh picks + buyback candidates
- Sell history with per-sell formula cards, per-sell `holdingDays` stamped permanently at sell time, and reversal support
- Transactions log: paginated buy / sell / charges / cashflow tabs with date filter
- **Reports**: 5-chapter storytelling layout — headline, how money is working, what it cost, ledger verification, month-by-month
- **`meta/stats` running totals**: incremented on every write — Reports loads with 1 Firestore read, no full collection scans
- **O(1) Firestore writes**: all buy/sell/delete paths use surgical document ops, never bulk replace
- Demat AMC auto-deduction every 30 days (logged to `charges` collection)
- Deposit / withdrawal tracking with full cashflow history
- Password-protected login — HMAC-SHA256 session tokens, 7-hour expiry

---

## Project Structure

```
FIRE/
├── app.py                      # Streamlit UI — all 8 pages, auth, routing, components
├── data_manager.py             # Firebase read/write + all business logic + charge calculations
├── migrate_to_firebase.py      # One-shot: imports CSV data into Firestore
├── export_from_firebase.py     # Backup: exports Firestore data to CSV
├── requirements.txt
├── firebase.json               # Firebase project config
├── .firebaserc                 # Bound to project: myfire-1783b
├── firestore.rules             # Firestore security rules
├── firestore.indexes.json      # Composite indexes for pagination queries
├── serviceAccountKey.json      # ⚠️  LOCAL ONLY — gitignored, never commit
├── DOCUMENTATION.html          # In-app docs — rendered on the ℹ️ Info page
├── .streamlit/
│   ├── config.toml             # Streamlit theme config
│   └── secrets.toml            # ⚠️  LOCAL ONLY — gitignored, never commit
└── data/
    └── etfs_cache.csv          # Live ETF price cache (local, auto-refreshed)
```

---

## Firebase Project

- **Project ID:** `myfire-1783b`
- **Console:** https://console.firebase.google.com/project/myfire-1783b/firestore

### Firestore Collections

| Path | What it stores |
|------|---------------|
| `meta/user` | User settings — investment, remaining cash, thresholds, AMC config |
| `meta/config` | App password hash (HMAC-SHA256 key) |
| `meta/stats` | Running totals — buy/sell counts, gross amounts, charges, open inv sum — updated on every write; enables O(1) Reports |
| `holdings/{id}` | Open positions — one document per ETF/stock held |
| `buys/{id}` | Buy transaction log — one document per buy event |
| `sells/{id}` | Sell transaction log — includes `holdingDays` stamped permanently at sell time |
| `charges/{id}` | Non-trade charges — Demat AMC, DP fees, manual entries |
| `cashflow/{id}` | Deposit / withdrawal log — every bank transfer in or out |

---

## Local Development Setup

### 1. Clone and switch to this branch

```bash
git clone https://github.com/RavindraMedhat/FIRE_firebase.git
cd FIRE_firebase
git checkout feature/firebase-firestore
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add Firebase credentials

1. Go to [Firebase Console](https://console.firebase.google.com) → project `myfire-1783b`
2. Click **Gear icon → Project settings → Service accounts**
3. Click **Generate new private key** → download the JSON file
4. Save it as `serviceAccountKey.json` in the project root

> Gitignored — will never be committed to git.

### 4. Run the app

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

- **First launch** → prompted to create a password (stored as HMAC key in Firestore `meta/config`)
- **Every session** → login screen → valid for 7 hours (token stored in URL query param `?s=...`)

---

## Deploying on Streamlit Cloud

### 1. Create the app

- Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
- **Repo:** `RavindraMedhat/FIRE_firebase`
- **Branch:** `feature/firebase-firestore`
- **Main file:** `app.py`

### 2. Add secrets

Click **Advanced settings → Secrets** and paste the contents of your local `.streamlit/secrets.toml`.  
It contains your Firebase service account key in this format:

```toml
[gcp_service_account]
type = "service_account"
project_id = "myfire-1783b"
private_key_id = "your_key_id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk-xxxxx@myfire-1783b.iam.gserviceaccount.com"
client_id = "your_client_id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"
```

### 3. Deploy

Click **Deploy**. Credential resolution:

| Environment | Credential source |
|-------------|------------------|
| Local | `serviceAccountKey.json` file |
| Streamlit Cloud | `st.secrets["gcp_service_account"]` |

---

## Utility Scripts

### `migrate_to_firebase.py` — CSV → Firebase (run once)

Imports existing CSV data into Firestore. Safe to re-run — overwrites by document ID.

```bash
python migrate_to_firebase.py
```

Reads: `data/user.csv`, `data/holdings.csv`, `data/buys.csv`, `data/sells.csv`

### `export_from_firebase.py` — Firebase → CSV (backup anytime)

Downloads everything from Firestore back to local CSV files.

```bash
python export_from_firebase.py
```

Saves to `data/` folder.

---

## Charges Model (Kotak Securities — Delivery, 2025)

| Type | Brokerage | STT buy | STT sell |
|------|-----------|---------|---------|
| Equity ETF | 0.05% | 0% | 0.001% |
| Jewellery ETF | 0.05% | 0% | 0.001% |
| Stocks | 0.10% | 0.1% | 0.1% |

**Additional on every trade:** Exchange transaction 0.00297% · SEBI 0.0001% · Stamp duty 0.015% (buy only) · GST 18% on (brokerage + exchange + SEBI)

**Not auto-computed — log manually via Settings → Add Manual Charge:**
- DP charges: ₹27 min / ISIN / day (auto-deducted by Kotak on delivery sells)
- Demat AMC: ₹18.88/month (₹16 + 18% GST) — the app auto-deducts this every 30 days

---

## Key Concepts

### investment vs remainingAmount vs totalDeposited

| Field | Meaning | Changes when |
|-------|---------|-------------|
| `totalDeposited` | Cumulative bank deposits — raw money added | Only on deposit / withdrawal |
| `investment` | `totalDeposited + Σ net realized P&L` | On every sell (up on profit, down on loss) |
| `remainingAmount` | Liquid cash right now | Decreases on buy + AMC; increases on sell proceeds |

### Weighted average price on buy

```
new_avg = (old_avg × old_qty + price × qty) / (old_qty + qty)
```

Average price is not adjusted on partial sells — it stays until you buy more.

### Realized P&L on sell

```
gross_pl = qty × (sell_price − avg_buy_price)
net_pl   = gross_pl − brokerage − tax − dividend_paid_to_self
```

`investment` is updated by `+net_pl` on every sell.

---

## ETF Data Source

Prices are fetched live from a **Google Apps Script API** and cached in `data/etfs_cache.csv`.  
Click **🔄 Refresh ETFs** in the sidebar to pull fresh data anytime.

---

## Security

| File | Reason gitignored |
|------|-------------------|
| `serviceAccountKey.json` | Firebase private key — never commit |
| `.streamlit/secrets.toml` | Same key in TOML format for Streamlit Cloud |

---

## Git Remotes

| Remote | Repo | Branch |
|--------|------|--------|
| `origin` | github.com/RavindraMedhat/FIRE_web | `master` — original CSV version |
| `firebase` | github.com/RavindraMedhat/FIRE_firebase | `feature/firebase-firestore` — this repo |

```bash
git push firebase feature/firebase-firestore
```
