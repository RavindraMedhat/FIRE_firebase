# Kotak Neo — Complete Charge Structure & Optimization Guide

---

## 1. What Is Kotak Neo

Kotak Neo is the self-service (DIY) digital trading platform by Kotak Securities. It is separate from the full-service "Kotak Securities" dealer-assisted model. You trade yourself through the app/web — no dealer, lower brokerage.

Your account is on the **Kotak Trade Plan (delivery, DIY)** — this document is written specifically for that plan and your ETF/stock portfolio.

---

## 2. Two Buckets of Charges

Every rupee you pay Kotak goes into one of two buckets:

| Bucket | Who gets it | Can you avoid it? |
|---|---|---|
| **Kotak's own fees** | Kotak Securities | Partially — by choosing the right plan or batching trades |
| **Government/regulator pass-throughs** | SEBI, Government, NSE | No — same for every broker in India |

---

## 3. Every Charge Explained — One by One

### 3.1 Brokerage (Kotak's fee)

This is Kotak's revenue. Charged as a % of trade value on every buy and every sell.

| Segment | Your current rate |
|---|---|
| Equity ETF (delivery) | **0.05%** of trade value |
| Jewellery/Gold ETF (delivery) | **0.05%** of trade value |
| Stocks (delivery) | **0.10%** of trade value |

**Example:** Buy ₹5,000 of NIFTY IT ETF
```
Brokerage = 5000 × 0.05% = ₹2.50
```

**Important:** Brokerage is charged on **both buy and sell separately**.

---

### 3.2 STT — Securities Transaction Tax (Government)

A tax levied by the Central Government on every securities transaction. Collected by the exchange and paid to the government. **You have zero control over this.**

| Segment | Buy | Sell |
|---|---|---|
| Equity ETFs (NIFTY, Bank BeES etc.) | ₹0 | **0.001%** of sell value |
| Gold/Silver/Jewellery ETFs | ₹0 | **0.001%** of sell value |
| Equity Stocks (Reliance, Airtel etc.) | **0.1%** | **0.1%** |

**Key insight for ETFs:** STT on sell is tiny (0.001%) and NIL on buy — this is why ETFs are far cheaper than stocks from an STT perspective.

**Example:** Sell 18 units of NIFTY Realty at ₹77.85 → Value = ₹1401.30
```
STT (ETF sell) = 1401.30 × 0.001% = ₹0.014  (negligible)
```

**Example:** Sell 2 units of Reliance at ₹1413.50 → Value = ₹2827.00
```
STT (stock sell) = 2827 × 0.1% = ₹2.83
STT (stock buy ) = 2827 × 0.1% = ₹2.83  ← both sides charged!
```

---

### 3.3 Exchange Transaction Charges (NSE/BSE)

Paid to the exchange (NSE or BSE) for using their infrastructure. Charged on **every trade, both buy and sell**.

| Exchange | Rate |
|---|---|
| NSE | **0.00297%** (₹2.97 per ₹1 lakh) |
| BSE | **0.00275%** (₹2.75 per ₹1 lakh) |

Most ETFs trade on NSE (0.00297%). This rate applies to both buy and sell.

**Example:** Buy ₹5,000 of any ETF on NSE
```
Exchange charge = 5000 × 0.00297% = ₹0.149
```

---

### 3.4 SEBI Turnover Charge (Regulator)

Paid to SEBI for market oversight. Extremely small.

| Rate | ₹1 per ₹1 crore of turnover |
|---|---|
| Percentage | **0.0001%** |

**Example:** ₹5,000 trade
```
SEBI charge = 5000 × 0.0001% = ₹0.005  (half a paisa)
```

---

### 3.5 Stamp Duty (State Government)

Paid to the state government. Charged on **buy only**, not on sell.

| Segment | Rate (all states — unified since 2020) |
|---|---|
| Equity delivery (ETFs + Stocks) | **0.015%** of buy value |

**Example:** Buy ₹5,000 of any ETF
```
Stamp Duty = 5000 × 0.015% = ₹0.75
```

---

### 3.6 GST — Goods and Services Tax (Government)

18% GST is charged on the combined total of **Brokerage + Exchange charge + SEBI charge**. Stamp Duty and STT are excluded from the GST base.

```
GST base  = Brokerage + Exchange charge + SEBI charge
GST       = GST base × 18%
```

**Example:** Buy ₹5,000 ETF on NSE
```
Brokerage    = ₹2.50
Exchange     = ₹0.149
SEBI         = ₹0.005
GST base     = ₹2.654
GST (18%)    = ₹0.478
```

---

### 3.7 DP Charges — Depository Participant Charges

Charged when you **sell delivery stocks/ETFs** (because physical debit from your demat account happens). This does NOT appear on the contract note — it appears as a separate debit in your Kotak ledger a few days after the sell settles.

| Plan | DP charge per ISIN per sell day |
|---|---|
| Kotak Neo / Trade Free | **₹13.50 + 18% GST = ₹15.93** per ISIN per day |

**Critical rule:** DP charges are per **ISIN per day** — not per quantity.

