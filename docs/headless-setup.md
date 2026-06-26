# Headless setup (reliable LAN / USB workflow)

This is the **linear** walkthrough for setting up FlightPaper *without*
fighting the iPhone hotspot. The original [getting-started](getting-started.md)
guide does everything over the hotspot — which is what the device uses in
the field, but it's a miserable way to *develop and debug*, because the
hotspot's LAN is flaky and hard to inspect.

The fix is to separate the two jobs the network does:

- **Setup + development** → your **home Wi-Fi** (or a USB cable). Rock
  solid, easy to inspect, your Mac and Pi are already on it.
- **Field use** → the **iPhone hotspot**. Only needed when you physically
  leave the house.

The key realization: the Pi needs the internet to fetch aircraft from
OpenSky. Your home Wi-Fi gives it that *and* lets your phone reach it on
the same LAN — so you can run the **entire system end-to-end at your
desk**, pairing and all, and never touch the hotspot until you go outside.

Follow this top-to-bottom.

```
Part A: The Pi                 Part B: The iPhone app
──────────────                 ──────────────────────
1. Flash for HOME Wi-Fi        1. Install Xcode + Node + CocoaPods
2. Boot + SSH over .local      2. Clone repo, install npm deps
3. Run install.sh              3. Run dev client in the Simulator
4. See QR on ePaper            4. Run dev client on your real iPhone
            │                              │
            └───────────────┬──────────────┘
                            ▼
            Part C: Pair them over your HOME LAN
                            │
                            ▼
            Part D: Add the hotspot for field use
```

There's also an **Appendix** for setting the Pi up over a plain USB
cable with no Wi-Fi at all — the most bulletproof option for a Pi Zero.

---

## Part A — The Pi, on your home Wi-Fi (from an empty SD card)

### A1. Buy parts

Same minimum set as the [hardware doc](hardware.md):

- **Raspberry Pi Zero 2 W**
- **microSD card, 16 GB+** (brand-name Class 10)
- **PiSugar 3 1200 mAh** battery board
- **Waveshare 2.13" ePaper HAT V2 / Rev2.1** (250×122 B/W)
- **Micro-USB cable**
- An iPhone (only needed at the very end, for field use)

Plug nothing in yet.

### A2. Flash the SD card — pointing at your HOME Wi-Fi

You'll install **Raspberry Pi OS Lite (64-bit, Bookworm)**. "Lite" = no
desktop, which is what you want for a headless device.

1. On your Mac, install **Raspberry Pi Imager** from
   <https://www.raspberrypi.com/software/>.
2. Plug the microSD card into your Mac (you may need an SD adapter).
3. Open Imager. **Choose Device** → Raspberry Pi Zero 2 W. **Choose OS**
   → Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)**.
   **Choose Storage** → your SD card.
4. Click **Next**, then **Edit Settings** (the important step):
   - **General** tab:
     - Hostname: `flightpaper`
     - Username: `pi` (the rest of this guide assumes `pi`)
     - Password: a strong password you'll remember.
     - Configure wireless LAN: enter your **home Wi-Fi** SSID and
       password — *not* the hotspot this time.
     - Wireless LAN country: your country code (e.g. `US`).
     - Locale: your timezone.
   - **Services** tab:
     - Enable SSH ✓ → **Use password authentication**.
   - Save.
5. **Write**. Takes 5–10 minutes. Eject when done.

### A3. First boot

1. Insert the SD card into the Pi.
2. Plug the **micro-USB power cable** into the Pi's **PWR** port (the one
   nearest the corner). The green LED blinks while it boots.
3. Wait ~60 seconds — the Pi expands its filesystem on first boot.

Because the Pi joined your home Wi-Fi, it's now on the **same network as
your Mac**. No hotspot juggling.

### A4. SSH in over your home LAN

From your Mac terminal:

```bash
ssh pi@flightpaper.local
```

Type the password from A2 → you're in. `flightpaper.local` works because
Raspberry Pi OS runs Avahi (mDNS) and macOS speaks Bonjour, so the name
resolves on your home LAN automatically.

(If `.local` doesn't resolve, see **When it doesn't work** at the bottom —
it's almost always a router setting, and there's a one-liner.)

### A5. Run the installer

