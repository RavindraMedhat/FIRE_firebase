# FIRE – Application Documentation

A single-user, local-only Python port of the Flutter FIRE app.
Tracks ETF/stock investments, generates buy/sell signals, and auto-computes
Kotak Securities charges on every trade.

---

## 1. What this app is

**FIRE** = **F**inancial **I**ndependence, **R**etire **E**arly — a personal
portfolio tracker built for one user (you) with everything stored in local
CSV files. No login, no database, no cloud.

**What it does:**
- Fetches live ETF market data from a Google Apps Script API
- Tracks your current holdings and sell history
- Recommends ETFs to buy (greatest dip vs 20-day moving average)
- Flags existing holdings as sell candidates (in profit) or buy-more candidates (in dip)
- Auto-computes **Kotak Trade Plan** charges (brokerage + STT + stamp + exchange + SEBI + GST) on every buy/sell
- Generates P/L reports

---

## 2. Tech stack

| Layer | Tech |
|---|---|
| UI | **Streamlit** (web app in browser, `localhost:8501`) |
| Data | **pandas** for dataframe ops, **CSV** for storage |
| HTTP | **requests** for the live ETF API |
| Runtime | **Python 3.8+** |

---

## 3. Project structure

```
python_version/
├── app.py                 # Streamlit UI (6 pages + routing)
├── data_manager.py        # Business logic + CSV I/O + Kotak charges
├── requirements.txt       # Python dependencies
├── README.md              # Quick-start guide
├── DOCUMENTATION.md       # This file
├── .streamlit/
│   └── config.toml        # Dark theme + server config
└── data/                  # Auto-created CSV storage
    ├── user.csv           # Single-row user profile + settings
    ├── holdings.csv       # Current holdings
    ├── sells.csv          # Historical sell transactions
    └── etfs_cache.csv     # Last-fetched ETF market data
```

---

## 4. Data model (CSV schemas)

### `user.csv` — one row
| Column | Type | Meaning |
|---|---|---|
| `userName` | str | Your name |
| `investment` | float | Running net capital (adjusts on each sell by realized P/L) |
| `remainingAmount` | float | Cash available to invest |
| `taxPercentage` | float | Legacy (kept for compatibility, **unused** — charges are auto-computed) |
| `brokeragePercentage` | float | Legacy (same) |
| `dividendPercentage` | float | % of each sell you personally keep as "pay to self" |
| `sellProfitTarget` | float | Sell signal threshold (default 3%) |
| `buyInDipThreshold` | float | Buy-more signal threshold (default 2.5%) |

### `holdings.csv` — one row per currently-held ETF/stock
| Column | Type | Meaning |
|---|---|---|
| `id` | str (uuid) | Unique holding id |
| `etfName` | str | Name (matches ETF API) |
| `etfType` | str | `Equity`, `Jewellery`, or `Stocks` |
| `averagePrice` | float | Weighted average buy price |
| `lastPurchasePrice` | float | Price of most recent buy |
| `totalQuantity` | int | Units held |
| `lastPurchaseDate` | str (ISO) | Date of last buy |

### `sells.csv` — one row per sell transaction
| Column | Type | Meaning |
|---|---|---|
| `id`, `etfName`, `etfType` | — | Same as above |
| `quantity`, `averagePurchasePrice`, `sellPrice` | — | Trade details |
| `brokerageCharges` | float | Kotak brokerage paid |
| `tax` | float | STT + exchange + SEBI + GST (bundled) |
| `dividendPaidToSelf` | float | Personal savings cut |
| `lastPurchaseDate`, `sellDate` | str (ISO) | Dates |

### `etfs_cache.csv` — market data (refreshed on app open)
Columns mirror the Google Apps Script API response:
`etfCode, name, cmp, the20Dma, change20DmaVsCmp, changePercentage,
dailyAverageVolumeInLast30/90/365Days, type`

---

## 5. Core concepts

