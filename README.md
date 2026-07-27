# SharafDG PriceMatcher v2.2

This repository contains:

- `Windows_Agent/` — the Windows Playwright repricing application and remote API.
- `Android_App/` — the Android remote-control application.
- `.github/workflows/build-apk.yml` — the GitHub Actions workflow that builds the APK.

## Build the APK on GitHub

Android Studio is **not required** for the GitHub build.

1. Upload all files and folders in this package to the **root** of your GitHub repository.
2. Confirm the repository contains `.github/workflows/build-apk.yml`.
3. Open the repository's **Actions** tab.
4. Select **Build Android APK**.
5. Click **Run workflow**, select the `main` branch, and confirm.
6. Wait for the run to finish with a green check mark.
7. Open the completed run and download the `PriceMatcher-Remote-APK` artifact.
8. Extract the downloaded artifact ZIP and install `PriceMatcher-Remote-v2.2-debug.apk` on your Android phone.

The workflow installs Java 17 and Gradle 8.9 on the GitHub runner. Therefore, a Gradle Wrapper is not required in this repository.

## Repository root structure

```text
.github/
  workflows/
    build-apk.yml
Android_App/
Windows_Agent/
.gitignore
README.md
GITHUB_UPLOAD_GUIDE.txt
```

Do not upload the outer ZIP file or place these items inside an extra parent folder.

## Windows agent

1. Open `Windows_Agent`.
2. Run `BUILD_EXE.bat` to build the Windows executable, or run the Python source directly after installing its dependencies.
3. Start `PriceMatcherRemote.exe` or `PriceMatcherRemote.py`.
4. On first use, sign in to Seller Hub in the browser opened by the application.
5. Run `ALLOW_FIREWALL.bat` as Administrator when remote access is needed.

Keep access tokens, browser profiles, logs, and generated executables private. They are excluded by `.gitignore`.
