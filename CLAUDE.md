# FIRE — Project Context for Claude

This file gives Claude full context to work on this codebase without needing conversation history.

---

## What this project is

**FIRE** (Financial Independence Investment Tracker) is a personal ETF/stock investment tracker built with **Python + Streamlit + Firebase Firestore**. It is a **single-user app** — one password, one set of holdings.

The **multi-user version** lives at `/Users/ravi/Desktop/FIRE_multi`.

**Current git branch:** `feature/firebase-firestore`
**Firebase project:** `myfire-1783b`
**Streamlit Cloud:** deployed from branch `feature/firebase-firestore`

---

## Project structure

```
FIRE/
├── app.py                      # Streamlit UI — all 8 pages, auth, routing, components (~3200 lines)
├── data_manager.py             # Firebase read/write + all business logic (~2000 lines)
├── migrate_to_firebase.py      # One-shot: imports CSV data into Firestore
├── export_from_firebase.py     # Backup: exports Firestore data to CSV
├── requirements.txt
├── firebase.json
├── .firebaserc                 # Bound to project: myfire-1783b
├── firestore.rules
├── firestore.indexes.json      # Composite indexes for pagination queries
├── serviceAccountKey.json      # ⚠ LOCAL ONLY — gitignored
├── DOCUMENTATION.html          # In-app docs — rendered on ℹ️ Info page
├── .streamlit/
│   ├── config.toml             # Dark theme
│   └── secrets.toml            # ⚠ LOCAL ONLY — gitignored
│       # Contains: [gcp_service_account] service account JSON + etf_api_url
└── data/
    └── etfs_cache.csv          # Live ETF price cache (auto-refreshed)
```

---

## How to run