```
Sell 10 units of NIFTY IT on Monday     → ₹15.93 DP charge
Sell 20 units of NIFTY IT on same Monday → STILL ₹15.93 (same ISIN, same day)
Sell 10 units of NIFTY IT on Tuesday   → another ₹15.93 (different day)
Sell NIFTY IT + SBI Gold on same day   → ₹15.93 × 2 = ₹31.86 (two ISINs)
```

**Note:** Your Kotak ledger for Apr–Jun 2026 shows NO DP charge entries. This could mean your current plan bundles DP charges into the trade charges, or charges were not applied due to the small portfolio size. Watch the ledger on future sells.

---

### 3.8 Demat AMC — Annual Maintenance Charge

Monthly maintenance charge for keeping your demat account active with CDSL.

| | Amount |
|---|---|
| Base charge | ₹16.00 / month |
| GST (18%) | ₹2.88 |
| **Total per month** | **₹18.88** |

The FIRE app auto-deducts this every 30 days and logs it to the `charges` collection. It reduces your `remainingAmount` directly.

---

## 4. Full Example — One Complete Buy

**Scenario:** Buy 10 units of NIFTY IT ETF at ₹32.60 on NSE

| Component | Formula | Amount |
|---|---|---|
| Trade value | 10 × ₹32.60 | ₹326.00 |
| Brokerage (0.05%) | 326 × 0.05% | ₹0.1630 |
| Exchange (0.00297%) | 326 × 0.00297% | ₹0.0097 |
| SEBI (0.0001%) | 326 × 0.0001% | ₹0.0003 |
| GST 18% on above 3 | (0.163 + 0.0097 + 0.0003) × 18% | ₹0.0308 |
| Stamp Duty 0.015% | 326 × 0.015% | ₹0.0489 |
| STT on buy (ETF) | 0% | ₹0.00 |
| **Total charges** | | **₹0.2527** |
| **Total outflow** | 326 + 0.2527 | **₹326.2527** |
| **Charge as % of trade** | 0.2527 / 326 | **0.078%** |

---

## 5. Full Example — One Complete Sell

**Scenario:** Sell 18 units of NIFTY Realty ETF at ₹77.85 on NSE

| Component | Formula | Amount |
|---|---|---|
| Trade value | 18 × ₹77.85 | ₹1401.30 |
| Brokerage (0.05%) | 1401.30 × 0.05% | ₹0.7007 |
| Exchange (0.00297%) | 1401.30 × 0.00297% | ₹0.0416 |
| SEBI (0.0001%) | 1401.30 × 0.0001% | ₹0.0014 |
| GST 18% on above 3 | (0.7007 + 0.0416 + 0.0014) × 18% | ₹0.1335 |
| Stamp Duty | sell side = 0 | ₹0.00 |
| STT on sell (ETF) | 1401.30 × 0.001% | ₹0.0140 |
| **Total charges** | | **₹0.8912** |
| **Net credited to account** | 1401.30 − 0.8912 | **₹1400.41** |

---

## 6. Your Actual Charges So Far (from Firebase)

As of May 2026, across **87 buys + 11 sells** on ₹54,264 deployed:

| Category | Amount Paid |
|---|---|
| Buy brokerage | ₹45.24 |
| Buy statutory (exchange + SEBI + stamp + GST) | ₹54.47 |
| **Total buy charges** | **₹99.72** |
| Sell brokerage | ₹12.24 |
| Sell statutory | ₹11.30 |
| **Total sell charges** | **₹23.54** |
| Demat AMC (2 months) | ₹37.76 |
| **Grand total paid** | **₹161.02** |

**Effective charge rate on buys:** 99.72 / 54264 = **0.184%**
**Effective charge rate on sells:** 23.54 / 16046 = **0.147%**

---

## 7. Which Charges Are Fixed vs Variable

| Charge | Type | Grows with |
|---|---|---|
| Brokerage | Variable | Trade value |
| Exchange charge | Variable | Trade value |
| SEBI charge | Variable | Trade value (tiny) |
| Stamp duty | Variable | Buy value only |
| STT | Variable | Trade value |
| GST | Variable | Brokerage + exchange + SEBI |
| DP charges | Fixed per ISIN per day | Number of sell days × ISINs |
| Demat AMC | Fixed | Time (not trades) |

---

## 8. Charge Optimization Strategy

### Strategy 1 — Consolidate buys into fewer, larger orders (HIGH IMPACT)

All charges scale linearly with trade value (proportional). But **brokerage has a minimum implied fixed cost** per order at small values. For tiny trades, you're paying the same % but on a smaller base — the charge % stays the same but the per-rupee burden on returns is higher.

**More importantly:** Every time you place an order, you pay exchange + SEBI + GST + stamp duty. Placing 5 small orders instead of 1 large order multiplies the number of charge events.

```
5 buys × ₹500 each = ₹2500 total
Charges ≈ ₹2500 × 0.184% = ₹4.60

1 buy × ₹2500
Charges ≈ ₹2500 × 0.184% = ₹4.60  ← same rupee amount, but you saved 4 order events
```