You're on the Pi now, and it has real internet through your home router —
so `apt` and `git` just work:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/your-fork/rpi-flightpod.git
cd rpi-flightpod
sudo apps/pi/install.sh
```

The installer takes 5–10 minutes: Python deps, a venv, SPI + I2C enabled,
config directories, and the systemd service. Watch it come up:

```bash
sudo systemctl status flightpaper
sudo journalctl -u flightpaper -f          # Ctrl+C to leave
```

Within ~10 seconds the ePaper renders a **boot** screen, then a
**pairing** screen with a QR code. **Don't scan it yet** — set up the
phone first.

### A6. (Recommended) PiSugar battery server

The battery icon only works if PiSugar's own server is running:

```bash
curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
systemctl status pisugar-server
```

Skip it and FlightPaper still works — the battery icon just shows
`BAT --`.

Leave the Pi powered and on your home Wi-Fi. We'll come back in Part C.

---

## Part B — The iPhone app (from scratch)

You can do this in parallel with Part A.

### B1. Install the prerequisites on your Mac

- **Xcode** (free, Mac App Store). Open it once to accept the license —
  that installs the iOS Simulator and the iOS build toolchain.
- **Node.js 22 LTS.** Easiest via [nvm](https://github.com/nvm-sh/nvm):
  ```bash
  nvm install 22
  nvm use 22
  ```
  Use 22, not the newest. Newer Node has a known issue that hangs this
  project's test runner.
- **Watchman** (for the Metro bundler): `brew install watchman`.
- **CocoaPods** (the dev-client build installs native pods):
  `brew install cocoapods`.

### B2. Clone the repo + install deps

```bash
git clone https://github.com/your-fork/rpi-flightpod.git
cd rpi-flightpod/apps/mobile
npm install
```

Confirm the build is healthy:

```bash
npm run typecheck                 # prints nothing, exits 0
node scripts/verify-crypto.cjs    # 8 passed, 0 failed
```

### B3. Run the dev client in the iOS Simulator

This app uses native modules (camera, background location, crypto), so it
needs a **development build** — *not* Expo Go. The Simulator dev client is
the fastest way to see real behavior:

```bash
npx expo run:ios
```

The first run compiles the native app (a few minutes — Xcode is doing the
work) and installs it into the Simulator, then starts Metro. After that,
**JavaScript-only changes don't need a rebuild** — just `npm start` and
press `r` to reload. You only re-run `npx expo run:ios` when something
*native* changes (a native dependency, `app.config.ts`, permissions).

Once it boots you'll see the **Pair FlightPaper** screen. To explore
without a Pi: tap **Enter mock device mode** → **Enable**. The app jumps
to the home screen with canned data. Turn mock mode back off (Security →
Mock device → off) before pairing the real Pi.

### B4. Run the dev client on your real iPhone

The Simulator can't do the camera or real background GPS. For those you
need the app on a physical iPhone. Plug the iPhone into your Mac with a
cable, unlock it, and tap **Trust** when it asks.

```bash
npx expo run:ios --device
```

Pick your iPhone from the list. The first time, Xcode needs a signing
identity:

- **Free Apple ID**: open `apps/mobile/ios/` in Xcode once, select the
  project → **Signing & Capabilities** → pick your personal team, let
  Xcode auto-manage signing. Free-ID builds **expire after 7 days** — you
  re-run this command to reinstall.
- **Paid Apple Developer Program** ($99/yr): same flow, no expiry, and
  background location is more reliable.

After it installs, on the iPhone open **Settings → General → VPN & Device
Management** → trust your developer profile. (Free Apple ID only.)

Keep your iPhone on the **same home Wi-Fi as your Mac** so the dev client
can reach the Metro bundler.

---

## Part C — Pair them over your home LAN

This is the payoff: with the Pi, your Mac, and your iPhone all on the same
home Wi-Fi, you can pair and run the whole system **at your desk** — no
hotspot.

You should now have:

- The Pi powered on, on home Wi-Fi, showing a QR on the ePaper. (A5–A6)
- The FlightPaper dev client on your iPhone, on the same home Wi-Fi. (B4)

Do this:

1. Open FlightPaper on the iPhone.
2. Tap **Scan pairing QR** → grant camera permission.
3. Point the camera at the ePaper QR. The QR carries the Pi's home-LAN
   address, which your phone can reach directly.
4. The app says "Pairing with your FlightPaper…", then jumps to Home.
5. The ePaper switches from the pairing page to the radar/boot page —
   you're paired.

Now test location:

1. App → **Location** → **Allow While Using App**, then **Allow Always
   (background)**.
2. Tap **Send Now**. Within ~10 s the Pi's ePaper updates with the
   aircraft around the coordinates you sent.
3. Tap **Start Live GPS**, lock the phone, and confirm the Pi keeps
   refreshing.

If that all works on your home LAN, your build is correct. The only thing
left is making it work *away* from home.

---

## Part D — Add the iPhone hotspot for field use

In the field there's no home Wi-Fi, so the Pi rides the iPhone hotspot —
which gives it internet (via the phone's cellular, for OpenSky) *and*
keeps it reachable by the phone on the same little network.

You don't re-flash. You just teach the Pi a **second** Wi-Fi network.
Raspberry Pi OS Bookworm uses NetworkManager, so from an SSH session on
the Pi:

```bash
sudo nmcli connection add type wifi con-name hotspot ifname wlan0 \
  ssid "YOUR IPHONE HOTSPOT NAME"
