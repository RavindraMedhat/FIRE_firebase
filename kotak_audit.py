#!/usr/bin/env python3
"""
kotak_audit.py — Automated Kotak Securities vs FIRE app audit

Usage:
    python3 kotak_audit.py                           # auto-detect latest reports
    python3 kotak_audit.py --ledger L.xlsx --txn T.xlsx
    python3 kotak_audit.py --mark-done 1-1 1-2       # mark actions as done
    python3 kotak_audit.py --history                 # show audit history only
"""

import os, sys, json, glob, argparse, webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

SCRIPT_DIR        = Path(__file__).parent
REPORTS_DIR       = SCRIPT_DIR / "reports"
AUDIT_LOG         = REPORTS_DIR / "audit_log.json"
ROUNDING_TOLERANCE = 5.0   # gap ≤ this is flagged WARN (rounding), above is FAIL
EXACT_PRICE_TOL    = 0.01  # "same price" — covers 1-paise entry errors
LOOSE_PRICE_PCT    = 0.001 # 0.1% fallback for larger rounding (e.g. ₹1275.4 vs ₹1275.5)

# ── Utilities ────────────────────────────────────────────────────────────────

def c(v):
    if pd.isna(v): return 0.0
    try: return float(str(v).replace(',', '').strip() or 0)
    except: return 0.0

def parse_ddmmyyyy(s):
    try: return datetime.strptime(str(s).strip(), '%d/%m/%Y').date()
    except: return None

def price_match_app(app_df, price, trade_date, price_col, date_col):
    """Two-pass: exact ±₹0.01 first; 0.1% fallback only when no exact match exists."""
    pm = app_df[abs(app_df[price_col].astype(float) - price) < EXACT_PRICE_TOL]
    if not pm.empty and trade_date:
        pm = pm[pm[date_col].apply(lambda d: days_apart(d, trade_date) <= 5)]
    if pm.empty:
        pm = app_df[abs(app_df[price_col].astype(float) - price) < price * LOOSE_PRICE_PCT]
        if not pm.empty and trade_date:
            pm = pm[pm[date_col].apply(lambda d: days_apart(d, trade_date) <= 5)]
    return pm

def days_apart(iso_str, d2):
    try:
        d1 = date.fromisoformat(str(iso_str)[:10])
        return abs((d1 - d2).days)
    except: return 999

# ── File detection ───────────────────────────────────────────────────────────

def auto_detect(pattern, label):
    files = sorted(glob.glob(str(REPORTS_DIR / pattern)))
    if not files:
        sys.exit(f"ERROR: No {label} found in {REPORTS_DIR}/\nExpected pattern: {pattern}")
    if len(files) > 1:
        print(f"  Multiple {label} found — using latest: {Path(files[-1]).name}")
    return Path(files[-1])

# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_ledger(path):
    df = pd.read_excel(path, header=7)
    df.columns = ['Settlement Date', 'Transaction Date', 'Exchange',
                  'Transaction Type', 'Description', 'Invoice Number',
                  'Debit', 'Credit', 'Net Balance']
    df = df.dropna(subset=['Transaction Type'])
    df['Debit']  = df['Debit'].apply(c)
    df['Credit'] = df['Credit'].apply(c)

    deposits    = df[df['Transaction Type'] == 'Deposit']['Credit'].sum()
    withdrawals = df[df['Transaction Type'] == 'Withdrawal']['Debit'].sum()
    demat_df    = df[df['Transaction Type'] == 'Demat'].copy()
    closing     = c(df.iloc[0]['Net Balance'])

    # Extract latest settlement date for incremental / post-report filtering
    all_dates = [parse_ddmmyyyy(d) for d in df['Settlement Date'] if parse_ddmmyyyy(d)]
    latest_date = max(all_dates) if all_dates else None

    return {
        'deposits':        deposits,
        'withdrawals':     withdrawals,
        'net_deposits':    deposits - withdrawals,
        'demat_df':        demat_df,
        'closing_balance': closing,
        'latest_date':     latest_date,
    }

def parse_txn(path):
    df = pd.read_excel(path, header=7)
    df.columns = ['Trade Date', 'Trade Time', 'Order Time', 'Security Name',
                  'ISIN', 'Exchange', 'Order Source', 'Transaction Type',
                  'Product Type', 'Quantity', 'Market Rate', 'Total',
                  'GST', 'Brokerage', 'Misc', 'Total Charges', 'STT/CTT']
    df = df.dropna(subset=['Trade Date'])
    df['Quantity']    = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0).astype(int)
    df['Market Rate'] = df['Market Rate'].apply(c)

    dates = [parse_ddmmyyyy(d) for d in df['Trade Date'] if parse_ddmmyyyy(d)]
    period_from = min(dates).isoformat() if dates else None
    period_to   = max(dates).isoformat() if dates else None

    return {
        'buys':        df[df['Transaction Type'] == 'Buy'].copy(),
        'sells':       df[df['Transaction Type'] == 'Sell'].copy(),
        'period_from': period_from,
        'period_to':   period_to,
    }

