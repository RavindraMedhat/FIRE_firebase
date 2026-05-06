# 🔥 FIRE — Financial Independence Investment Tracker

A personal ETF/stock investment tracker built with Python + Streamlit.  
Tracks holdings, buys, sells, P&L, charges (Kotak Securities), and suggestions.

Supports **two backends** — switch with one env variable, no code changes needed:

| Backend | Where data lives | When to use |
|---------|-----------------|-------------|
| `firebase` *(default)* | Firebase Firestore cloud | Deployment, multi-device |
| `csv` | Local CSV files in `./data/` | Offline, no internet, quick local use |

---

## Project Structure

```
FIRE/
├── app.py                      # Streamlit UI (all pages)
├── data_manager.py             # Backend selector + all business logic
├── models.py                   # Shared types: UserSettings, column schemas
├── backends/
│   ├── csv_backend.py          # CSV I/O (reads/writes ./data/*.csv)
│   └── firebase_backend.py     # Firestore I/O (reads/writes Firebase)
├── migrate_to_firebase.py      # One-shot: CSV → Firebase import
├── export_from_firebase.py     # Anytime: Firebase → CSV backup
├── requirements.txt
├── firebase.json               # Firebase project config
├── .firebaserc                 # Binds to project myfire-1783b
├── firestore.rules             # Firestore security rules
├── firestore.indexes.json      # Firestore indexes
├── serviceAccountKey.json      # ⚠️  LOCAL ONLY — never committed
├── .streamlit/
│   ├── config.toml             # Streamlit theme config
│   └── secrets.toml            # ⚠️  LOCAL ONLY — never committed
└── data/
    ├── etfs_cache.csv          # ETF price cache (always local, auto-refreshed)
    ├── config.json             # ⚠️  LOCAL ONLY — password hash (CSV mode only)
    ├── holdings.csv            # Used by CSV backend / export snapshots
    ├── buys.csv                # Used by CSV backend / export snapshots
    ├── sells.csv               # Used by CSV backend / export snapshots
    └── user.csv                # Used by CSV backend / export snapshots
```

---

## Firebase Project

- **Project ID:** `myfire-1783b`
- **Console:** https://console.firebase.google.com/project/myfire-1783b/firestore

### Firestore Collections

| Collection | What it stores |
|------------|---------------|
| `meta/user` | User settings (investment, remaining cash, thresholds) |
| `meta/config` | App password hash |
| `holdings/` | Current open positions (one doc per holding) |
| `buys/` | Buy transaction log (one doc per buy) |
| `sells/` | Sell transaction log (one doc per sell) |

---

## Switching Backends

### Run with Firebase (default)

```bash
streamlit run app.py
```

### Run with CSV files

```bash
FIRE_BACKEND=csv streamlit run app.py
```

### On Streamlit Cloud — add one line to Secrets

```toml
FIRE_BACKEND = "csv"    # omit this line (or set "firebase") for Firebase
```

> `data_manager.py` checks the `FIRE_BACKEND` env var first, then `st.secrets`, then defaults to `firebase`.

---

## Local Development Setup

### 1. Clone the repo

