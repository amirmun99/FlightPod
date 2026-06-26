# Getting started (newbie quick-start)

This is the **linear** walkthrough. If you've never built a Raspberry Pi
project before and have never published an iOS app, follow this guide
top-to-bottom and you'll end up with a working FlightPaper.

The other docs in this folder go deeper on specific subsystems. This
one is just the happy path.

## What you're building

A tiny Raspberry Pi taped to a 2.13" ePaper display that shows nearby
aircraft. Your iPhone is the brain: it provides Wi-Fi (via Personal
Hotspot) and GPS, and runs a companion app that controls the Pi.

You'll do two builds in parallel — they don't depend on each other
until the very end, when you pair them.

```
Part A: The Pi             Part B: The iPhone app
──────────────             ──────────────────────
1. Buy parts               1. Install Xcode + Node
2. Flash SD card           2. Clone repo, install npm deps
3. Boot + SSH              3. Run in iOS Simulator
4. Run install.sh          4. Build a dev client for your iPhone
5. See QR on ePaper        5. Install on real iPhone
                                        │
                                        ▼
                         6. Scan QR. Done.
```

---

## Part A — The Pi (from an empty SD card)

### A1. Buy parts

Same list as the [hardware doc](hardware.md), but the minimum-viable set is:

- **Raspberry Pi Zero 2 W** (any reputable reseller)
- **microSD card, 16 GB+** (a brand-name Class 10)
- **PiSugar 3 1200 mAh** (the battery board)
- **Waveshare 2.13" ePaper HAT V2 / Rev2.1** (250×122 B/W version)
- **Micro-USB cable** (for first boot)
- **iPhone with hotspot**

Plug nothing in yet.

### A2. Flash the SD card

You'll install **Raspberry Pi OS Lite (64-bit, Bookworm)**. "Lite"
means no desktop, which is what you want.

1. On your Mac, install **Raspberry Pi Imager** from
   <https://www.raspberrypi.com/software/>.
2. Plug the microSD card into your Mac (you may need an SD adapter).
3. Open Raspberry Pi Imager. Click **Choose Device** → Raspberry Pi
   Zero 2 W. Click **Choose OS** → Raspberry Pi OS (other) →
   **Raspberry Pi OS Lite (64-bit)**. Click **Choose Storage** →
   your SD card.
4. Click **Next**, then **Edit Settings** (the magic step):
   - **General** tab:
     - Hostname: `flightpaper`
     - Enable SSH ✓
     - Username: `pi` (or whatever you want, but the rest of this
       guide assumes `pi`)
     - Password: a strong password you'll remember.
     - Configure wireless LAN: turn on your iPhone hotspot first,
       then enter the **exact** SSID and password.
     - Wireless LAN country: your country code (e.g. `US`).
     - Locale: your timezone.
   - **Services** tab:
     - Enable SSH ✓ → **Use password authentication**.
   - Save.
5. **Write**. Takes 5–10 minutes. Eject when it's done.

### A3. First boot

1. **Turn on your iPhone Personal Hotspot** (Settings → Personal
   Hotspot → on). Leave the Settings → Personal Hotspot screen open
   — iOS sometimes lets the hotspot go to sleep when you leave that
   screen.
2. Insert the SD card into the Pi.
3. Plug the **micro-USB power cable** into the Pi. The green LED
   blinks while it boots.
4. Wait 60 seconds. The Pi has to expand the filesystem on first
   boot.

### A4. SSH in

From your Mac terminal:

```bash
ssh pi@flightpaper.local
```

If that resolves, type the password you set in A2 → you're in.

If `.local` doesn't resolve (rare on Macs but common in some
networks), find the Pi's IP:

- On iOS 17+: Settings → Personal Hotspot → **Family Sharing /
  Connected Devices** (the exact name moves around).
- Or download a "Network Analyzer" app to scan the hotspot subnet.

Then ssh by IP: `ssh pi@<the IP>`.

### A5. Run the installer