sudo nmcli connection modify hotspot \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "your-hotspot-password" \
  connection.autoconnect yes \
  connection.autoconnect-priority 5
```

Use the **exact** hotspot SSID (it's usually your iPhone's name —
Settings → General → About → Name) and its Wi-Fi password (Settings →
Personal Hotspot).

Now the Pi knows both networks. NetworkManager auto-joins whichever is in
range:

- **At home** → home Wi-Fi (the `preconfigured` connection from the
  imager).
- **Out in the field** → the hotspot, once you turn it on.

Check what it's on right now:

```bash
nmcli device status          # which connection is active
iwgetid -r                   # current SSID
hostname -I                  # current IP
```

**Field checklist:** turn on Personal Hotspot (Settings → Personal
Hotspot, and *stay on that screen* — iOS sleeps the hotspot otherwise),
wait for the Pi to associate (`nmcli device status` shows `connected`),
and re-pair if the app shows the device as unreachable (the Pi's IP
changed networks, so the stored address moved).

That's the whole point of this guide: you proved everything works on a
reliable home LAN first, so if something breaks in the field you *know*
it's the hotspot, not your build.

---

## Appendix — Set up the Pi over USB, no Wi-Fi at all

The most bulletproof setup path for a Pi Zero 2 W: talk to it over a
single USB cable using **USB gadget (Ethernet-over-USB)** mode. Great when
Wi-Fi is being difficult or you're somewhere with a locked-down network.

### Enable gadget mode on the SD card

After flashing (A2) but before first boot, with the SD card still in your
Mac, open the **`bootfs`** partition (it mounts at `/Volumes/bootfs`):

1. In `config.txt`, add this line at the end:
   ```
   dtoverlay=dwc2
   ```
2. In `cmdline.txt` (one single long line — don't add newlines), insert
   this immediately after `rootwait`:
   ```
   modules-load=dwc2,g_ether
   ```

Eject the card and put it in the Pi.

### Connect

1. Plug the USB cable from your Mac into the Pi's **USB** port — the
   **middle** micro-USB, labelled USB/data, *not* PWR. This both powers
   the Pi and creates the data link.
2. Wait ~60 seconds. macOS detects a new Ethernet-style interface (a USB
   gadget). SSH straight in:
   ```bash
   ssh pi@flightpaper.local
   ```

### Give the Pi internet over the cable (so `apt`/`git` work)

The Pi has no Wi-Fi internet in this mode, so share your Mac's:

1. macOS **System Settings → General → Sharing → Internet Sharing**.
2. **Share your connection from**: your Mac's Wi-Fi.
3. **To computers using**: the USB gadget interface (often shown as
   "RNDIS/Ethernet Gadget" or similar).
4. Turn Internet Sharing on.

Now run the installer exactly as in **A5**. When you're done, you can move
the Pi to home Wi-Fi / the hotspot per Parts A–D; the gadget config stays
harmless and only activates over USB.

---

## When it doesn't work

| Symptom | Fix |
|---|---|
| `ssh: Could not resolve hostname flightpaper.local` | Your router may block mDNS. Find the Pi's IP from your router's device list (or a "Network Analyzer" app), then `ssh pi@<IP>`. |
| SSH connects but `apt update` fails | The Pi has Wi-Fi but no internet. Confirm your home router has internet and the Pi is on the right SSID: `iwgetid -r`. |
| App can't find the Pi on home Wi-Fi | Your router has **AP/client isolation** turned on (common on "Guest" networks). Move both devices to the main network, or disable isolation. |
| Paired at home, unreachable in the field | The Pi's IP changed when it moved to the hotspot. Re-scan the pairing QR (it carries the new address). |
| `nmcli` says hotspot stays `disconnected` in the field | iOS slept the hotspot. Re-open Settings → Personal Hotspot and keep that screen open; enable **Maximize Compatibility**. |
| `npx expo run:ios` fails on `pod install` | CocoaPods missing or stale: `brew install cocoapods`, then delete `apps/mobile/ios/Pods` and re-run. |
| Dev client opens but shows a red "could not connect to Metro" | The iPhone isn't on the same Wi-Fi as your Mac, or Metro isn't running. Same network + `npm start`. |
| App vanished from the iPhone after a week | Free Apple ID dev builds expire in 7 days. Re-run `npx expo run:ios --device`. |
| USB gadget: no `flightpaper.local` over the cable | You used the PWR port. Move the cable to the **middle USB/data** port. |

Full troubleshooting at [`troubleshooting.md`](troubleshooting.md); the
original hotspot-first path is in [`getting-started.md`](getting-started.md).