```bash
git clone https://github.com/RavindraMedhat/FIRE_firebase.git
cd FIRE_firebase
git checkout feature/firebase-firestore
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3a. Firebase backend — add credentials

- Go to [Firebase Console](https://console.firebase.google.com) → project `myfire-1783b`
- **Gear icon → Project settings → Service accounts → Generate new private key**
- Save the downloaded file as `serviceAccountKey.json` in the project root

> Gitignored — will never be committed.

### 3b. CSV backend — no credentials needed

Just run with `FIRE_BACKEND=csv`. Data is saved to `./data/*.csv` automatically.

### 4. Run the app

```bash
# Firebase
streamlit run app.py

# CSV
FIRE_BACKEND=csv streamlit run app.py
```

Opens at http://localhost:8501

**First time:** you will be asked to create a password.  
**Every session after:** login screen appears before the app loads.

> Password is stored in Firebase (`meta/config`) for the Firebase backend,  
> and in `data/config.json` (gitignored) for the CSV backend.

---

## Deploying on Streamlit Cloud

### 1. Go to share.streamlit.io

- Click **New app**
- Repo: `RavindraMedhat/FIRE_firebase`
- Branch: `feature/firebase-firestore`
- Main file: `app.py`

### 2. Add Secrets (replaces serviceAccountKey.json in the cloud)

- Click **Advanced settings → Secrets**
- Paste the entire contents of your local `.streamlit/secrets.toml`
- It looks like this (fill in your values from `serviceAccountKey.json`):

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

> Your local `.streamlit/secrets.toml` already has all this filled in — just open it and copy-paste.

### 3. Deploy

Click **Deploy**. The app will:
- Use `serviceAccountKey.json` when running locally
- Use `st.secrets["gcp_service_account"]` when running on Streamlit Cloud

---

## Utility Scripts

### Migrate CSV → Firebase (run once after fresh setup)

If you have old CSV data in `data/` and want to load it into Firebase:

```bash
python migrate_to_firebase.py
```

Migrates: `user.csv`, `holdings.csv`, `buys.csv`, `sells.csv`

---

### Export Firebase → CSV (backup anytime)

To get a local CSV snapshot of everything in Firebase:

```bash
python export_from_firebase.py
```

Saves to `data/` folder. Safe to re-run — overwrites existing files.  
Useful if you ever want to switch back to the CSV version.

---

## Git Remotes

| Remote name | URL | Purpose |
|-------------|-----|---------|
| `origin` | github.com/RavindraMedhat/FIRE_web | Original CSV version (master branch) |
| `firebase` | github.com/RavindraMedhat/FIRE_firebase | Firebase version (this repo) |

### Push changes to this repo

```bash
git push firebase feature/firebase-firestore
```

---

## Backend Architecture

```
data_manager.py
│
│  reads FIRE_BACKEND env var / Streamlit secret
│
├── FIRE_BACKEND=csv      → backends/csv_backend.py
│                              load_user / save_user
│                              load_holdings / save_holdings
│                              load_buys / save_buys
│                              load_sells / save_sells
│                              load_config / save_config  (data/config.json)
│
└── FIRE_BACKEND=firebase → backends/firebase_backend.py
                               load_user / save_user
                               load_holdings / save_holdings
                               load_buys / save_buys
                               load_sells / save_sells
                               load_config / save_config  (Firestore meta/config)
```

Both backends expose the **exact same function signatures** — `data_manager.py`
and `app.py` never know which one is active.

`models.py` holds the shared `UserSettings` dataclass and column lists imported
by both backends.

ETF price cache (`data/etfs_cache.csv`) is **always local** regardless of backend.

---

## Security — What is gitignored

| File | Why |
|------|-----|
| `serviceAccountKey.json` | Firebase private key — never commit |
| `.streamlit/secrets.toml` | Contains the same key in TOML format |
| `data/config.json` | Password hash for CSV backend — keep local |
| `data set/` | Personal watchlist spreadsheets |
| `fire_mobile/` | Old mobile version |
| `fire full/` | Old Flutter version |

---

## ETF Data Source

ETF prices are fetched from a Google Apps Script API (live market data).  
The result is cached locally in `data/etfs_cache.csv`.  
Click **Refresh ETFs** in the sidebar to fetch fresh data anytime.

---

## Charges Model (Kotak Securities — Delivery, 2025)

| Type | Brokerage | STT (buy) | STT (sell) |
|------|-----------|-----------|------------|
| Equity ETF | 0.05% | 0% | 0.001% |
| Jewellery ETF | 0.05% | 0% | 0.001% |
| Stocks | 0.10% | 0.1% | 0.1% |

Additional: Exchange transaction (0.00297%), SEBI (0.0001%), Stamp duty (0.015% on buy), GST (18% on brokerage + exchange + SEBI).

---

## Branches

| Branch | Description |
|--------|-------------|
| `master` | Original version — CSV file storage, no login |
| `feature/firebase-firestore` | Current version — Firebase Firestore, password login |