```bash
cd /Users/ravi/Desktop/FIRE
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. First launch → create password. Every session → login screen → valid 7 hours.

---

## Authentication

- Password hash stored as HMAC-SHA256 key in `meta/config` Firestore document
- On login: HMAC-SHA256 token generated, stored in URL query param `?s=...`
- Token expires after 7 hours
- `load_config()` / `save_config()` manage the config doc
- Session state key: `st.session_state.authenticated = True`

---

## Firestore collections (single-user, root level)

| Path | What it stores |
|---|---|
| `meta/user` | UserSettings — investment, remainingAmount, thresholds, AMC config |
| `meta/config` | Password hash (HMAC-SHA256 key) |
| `meta/stats` | Running totals — updated on every write; enables O(1) Reports |
| `holdings/{id}` | Open positions — one doc per ETF/stock held |
| `buys/{id}` | Buy transaction log |
| `sells/{id}` | Sell log — includes `holdingDays` stamped permanently at sell time |
| `charges/{id}` | Non-trade charges — AMC, DP fees, manual entries |
| `cashflow/{id}` | Deposits and withdrawals |

### `meta/stats` fields (running totals)

```
buyCount, buyGross, buyBrokerage, buyTotalCharges
sellCount, sellGross, sellBrokerage, sellNetPL, sellTotalCharges, sellDividend
chargesTotal
openInvTotal      → Σ(avgPrice × remainingQty) across all open holdings
openInvDateSum    → Σ(avgPrice × remainingQty × weightedBuyEpoch)
```

`today_epoch − openInvDateSum/openInvTotal` = weighted avg hold days for open positions.

### Document field schemas

**holdings**: `id, etfName, etfType, averagePrice, lastPurchasePrice, totalQuantity, lastPurchaseDate`

**buys**: `id, holdingId, etfName, etfType, quantity, price, brokerageCharges, tax, totalCharges, buyDate`

**sells**: `id, etfName, etfType, quantity, averagePurchasePrice, sellPrice, brokerageCharges, tax, dividendPaidToSelf, lastPurchaseDate, sellDate, holdingDays`

**charges**: `id, chargeType, amount, description, chargeDate`

**cashflow**: `id, type (deposit/withdrawal), amount, date, note`

### UserSettings dataclass fields

`userName, investment, remainingAmount, taxPercentage, brokeragePercentage, dividendPercentage, sellProfitTarget, buyInDipThreshold, amcAmount, lastAmcDate, totalDeposited, defaultPageSize`

---

## Key concepts

### investment vs remainingAmount vs totalDeposited

| Field | Meaning | Changes when |
|---|---|---|
| `totalDeposited` | Cumulative bank deposits minus withdrawals | Only on deposit/withdrawal |
| `investment` | `totalDeposited + Σ net realized P&L` | On every sell, AMC charge, manual charge |
| `remainingAmount` | Liquid cash right now | Decreases on buy + charges; increases on sell proceeds |

### Weighted average price

```
new_avg = (old_avg × old_qty + price × qty) / (old_qty + qty)
```

Not adjusted on partial sells. Stays until next buy.

### Realized P&L on sell

```
gross_pl = qty × (sell_price − avg_buy_price)
net_pl   = gross_pl − brokerage − tax − dividend_paid_to_self
```

`investment` updated by `+net_pl` on every sell.

### holdingDays (on sell records)

```
holding_days = sell_epoch − Σ(price × qty × buy_epoch) / Σ(price × qty)
```

Weighted-avg hold days across all buy lots for that holding. Stamped permanently at sell time using `holdingId` to find the correct lots (not ETF name — avoids mixing cycles when ETF was fully sold and repurchased).

### Reconciliation identity

```
accountBalance  = remainingAmount + costBasis (from holdings)
expectedBalance = totalDeposited + sellNetPL − buyTotalCharges − chargesTotal
diff ≈ 0 (small float rounding OK, > ₹1 signals a real bug)
```

---

## Kotak Securities charge structure

```python
KOTAK_RATES = {
    "Equity":    {"brokerage_pct": 0.05, "stt_buy_pct": 0.0,  "stt_sell_pct": 0.001},
    "Jewellery": {"brokerage_pct": 0.05, "stt_buy_pct": 0.0,  "stt_sell_pct": 0.001},
    "Stocks":    {"brokerage_pct": 0.10, "stt_buy_pct": 0.1,  "stt_sell_pct": 0.1},
}
# On every trade:
exchange_tx = value × 0.00297 / 100
sebi        = value × 0.0001  / 100
stamp       = value × 0.015   / 100   # buy only
gst         = (brokerage + exchange_tx + sebi) × 18%
tax         = stt + stamp + exchange_tx + sebi + gst
ch["total"] = brokerage + tax
```

---

## data_manager.py architecture

### Module-level state

```python
_DATA_CACHE: dict = {}   # in-process cache; keys: "user","holdings","buys","sells","charges","cashflow"
db = firestore.client()  # Firebase client, initialized once at module load
```

### Write invariant

Every write that changes portfolio state must:
1. Update Firestore document(s)
2. Call `_update_stats(delta)` with correct increments
3. Update `user.investment` and/or `user.remainingAmount` in memory
4. Call `save_user(user)`
5. Pop the relevant key from `_DATA_CACHE`

### Key functions

| Function | Location | What it does |
|---|---|---|
| `load_stats()` | dm:294 | Read `meta/stats` doc — 1 Firestore read |
| `_update_stats(delta)` | dm:302 | Increment/decrement stats fields |
| `rebuild_stats()` | dm:311 | Full rescan → recompute stats from scratch |
| `load_user()` | dm:416 | Load UserSettings from `meta/user` |
| `save_user(u)` | dm:442 | Write UserSettings back |
| `buy_etf(user, name, type, price, qty)` | dm:961 | Add/update holding + write buy doc + update stats |
| `sell_holding(user, holding_id, price, qty, div)` | dm:1028 | Sell + stamp holdingDays + update stats |
| `update_buy_price(user, buy_id, new_exec_value)` | dm:1134 | Correct a buy price + rebuild_stats |
| `update_sell_price(sell_id, kotak_total)` | dm:1188 | Correct a sell price + rebuild_stats |
| `delete_holding(user, holding_id)` | dm:1299 | Remove holding + buy lots + refund actual charges |
| `reverse_buy(user, buy_id)` | dm:1323 | Undo a buy — shrinks/removes holding, restores cash |
| `reverse_sell(user, sell_id)` | dm:1385 | Undo a sell — restores holding, deducts cash |
| `generate_suggestions(user, etfs, holdings)` | dm:1211 | Top dip per ETF type, excluding held ETFs |
| `classify_holdings(holdings, etfs, user)` | dm:1252 | Split into sell/buy/others groups |
| `compute_money_summary_from_stats(user, holdings, etfs, _stats=)` | dm:1604 | O(1) Reports summary — pass `_stats=` to avoid second load |
| `compute_holding_time_stats(holdings, sells, buys)` | dm:1901 | Per-ETF weighted avg hold days |
| `check_and_apply_amc(user)` | dm:556 | Auto-deduct monthly AMC — fresh Firestore read to prevent double-deduction |
| `backfill_sell_holding_days()` | dm:792 | Stamps holdingDays on old sell records that don't have it |
| `fetch_buys_for_etf(name)` / `fetch_sells_for_etf(name)` | dm:678/636 | Targeted queries — used by _history_dialog |
| `buyback_opportunities(sells, etfs, holdings)` | dm:1512 | ETFs sold previously now trading below sell price |
| `money_by_month(buys, sells)` | dm:1987 | Monthly deployed/realized breakdown |

---

## app.py architecture

### Session state keys

| Key | What it holds |
|---|---|
| `authenticated` | bool — True when logged in |
| `user` | UserSettings object |
| `etfs` | pd.DataFrame of ETF prices |
| `suggestions` | list[dict] — current buy suggestions |
| `txn_df_{kind}` | Paginated transaction list cache (kind: buy/sell/charge/cash) |
| `txn_cursor_{kind}` | Firestore pagination cursor |
| `txn_filter_key` | `"from_to"` string — date filter state for transactions |
| `sh_df` | Sell history list cache |
| `sh_cursor` | Sell history pagination cursor |
| `home_filter` | Active tab on Home page |
| `sug_mode` | Active tab on Suggestions page |
| `active_{holding_id}` | Which inline panel is open on a holding card |

### Routing

```
ensure_state()           # load user, ETFs, suggestions; run AMC check
render_sidebar() → page  # navigation radio
page_home / page_suggestions / page_listed_etfs /
page_transactions / page_sell_history / page_reports / page_settings / page_info
```

### Guard pattern (double-click prevention)

```python
_guard = f"_op_done_{operation}_{unique_key}"
if not st.session_state.get(_guard):
    st.session_state[_guard] = True
    try:
        # ... write ...
        del st.session_state[_guard]   # clear on success — allows re-use
        _clear_txn_cache()
        st.rerun()
    except Exception as e:
        del st.session_state[_guard]
        st.error(str(e))