# ── Audit checks ─────────────────────────────────────────────────────────────

def check_deposits(ledger, user, cashflow):
    kotak_net = ledger['net_deposits']
    app_total = user.totalDeposited

    # Find any cashflow entries AFTER Kotak ledger's last entry date
    # so we can warn rather than fail for expected timing differences
    ledger_latest = ledger.get('latest_date')
    post_report = []
    if ledger_latest and cashflow is not None and not cashflow.empty:
        for _, row in cashflow.iterrows():
            try:
                d = date.fromisoformat(str(row['date'])[:10])
                if d > ledger_latest:
                    post_report.append(float(row['amount']) *
                                       (1 if row['type'] == 'deposit' else -1))
            except Exception:
                pass

    post_total = sum(post_report)
    adjusted   = app_total - post_total   # app deposits excluding post-report ones
    diff       = adjusted - kotak_net
    ok         = abs(diff) < 1.0

    note = 'Match' if ok else f'Gap ₹{diff:+.2f}'
    if post_total and ok:
        note = f'Match ({len(post_report)} new txn(s) after report: ₹{post_total:+,.0f} excluded)'
    elif post_total and not ok:
        note = f'Gap ₹{diff:+.2f} even after excluding ₹{post_total:+,.0f} post-report deposits'

    return {
        'pass':  ok,
        'kotak': kotak_net,
        'app':   adjusted,
        'diff':  diff,
        'post_report_amount': post_total,
        'note':  note,
    }

def check_demat(ledger, app_charges, from_date=None):
    demat_df = ledger['demat_df'].copy()

    # Filter to only entries after last audit date
    if from_date:
        from_d = date.fromisoformat(from_date)
        def after_last(s):
            d = parse_ddmmyyyy(s)
            return d is not None and d > from_d
        demat_df = demat_df[demat_df['Settlement Date'].apply(after_last)]

    if demat_df.empty:
        return {'pass': True, 'issues': [], 'checked': 0,
                'note': 'No new demat charges since last audit'}

    issues = []
    for _, row in demat_df.iterrows():
        desc       = str(row['Description'])
        amount     = row['Debit']
        settle_str = str(row['Settlement Date'])
        settle_d   = parse_ddmmyyyy(settle_str)
        is_amc     = 'Account charge' in desc or 'month of' in desc.lower()

        if is_amc:
            match = app_charges[
                app_charges['chargeType'].str.lower().str.contains('amc', na=False) &
                (abs(app_charges['amount'].astype(float) - amount) < 0.01)
            ]
            charge_label = f"AMC ₹{amount:.2f} ({settle_str})"
        else:
            match = app_charges[
                app_charges['chargeType'].isin(['DP Charge', 'DP Charges']) &
                (abs(app_charges['amount'].astype(float) - amount) < 0.01)
            ]
            # Narrow by date proximity (DP charge date should be within 3 days of ledger entry)
            if settle_d is not None and not match.empty:
                match = match[match['chargeDate'].apply(lambda d: days_apart(d, settle_d) <= 3)]
            charge_label = f"DP ₹{amount:.2f} ({settle_str}) — {desc[:60]}"

        if match.empty:
            issues.append({
                'type':   'AMC' if is_amc else 'DP',
                'desc':   desc,
                'date':   settle_str,
                'amount': amount,
                'label':  charge_label,
            })

    return {
        'pass':    len(issues) == 0,
        'issues':  issues,
        'checked': len(demat_df),
        'note':    f'All {len(demat_df)} charges matched' if not issues
                   else f'{len(issues)} of {len(demat_df)} missing in app',
    }

def check_buys(txn, app_buys):
    raw_buys = txn['buys']
    if raw_buys.empty:
        return {'pass': True, 'total': 0, 'matched': 0,
                'issues': [], 'note': 'No buys in this period'}

    # Kotak sometimes splits one order into multiple partial-fill rows (same price+date).
    # Group them so we compare logical trades, not execution fills.
    kb = raw_buys.copy()
    kb['_date'] = kb['Trade Date'].apply(parse_ddmmyyyy)
    groups = (kb.groupby(['Trade Date', 'Market Rate'], as_index=False)
                .agg({'Quantity': 'sum', 'Security Name': 'first', '_date': 'first'}))

    issues, matched_count = [], 0

    for _, kg in groups.iterrows():
        qty        = int(kg['Quantity'])
        price      = float(kg['Market Rate'])
        name       = str(kg['Security Name'])
        trade_date = kg['_date']

        price_match = price_match_app(app_buys, price, trade_date, 'price', 'buyDate')

        total_app_qty = int(price_match['quantity'].astype(int).sum()) if not price_match.empty else 0
        exact = (price_match[price_match['quantity'].astype(int) == qty]
                 if not price_match.empty else pd.DataFrame())

        if not exact.empty or total_app_qty == qty:
            matched_count += 1
        else:
            if total_app_qty > 0:
                issues.append({
                    'type':        'qty_mismatch',
                    'security':    name,
                    'trade_date':  str(kg['Trade Date']),
                    'price':       price,
                    'kotak_qty':   qty,
                    'app_qty':     total_app_qty,
                    'description': f"{name}  {kg['Trade Date']}  @₹{price}  —  Kotak qty={qty}, app qty={total_app_qty}",
                })
            else:
                issues.append({
                    'type':        'missing_buy',
                    'security':    name,
                    'trade_date':  str(kg['Trade Date']),
                    'price':       price,
                    'kotak_qty':   qty,
                    'app_qty':     0,
                    'description': f"{name}  {kg['Trade Date']}  @₹{price}  qty={qty}  — not found in app",
                })

    total = len(groups)
    raw   = len(raw_buys)
    ok    = len(issues) == 0
    suffix = f' ({raw} raw rows)' if raw != total else ''
    return {
        'pass':    ok,
        'total':   total,
        'matched': matched_count,
        'issues':  issues,
        'note':    f'All {total} matched{suffix}' if ok
                   else f'{len(issues)} issue(s) out of {total} trade groups{suffix}',
    }

