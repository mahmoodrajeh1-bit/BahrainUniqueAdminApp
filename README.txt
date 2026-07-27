# SharafDG PriceMatcher

This repository contains:

- `Windows_Agent/` — the Windows Playwright repricing application and phone-control API.
- `Android_App/` — the Android remote-control application.
- `.github/workflows/build-apk.yml` — GitHub Actions workflow that builds the Android APK.

## Build the APK with GitHub Actions (recommended)

Android Studio is **not required** for this method.

1. Upload all files and folders from this package to the **root** of your GitHub repository.
2. Make sure the hidden `.github` folder is uploaded.
3. Open the repository on GitHub.
4. Select the **Actions** tab.
5. Select **Build Android APK**.
6. Click **Run workflow**, then click the green **Run workflow** button.
7. Wait for the build to finish with a green check mark.
8. Open the completed workflow run.
9. Under **Artifacts**, download `PriceMatcher-Remote-APK`.
10. Extract the downloaded artifact ZIP and install `app-debug.apk` on your Android phone.

The workflow installs Java 17 and Gradle 8.9 on the GitHub runner, so the repository does not require a local Android SDK or Gradle installation.

The workflow also runs automatically whenever Android files or the workflow itself are pushed to the `main` or `master` branch.

## Repository structure

```text
NewProjectPriceUpdater/
├── .github/
│   └── workflows/
│       └── build-apk.yml
├── Android_App/
│   ├── app/
│   ├── build.gradle.kts
│   ├── gradle.properties
│   └── settings.gradle.kts
├── Windows_Agent/
├── .gitignore
└── README.md
```

## Windows agent setup

1. Open the `Windows_Agent` folder.
2. Run `BUILD_EXE.bat` to build the Windows executable, if required.
3. Start `PriceMatcherRemote.exe`.
4. Run `ALLOW_FIREWALL.bat` as Administrator if the Android app cannot connect.
5. Use the Tailscale address shown in the Windows application when connecting remotely.

## Important files not to upload

The `.gitignore` excludes local browser profiles, logs, generated executables, APK outputs, access-token files, and other computer-specific data.

## Optional local Android build

Android Studio is only needed when you want to edit or debug the Android app locally. Open the `Android_App` folder as the project.