### 5.1 ETF types
The app knows three asset types (from the live API's `Type` field):
- **Equity** — broad-market ETFs (Nifty, Sensex variants)
- **Jewellery** — Gold / Silver ETFs
- **Stocks** — direct equity (Reliance, Bajaj Finance, etc.)

### 5.2 Buy/sell signals (on the Home page)
Each holding is classified into one of three tabs based on current market
price (CMP) vs your average buy price:

| Tab | Condition | Meaning |
|---|---|---|
| 🟢 Sell | `CMP > avgPrice × (1 + sellProfitTarget%)` | In profit — consider selling |
| 🔴 Buy more | `CMP < avgPrice × (1 − buyInDipThreshold%)` | In dip — consider averaging down |
| ⚪ Others | neither | Hold |

Defaults: sell target 3%, dip threshold 2.5%. Configurable in Settings.

### 5.3 Suggestions algorithm (💡 Suggestions page)
Generates up to 3 buy recommendations — one per asset type:

```
1. Group all ETFs by type: Equity, Jewellery, Stocks.
2. Sort each group ascending by change20DmaVsCmp (= deepest dip first).
3. Take top 5 from Equity, top 3 from Jewellery, top 3 from Stocks.
4. Remove any ETF you already hold.
5. For each type, pick the one with greatest dip.
6. Suggested quantity = ceil(investment / 25 / CMP).
```

The `/25` divisor is the Flutter app's allocation heuristic: roughly 4%
of total investment per pick.

### 5.4 Kotak charges (auto-applied on every buy & sell)

Rates from your Kotak Trade Plan PDF + standard 2025 statutory rates.

**Brokerage (% of trade value):**
| Asset | Buy | Sell |
|---|---|---|
| ETFs (Equity/Jewellery) | 0.05% | 0.05% |
| Stocks | 0.10% | 0.10% |

**Securities Transaction Tax (STT):**
| Asset | Buy | Sell |
|---|---|---|
| ETFs | 0% | 0.001% |
| Stocks | 0.1% | 0.1% |

**Other statutory (applied on every trade):**
| Charge | Rate | Notes |
|---|---|---|
| Stamp Duty | 0.015% | **Buy only**, all securities |
| Exchange Tx | 0.00297% | NSE equity cash |
| SEBI | 0.0001% | ₹10 per crore |
| GST | 18% of (brokerage + exchange + SEBI) | Goods & services tax |

Computed by `data_manager.compute_kotak_charges(value, etf_type, side)`
→ returns a dict `{brokerage, stt, stamp, exchangeTx, sebi, gst, total, tax}`.

---

## 6. Application flow

### 6.1 App startup

```
streamlit run app.py
        │
        ▼
┌────────────────────────────────────────┐
│  ensure_state()                        │
│                                        │
│  1. Load user.csv → session.user      │
│  2. Fetch live ETFs from API          │
│     ├── success → cache to CSV         │
│     └── fail    → load cached CSV      │
│  3. Compute buy suggestions           │
│     → session.suggestions              │
└────────────────────────────────────────┘
        │
        ▼
  Render sidebar + current page
```

### 6.2 Buy flow (from Suggestions or "Buy more" on Home)

```
User clicks Buy
        │
        ▼
Enter price + quantity
        │
        ▼
UI calls compute_kotak_charges(value, etf_type, "buy")
        │
        ▼
Shows itemized breakdown:
  Trade value
  + Brokerage
  + STT (if stock)
  + Stamp duty
  + Exchange
  + SEBI
  + GST
  = Total cost
        │
        ▼
User confirms → data_manager.buy_etf(...)
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 1. Load holdings.csv                            │
│ 2. If ETF already held:                         │
│      new_avg = (old_avg × old_qty +             │
│                 new_price × new_qty) / total_qty│
│      update row                                 │
│    else: append new row                         │
│ 3. Save holdings.csv                            │
│ 4. user.remainingAmount -= (value + charges)    │
│ 5. user.investment      -= charges              │
│ 6. Save user.csv                                │
│ 7. Regenerate suggestions                       │
└─────────────────────────────────────────────────┘
```

### 6.3 Sell flow

```
User picks a holding → Sell action
        │
        ▼
Enter sell price + quantity
        │
        ▼
UI calls compute_kotak_charges(value, etf_type, "sell")
        │
        ▼
Shows breakdown:
  Gross
  - Brokerage, STT, Exchange, SEBI, GST
  - Dividend (user.dividendPercentage% of gross)
  = Net proceeds
  Realized P/L = (sell - avg) × qty - all charges - dividend
        │
        ▼
User confirms → data_manager.sell_holding(...)
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 1. Load holdings + sells                        │
│ 2. Compute Kotak charges (server-side)          │
│ 3. Append sell row to sells.csv                 │
│ 4. If quantity == full holding: drop row        │
│    else: recompute avg price for remaining qty  │
│      new_avg = (old_avg × old_qty -             │
│                 sell_price × sold_qty)          │
│                / (old_qty - sold_qty)           │
│ 5. Save holdings.csv                            │
│ 6. user.remainingAmount += (value - charges - div)│
│ 7. user.investment      += ((sell-avg)*qty      │
│                             - charges - div)    │
│ 8. Save user.csv                                │
│ 9. Regenerate suggestions                       │
└─────────────────────────────────────────────────┘
```

### 6.4 Reports (📊 Reports page)

`data_manager.compute_report(holdings, sells, etfs)` aggregates:

| Metric | Formula |
|---|---|
| **Portfolio %** | `(currentValue - costBasis) / costBasis × 100` |
| **Profit/Loss (gross)** | `Σ (sellPrice - avgPrice) × qty` |
| **Growth (net)** | `Σ [(sellPrice - avgPrice) × qty − brokerage − tax − dividend]` |
| **Total Tax** | `Σ tax` across all sells |
| **Total Brokerage** | `Σ brokerageCharges` |
| **Pay to Self** | `Σ dividendPaidToSelf` |
| **Holdings amount** | `⌊Σ avgPrice × qty⌋` |

---

## 7. Page-by-page walkthrough

| Page | Purpose | Key actions |
|---|---|---|
| 🏠 **Home** | Portfolio overview | View holdings split Sell/Buy/Others; sell or buy-more |
| 💡 **Suggestions** | Buy picks | See pre-computed recommendations; buy with one click |
| 📋 **Listed ETFs** | Browse all ETFs | Filter by type, search, sorted by dip |
| 📜 **Sell History** | All past sells | Gross & net P/L per transaction; totals at top |
| 📊 **Reports** | Aggregated metrics | Portfolio %, realized gains, fees paid |
| ⚙️ **Settings** | Profile + thresholds | Edit investment, dividend %, profit/dip thresholds; view Kotak rates |

**Sidebar (always visible):**
- 🔥 FIRE title
- Navigation radio
- 🔄 Refresh ETFs button (live API call + regenerate suggestions)
- Last-fetched timestamp
- Investment & Remaining quick-metric cards

---

## 8. Key files & functions

### `data_manager.py` — all business logic lives here

| Function | Role |
|---|---|
| `load_user() / save_user()` | CSV round-trip for user profile |
| `load_holdings() / save_holdings()` | CSV round-trip for holdings |
| `load_sells() / save_sells()` | CSV round-trip for sells |
| `fetch_etfs()` | Hits the Google Apps Script API, filters `cmp > 0`, caches |
| `load_etfs_cache()` | Reads cached CSV (fallback when offline) |
| `get_etfs(refresh=False)` | Picks fresh vs cached |
| `last_fetch_time()` | `mtime` of the cache file |
| **`compute_kotak_charges(value, etf_type, side)`** | **Returns full fee breakdown** |
| **`buy_etf(user, name, type, price, qty)`** | Execute a buy, persist all state |
| **`sell_holding(user, id, price, qty, dividend)`** | Execute a sell, persist, return charges |
| `generate_suggestions(user, etfs, holdings)` | Run the suggestion algorithm |
| `classify_holdings(holdings, etfs, user)` | Split holdings into sell / buy / others |
| `compute_report(holdings, sells, etfs)` | Build the Reports page metrics |

### `app.py` — UI + routing

| Section | Role |
|---|---|
| `CUSTOM_CSS` | Dark-theme polish for cards, badges, metrics |
| `ensure_state()` | Session bootstrap — runs on first request |
| `refresh_etfs()` | Manual re-fetch + re-suggest |
| `fmt_money / fmt_pct / pnl_class / badge` | Display helpers |
| `_render_charge_breakdown()` | The itemized Kotak fee box under every trade form |
| `_sell_form() / _buy_more_form()` | Inline forms on each holding card |
| `page_home / page_suggestions / page_listed_etfs / page_sell_history / page_reports / page_settings` | One function per screen |

---

## 9. How to run

```bash
cd python_version
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

**First-run checklist:**
1. Open ⚙️ Settings → set your total investment → Save.
2. Go to 💡 Suggestions → see the top picks → click Buy.
3. Home will now show the holding; when CMP moves, it'll appear in
   the 🟢 Sell or 🔴 Buy-more tab automatically.

---

## 10. Extending the app

**Change broker rates:** edit `KOTAK_RATES` and the other `*_PCT` constants
at the top of `data_manager.py`. All buy/sell code uses the single
`compute_kotak_charges` entry point.

**Change the suggestion algorithm:** edit `generate_suggestions()` in
`data_manager.py` — change the `top_n(...)` counts, the allocation `/25`,
or the sort criterion.

**Change buy/sell thresholds:** edit via Settings page, or change
defaults in `UserSettings.sellProfitTarget` / `buyInDipThreshold`.

**Add a new page:** write a `page_xxx()` function in `app.py`, add an
entry to the sidebar `st.radio(...)` list, and a matching branch in the
router at the bottom.

**Switch data source:** replace `API_URL` at the top of
`data_manager.py`. Any endpoint returning the same JSON schema (list of
dicts with keys `"ETF Code"`, `"Name"`, `"CMP"`, `"20 DMA"`, ...) will work.

---

## 11. Known simplifications

1. **Avg price ignores buy-side charges** — Kotak shows traded avg the
   same way. Buy charges are deducted from `remainingAmount` and
   `investment` instead. Cost-basis P/L is slightly under-reported by
   the buy fees (tiny for ETFs, small for stocks).
2. **Single-user only** — no login, no multi-user isolation.
3. **ETF data is only as fresh as the upstream Google Apps Script** —
   if the sheet lags, so do our suggestions.
4. **No retry / offline queue** — if the API is down on startup, we
   fall back to the cached CSV.
5. **Holdings count > 20 warning** — soft UX nudge from the original
   Flutter app, not enforced.

---

## 12. Data flow summary (one picture)

```
┌─────────────────────┐
│ Google Apps Script  │
│   ETF API (live)    │
└──────────┬──────────┘
           │ fetch_etfs() on startup + Refresh
           ▼
┌─────────────────────┐      ┌─────────────────────┐
│  etfs_cache.csv     │◄────►│   st.session_state  │
└─────────────────────┘      │  .etfs              │
                             │  .user              │
                             │  .suggestions       │
┌─────────────────────┐      └──────────┬──────────┘
│  user.csv           │◄────►           │
│  holdings.csv       │◄────►  Business logic
│  sells.csv          │◄────►  (data_manager.py)
└─────────────────────┘                 │
                                        ▼
                             ┌─────────────────────┐
                             │  Streamlit UI       │
                             │  (app.py, 6 pages)  │
                             └─────────────────────┘
```