def check_sells(txn, app_sells):
    kotak_sells = txn['sells']
    if kotak_sells.empty:
        return {'pass': True, 'total': 0, 'matched': 0,
                'issues': [], 'note': 'No sells in this period'}

    issues, matched_rows = [], []

    for _, ks in kotak_sells.iterrows():
        qty        = int(ks['Quantity'])
        price      = float(ks['Market Rate'])
        name       = str(ks['Security Name'])
        trade_date = parse_ddmmyyyy(ks['Trade Date'])

        price_match = price_match_app(app_sells, price, trade_date, 'sellPrice', 'sellDate')

        exact = price_match[price_match['quantity'].astype(int) == qty]

        if not exact.empty:
            matched_rows.append(name)
        else:
            partial_qty = int(price_match.iloc[0]['quantity']) if not price_match.empty else None
            if partial_qty is not None:
                issues.append({
                    'type':        'qty_mismatch',
                    'security':    name,
                    'trade_date':  str(ks['Trade Date']),
                    'price':       price,
                    'kotak_qty':   qty,
                    'app_qty':     partial_qty,
                    'description': f"{name}  {ks['Trade Date']}  @₹{price}  —  Kotak qty={qty}, app qty={partial_qty}",
                })
            else:
                issues.append({
                    'type':        'missing_sell',
                    'security':    name,
                    'trade_date':  str(ks['Trade Date']),
                    'price':       price,
                    'kotak_qty':   qty,
                    'app_qty':     0,
                    'description': f"{name}  {ks['Trade Date']}  @₹{price}  qty={qty}  — not found in app",
                })

    total = len(kotak_sells)
    ok    = len(issues) == 0
    return {
        'pass':    ok,
        'total':   total,
        'matched': len(matched_rows),
        'issues':  issues,
        'note':    f'All {total} matched' if ok
                   else f'{len(issues)} issue(s) out of {total} sells',
    }

def check_balance(ledger, user, buys, sells, cashflow, charges):
    kotak = ledger['closing_balance']
    app   = user.remainingAmount

    # Indian equity settles T+1. A trade on date D is in the ledger only when
    # D + 1 calendar day <= ledger_latest. Trades where D+1 > ledger_latest are
    # still pending settlement and must be backed out of app_remaining before comparing.
    ledger_latest = ledger.get('latest_date')
    post_buy_out, post_sell_in, post_deposit, post_charge = 0.0, 0.0, 0.0, 0.0
    newer_count = 0

    if ledger_latest:
        for _, b in buys.iterrows():
            try:
                d = date.fromisoformat(str(b['buyDate'])[:10])
                if d + timedelta(1) > ledger_latest:          # T+1 not yet settled
                    post_buy_out += float(b['price']) * int(b['quantity']) + float(b['totalCharges'])
                    newer_count  += 1
            except Exception:
                pass
        for _, s in sells.iterrows():
            try:
                d = date.fromisoformat(str(s['sellDate'])[:10])
                if d + timedelta(1) > ledger_latest:          # T+1 not yet settled
                    post_sell_in += float(s['sellPrice'])*int(s['quantity']) - float(s['brokerageCharges']) - float(s['tax'])
                    newer_count  += 1
            except Exception:
                pass
        for _, cf in cashflow.iterrows():
            try:
                if date.fromisoformat(str(cf['date'])[:10]) > ledger_latest:
                    post_deposit += float(cf['amount']) * (1 if cf['type'] == 'deposit' else -1)
                    newer_count  += 1
            except Exception:
                pass
        for _, ch in charges.iterrows():
            try:
                if date.fromisoformat(str(ch['chargeDate'])[:10]) > ledger_latest:
                    post_charge += float(ch['amount'])         # charge not yet in ledger
                    newer_count += 1
            except Exception:
                pass

    # Adjust app remaining back to what it would have been at Kotak closing
    app_at_close = app + post_buy_out - post_sell_in - post_deposit + post_charge

    gap  = kotak - app_at_close
    ok   = abs(gap) <= ROUNDING_TOLERANCE
    warn = ok and abs(gap) > 0.5

    if newer_count:
        note = (f'Adjusted for {newer_count} post-report txn(s): '
                f'App@close=₹{app_at_close:,.2f}  Gap ₹{gap:+.2f}'
                + (' — rounding' if ok and abs(gap) > 0.5 else ''))
    elif ok and abs(gap) > 0.5:
        note = f'Gap ₹{gap:+.2f} — rounding only'
    elif ok:
        note = 'Match'
    else:
        note = f'Gap ₹{gap:+.2f} — investigate'

    return {
        'pass':        ok,
        'warn':        warn,
        'kotak':       kotak,
        'app':         app_at_close,
        'app_current': app,
        'gap':         gap,
        'newer_count': newer_count,
        'note':        note,
    }

