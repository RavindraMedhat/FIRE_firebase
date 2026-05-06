# FIRE – Python (Local, Single User)

A Python/Streamlit port of the Flutter FIRE app.  
Stores everything locally in CSV files (no database, no login).

## Setup

```bash
cd python_version
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501

## Data files (auto-created in `data/`)

- `user.csv` – your profile + percentages (single row)
- `holdings.csv` – current ETF holdings
- `sells.csv` – historical sell transactions
- `etfs_cache.csv` – cached ETF market data

## First run

1. Open Settings from the sidebar.
2. Enter your investment, tax %, brokerage %, dividend %.
3. Click **Save**.
4. Go to Home – ETF data is fetched from the live API on first load.
   Click **Refresh ETFs** in the sidebar any time to re-fetch.
# FIRE_web
# FIRE_web