The saving isn't in the rupee amount of charges (proportional), but in **DP charges on sell side** — if you accumulate positions in fewer batches, you make fewer sell events → fewer DP charge hits.

---

### Strategy 2 — Batch sells by ISIN and do them in one day (HIGH IMPACT for DP charges)

DP charges are **per ISIN per day**, not per quantity.

```
WRONG:  Sell NIFTY IT on Monday (₹15.93) + sell remaining NIFTY IT on Tuesday (₹15.93) = ₹31.86

RIGHT:  Sell all NIFTY IT on Monday = ₹15.93  ← saves ₹15.93
```

**Never split a sell of the same ETF across multiple days.**

---

### Strategy 3 — Sell multiple ISINs on the same day (MEDIUM IMPACT)

If you need to sell 3 different ETFs, doing it all on one day vs 3 separate days saves 2 extra DP charge events.

```
Sell NIFTY IT + SBI Gold + NIFTY Realty all on Monday:
DP charges = ₹15.93 × 3 = ₹47.79

Sell each on a different day:
DP charges = ₹15.93 × 3 = ₹47.79  ← same! (3 ISINs × 1 day each)

But if you sell NIFTY IT on Mon + Tue (partial each day):
DP charges = ₹15.93 + ₹15.93 = ₹31.86 just for that one ISIN!
```

---

### Strategy 4 — ETFs over stocks for lower STT (MEDIUM IMPACT)

| Trade ₹10,000 | ETF | Stock |
|---|---|---|
| STT on buy | ₹0 | ₹10.00 |
| STT on sell | ₹0.10 | ₹10.00 |
| **Total STT** | **₹0.10** | **₹20.00** |

For the same trade size, ETFs cost **200× less in STT** than individual stocks. This alone makes ETFs significantly cheaper for buy-and-hold strategies.

---

### Strategy 5 — Avoid over-trading (HIGH IMPACT on returns)

Each round-trip (buy + sell) costs approximately **0.33%** of trade value in total charges (buy 0.184% + sell 0.147%). 

For a ₹5,000 position:
```
Round-trip cost = ₹5000 × 0.33% = ₹16.50
```
To break even, the ETF must gain **at least 0.33%** just to cover charges. Unnecessary trades eat returns directly.

**Rule:** Only sell when profit target is meaningfully above the round-trip charge rate. For a ₹5,000 trade, the minimum sensible profit before selling is ₹50–₹100 (1–2%).

---

### Strategy 6 — Use "Kotak gross total" field correctly on sells (DATA ACCURACY)

When recording a sell in the FIRE app, the sell form has a field:
```
"Kotak gross total — Market Rate × Qty (optional)"
```

**Always enter Market Rate × Qty from your Kotak transaction statement**, NOT the net credit from the ledger. Using the net credit causes charges to be double-counted in reconciliation.

Example for NIFTY Realty (18 units @ ₹77.85):
```
Enter: 18 × 77.85 = 1401.30  ✓  (Market Rate × Qty)
NOT:   1400.42               ✗  (net credit after charges)
```

---

### Strategy 7 — Evaluate plan upgrade for high-volume months (LOW IMPACT currently)

| Plan | Delivery brokerage | Monthly fee | Break-even volume |
|---|---|---|---|
| **Your current plan** | 0.05% (ETF) | ₹0 | — |
| Trade Free Plan | 0.20% | ₹0 | always worse for ETF delivery |
| Trade Free Pro | 0.10% | ₹249 + GST = ₹294 | need ₹2.94L+ monthly buys to save |

At your current portfolio size and trade frequency, your current plan is optimal. Trade Free Pro only saves money if you trade more than ₹2–3 lakh per month in delivery.

---

## 9. Quick Reference — Charge Rates at a Glance

| Charge | Rate | Buy | Sell |
|---|---|---|---|
| Brokerage (ETF) | 0.05% | ✓ | ✓ |
| Brokerage (Stock) | 0.10% | ✓ | ✓ |
| Exchange (NSE) | 0.00297% | ✓ | ✓ |
| SEBI | 0.0001% | ✓ | ✓ |
| Stamp Duty | 0.015% | ✓ | ✗ |
| STT (ETF) | 0.001% | ✗ | ✓ |
| STT (Stock) | 0.1% | ✓ | ✓ |
| GST | 18% on brokerage+exchange+SEBI | ✓ | ✓ |
| DP charge | ₹15.93 flat per ISIN | ✗ | ✓ |
| Demat AMC | ₹18.88 / month | — | — |

---

## 10. The One Number to Remember

**For ETF delivery trades on your plan, the all-in round-trip charge rate is approximately 0.33%.**

Buying ₹10,000 of ETFs and selling them = ₹33 gone in charges, regardless of profit or loss.

Every trade must be worth at least ₹33 in expected gain before it's worth doing.

---

*Sources: Kotak Neo official pricing page, chittorgarh.com Kotak Securities 2026, FIRE app data_manager.py charge model, Firebase transaction data.*
