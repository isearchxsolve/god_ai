# 📱 Screen Guard — Anti-Screenshot & Anti-Recording Android Protection
# Keep Your Content Private. Keep Your Screens Secure.

> **A production-ready Android app that prevents screenshots, screen recording, and screen mirroring.**
> Built for privacy-conscious users, enterprise security, and content creators who need to protect sensitive information.

---

## ⚡ What This Is

Screen Guard is a **complete Android application** with native-level screen protection. It prevents:
- ✅ Screenshots (system + app-level)
- ✅ Screen recording (internal + external apps)
- ✅ Screen mirroring (Chromecast, Miracast, etc.)
- ✅ Screencasting (via USB or wireless)

**Built for:**
- Privacy-conscious users (banking, messaging, personal photos)
- Enterprise security (confidential documents, trade secrets)
- Content creators (preventing piracy of premium content)
- Parents (controlling what kids can capture)
- Healthcare (HIPAA-sensitive information on mobile)

---

## 📦 What You Get

### Source Code
```
screen-guard-android/
├── app/
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/screenguard/
│   │   │   │   ├── MainActivity.kt          # Main activity with protection
│   │   │   │   ├── ScreenGuardService.kt      # Background protection service
│   │   │   │   ├── ScreenProtection.kt         # Core protection logic
│   │   │   │   └── SettingsActivity.kt          # User settings
│   │   │   ├── res/
│   │   │   │   ├── layout/                    # UI layouts
│   │   │   │   ├── drawable/                   # Icons and graphics
│   │   │   │   └── values/                     # Strings, colors, themes
│   │   │   └── AndroidManifest.xml             # App manifest
│   │   └── test/                               # Unit tests
│   ├── build.gradle.kts                        # Build configuration
│   └── proguard-rules.pro                      # ProGuard obfuscation rules
└── docs/
    ├── BUILD_GUIDE.md                          # Step-by-step build instructions
    ├── INSTALL_GUIDE.md                        # Sideload or Play Store install
    ├── CUSTOMIZATION.md                        # How to rebrand and customize
    └── PLAY_STORE_GUIDE.md                     # Publishing checklist
```

### Documentation
- `README.md` — This file (overview + quick start)
- `BUILD_GUIDE.md` — How to build the APK from source
- `INSTALL_GUIDE.md` — Sideload or Google Play Store installation
- `CUSTOMIZATION.md` — Rebrand, change colors, modify protection settings
- `PLAY_STORE_GUIDE.md` — Step-by-step publishing checklist
- `PRIVACY_POLICY.md` — Required for Google Play submission

---

## 🚀 Quick Start

### Option 1: Build from Source (15 minutes)

```bash
# Clone or unzip the source
cd screen-guard-android

# Open in Android Studio
# File → Open → Select project folder

# Build APK
# Build → Build Bundle(s) / APK(s) → Build APK(s)

# Install on device
# Connect phone via USB → Run → Run 'app'
```

### Option 2: Sideload Pre-built APK (2 minutes)

```bash
# Enable developer options on your Android device
# Settings → About Phone → Tap "Build Number" 7 times

# Enable USB debugging
# Settings → System → Developer Options → USB Debugging

# Install APK
adb install app/build/outputs/apk/debug/app-debug.apk
```

### Option 3: Google Play Store

See `PLAY_STORE_GUIDE.md` for publishing to Google Play.

---

## 🛠️ Build Requirements

- **Android Studio** Arctic Fox or newer
- **Kotlin** 1.5+ (included in Android Studio)
- **Minimum SDK:** Android 6.0 (API 23)
- **Target SDK:** Android 13+ (API 33+)
- **Gradle:** 7.0+ (included)

---

## 🎨 Customization

### Rebrand (5 minutes)

Edit `app/src/main/res/values/strings.xml`:
```xml
<string name="app_name">Your App Name</string>
<string name="app_description">Your description</string>
```

Replace `app/src/main/res/drawable/app_icon.png` with your own icon (512x512).

### Change Colors (2 minutes)

Edit `app/src/main/res/values/colors.xml`:
```xml
<color name="primary">#YOUR_COLOR</color>
<color name="accent">#YOUR_COLOR</color>
<color name="background">#YOUR_COLOR</color>
```

### Modify Protection Settings (3 minutes)

Edit `ScreenProtection.kt`:
```kotlin
// Enable/disable specific protections
const val PREVENT_SCREENSHOTS = true
const val PREVENT_SCREEN_RECORDING = true
const val PREVENT_MIRRORING = true
const val SHOW_OVERLAY_WARNING = true
```

---

## 📋 Features

| Feature | Description | Security Level |
|---------|-------------|---------------|
| **FLAG_SECURE** | Android system-level screenshot prevention | Basic |
| **Window Protection** | Blocks screen recording apps from capturing window | Intermediate |
| **Media Projection Block** | Prevents system-level screen recording APIs | Advanced |
| **Overlay Warning** | Shows visible warning when screen recording is detected | User Awareness |
| **Mirroring Detection** | Detects and blocks Chromecast/Miracast connections | Advanced |
| **Background Service** | Protection persists even when app is in background | Persistent |
| **Customizable UI** | Change colors, icons, text to match your brand | Customization |

---

## 🛡️ Security Architecture

Screen Guard uses **multiple layers of protection**:

1. **Android FLAG_SECURE** — System-level flag that prevents screenshots and screen recording for the app's window
2. **WindowManager Protection** — Blocks `MediaProjection` API access for the app
3. **Background Service** — Monitors for screen recording attempts even when app is minimized
4. **Overlay Detection** — Detects when screen recording overlays are active and shows warning
5. **Mirroring Detection** — Checks for active casting connections and blocks them

---

## 📱 Google Play Store Publishing

See `PLAY_STORE_GUIDE.md` for the complete publishing checklist including:
- Google Play Console setup
- App signing requirements
- Screenshot and video requirements
- Content rating questionnaire
- Privacy policy requirements
- Launch checklist

---

## ⚠️ Limitations

- **Rooted devices** can bypass FLAG_SECURE using Xposed modules
- **External cameras** pointed at the screen cannot be prevented
- **Accessibility services** with screen recording permissions may bypass protection
- **Kernel-level** screen capture (very rare) cannot be blocked from user space

**Recommendation:** Screen Guard is designed for **honest users who want privacy**, not for high-security environments against determined attackers.

---

## 📝 License

Single-user license. See `LICENSE.md` for full terms.

---

**Built for:** Privacy users, content creators, enterprise security, parents  
**Stack:** Kotlin, Android SDK, Android Studio  
**Version:** 1.0  
**Min SDK:** Android 6.0 (API 23)  
**Target SDK:** Android 13+ (API 33+)