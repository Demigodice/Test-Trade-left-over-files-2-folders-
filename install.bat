@echo off
rem Install the Day Trader scheduled task (Mon-Fri, 09:05 IST).
schtasks /create /f /tn "DayTraderSession" /sc weekly /d MON,TUE,WED,THU,FRI /st 09:05 /tr "\"D:\Final trading project\Windows task scheduler file\run_session.bat\"" /rl LIMITED
if errorlevel 1 (
  echo Could not create the task. Try running this file as Administrator.
) else (
  echo Task "DayTraderSession" created. It runs run_session.bat Mon-Fri 09:05.
)
pause
