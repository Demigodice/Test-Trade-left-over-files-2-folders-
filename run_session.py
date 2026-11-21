# -*- coding: utf-8 -*-
"""
Hands-free day-trading session runner (NSE, IST).

Runs the whole day-trader-skill pipeline by itself:
  scan -> entry -> exit plan -> time machine -> budget -> risk
and prints a BIG BANNER (with beeps) when you should BUY or SELL.
It never places an order: you buy/sell yourself in your broker app.

Started by the Windows Task Scheduler task (see install.bat) every
trading day at 09:05 IST. The script waits for the market itself.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

PROJECT = r"D:\Final trading project\day-trader-skill"
TRADER = os.path.join(PROJECT, "trader")

MAX_TRADES = 3
FIRST_SCAN = "09:50"     # first opening-range scan of the day
RESCAN_EVERY_MIN = 15    # re-scan if nothing triggered yet
LAST_SCAN = "14:00"      # give up looking for new entries after this
MONITOR_EVERY_SEC = 60   # alerts check interval while in a trade
END_OF_DAY = "15:20"     # final flat-by sweep, then exit

BANNER_WIDTH = 74


# ------------------------------------------------------------------ helpers

def now_hm():
    """Local time as HH:MM. Assumes the PC clock is set to IST (India)."""
    return datetime.now().strftime("%H:%M")


def hms_to_min(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def now_min():
    return hms_to_min(now_hm())


def sleep_until(hhmm):
    """Sleep until local time HH:MM (today)."""
    target = hms_to_min(hhmm)
    while True:
        cur = now_min()
        if cur >= target:
            return
        # sleep in small chunks so a long lunch wait stays responsive
        time.sleep(min(60, max(1, (target - cur) * 60 // 2)))


def run(script, args):
    """Run one skill script, return its stdout text."""
    p = subprocess.run(
        [sys.executable, os.path.join(PROJECT, script)] + args,
        cwd=PROJECT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    return out.strip()


def banner(lines, title="ATTENTION"):
    """Big terminal banner + beeps. ANSI colours where supported."""
    os.system("")  # enable ANSI on Windows terminals
    beep = "\a" * 3
    print("\n" * 3)
    for line in lines:
        print(" " * 8 + line.upper())
    print()
    print(beep, end="", flush=True)
    print("=" * BANNER_WIDTH)
    print(("== " + title + " ==").center(BANNER_WIDTH))
    print("=" * BANNER_WIDTH)
    for line in lines:
        print(line.center(BANNER_WIDTH))
    print("=" * BANNER_WIDTH + "\a")
    time.sleep(15)  # stay on screen long enough to be seen


def read_json(name):
    try:
        with open(os.path.join(TRADER, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


TICKER_RE = re.compile(r"^\s*\d{1,2}:\d{2}\s*[AP]M\s+([A-Z0-9.\-]+)\s+\$?([\d,]+)")


def parse_hits(scan_out):
    """Ticker lines from the orb scan output."""
    hits = []
    for line in scan_out.splitlines():
        m = TICKER_RE.match(line)
        if m:
            tkr = m.group(1).split(".")[0]
            if tkr not in hits:
                hits.append(tkr)
    return hits


# ------------------------------------------------------------------ steps

def trading_day_ok():
    """Weekend / NSE holiday check: ask the scanner itself."""
    out = run(r"trader-scanner\scan.py", ["orb", "--at", FIRST_SCAN, "--min-price", "0"])
    low = out.lower()
    if "holiday" in low or "weekend" in low:
        print(out)
        print("\nNot a trading day. Exiting. Nothing was placed.")
        return False
    return True  # live output may be empty early; the scan loop retries


def try_build_trade(tkr):
    """scan hit -> entry -> plan -> time machine -> size -> risk.
    Returns (banner_lines, ok)."""
    print("\n--- candidate:", tkr, "-------------------------------------")
    entry = run(r"trader-entry\entry.py",
                ["check", tkr, "--setup", "orb", "--write"])
    print(entry[:600])
    if "TRIGGERED" not in entry:
        return None, False

    plan = run(r"trader-exit\exit.py",
               ["plan", "--stop", "or-mid", "--target", "1R", "--write"])
    print(plan[:600])
    if "Stop" not in plan and "stop" not in plan:
        return None, False
    if not read_json("plan.json"):
        return None, False

    # Time machine: the honest odds, before any money is at risk
    tm = run(r"trader-timemachine\timemachine.py", ["run", "--write"])
    odds = ""
    for ln in tm.splitlines():
        if "target first" in ln or "stop first" in ln:
            odds += ln.strip() + "   "
    print(odds or tm[:200])

    size = run(r"trader-budget\size.py", ["--write"])
    print(size[:600])
    orders = read_json("orders.json")
    if not orders:
        return None, False
    order = orders[0] if isinstance(orders, list) else orders
    if not str(order.get("qty", "0")).strip() or int(order.get("qty", 0)) <= 0:
        print("Size came out to 0 shares (too expensive for the budget). Skip.")
        return None, False

    risk = run(r"trader-risk\check.py", [])
    print(risk[:400])
    if "PASS" not in risk:
        return None, False

    planj = read_json("plan.json") or {}
    lines = [
        "BUY %s  %s SHARES" % (tkr, order.get("qty")),
        "ENTRY around  %s" % order.get("entry") or planj.get("entry", ""),
        "STOP-LOSS     %s" % planj.get("stop", ""),
        "TARGET        %s" % planj.get("target", ""),
        "RISK if stop hits: about %s" % order.get("max_loss", ""),
        "Odds: %s" % (odds or "see the log above"),
        "Flat by 15:15 - no overnight hold. Place it in YOUR broker app.",
    ]
    return [l for l in lines if l.strip()], True


def add_alerts():
    out = run(r"trader-alerts\alerts.py", ["add", "--from-plan"])
    print(out[:300])


def monitor_until_flat():
    """Every MONITOR_EVERY_SEC: check alerts. Big banner on SELL reasons.
    Returns when stop/target/flat-by fires (trade over)."""
    while now_min() < hms_to_min("15:20"):
        out = run(r"trader-alerts\alerts.py", ["check"])
        hit_lines = [ln for ln in out.splitlines() if ln.startswith("ALERT")]
        if hit_lines:
            low = " ".join(hit_lines).lower()
            if "stop" in low:
                banner(hit_lines + ["SELL NOW / your stop should have filled."],
                       "STOP HIT - GET OUT")
                return
            if "target" in low:
                banner(hit_lines + ["TARGET HIT - book it (sell now)."],
                       "TARGET HIT - SELL")
                return
            if "flat" in low:
                banner(hit_lines + ["Close whatever is still open. NOW."],
                       "FLAT BY CLOSE - SELL EVERYTHING")
                return
            banner(hit_lines, "ALERT")
        time.sleep(MONITOR_EVERY_SEC)
    banner(["15:20 - the session runner is closing. If a position is still",
            "open, SELL it now in your broker app."],
           "END OF DAY - FLAT")


# ------------------------------------------------------------------ main

def main():
    os.makedirs(TRADER, exist_ok=True)
    print("=" * BANNER_WIDTH)
    print("DAY TRADER - NSE session runner (hands-free)".center(BANNER_WIDTH))
    print(("started " + datetime.now().strftime("%Y-%m-%d %H:%M")).center(BANNER_WIDTH))
    print("=" * BANNER_WIDTH)
    print("It will show a BIG BANNER when you should BUY or SELL.")
    print("You place the orders yourself. Nothing is auto-traded.\n")

    if datetime.now().weekday() >= 5:
        print("It is the weekend. Exiting.")
        return
    if not trading_day_ok():
        return

    sleep_until(FIRST_SCAN)
    print("[" + now_hm() + "] market scan begins")

    trades_done = 0
    while trades_done < MAX_TRADES and now_min() < hms_to_min(LAST_SCAN):
        scan = run(r"trader-scanner\scan.py",
                   ["orb", "--at", now_hm(), "--min-price", "0"])
        print(scan[:500])
        hits = parse_hits(scan)
        if not hits:
            print("[%s] no setups yet; next scan in %d min"
                  % (now_hm(), RESCAN_EVERY_MIN))
            sleep_until((datetime.now() + timedelta(minutes=RESCAN_EVERY_MIN))
                        .strftime("%H:%M"))
            continue

        traded = False
        for tkr in hits:
            lines, ok = try_build_trade(tkr)
            if not ok:
                continue
            banner(lines, "BUY SIGNAL - %s" % tkr)
            add_alerts()
            monitor_until_flat()
            trades_done += 1
            traded = True
            if trades_done >= MAX_TRADES or now_min() >= hms_to_min("14:45"):
                break
        if not traded:
            sleep_until((datetime.now() + timedelta(minutes=RESCAN_EVERY_MIN))
                        .strftime("%H:%M"))

    # final sweep
    sleep_until(END_OF_DAY)
    out = run(r"trader-alerts\alerts.py", ["check"])
    for ln in out.splitlines():
        if ln.startswith("ALERT"):
            banner([ln], "END OF DAY")
    print("\n[" + now_hm() + "] session over. Runner exiting. Nothing was auto-traded.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print("Runner error:", repr(e))
        time.sleep(60)
