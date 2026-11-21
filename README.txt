DAY TRADER - Windows Task Scheduler setup
=========================================

What this folder does
---------------------
It makes the day-trader-skill run hands-free every trading day (Mon-Fri,
09:05 IST). The runner chains the whole pipeline by itself: Nifty-50 scan,
entry check, stop/target plan, Time Machine odds, position sizing, risk
check, and a 1-minute alerts loop while a trade is open.

It NEVER places an order. When you should act, it prints a BIG BANNER
plus beeps:
  - BUY SIGNAL - <TICKER>   with entry / stop / target / odds
  - STOP HIT - SELL
  - TARGET HIT - SELL
  - FLAT BY CLOSE - SELL EVERYTHING (15:15)
You buy and sell yourself in your broker app.

Budget configured in day-trader-skill\trader\config.json:
  Rs 2000 total, max loss per trade Rs 150, max daily loss Rs 1800
  (worst case you end the day at Rs 200), max 3 trades/day.

How to use
----------
1. Double-click  install.bat     (once; if blocked, right-click -> Run as
                                 administrator). Creates the "DayTraderSession"
                                 task, Mon-Fri 09:05.
2. That's it. Every trading day a console window opens at 09:05 and runs
   the session until ~15:20 IST. Leave the PC on with the screen unlocked.
3. To remove everything: double-click  uninstall.bat, then delete this
   folder. Nothing else was changed on the PC.

Files
-----
  install.bat      create the scheduled task
  uninstall.bat    remove the scheduled task
  run_session.bat  launched by the task; opens the console and runs the day
  run_session.py   the hands-free session logic (no extra dependencies)

Notes
-----
- The PC clock must be set to IST (India) - the session times are IST.
- No trading-day? (weekend / NSE holiday) the runner notices and exits.
- The skill itself still requires YOUR confirmation for any order; the
  runner just tells you when and at what levels. Education only, not
  financial advice.
