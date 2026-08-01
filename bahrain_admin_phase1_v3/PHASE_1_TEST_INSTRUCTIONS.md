# Bahrain Unique Admin - Phase 1 migration candidate

This copy modernizes the Android host project for current Flutter/Android Studio:

- Android embedding v2
- Gradle 8.10.2
- Android Gradle Plugin 8.7.3
- Java 17
- AndroidX
- minSdk 23
- Modern Flutter Gradle plugin loader
- Firebase Google Services plugin retained
- Debug signing enabled for private test APKs

## Important

The original Dart application was written for Dart 2.1 / Flutter 1.x. The Android host migration is complete in this candidate, but Dart 3 package/API migration must be validated by your installed Flutter SDK. Because SDK/package downloads and Android emulation are unavailable in the preparation environment, this ZIP is a test candidate rather than a claimed successful APK build.

## Run in Android Studio Terminal

```powershell
flutter clean
flutter pub get
flutter analyze
flutter build apk --debug
```

The APK, after a successful build, will be at:

`build\app\outputs\flutter-apk\app-debug.apk`

Send the complete output of the first failing command. Do not manually delete or rewrite files before sending the error.

## Rollback

The original dependency file is included as `pubspec.legacy.yaml`.