You're now on the Pi.

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/your-fork/rpi-flightpod.git
cd rpi-flightpod
sudo apps/pi/install.sh
```

The installer takes 5–10 minutes. It installs Python deps, builds a
venv, enables SPI + I2C, creates the config directories, and starts
the systemd service.

When it finishes, watch the service come up:

```bash
sudo systemctl status flightpaper
sudo journalctl -u flightpaper -f          # Ctrl+C to leave
```

Within 10 seconds the ePaper should render a **boot** screen, then a
**pairing** screen with a QR code in the upper-left. **Don't scan
it yet** — we'll set up the phone first, then come back.

### A6. (Optional but recommended) Install PiSugar's battery server

The battery icon on the device works only if the official PiSugar
server is running. From the Pi:

```bash
curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
systemctl status pisugar-server
```

If you skip this, FlightPaper still works — the battery icon will
just show `BAT --`.

You can now disconnect the micro-USB cable; the Pi runs on the
PiSugar battery. The pairing QR stays on the ePaper until somebody
pairs.

---

## Part B — The iPhone app

You can do this in parallel with Part A. The two streams meet at A6
+ B5.

### B1. Install the prerequisites on your Mac

You need:

- **Xcode** (free in the Mac App Store). After installing, open it
  once to accept the license. This drops the iOS Simulator on your
  Mac.
- **Node.js LTS**. Easiest way: install [nvm](https://github.com/nvm-sh/nvm),
  then:
  ```bash
  nvm install 22
  nvm use 22
  ```
- **Watchman** (recommended for the Metro bundler): `brew install
  watchman`.
- An **Expo account** (free) at <https://expo.dev/signup>.

### B2. Clone the repo + install deps

```bash
git clone https://github.com/your-fork/rpi-flightpod.git
cd rpi-flightpod/apps/mobile
npm install
```

Confirm the build is healthy:

```bash
npm run typecheck                 # should print nothing then exit 0
node scripts/verify-crypto.cjs    # 8 passed, 0 failed
```

### B3. Run in the iOS Simulator (Expo Go)

This is the fastest way to see the app, but **background location
won't fire** because Expo Go is a sandbox.

```bash
npm run start:go
```

Metro starts. When the QR code shows up in the terminal, press `i` to
launch the iOS Simulator. The first launch downloads Expo Go into the
simulator (one-time, ~30 s).

Once the app opens you'll see the **Pair FlightPaper** screen. Tap
**Enter mock device mode** → **Enable**. The app jumps to the home
screen with canned data — exactly what'll appear once you pair a real
Pi. Play around: open Radar, Aircraft list, Settings (it'll let you
PATCH the mock config), Logs, About.

Disable mock mode when you're done (Security → Mock device → off) so
you can pair the real Pi later.

### B4. Build a dev client for your iPhone

The simulator is fine for UI work, but for the QR scanner +
background GPS + the actual pairing handshake you need the app on a
physical iPhone, built with **Expo Application Services (EAS)**.

```bash
cd apps/mobile
npx eas login                       # use the account from B1
npx eas init                        # links the project to EAS
npm run build:dev:ios               # eas build --profile development --platform ios
```

EAS will ask which signing identity to use:

- **Free Apple ID**: pick "free", let EAS generate the certificate.
  The resulting build expires in 7 days; you'll re-build weekly.
- **Paid Apple Developer Program** ($99/year): pick that account.
  No expiry, and background location is reliable.

The build runs in the cloud (~10–20 minutes the first time, faster
later). When it finishes, EAS prints a URL and shows a QR code in the
terminal.

### B5. Install on your real iPhone

1. On your iPhone, open the **Camera** app and point it at the QR in
   the terminal (or just tap the URL in iMessage if you texted it to
   yourself). Safari opens the EAS install page.
2. Tap **Install**. iOS asks you to confirm; agree.
3. The app installs as `FlightPaper (Dev)`.
4. Open **iOS Settings → General → VPN & Device Management** →
   trust your developer profile. (Free Apple ID only; paid accounts
   skip this.)
5. Open the app.

If you used a free Apple ID, mark your calendar: the build expires in
7 days. Re-run `npm run build:dev:ios` and reinstall.

---

## Part C — Pair them

You should now have:

- The Pi powered on, showing a QR on the ePaper. (A5–A6)
- The FlightPaper app installed on your iPhone. (B5)
- Your iPhone hotspot still on, and the Pi associated to it. (A3)

Do this:

1. Open the FlightPaper app on the iPhone.
2. Tap **Scan pairing QR**. iOS asks for camera permission → grant.
3. Point the camera at the ePaper QR.
4. The app says "Pairing with your FlightPaper…" for a second, then
   bounces to the Home screen.
5. The ePaper transitions from the pairing page to the boot/radar
   page. You're paired.

Now grant the GPS permissions so the device gets your location:

1. App → **Location**.
2. Tap **Allow While Using App** → grant.
3. Tap **Allow Always (background)** → grant.
4. Tap **Send Now** to send one fix. The Pi's ePaper should update
   within ~10 s with the aircraft around you.
5. Tap **Start Live GPS** to enable the background task. Lock the
   phone. As you move, the Pi keeps refreshing with new aircraft.

That's the whole setup. Watch [docs/iphone-background-location.md](iphone-background-location.md)
for the force-quit caveat and the free-Apple-ID expiry details.

---

## What's next

- **Customize.** Open the **Settings** screen. Change the radar
  radius, the units (km/nm, ft/m, kt/mph/kmh), and the polling
  interval. Tap Save — the Pi reloads the config immediately.
- **Try the other pages.** Settings → Display → Default page →
  `closest` or `list` or `status`. The ePaper switches.
- **Read the proper docs.** Once you're comfortable, the rest of
  this folder explains what's happening under the hood:
  [security](security.md), [pairing](pairing.md), [opensky](opensky.md),
  [display layouts](display-layouts.md), [iPhone background location](iphone-background-location.md).

## When it doesn't work

The most common newbie problems and the one-liner fixes:

| Symptom | Fix |
|---|---|
| `ssh: Could not resolve hostname flightpaper.local` | Use the iPhone's hotspot → Family Sharing screen to find the IP, ssh by IP instead. |
| `sudo apps/pi/install.sh` fails on `apt update` | The Pi can't reach the internet through the hotspot. Make sure the iPhone has cellular data and the hotspot is on with **Maximize Compatibility** enabled on iOS 14+. |
| ePaper stays blank after install | Wrong driver variant — see `display.driver` in [hardware.md](hardware.md). |
| App can't find the Pi | Verify the Pi is associated to the hotspot: ssh in and `hostname -I`. Compare to the IP in the QR. |
| Pair says `bad_envelope` | The QR was already used or expired. Wait for the ePaper to refresh, scan again. |
| GPS is greyed out | Tap "Allow Always (background)". If iOS won't show the dialog, the foreground permission isn't granted — fix that first. |
| App vanished from my phone after a week | Free Apple ID dev builds expire in 7 days. Re-run `npm run build:dev:ios`. |

Full troubleshooting at [`troubleshooting.md`](troubleshooting.md).
