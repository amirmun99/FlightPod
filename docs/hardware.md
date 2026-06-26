# Hardware

This document is the build sheet plus first-boot guide. Read it once
before you order parts and again before you assemble.

## Bill of materials

| Item | Notes |
|---|---|
| Raspberry Pi Zero 2 W | Wi-Fi + USB. Buy from a reputable reseller. |
| microSD card (16 GB+) | Class 10 minimum; brand-name. Flash with Raspberry Pi OS Lite (Bookworm 64-bit). |
| PiSugar 3 1200 mAh | Battery board with charge circuit, power button, RTC, soft-shutdown. |
| Waveshare 2.13" ePaper HAT V2 / Rev2.1 | 250×122, B/W, SPI. The driver registry in `flightpaper/display/` defaults to this variant. |
| Micro-USB cable | For first boot + charging. |
| iPhone | With hotspot capability. The companion app is iOS-only for the MVP. |

Optional but useful:

| Item | Notes |
|---|---|
| Header pin extender | If your case stack is taller than the default Pi headers. |
| 3D-printed case | Plenty of community designs for Pi Zero + 2.13" HAT. |

## Assembly order

1. **PiSugar 3 → Pi Zero 2 W.** Magnet the battery board to the back of
   the Pi. Connect the pogo-pin lead so the PiSugar can read battery
   state and trigger soft-shutdown.
2. **Pi → ePaper HAT.** The Waveshare HAT seats on the 40-pin header.
   Press straight down, no rocking; the ePaper ribbon is fragile.
3. **microSD card.** Flash *before* assembly. Use Raspberry Pi Imager,
   enable SSH, enable Wi-Fi for your iPhone hotspot, set a hostname
   (`flightpaper.local` is a good default), and set a strong password.
4. **Power-on test.** Plug in micro-USB; the green LED blinks while the
   Pi boots. The first boot expands the filesystem and can take a
   minute.

## Enable SPI + I2C

The Waveshare HAT needs SPI; the PiSugar 3 status server uses I2C
under the hood (we talk to it over a local TCP socket, but the kernel
modules need to be loaded). Enable both:

```bash
sudo bash apps/pi/scripts/enable_interfaces.sh
sudo reboot
```

(The full installer also runs this.)

Quick checks after the reboot:

```bash
ls /dev/spi*       # expect /dev/spidev0.0
i2cdetect -y 1     # expect addresses, including 0x57 if PiSugar 3 present
```

## Install the PiSugar power-manager (optional but recommended)

```bash
curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
systemctl status pisugar-server
```

The official `pisugar-server` listens on `127.0.0.1:8423`. FlightPaper
talks to it over that socket — see
[`apps/pi/flightpaper/hardware/pisugar3.py`](../apps/pi/flightpaper/hardware/pisugar3.py).
If `pisugar-server` is not running, FlightPaper degrades gracefully and
shows `BAT --` on the status bar; nothing else breaks.

## First boot

1. Bring up the iPhone hotspot. Confirm the SSID + password matches
   what you put in Raspberry Pi Imager.
2. Power on the Pi. SSH in over the hotspot:
   ```bash
   ssh pi@flightpaper.local
   ```
   If `.local` fails, find the Pi via your hotspot's connected-devices
   list or a Network Analyzer app on the phone.
3. Clone the repo and run the installer:
   ```bash
   git clone https://github.com/your-fork/rpi-flightpod.git
   cd rpi-flightpod
   sudo apps/pi/install.sh
   ```
4. Watch the service come up:
   ```bash
   sudo systemctl status flightpaper
   sudo journalctl -u flightpaper -f
   ```
5. The ePaper should render the pairing page within ~10 seconds (boot
   page first, then pair).
6. Open the iPhone app, scan the QR. See [`docs/pairing.md`](pairing.md).

## Choosing the ePaper variant

The Waveshare 2.13" family has several silicon revisions over the
years. Default is `waveshare_2in13_rev2_1` (250×122, B/W).

```yaml
# /etc/flightpaper/config.yml
display:
  driver: waveshare_2in13_rev2_1
  width: 250
  height: 122
  rotation: 0          # 0 | 90 | 180 | 270
```

The driver registry is import-guarded so the Pi package runs on macOS
for development. If you have a different revision, add an entry under
`apps/pi/flightpaper/display/waveshare_driver.py` and point
`display.driver` at it.

Visual symptoms vs. likely cause:

| Symptom | Likely cause |
|---|---|
| ePaper stays blank after first boot | Wrong driver variant — try `rev2_2` or earlier. |
| Heavy ghosting (faint past frames) | Set `display.partial_refresh: false`. |
| Drifted alignment | `display.rotation` wrong for the case orientation. |
