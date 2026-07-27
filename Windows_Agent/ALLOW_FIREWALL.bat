@echo off
title Allow PriceMatcher Remote
net session >nul 2>&1
if errorlevel 1 (
  echo Please right-click this file and choose "Run as administrator".
  pause
  exit /b 1
)
netsh advfirewall firewall delete rule name="PriceMatcher Remote" >nul 2>&1
netsh advfirewall firewall add rule name="PriceMatcher Remote" dir=in action=allow protocol=TCP localport=8765
echo Windows Firewall rule added for TCP port 8765.
pause
