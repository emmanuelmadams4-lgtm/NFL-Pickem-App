# Getting the app on your phone (no App Store, no Play Store)

## My pick

**iPhone:** join the Apple Developer Program ($99/year), then install with an **EAS internal (ad hoc) build**. It lasts about a year, push notifications work, and JavaScript fixes ship over the air with `eas update` without reinstalling.
**Android:** build an **APK** with EAS and install it directly. Free.

Use Expo Go only for a quick look before you pay for anything.

## iPhone options compared

| Option | Apple account | Mac needed | Push alerts | How long it lasts | Device limit | Best for |
|---|---|---|---|---|---|---|
| **Expo Go** (free app from the App Store) | None | No | No remote push (in-app/local only) | As long as Expo Go supports SDK 57 | n/a | First look today |
| **Free Apple ID + Xcode** ("Personal Team") | Free | Yes | No (push credentials need a paid account) | **7 days**, then rebuild | 3 devices, 3 apps per device | Not worth it |
| **EAS internal / ad hoc build** | **Paid, $99/yr** | No (EAS builds in the cloud) | Yes | Until the provisioning profile expires (about 1 year) | 100 iPhones per year | **Daily use (pick)** |
| **TestFlight** (internal testing) | **Paid, $99/yr** | No | Yes | **90 days per build**, then upload a new one | 100 internal testers | Fallback if ad hoc gives trouble |
| Enterprise program | $299/yr, organizations only | | | | | Not eligible / not needed |

Facts above come from Expo's docs ("This method requires a paid Apple Developer account ... at most 100 iPhones per year"; "remote push notifications ... are not [available in Expo Go]"; "A paid Apple Developer Account is required to generate [push] credentials"; TestFlight internal groups "up to 100 members") and Apple's TestFlight help (builds expire after 90 days; free accounts: profiles expire after 7 days, 3 devices).

## Step by step: iPhone (ad hoc)

One-time:

1. Enroll at developer.apple.com/programs ($99/yr). Approval can take a day or two.
2. Create a free Expo account at expo.dev.
3. On any computer: `npm i -g eas-cli`, then `eas login`.
4. In `apps/mobile`: `eas init` (links the project and writes its `projectId`).
5. Register your iPhone: `eas device:create` → open the link on the iPhone → install the profile it offers.
   New Apple memberships can take 24 to 72 hours to accept a new device.

Each build:

6. `eas build --platform ios --profile preview` (sign in with your Apple ID when asked; EAS makes the certificates).
7. Open the build link on your iPhone and install.
8. First launch: iOS may ask you to turn on **Developer Mode** (Settings → Privacy & Security → Developer Mode), then restart.

Code-only updates later: `eas update --branch preview` (no reinstall).

## Step by step: TestFlight (fallback)

1. Same Apple account as above.
2. `eas build --platform ios --profile production --auto-submit`
3. In App Store Connect → TestFlight, add yourself as an internal tester.
4. Install the TestFlight app on your iPhone and accept.
5. Rebuild at least every 90 days.

## Step by step: Android (no Play Store)

1. `eas build --platform android --profile preview` (the `preview` profile sets `buildType: apk`).
2. Open the link on the phone, download the APK, allow "install unknown apps" for your browser when asked.
3. Push on Android needs a free Firebase project for FCM V1 credentials: `eas credentials` → Android → upload the service account key. Without it, everything but remote push still works.

No Google account fee is needed. ($25 Play Console is only for Play Store publishing.)

## Making your phone reach your server

The app talks only to your own backend. API keys stay there.

| Way | Cost | Privacy | Pick |
|---|---|---|---|
| **Tailscale** on the server and the phone, plus `tailscale serve` for HTTPS | Free personal plan | Server is never on the public internet | **Yes** |
| Small cloud server + HTTPS + the app's access token | About $5 to $12/mo | Public URL, token-protected | If the home computer isn't always on |
| Same Wi-Fi, `http://<computer-ip>:8000` | Free | Private | Testing only |

Tailscale steps:
1. Install Tailscale on the server computer and on your phone; sign in to both with the same account.
2. In the Tailscale admin console, turn on MagicDNS and HTTPS certificates.
3. On the server: `tailscale serve --bg 8000`. It prints an address like `https://my-server.tail1234.ts.net`.
4. In the app: Settings → Server URL = that address, plus your access token. The token is kept in the phone's secure storage.

iPhones block plain `http://` to named servers, so use the HTTPS address from step 3.

## What works offline

The last loaded week board, every matchup you opened (or saved with "Download week"), your picks and your results. Each screen shows "Offline · updated 2h ago". Picks made offline are queued and sent when you're back online.
