# 🔥 FIRE — Financial Independence Investment Tracker

A personal ETF/stock investment tracker built with **Python + Streamlit**.  
Data is stored in **Firebase Firestore** — visible live at [console.firebase.google.com](https://console.firebase.google.com/project/myfire-1783b/firestore).

> **Other branches**
> - `master` — original version, CSV file storage, no login
> - `feature/firebase-firestore-csv` — flexible version supporting both Firebase and CSV backends

---

## Features

- Track ETF and stock holdings with average price, quantity, and P&L
- Log every buy and sell with automatic Kotak Securities charge calculation
- Dashboard with portfolio summary, unrealised P&L, and type breakdown
- Buy/sell suggestions based on 20-DMA dip threshold
- Sell history with reversal support
- Reports page — money flow, fees, month-wise breakdown
- Password-protected login (single user)

---

## Project Structure

```
FIRE/
├── app.py                      # Streamlit UI — all pages and components
├── data_manager.py             # Firebase read/write + all business logic
├── migrate_to_firebase.py      # One-shot: imports CSV data into Firebase
├── export_from_firebase.py     # Backup: exports Firebase data to CSV
├── requirements.txt
├── firebase.json               # Firebase project config
├── .firebaserc                 # Bound to project: myfire-1783b
├── firestore.rules             # Firestore security rules (permissive for dev)
├── firestore.indexes.json      # Firestore composite indexes
├── serviceAccountKey.json      # ⚠️  LOCAL ONLY — gitignored, never commit
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
| `meta/user` | User settings — investment amount, remaining cash, thresholds |
| `meta/config` | App password hash (SHA-256) |
| `holdings/{id}` | Open positions — one document per ETF/stock held |
| `buys/{id}` | Buy transaction log — one document per buy |
| `sells/{id}` | Sell transaction log — one document per sell |

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

### 4. (Optional) Migrate existing CSV data

If you have data in `./data/*.csv` from the old CSV version, import it once:

```bash
python migrate_to_firebase.py
```

### 5. Run the app

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

- **First launch** → prompted to create a password
- **Every session after** → login screen before the app loads

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

> Your `.streamlit/secrets.toml` already has all values filled in — just open and copy-paste.

### 3. Deploy

Click **Deploy**. Credential resolution:

| Environment | Credential source |
|-------------|------------------|
| Local | `serviceAccountKey.json` file |
| Streamlit Cloud | `st.secrets["gcp_service_account"]` |

---

## Utility Scripts

### `migrate_to_firebase.py` — CSV → Firebase (run once)

Imports your existing CSV data into Firestore. Safe to re-run — overwrites by document ID.

```bash
python migrate_to_firebase.py
```

Reads: `data/user.csv`, `data/holdings.csv`, `data/buys.csv`, `data/sells.csv`

---

### `export_from_firebase.py` — Firebase → CSV (backup anytime)

Downloads everything from Firestore back to local CSV files.

```bash
python export_from_firebase.py
```

Saves to `data/` folder. Useful as a backup or to switch back to the CSV version.

---

## Charges Model (Kotak Securities — Delivery, 2025)

| Type | Brokerage | STT buy | STT sell |
|------|-----------|---------|---------|
| Equity ETF | 0.05% | 0% | 0.001% |
| Jewellery ETF | 0.05% | 0% | 0.001% |
| Stocks | 0.10% | 0.1% | 0.1% |

**Additional on every trade:** Exchange transaction 0.00297% · SEBI 0.0001% · Stamp duty 0.015% (buy only) · GST 18% on (brokerage + exchange + SEBI)

---

## ETF Data Source

Prices are fetched live from a **Google Apps Script API** and cached in `data/etfs_cache.csv`.  
Click **Refresh ETFs** in the sidebar to pull fresh data anytime.

---

## Security

| File | Reason gitignored |
|------|-------------------|
| `serviceAccountKey.json` | Firebase private key — never commit |
| `.streamlit/secrets.toml` | Same key in TOML format for Streamlit |
| `data set/` | Personal watchlist spreadsheets |
| `fire_mobile/` | Old mobile version |
| `fire full/` | Old Flutter version |

---

## Git Remotes

| Remote | Repo | Branch |
|--------|------|--------|
| `origin` | github.com/RavindraMedhat/FIRE_web | `master` — original CSV version |
| `firebase` | github.com/RavindraMedhat/FIRE_firebase | `feature/firebase-firestore` — this repo |

```bash
# Push changes to this repo
git push firebase feature/firebase-firestore
```
