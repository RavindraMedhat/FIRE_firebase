#!/usr/bin/env python3
"""
kotak_order.py — Playwright-based Kotak Neo order automation

Reads kotak_orders.json (exported from FIRE Settings page) and places
each order in a visible Chrome window, pausing for your confirmation
before submitting.

Setup (one time):
    pip install playwright
    playwright install chromium

Usage:
    python kotak_order.py
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

# ── paths ────────────────────────────────────────────────────────────────────
ORDERS_FILE  = Path(__file__).parent / "kotak_orders.json"
PROFILE_DIR  = Path.home() / ".kotak-browser-profile"
KOTAK_URL    = "https://trade.kotakneo.com/Landing"

# ── ETF name → Kotak Neo sidebar symbol ──────────────────────────────────────
SYMBOL_MAP = {
    "CPSE ETF":                              "CPSEETF",
    "NIFTY Metal ETF":                       "METALIETF",
    "NIFTY Dividend Opportunities 50 TRI":   "DIVOPPBEES",
    "NIFTY 50 Value 20":                     "NV20IETF",
    "Hindustan Unilever Ltd":                "HINDUNILVR",
    "ITC Ltd":                               "ITC",
    "HDFC Bank Ltd":                         "HDFCBANK",
    "Larsen & Toubro Ltd":                   "LT",
    "LIC Housing Finance Ltd":               "LICHSGFIN",
    "Gold BeES":                             "GOLDBEES",
    "Nippon India ETF Shariah BeES":         "SHARIABEES",
    "SBI ETF Gold":                          "SETFGOLD",
    "Kotak Gold ETF":                        "KOTAKGOLD",
    "Nippon India ETF Nifty PSU Bank BeES":  "PSUBNKBEES",
    "Mirae Asset NYSE FANG+ ETF":            "MAFANG",
    "Nippon India ETF Nifty BeES":           "NIFTYBEES",
    "SBI Nifty 50 ETF":                      "SETFNIF50",
    "Tata Gold ETF":                         "TATGOLD",
}


def resolve_symbol(name: str) -> str:
    if name in SYMBOL_MAP:
        return SYMBOL_MAP[name]
    for k, v in SYMBOL_MAP.items():
        if k.lower() in name.lower() or name.lower() in k.lower():
            return v
    return name.replace(" ", "").upper()[:12]


# ── navigation ────────────────────────────────────────────────────────────────

async def navigate_to_security(page: Page, order: dict) -> bool:
    """Click the security in the sidebar by symbol text."""
    name   = order["name"]
    symbol = order.get("symbol") or resolve_symbol(name)
    print(f"  → Navigating to {name} (symbol: {symbol})")

    try:
        # Playwright waits for React to render, then clicks the exact text
        loc = page.get_by_text(symbol, exact=True).first
        await loc.wait_for(state="visible", timeout=6000)
        await loc.click()
        await asyncio.sleep(1.5)
        return True
    except Exception:
        pass

    # Fallback: use the search bar
    print(f"  ⚠ Sidebar symbol not found, trying search...")
    try:
        search = page.get_by_placeholder("Search").first
        await search.wait_for(state="visible", timeout=4000)
        await search.click()
        await search.fill(name[:15])
        await asyncio.sleep(1.5)
        result = page.get_by_text(name, exact=False).first
        await result.wait_for(state="visible", timeout=4000)
        await result.click()
        await asyncio.sleep(1.5)
        return True
    except Exception as e:
        print(f"  ✗ Navigation failed: {e}")
        return False


# ── order form ────────────────────────────────────────────────────────────────

async def fill_order_form(page: Page, order: dict) -> bool:
    """Click Buy/Sell, fill Qty + Price, set Limit + Cash."""
    action = order["action"]
    qty    = str(order["qty"])
    price  = f"{order['price']:.2f}"

    try:
        # Click the Buy or Sell button on the detail page
        btn = page.get_by_role("button", name=action.capitalize(), exact=True).first
        await btn.wait_for(state="visible", timeout=5000)
        await btn.click()
        await asyncio.sleep(1.2)
    except Exception as e:
        print(f"  ✗ Could not click {action} button: {e}")
        return False

    # Fill Quantity
    qty_filled = False
    for sel in ["input[placeholder*='Qty']", "input[placeholder*='qty']",
                "input[placeholder*='Quantity']", "input[name*='qty']"]:
        try:
            f = page.locator(sel).first
            await f.wait_for(state="visible", timeout=2000)
            await f.triple_click()
            await f.fill(qty)
            qty_filled = True
            break
        except Exception:
            continue

    if not qty_filled:
        print("  ⚠ Could not find Qty field — fill manually in browser")

    # Fill Price
    price_filled = False
    for sel in ["input[placeholder*='Price']", "input[placeholder*='price']",
                "input[placeholder*='price']", "input[name*='price']"]:
        try:
            f = page.locator(sel).first
            await f.wait_for(state="visible", timeout=2000)
            await f.triple_click()
            await f.fill(price)
            price_filled = True
            break
        except Exception:
            continue

    if not price_filled:
        print("  ⚠ Could not find Price field — fill manually in browser")

    # Ensure Order Type = Limit
    try:
        await page.get_by_text("Limit", exact=True).first.click()
    except Exception:
        pass

    # Ensure Product Type = Cash (Kotak Neo calls CNC "Cash")
    try:
        await page.get_by_text("Cash", exact=True).first.click()
    except Exception:
        pass

    return True


async def submit_order(page: Page, order: dict) -> bool:
    """Click the final submit button and confirm."""
    action = order["action"]
    try:
        # Last Buy/Sell button is the form submit (not the detail page button)
        btns = page.get_by_role("button", name=action.capitalize(), exact=True)
        count = await btns.count()
        await btns.nth(count - 1).click()
        await asyncio.sleep(1.5)

        # Dismiss any confirmation popup if present
        for label in ["Confirm", "Proceed", "Place Order"]:
            try:
                confirm = page.get_by_role("button", name=label)
                await confirm.wait_for(state="visible", timeout=2000)
                await confirm.click()
                await asyncio.sleep(1)
                break
            except Exception:
                continue

        return True
    except Exception as e:
        print(f"  ✗ Submit failed: {e}")
        return False


# ── main loop ─────────────────────────────────────────────────────────────────

async def run():
    if not ORDERS_FILE.exists():
        print(f"\n✗ {ORDERS_FILE} not found.")
        print("  → Open FIRE → Settings → Export orders for Playwright first.")
        sys.exit(1)

    with open(ORDERS_FILE) as f:
        orders = json.load(f)

    if not orders:
        print("No orders in file.")
        sys.exit(0)

    W = 58
    print("\n" + "=" * W)
    print(f"  Kotak Order Automation   {len(orders)} order(s)")
    print("=" * W)
    for i, o in enumerate(orders, 1):
        print(f"  {i}. {o['action']:4s}  {o['name']:<38s}  {o['qty']:>4} qty @ ₹{o['price']:.2f}")
    print("=" * W)
    input("\nPress ENTER to open browser, Ctrl+C to cancel...")

    async with async_playwright() as p:
        print(f"\nOpening browser (profile: {PROFILE_DIR})")
        print("First time? Log into Kotak Neo — profile is saved for next time.\n")

        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            viewport={"width": 1440, "height": 900},
        )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(KOTAK_URL)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)

        # Wait for login if needed
        if "login" in page.url.lower() or await page.get_by_text("Login", exact=True).is_visible():
            print("Please log in to Kotak Neo in the browser...")
            try:
                await page.wait_for_url("**Landing**", timeout=120_000)
                print("Logged in! Starting orders...\n")
            except Exception:
                print("Login timeout. Exiting.")
                await ctx.close()
                return

        placed = skipped = failed = 0

        for i, order in enumerate(orders):
            sep = "─" * W
            print(f"\n{sep}")
            print(f"  Order {i+1}/{len(orders)}:  {order['action']}  {order['name']}")
            print(f"  Qty: {order['qty']}   Price: ₹{order['price']:.2f}")
            print(sep)

            ok = await navigate_to_security(page, order)
            if not ok:
                resp = input("  Navigation failed. Press ENTER to retry, S to skip: ").strip().upper()
                if resp == "S":
                    skipped += 1
                    continue
                ok = await navigate_to_security(page, order)
                if not ok:
                    print("  ✗ Skipping after retry.")
                    failed += 1
                    continue

            ok = await fill_order_form(page, order)
            if not ok:
                resp = input("  Form fill failed. S to skip: ").strip().upper()
                if resp == "S":
                    await page.keyboard.press("Escape")
                    skipped += 1
                    continue

            print(f"\n  ✅ Form filled — check the browser window.")
            resp = input("  ENTER to submit  |  S to skip: ").strip().upper()

            if resp == "S":
                print(f"  ↷ Skipped.")
                await page.keyboard.press("Escape")
                skipped += 1
                continue

            ok = await submit_order(page, order)
            if ok:
                print(f"  ✓ Submitted!")
                placed += 1
            else:
                print(f"  ✗ Submit failed — check browser.")
                failed += 1

            await asyncio.sleep(1.5)

        print(f"\n{'=' * W}")
        print(f"  Done — {placed} placed  |  {skipped} skipped  |  {failed} failed")
        print(f"{'=' * W}")
        input("\nPress ENTER to close browser...")
        await ctx.close()


if __name__ == "__main__":
    asyncio.run(run())
