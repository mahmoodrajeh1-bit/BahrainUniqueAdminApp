@echo off
title Build PriceMatcher Remote APK
cd /d "%~dp0"

if not exist gradlew.bat (
  echo Gradle wrapper is not included in this package.
  echo Open this folder in Android Studio first.
  echo Android Studio will configure Gradle and download the Android SDK components.
  echo Then use: Build ^> Build APK(s)
  pause
  exit /b 1
)

call gradlew.bat assembleDebug
echo.
echo APK location:
echo app\build\outputs\apk\debug\app-debug.apk
pause