```

Applied in: `_buy_dialog`, `_sell_dialog`, `_delete_dialog`, `_reverse_dialog`, `_edit_buy_dialog`, `_edit_sell_dialog`, fix reconciliation button.

### `_clear_txn_cache()`

Evicts `txn_df_*`, `txn_cursor_*`, `sh_df`, `sh_cursor` from session state. Called after every write so Transactions and Sell History pages reload fresh.

---

## Pages

| Page | File location | Key behaviour |
|---|---|---|
| 🏠 Home | `page_home()` | Holdings in sell/dip/hold tabs. Per-card: avg, CMP, qty, hold time, P/L, profit projection. Inline sell/buy-more/history. `wavg_open_days` from meta/stats. |
| 💡 Suggestions | `page_suggestions()` | Fresh picks + buy-back tab. Cards show DIP vs 20-DMA %, profit projection. Widget keys by ETF name (not index). |
| 📋 Listed ETFs | `page_listed_etfs()` | Filterable/searchable ETF price table. |
| 📄 Transactions | `page_transactions()` | 4 tabs: Buys/Sells/Charges/Cashflow. Date-filtered, paginated. Reverse on buys/sells. Edit price on buys/sells. |
| 📈 Sell History | `page_sell_history()` | Paginated sells with hold time. Summary metrics at top. |
| 📊 Reports | `page_reports()` | 5-chapter: Headline → How money works → What it cost → Reconcile → Month by month. Loads stats once (`_s = dm.load_stats()`), passes to `compute_money_summary_from_stats`. |
| ⚙️ Settings | `page_settings()` | General + Deposit + Withdraw + Add Charge + Maintenance (rebuild stats, reset all). |
| ℹ️ Info | `page_info()` | Renders `DOCUMENTATION.html` in an iframe. |

---

## Suggestion algorithm

```
top_5_equity    = ETFs where type="Equity" and cmp>0, sorted by change20DmaVsCmp asc, take 5
top_3_jewellery = same for "Jewellery", take 3
top_3_stocks    = same for "Stocks", take 3
pool = top_5 + top_3 + top_3
pool = filter out ETFs already in holdings
result = single lowest change20DmaVsCmp per type from pool  → max 3 suggestions
quantity = ceil(investment / 25 / cmp)
```

`change20DmaVsCmp` is negative when CMP < 20-DMA. Lower = bigger dip = stronger signal.

---

## Known behaviours / design decisions

- Buy lots in `buys` are **never deleted on partial sells** — they stay as historical records
- `openInvTotal` is maintained via `_update_stats` deltas; `rebuild_stats` uses `holdings` (remaining qty × avg) not buy lot totals
- `holdingDays` on sells uses `holdingId` to fetch correct buy lots (prevents mixing cycles on sold+repurchased ETFs)
- `check_and_apply_amc` re-reads `lastAmcDate` fresh from Firestore before deducting (prevents double-deduction from two browser tabs)
- Suggestion inputs keyed by `sug_p_{name}` / `sug_q_{name}` (not `p_0`) — prevents stale price after buying shifts the list
- Date range queries use `T23:59:59` suffix on `date_to` — ISO timestamps like `"2026-05-25T14:32"` are lexicographically after plain `"2026-05-25"` so `<=` would miss same-day records
- `rebuild_stats()` is called by `update_buy_price`, `update_sell_price`, and the maintenance button — not on normal buy/sell
- Reports page loads `load_stats()` once and passes `_stats=` to `compute_money_summary_from_stats` (avoids double Firestore read)
- Home page uses `meta/stats` for `wavg_open_days` and passes `pd.DataFrame()` for sells to `compute_holding_time_stats` (eliminates `load_sells()` on Home render)

---

## Common tasks

### Add a new UserSettings field

1. Add with default to `UserSettings` dataclass (dm:400)
2. Add to `USER_COLUMNS` list (dm:~160)
3. Add to `load_user()` with `float(row.get(..., default) or default)` (dm:416)
4. Add `newField=user.newField` to every `UserSettings(...)` constructor in `app.py`

### Debug a reconciliation drift

```python
import data_manager as dm
stats    = dm.load_stats()
user     = dm.load_user()
holdings = dm.load_holdings()
cost     = sum(float(h["averagePrice"])*int(h["totalQuantity"]) for _, h in holdings.iterrows())
account  = user.remainingAmount + cost
expected = user.totalDeposited + stats["sellNetPL"] - stats["buyTotalCharges"] - stats["chargesTotal"]
print(f"Drift: {account - expected:.4f}")
```

### Force stats rebuild

```python
import data_manager as dm
dm.rebuild_stats()
```

### Check what a sell record looks like

```python
import data_manager as dm
sells = dm.load_sells()
print(sells[sells["etfName"] == "NIFTY PSU Bank"].to_string())
```

---

## Git branches

| Branch | What |
|---|---|
| `master` | Original CSV-based version (no Firebase) |
| `feature/firebase-firestore` | **Active** — current Firebase version |
| `feature/firebase-firestore-csv` | Hybrid version supporting both backends |

Push command: `git push firebase feature/firebase-firestore`

Remote `firebase` → `github.com/RavindraMedhat/FIRE_firebase`
Remote `origin` → `github.com/RavindraMedhat/FIRE_web` (CSV version)
