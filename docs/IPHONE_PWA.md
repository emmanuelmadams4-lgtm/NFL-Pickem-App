# Putting Pick'em Intel on your iPhone (PWA)

> The steps below are written from Apple's and Tailscale's docs and have not been run on your phone yet (UNVERIFIED). Your first install is the test; tell me what you see.

The web app is also the iPhone app. You add it to your Home Screen from Safari. It opens full screen like a normal app, works offline, and can send alerts.

No App Store, no TestFlight, no $99 Apple account, nothing that expires.

## What you need

| Need | Why |
|---|---|
| iPhone on iOS 16.4 or newer | Alerts for Home Screen web apps start at 16.4 |
| The server reachable over **HTTPS** | Install, offline mode and alerts only work on HTTPS |
| Your access token | The app asks for it once |

## Step 1: give the server an HTTPS address (Tailscale, free, private)

1. Install Tailscale on the server computer and on your iPhone. Sign in to both with the same account.
2. In the Tailscale admin console, turn on **MagicDNS** and **HTTPS certificates**.
3. On the server: `tailscale serve --bg 8000`. It prints an address like `https://my-server.tail1234.ts.net`. If it says Serve is not enabled, open the link it prints and enable it. Do not use Funnel.

Full server setup, backups and token rotation are in `docs/DEPLOY.md`.

The server is never on the public internet. Only your devices can reach it.

(Other option: a small cloud server with HTTPS and the access token, about $5 to $12 a month.)

## Step 2: install on the iPhone

Install first, then sign in. The Home Screen app keeps its own storage, separate from Safari, so signing in inside Safari is not shared with it.

1. Open that `https://…ts.net` address in **Safari**. Do not sign in there.
2. Tap **Share** → **Add to Home Screen** → **Add**.
3. Open **Pick'em** from your Home Screen. From now on use this icon, not the Safari tab.
4. Paste your access token and sign in, inside the Home Screen app.

The app is tied to the server's address. If the server moves to a new computer, delete the icon and add it again from the new address.

## Step 3: turn on alerts (optional)

Server side, once:
```bash
docker compose exec app python -m nflpi.jobs vapid   # prints two keys
```
Put them in `.env` as `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY`, set `VAPID_SUBJECT=mailto:<your email>`, then `docker compose up -d`.

On the iPhone, inside the Home Screen app: **Settings → Alerts → On**, then allow notifications.

You get:
* Pick flipped, or a win chance moved 10+ points
* A QB in this week's games listed Out, Doubtful or Questionable
* "No pick yet" reminder before kickoff (choose 30 min, 1 hour or 3 hours in Settings)

Alerts come from your server through Apple's push service. Apple does not require a developer account for this.

## Offline

The app keeps the last data it loaded: the week board, every matchup you opened, your results. **Settings → Save this week for offline** downloads every matchup at once. When there's no signal, a banner says "Offline · showing data from 2h ago". Picks made offline wait and send when you're back online. Picks still lock at kickoff.

## Desktop

The same address works in any desktop browser. Chrome and Edge also offer "Install app" from the address bar.