def check_recon(user, holdings, stats):
    cost     = sum(float(h['averagePrice']) * int(h['totalQuantity'])
                   for _, h in holdings.iterrows())
    account  = user.remainingAmount + cost
    expected = (user.totalDeposited + stats['sellNetPL']
                - stats['buyTotalCharges'] - stats['chargesTotal'])
    drift    = account - expected
    ok       = abs(drift) < 1.0
    return {
        'pass':     ok,
        'account':  account,
        'expected': expected,
        'drift':    drift,
        'note':     f'Drift ₹{drift:+.4f}' + (' — run rebuild_stats' if not ok else ''),
    }

# ── Run audit ────────────────────────────────────────────────────────────────

def run_audit(ledger_path, txn_path, from_date, audit_num):
    import data_manager as dm

    print("  Loading Kotak reports...")
    ledger = parse_ledger(ledger_path)
    txn    = parse_txn(txn_path)

    print("  Loading Firebase data...")
    user     = dm.load_user()
    holdings = dm.load_holdings()
    buys     = dm.load_buys()
    sells    = dm.load_sells()
    charges  = dm.load_charges()
    stats    = dm.load_stats()

    cashflow = dm.load_cashflow()

    print("  Running checks...")
    dep   = check_deposits(ledger, user, cashflow)
    demat = check_demat(ledger, charges, from_date)
    buy   = check_buys(txn, buys)
    sell  = check_sells(txn, sells)
    bal   = check_balance(ledger, user, buys, sells, cashflow, charges)
    recon = check_recon(user, holdings, stats)

    # Build action items
    actions, idx = [], 1

    for issue in demat['issues']:
        actions.append({
            'id':          f"{audit_num}-{idx}",
            'type':        'missing_charge',
            'severity':    'high',
            'description': f"Add {issue['type']} charge in app: {issue['desc']} — ₹{issue['amount']:.2f}  (Kotak: {issue['date']})",
            'status':      'pending',
            'done_date':   None,
        }); idx += 1

    for issue in buy['issues']:
        if issue['type'] == 'qty_mismatch':
            desc = f"Fix qty: {issue['description']}"
        else:
            desc = f"Add missing buy: {issue['description']}"
        actions.append({
            'id':          f"{audit_num}-{idx}",
            'type':        issue['type'],
            'severity':    'high',
            'description': desc,
            'status':      'pending',
            'done_date':   None,
        }); idx += 1

    for issue in sell['issues']:
        actions.append({
            'id':          f"{audit_num}-{idx}",
            'type':        issue['type'],
            'severity':    'high',
            'description': f"Fix sell: {issue['description']}",
            'status':      'pending',
            'done_date':   None,
        }); idx += 1

    if not recon['pass']:
        actions.append({
            'id':          f"{audit_num}-{idx}",
            'type':        'recon_drift',
            'severity':    'critical',
            'description': f"Internal drift ₹{recon['drift']:.4f} — run dm.rebuild_stats() in app",
            'status':      'pending',
            'done_date':   None,
        }); idx += 1

    if not bal['pass']:
        actions.append({
            'id':          f"{audit_num}-{idx}",
            'type':        'balance_gap',
            'severity':    'high',
            'description': f"Unexplained balance gap ₹{bal['gap']:+.2f} — check for missing transactions",
            'status':      'pending',
            'done_date':   None,
        }); idx += 1

    all_pass = dep['pass'] and demat['pass'] and buy['pass'] and sell['pass'] and recon['pass']
    status   = 'clean' if (all_pass and not actions) else 'issues_found'

    return {
        'id':           audit_num,
        'run_date':     date.today().isoformat(),
        'ledger_file':  Path(ledger_path).name,
        'txn_file':     Path(txn_path).name,
        'period_from':  txn['period_from'],
        'period_to':    txn['period_to'],
        'check_from':   from_date,
        'status':       status,
        'kotak_closing':float(bal['kotak']),
        'app_remaining':float(bal['app']),
        'balance_gap':  float(bal['gap']),
        'sections': {
            'deposits': dep,
            'demat':    demat,
            'buys':     buy,
            'sells':    sell,
            'balance':  bal,
            'recon':    recon,
        },
        'actions': actions,
    }

# ── History ──────────────────────────────────────────────────────────────────

def load_history():
    if AUDIT_LOG.exists():
        with open(AUDIT_LOG) as f:
            return json.load(f)
    return {"audits": []}

