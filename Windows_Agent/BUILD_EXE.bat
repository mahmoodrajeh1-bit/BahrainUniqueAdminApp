@echo off
title Build SharafDG PriceMatcher Remote
cd /d "%~dp0"

echo Installing required Python packages...
py -m pip install --upgrade pip
py -m pip install playwright pyinstaller

echo Building PriceMatcherRemote.exe...
py -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name PriceMatcherRemote ^
  --collect-all playwright ^
  PriceMatcherRemote.py

if errorlevel 1 (
  echo.
  echo BUILD FAILED.
  pause
  exit /b 1
)

copy /Y "dist\PriceMatcherRemote.exe" "PriceMatcherRemote.exe" >nul

echo.
echo Build completed successfully.
echo Run PriceMatcherRemote.exe from this folder.
echo.
pause
