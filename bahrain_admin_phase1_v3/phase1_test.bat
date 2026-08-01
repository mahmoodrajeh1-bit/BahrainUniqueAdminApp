@echo off
setlocal
flutter clean || goto :error
flutter pub get || goto :error
flutter analyze || goto :error
flutter build apk --debug || goto :error
echo.
echo SUCCESS: build\app\outputs\flutter-apk\app-debug.apk
pause
exit /b 0
:error
echo.
echo BUILD STOPPED. Copy the full error output and send it back.
pause
exit /b 1