def save_history(history):
    REPORTS_DIR.mkdir(exist_ok=True)
    with open(AUDIT_LOG, 'w') as f:
        json.dump(history, f, indent=2, default=str)

def get_last_audit_date(history):
    if not history['audits']:
        return None
    return history['audits'][-1]['run_date']

def cmd_mark_done(action_ids):
    if not AUDIT_LOG.exists():
        print("No audit_log.json found.")
        return
    with open(AUDIT_LOG) as f:
        history = json.load(f)
    marked = set()
    for audit in history['audits']:
        for action in audit.get('actions', []):
            if action['id'] in action_ids:
                action['status']    = 'done'
                action['done_date'] = date.today().isoformat()
                marked.add(action['id'])
    save_history(history)
    for aid in action_ids:
        status = "✅ marked done" if aid in marked else "❌ not found"
        print(f"  {aid}: {status}")

# ── HTML report ──────────────────────────────────────────────────────────────

def _badge(text, color):
    return (f'<span style="background:{color};color:#fff;padding:3px 10px;'
            f'border-radius:4px;font-size:11px;font-weight:700;'
            f'letter-spacing:.5px">{text}</span>')

def _status_badge(ok, warn=False):
    if ok and not warn:   return _badge('PASS', '#16a34a')
    if ok and warn:       return _badge('WARN', '#d97706')
    return _badge('FAIL', '#dc2626')

def _audit_status_badge(status):
    m = {'clean': ('#16a34a', 'CLEAN'),
         'issues_found': ('#dc2626', 'ISSUES'),
         'issues_pending': ('#d97706', 'PENDING'),
         'fixed': ('#2563eb', 'FIXED')}
    color, label = m.get(status, ('#6b7280', status.upper()))
    return _badge(label, color)

def _money(v):
    return f'₹{float(v):,.2f}'

def _row(label, kotak, app, diff_ok=True):
    diff_color = '#16a34a' if diff_ok else '#dc2626'
    return (f'<tr><td>{label}</td>'
            f'<td class="num">{kotak}</td>'
            f'<td class="num">{app}</td>'
            f'<td class="num" style="color:{diff_color}">'
            f'{"✓" if diff_ok else "✗"}</td></tr>')

