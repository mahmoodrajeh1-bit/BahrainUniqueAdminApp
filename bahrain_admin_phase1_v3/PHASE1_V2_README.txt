Bahrain Unique Admin - Phase 1 V2

This package fixes the Dart 3 package-resolution blocker reported with Dart 3.12.2:
- SDK range changed to >=3.0.0 <4.0.0
- Old pubspec.lock removed
- Missing imported packages added
- Build-only packages moved to dev_dependencies
- Old fixed constraints updated where necessary

Run in Android Studio Terminal:
  flutter clean
  flutter pub get

Do not run flutter analyze until flutter pub get completes successfully.
Send the complete output if package resolution still fails.
