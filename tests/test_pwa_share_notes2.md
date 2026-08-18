RecallCheck 1.0 mobile app/share QA

- Android/Chromium: Install RecallCheck should invoke the native PWA install prompt when available.
- iPhone/iPad Safari: Add to Home Screen opens an in-product guide. iOS does not expose a web API that can complete Home Screen installation automatically.
- Share RecallCheck uses the Web Share API when available and falls back to copying the canonical URL.
- Installed mode uses the existing web app manifest plus the RecallCheck service worker.