def generate_html(history):
    audits = history['audits']
    current = audits[-1] if audits else None
    prev_audits = audits[:-1][-5:]  # up to 5 previous

    css = """
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;
         font-size:14px;line-height:1.6;padding:24px}
    h1{font-size:22px;color:#f8fafc;margin-bottom:4px}
    h2{font-size:16px;color:#94a3b8;margin:24px 0 12px;text-transform:uppercase;
       letter-spacing:.8px;font-weight:600}
    h3{font-size:14px;color:#cbd5e1;margin-bottom:8px;font-weight:600}
    .subtitle{color:#64748b;font-size:13px;margin-bottom:24px}
    .cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
    .card{background:#1e293b;border:1px solid #334155;border-radius:10px;
          padding:16px;flex:1;min-width:200px}
    .card.current{border-color:#3b82f6;background:#1e2d45}
    .card label{font-size:11px;color:#64748b;text-transform:uppercase;
                letter-spacing:.6px;display:block;margin-bottom:4px}
    .card .val{font-size:20px;font-weight:700;color:#f1f5f9}
    .card .sub{font-size:11px;color:#64748b;margin-top:2px}
    .section{background:#1e293b;border:1px solid #334155;border-radius:10px;
             padding:16px;margin-bottom:12px}
    .section-header{display:flex;align-items:center;gap:10px;margin-bottom:10px}
    .section-title{font-weight:600;color:#f1f5f9;font-size:14px}
    .section-note{font-size:12px;color:#64748b;margin-top:4px}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th{text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;
       letter-spacing:.5px;padding:6px 0;border-bottom:1px solid #334155}
    td{padding:6px 0;border-bottom:1px solid #1e293b;vertical-align:top}
    td.num{text-align:right;font-variant-numeric:tabular-nums;
           font-family:monospace;font-size:13px}
    .issue-row td{color:#fbbf24}
    .action{background:#292118;border:1px solid #92400e;border-radius:8px;
            padding:12px;margin-bottom:8px;display:flex;align-items:flex-start;gap:10px}
    .action.done{background:#0f2318;border-color:#166534;opacity:.7}
    .action-id{font-size:11px;font-family:monospace;color:#94a3b8;
               background:#0f172a;padding:2px 6px;border-radius:4px;
               white-space:nowrap;margin-top:2px}
    .action-desc{flex:1;font-size:13px}
    .action-status{font-size:11px;margin-top:4px}
    .action.done .action-status{color:#4ade80}
    .action:not(.done) .action-status{color:#f59e0b}
    .hist-row{display:flex;align-items:center;gap:12px;padding:8px 0;
              border-bottom:1px solid #334155;font-size:13px}
    .hist-row:last-child{border:none}
    .hist-num{color:#64748b;font-size:12px;width:24px}
    .hist-date{color:#94a3b8;width:100px}
    .hist-period{color:#64748b;flex:1;font-size:12px}
    .hist-gap{font-family:monospace;font-size:12px;color:#94a3b8;width:80px;text-align:right}
    .mono{font-family:monospace;font-size:13px}
    .gold{color:#fbbf24;font-weight:700}
    .green{color:#4ade80}
    .red{color:#f87171}
    .divider{border:none;border-top:1px solid #334155;margin:28px 0}
    .cmd-hint{background:#0f172a;border:1px solid #334155;border-radius:6px;
              padding:8px 12px;font-family:monospace;font-size:12px;color:#64748b;
              margin-top:6px}
    """

    def section_html(icon, title, check, detail_html=''):
        warn  = check.get('warn', False)
        badge = _status_badge(check['pass'], warn)
        note  = check.get('note', '')
        return f"""
        <div class="section">
          <div class="section-header">
            {badge}
            <span class="section-title">{icon} {title}</span>
            <span class="section-note">{note}</span>
          </div>
          {detail_html}
        </div>"""

    def deposits_detail(s):
        c = s['sections']['deposits']
        return f"""<table>
          <tr><th>Item</th><th class="num">Kotak</th><th class="num">App</th><th class="num">Match</th></tr>
          {_row('Net deposits', _money(c['kotak']), _money(c['app']), c['pass'])}
        </table>"""

    def demat_detail(s):
        c = s['sections']['demat']
        rows = ''
        for i in c['issues']:
            rows += f'<tr class="issue-row"><td>⚠ {i["desc"][:60]}</td><td class="num">{i["date"]}</td><td class="num gold">{_money(i["amount"])}</td><td>Not in app</td></tr>'
        if not rows:
            return f'<p style="color:#4ade80;font-size:13px">✓ {c["checked"]} charges verified</p>'
        return f"""<table>
          <tr><th>Description</th><th>Date</th><th class="num">Amount</th><th>Status</th></tr>
          {rows}
        </table>"""

    def trades_detail(s, key, price_col, qty_col):
        c = s['sections'][key]
        if c['total'] == 0:
            return f'<p style="color:#64748b;font-size:13px">{c["note"]}</p>'
        rows = ''
        for i in c['issues']:
            if i['type'] == 'qty_mismatch':
                row_note = f'Kotak={i["kotak_qty"]} App={i["app_qty"]}'
                row_cls  = 'issue-row'
            else:
                row_note = 'Missing in app'
                row_cls  = 'issue-row'
            rows += f'<tr class="{row_cls}"><td>⚠ {i["security"][:35]}</td><td>{i["trade_date"]}</td><td class="num">{_money(i["price"])}</td><td class="num">{i["kotak_qty"]}</td><td>{row_note}</td></tr>'
        match_line = f'<p style="color:#4ade80;font-size:13px;margin-bottom:6px">✓ {c["matched"]}/{c["total"]} matched</p>' if c['matched'] else ''
        if not rows:
            return match_line
        header = '<table><tr><th>Security</th><th>Date</th><th class="num">Price</th><th class="num">Qty</th><th>Status</th></tr>'
        return match_line + header + rows + '</table>'

    def balance_detail(s):
        c = s['sections']['balance']
        gap_color = '#4ade80' if c['pass'] else '#f87171'
        gap_color = '#f59e0b' if (c['pass'] and abs(c['gap']) > 0.5) else gap_color
        return f"""<table>
          <tr><th>Item</th><th class="num">Amount</th></tr>
          <tr><td>Kotak closing balance</td><td class="num gold">{_money(c['kotak'])}</td></tr>
          <tr><td>App remainingAmount</td><td class="num gold">{_money(c['app'])}</td></tr>
          <tr><td>Gap</td><td class="num" style="color:{gap_color}">{_money(abs(c['gap']))} {"(rounding)" if c['pass'] and abs(c['gap'])>0.5 else ""}</td></tr>
        </table>"""

    def recon_detail(s):
        c = s['sections']['recon']
        drift_color = '#4ade80' if c['pass'] else '#f87171'
        return f"""<table>
          <tr><th>Item</th><th class="num">Amount</th></tr>
          <tr><td>Account balance (remaining + cost basis)</td><td class="num mono">{_money(c['account'])}</td></tr>
          <tr><td>Expected balance (formula)</td><td class="num mono">{_money(c['expected'])}</td></tr>
          <tr><td>Drift</td><td class="num" style="color:{drift_color}">₹{c['drift']:+.4f}</td></tr>
        </table>"""

    def actions_html(audit):
        actions = audit.get('actions', [])
        if not actions:
            return '<p style="color:#4ade80;font-size:13px">✓ No action items</p>'

        pending = [a for a in actions if a['status'] == 'pending']
        done    = [a for a in actions if a['status'] == 'done']

        html = ''
        if pending:
            html += f'<p style="color:#f59e0b;font-size:12px;margin-bottom:8px">⚠ {len(pending)} pending</p>'
            for a in pending:
                sev_color = '#ef4444' if a['severity'] == 'critical' else '#f59e0b'
                html += f"""<div class="action">
                  <div>
                    <div class="action-id">{a["id"]}</div>
                  </div>
                  <div class="action-desc">
                    <span style="color:{sev_color}">{'🔴' if a['severity']=='critical' else '🟡'}</span>
                    {a['description']}
                    <div class="action-status">PENDING — run: python3 kotak_audit.py --mark-done {a["id"]}</div>
                  </div>
                </div>"""
        if done:
            html += f'<p style="color:#4ade80;font-size:12px;margin:8px 0">✅ {len(done)} completed</p>'
            for a in done:
                html += f"""<div class="action done">
                  <div><div class="action-id">{a["id"]}</div></div>
                  <div class="action-desc">
                    ✅ {a['description']}
                    <div class="action-status">Done {a.get('done_date', '')}</div>
                  </div>
                </div>"""
        return html

    # ── Build full HTML ──
    run_date   = current['run_date'] if current else '—'
    check_from = current.get('check_from') or 'beginning'
    period     = f"{current.get('period_from','?')} → {current.get('period_to','?')}" if current else '—'

    dashboard_items = ''
    for a in reversed(prev_audits):
        all_done   = all(x['status'] == 'done' for x in a.get('actions', []))
        eff_status = 'fixed' if (a['status'] == 'issues_found' and all_done) else a['status']
        pending_n  = sum(1 for x in a.get('actions', []) if x['status'] == 'pending')
        pnote      = f' · {pending_n} pending' if pending_n else ''
        pfrom      = a.get('period_from', '?')
        pto        = a.get('period_to', '?')
        bgap       = abs(a['balance_gap'])
        dashboard_items += (
            f'<div class="hist-row">'
            f'<span class="hist-num">#{a["id"]}</span>'
            f'<span class="hist-date">{a["run_date"]}</span>'
            f'{_audit_status_badge(eff_status)}'
            f'<span class="hist-period">Txn: {pfrom} → {pto}{pnote}</span>'
            f'<span class="hist-gap">₹{bgap:.2f} gap</span>'
            f'</div>'
        )

    current_sections = ''
    if current:
        current_sections = (
            section_html('💰', 'Deposits', current['sections']['deposits'], deposits_detail(current)) +
            section_html('🏦', 'Demat Charges', current['sections']['demat'], demat_detail(current)) +
            section_html('📥', 'Buy Transactions', current['sections']['buys'], trades_detail(current, 'buys', 'Market Rate', 'Quantity')) +
            section_html('📤', 'Sell Transactions', current['sections']['sells'], trades_detail(current, 'sells', 'Market Rate', 'Quantity')) +
            section_html('⚖️', 'Balance vs Kotak', current['sections']['balance'], balance_detail(current)) +
            section_html('🔄', 'Internal Reconciliation', current['sections']['recon'], recon_detail(current)) +
            '<div class="section"><div class="section-header"><span class="section-title">📋 Action Items</span></div>' +
            actions_html(current) + '</div>'
        )

    status_badge_html = _audit_status_badge(current['status']) if current else ''
    current_id        = current['id'] if current else '—'
    current_ledger    = current.get('ledger_file', '—') if current else '—'
    current_txn       = current.get('txn_file', '—') if current else '—'
    current_closing   = _money(current['kotak_closing']) if current else '—'
    current_remaining = _money(current['app_remaining']) if current else '—'
    current_gap_val   = _money(abs(current['balance_gap'])) if current else '—'
    gap_ok            = current and abs(current['balance_gap']) <= ROUNDING_TOLERANCE
    gap_color         = '#4ade80' if gap_ok else '#f87171'
    gap_sublabel      = 'Rounding only' if gap_ok else 'Investigate'

    if prev_audits:
        no_hist_msg   = '<p style="color:#64748b">No previous audits</p>'
        hist_content  = dashboard_items or no_hist_msg
        history_block = f'<h2>Audit History</h2><div class="section">{hist_content}</div>'
    else:
        history_block = ''

    html = (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        f'<title>Kotak Audit — {run_date}</title>\n'
        f'<style>{css}</style>\n'
        '</head>\n<body>\n'
        '<h1>📊 Kotak Audit Report</h1>\n'
        f'<p class="subtitle">Generated {run_date} &nbsp;·&nbsp; '
        f'Reports: {current_ledger} + {current_txn}</p>\n'
        f'{history_block}\n'
        f'<h2>Current Audit #{current_id} &nbsp; {status_badge_html}</h2>\n'
        '<div class="cards">\n'
        '  <div class="card current">\n'
        '    <label>Kotak Closing</label>\n'
        f'    <div class="val gold">{current_closing}</div>\n'
        '    <div class="sub">Ledger balance</div>\n'
        '  </div>\n'
        '  <div class="card current">\n'
        '    <label>App Remaining</label>\n'
        f'    <div class="val gold">{current_remaining}</div>\n'
        '    <div class="sub">remainingAmount</div>\n'
        '  </div>\n'
        '  <div class="card">\n'
        '    <label>Gap</label>\n'
        f'    <div class="val" style="color:{gap_color}">{current_gap_val}</div>\n'
        f'    <div class="sub">{gap_sublabel}</div>\n'
        '  </div>\n'
        '  <div class="card">\n'
        '    <label>Period Checked</label>\n'
        f'    <div class="val" style="font-size:14px">{period}</div>\n'
        f'    <div class="sub">Demat from: {check_from}</div>\n'
        '  </div>\n'
        '</div>\n'
        f'{current_sections}\n'
        '<hr class="divider">\n'
        '<p style="color:#475569;font-size:12px">\n'
        '  Run again: <span class="mono">python3 kotak_audit.py</span> &nbsp;·&nbsp;\n'
        '  Mark done: <span class="mono">python3 kotak_audit.py --mark-done &lt;id&gt;</span> &nbsp;·&nbsp;\n'
        '  History:   <span class="mono">python3 kotak_audit.py --history</span>\n'
        '</p>\n</body>\n</html>'
    )

    return html

