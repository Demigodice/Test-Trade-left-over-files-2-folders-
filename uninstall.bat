@echo off
schtasks /delete /f /tn "DayTraderSession"
echo Task "DayTraderSession" removed (if it existed).
pause
