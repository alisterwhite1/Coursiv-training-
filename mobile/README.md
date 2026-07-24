# RCA Navigator — Native Android/iOS Packaging

This directory wraps `rca-process-map.html` in a native app shell using
[Capacitor](https://capacitorjs.com/). The project is fully scaffolded and
tested up to the point where actual compilation needs real Android/iOS
build tools — Android Studio bundles the Android SDK, and this sandbox's
network policy blocks `dl.google.com` (confirmed: even resolving the
Android Gradle Plugin itself fails with a 403), so the final compile has
to happen on your own machine.

## What's already done

- `package.json` — Capacitor core/CLI/Android/iOS installed (v8.4.2)
- `capacitor.config.json` — app id `com.rcanavigator.app`, app name
  "RCA Navigator" (placeholder — see **Before you publish** below)
- `www/index.html` — a copy of the web app
- `android/` — full native Android Studio project, ready to open
- `ios/` — full native Xcode project, ready to open (Mac + Xcode only)

## Prerequisites (your machine, not this sandbox)

**For Android:**
- [Android Studio](https://developer.android.com/studio) (bundles the
  Android SDK — this is the one thing that couldn't be set up here)
- Node.js 18+ (to run the `npm` commands below)

**For iOS:**
- A Mac
- [Xcode](https://apps.apple.com/app/xcode/id497799835) (from the Mac
  App Store)
- An Apple Developer account (free to build/run on your own device;
  $99/year to publish to the App Store)
- Node.js 18+

## First-time setup

1. Copy this whole `mobile/` folder (and the `rca-process-map.html` one
   level up, which it references) to your machine
2. In the `mobile/` folder, run:
   ```
   npm install
   ```

## Building for Android

1. ```
   npx cap open android
   ```
   This opens the project in Android Studio (installs it first if you
   haven't already).
2. Let Android Studio finish its first Gradle sync (this is the part
   that needed the real SDK — it'll download everything it needs
   automatically).
3. Click the green **Run** button to build and launch on an emulator or
   a connected Android phone (USB debugging enabled).
4. To produce a real, installable file: **Build → Generate Signed App
   Bundle / APK**. For your own device/testing, an unsigned debug APK
   also works — Android Studio can build one from the same menu.

## Building for iOS

1. ```
   npx cap open ios
   ```
   This opens `ios/App/App.xcworkspace` in Xcode.
2. Select your Team under **Signing & Capabilities** (needs your Apple
   ID added in Xcode's settings first).
3. Choose a simulator or your connected iPhone as the run target, then
   click **Run**.
4. To submit to the App Store: **Product → Archive**, then follow
   Xcode's Organizer window to upload to App Store Connect.

## Updating the app after making changes to `rca-process-map.html`

Whenever the web app itself changes, run this from the `mobile/`
folder to pull the latest version into both native projects:

```
npm run sync
```

This copies the current `rca-process-map.html` into `www/index.html`
and runs `cap sync`, which updates both `android/` and `ios/` with the
new web content and any native plugin changes. Then just rebuild in
Android Studio / Xcode as above.

## Before you publish

A few things are placeholders right now and worth deciding before a
real store submission:

- **App id** (`com.rcanavigator.app` in `capacitor.config.json`) — this
  becomes the permanent Android package name / iOS bundle identifier.
  It's straightforward to change now, much more disruptive to change
  after publishing (a new app id means a new store listing, not an
  update to the old one). Worth finalizing once the organization/brand
  name question is settled.
- **App icon** — done for Android. The Strata mark (navy cross-section
  bars, amber base) from the visual identity review is now the real
  launcher icon at every density, including the adaptive icon's
  foreground/background layers. Source artwork lives in
  `resources/icon-only.png`, `icon-foreground.png`, and
  `icon-background.png`; regenerate with
  `npx capacitor-assets generate --android --iconBackgroundColor '#ffffff'`
  if the mark ever changes. iOS icons aren't generated yet — that needs
  the same command with `--ios` once there's a Mac to build on.
- **Splash screen** — the web app already has its own animated splash
  (CSS-based, plays after the native shell loads). There's a separate
  *native* splash screen concept in Capacitor (shown instantly before
  the web view even starts loading, avoiding any blank-screen flash) —
  not set up yet, worth doing before a real store release so the very
  first frame isn't blank.
- **Offline/network behavior** — since the app now requires Supabase
  sign-in to do anything, worth testing specifically on a real device
  with the network toggled off, to see exactly what a user sees (the
  auth gate's "can't reach Supabase" message) versus what you'd want a
  polished native app to show.