# ── Entry point ──────────────────────────────────────────────────────────────

def cmd_history(history):
    audits = history['audits']
    if not audits:
        print("No audits recorded yet.")
        return
    print(f"\n{'#':>3}  {'Date':<12}  {'Status':<14}  {'Gap':>8}  {'Period':<25}  Actions")
    print("─" * 80)
    for a in audits:
        pending = sum(1 for x in a.get('actions', []) if x['status'] == 'pending')
        done    = sum(1 for x in a.get('actions', []) if x['status'] == 'done')
        total   = pending + done
        period  = f"{a.get('period_from','?')} → {a.get('period_to','?')}"
        print(f"{a['id']:>3}  {a['run_date']:<12}  {a['status']:<14}  "
              f"₹{abs(a['balance_gap']):>6.2f}  {period:<25}  "
              f"{done}/{total} done")
    print()

def main():
    parser = argparse.ArgumentParser(description='Kotak vs FIRE audit tool')
    parser.add_argument('--ledger',     help='Path to Ledger Excel file')
    parser.add_argument('--txn',        help='Path to Transaction Statement Excel file')
    parser.add_argument('--mark-done',  nargs='+', metavar='ID', help='Mark action IDs as done')
    parser.add_argument('--history',    action='store_true', help='Show audit history')
    parser.add_argument('--no-browser', action='store_true', help='Save report but do not open browser')
    args = parser.parse_args()

    REPORTS_DIR.mkdir(exist_ok=True)
    history = load_history()

    if args.history:
        cmd_history(history)
        return

    if args.mark_done:
        print("Marking actions as done...")
        cmd_mark_done(args.mark_done)
        # Regenerate last report if it exists
        if history['audits']:
            rpt = REPORTS_DIR / f"audit_{history['audits'][-1]['run_date']}.html"
            rpt.write_text(generate_html(history))
            print(f"Report updated: {rpt}")
        return

    # Run audit
    ledger_path = args.ledger or auto_detect("Ledger_*.xlsx", "Ledger file")
    txn_path    = args.txn    or auto_detect("Transaction_Statement_*.xlsx", "Transaction Statement")

    audit_num   = len(history['audits']) + 1
    from_date   = get_last_audit_date(history)

    print(f"\n🔍 Kotak Audit #{audit_num}")
    print(f"   Ledger:  {Path(ledger_path).name}")
    print(f"   Txn:     {Path(txn_path).name}")
    print(f"   Demat check from: {from_date or 'beginning'}")
    print()

    result = run_audit(ledger_path, txn_path, from_date, audit_num)
    history['audits'].append(result)
    save_history(history)

    # Generate HTML
    html      = generate_html(history)
    rpt_path  = REPORTS_DIR / f"audit_{result['run_date']}.html"
    rpt_path.write_text(html)

    # Summary
    actions  = result['actions']
    pending  = [a for a in actions if a['status'] == 'pending']
    sections = result['sections']

    print(f"{'✅' if sections['deposits']['pass'] else '❌'} Deposits:        {sections['deposits']['note']}")
    print(f"{'✅' if sections['demat']['pass'] else '❌'} Demat charges:   {sections['demat']['note']}")
    print(f"{'✅' if sections['buys']['pass'] else '❌'} Buys:            {sections['buys']['note']}")
    print(f"{'✅' if sections['sells']['pass'] else '❌'} Sells:           {sections['sells']['note']}")
    print(f"{'⚠️' if sections['balance']['warn'] else ('✅' if sections['balance']['pass'] else '❌')} Balance:         {sections['balance']['note']}")
    print(f"{'✅' if sections['recon']['pass'] else '❌'} Reconciliation:  {sections['recon']['note']}")

    if pending:
        print(f"\n⚠️  {len(pending)} action item(s) need attention:")
        for a in pending:
            print(f"   [{a['id']}] {a['description']}")
        print(f"\n   Mark done: python3 kotak_audit.py --mark-done {' '.join(a['id'] for a in pending)}")
    else:
        print("\n🎉 All clear — no action items!")

    print(f"\n📄 Report saved: {rpt_path}")

    if not args.no_browser:
        webbrowser.open(f"file://{rpt_path.absolute()}")

if __name__ == '__main__':
    main()
