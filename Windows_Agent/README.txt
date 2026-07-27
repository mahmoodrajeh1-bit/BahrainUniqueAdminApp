SharafDG PriceMatcher Remote — Multi-Laptop Edition
=====================================================

This package adds phone control to the working Windows PriceMatcher.

PHONE FEATURES
--------------
- Register multiple laptops.
- Start, pause, resume and stop each laptop.
- View cycle, page, checked, updated, skipped and error totals.
- View recent activity logs.
- Works over mobile data through Tailscale.

WINDOWS SETUP
-------------
1. Extract the ZIP.
2. Run BUILD_EXE.bat.
3. Run PriceMatcherRemote.exe.
4. Run ALLOW_FIREWALL.bat as Administrator.
5. Install Tailscale and sign in.
6. Keep the laptop awake and connected to the internet.
7. Log in to Seller Hub once in the automation browser.

ANDROID SETUP
-------------
1. Install Tailscale on Android and sign in to the same account.
2. Find the laptop's Tailscale address, normally 100.x.x.x.
3. Open Chrome and browse to:
   http://100.x.x.x:8765
4. Tap + Laptop.
5. Enter a laptop name, the same address, and the token shown in the Windows app.
6. Save it.
7. Add other laptops the same way.
8. Use Chrome's “Add to Home screen” for app-like access.

IMPORTANT
---------
- Do not expose port 8765 through your router.
- Use Tailscale only.
- Do not share the access token.
- The laptop must not sleep or hibernate.
- This is a phone-friendly remote web app, not a compiled APK.
