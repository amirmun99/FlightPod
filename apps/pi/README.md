# FlightPaper — Pi service

Python service that runs on a Raspberry Pi Zero 2 W under systemd. Talks
to OpenSky, drives the Waveshare 2.13" ePaper, reads the PiSugar 3, and
exposes a local API consumed by the iPhone companion app.

> See the **[root README](../../README.md)** for the system-level
> overview. This file is the Pi-specific install + dev + operate guide.

## Install

```bash
# Fresh Raspberry Pi OS Lite (Bookworm) over the iPhone hotspot:
sudo apt update && sudo apt install -y git
git clone https://github.com/your-fork/rpi-flightpod.git
cd rpi-flightpod
sudo apps/pi/install.sh
```

The installer is idempotent — re-running re-copies the package and
restarts the service, but preserves your device identity and paired
clients under `/etc/flightpaper/secure/`.

To uninstall:

```bash
sudo apps/pi/uninstall.sh          # leaves /etc/flightpaper alone
sudo apps/pi/uninstall.sh --purge  # also wipes secrets + config + logs
```

## OS Lite setup

1. Flash Raspberry Pi OS Lite (Bookworm 64-bit) with Raspberry Pi
   Imager.
2. Imager → **Edit settings**:
   - Set hostname: `flightpaper.local`.
   - Enable SSH (with a strong password).
   - Add your iPhone hotspot SSID + password.
   - Locale + timezone.
3. Boot, give it 60 s, then ssh in:
   ```bash
   ssh pi@flightpaper.local
   ```

## SPI + I2C

The installer enables both for you. If you ever need to enable
manually (e.g. they were turned off by an OS update):

```bash
sudo bash apps/pi/scripts/enable_interfaces.sh
sudo reboot
```

The script wraps `raspi-config nonint do_spi 0` + `do_i2c 0`.

## systemd

The unit file lives at
[`systemd/flightpaper.service`](systemd/flightpaper.service). The
installer drops it at `/etc/systemd/system/flightpaper.service`.

```bash
sudo systemctl status flightpaper
sudo systemctl restart flightpaper
sudo systemctl stop flightpaper
sudo journalctl -u flightpaper -f
```

The unit runs `python -m flightpaper.main` from
`/opt/flightpaper/.venv/bin/python`, with `WorkingDirectory=/opt/flightpaper`
and an optional `EnvironmentFile=-/etc/flightpaper/env` for secrets.

## Config file

`/etc/flightpaper/config.yml` mirrors
[`config.example.yml`](config.example.yml). It's seeded on first
install and left alone on subsequent installs. Edit + restart:

```bash
sudo nano /etc/flightpaper/config.yml
sudo systemctl restart flightpaper
```

The Pydantic model in
[`flightpaper/config.py`](flightpaper/config.py) is the source of truth
for shape + defaults; YAML keys must match. The companion app's Settings
screen patches the whitelisted subset (see
`ConfigPatchRequest` in
[`flightpaper/api/schemas.py`](flightpaper/api/schemas.py)).

## Display driver notes

Default is `display.driver = waveshare_2in13_rev2_1` (250×122, B/W).

If you have a different Waveshare 2.13" revision and the ePaper stays
blank, try one of the other registered variants in
[`flightpaper/display/waveshare_driver.py`](flightpaper/display/waveshare_driver.py).
Set `display.driver` in the config and restart.

Test rendering on macOS without hardware:

```bash
python scripts/render_preview.py --page radar --output /tmp/r.png
open /tmp/r.png

python scripts/render_preview.py --all --output-dir /tmp/preview/
```

Test on the device:

```bash
sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/test_display.py
```

## PiSugar notes

Install the official server (optional but recommended):

```bash
curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
systemctl status pisugar-server
```

`pisugar-server` listens on `127.0.0.1:8423`. FlightPaper talks to it
over that socket; if it's not running, the device shows `BAT --` and
keeps going.

Test the integration:

```bash
sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/test_battery.py
```

## Reset pairing

Three ways (see also [`docs/security.md`](../../docs/security.md)):

```bash
# 1. From a shell on the Pi:
sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/reset_pairing.py
sudo systemctl restart flightpaper

# 2. From any paired client:
POST /api/secure/pairing/reset    # via the companion app's Security screen

# 3. From the PiSugar button:
# Very-long press (~5 s) triggers a reset + reboot.
```

A new QR appears on the next ePaper refresh.

## Development on macOS

The package is import-safe on macOS: SPI, GPIO, and the PiSugar
interface are wrapped so they degrade to "unavailable" rather than
crashing. You can build and test most of the system on your laptop.

```bash
cd apps/pi
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest                # 315 tests, ~2 s

# Run the server against the OpenSky mock:
python scripts/mock_opensky_server.py &
uvicorn flightpaper.api.server:app --reload --port 9077
```

For full dev workflow see [`docs/development.md`](../../docs/development.md).

## Troubleshooting

Full table at [`docs/troubleshooting.md`](../../docs/troubleshooting.md).
Pi-side highlights:

- `systemctl status flightpaper` → see Active state + last log lines.
- `journalctl -u flightpaper -f` → live tail.
- `journalctl -u flightpaper -p err` → only errors.
- `ls /dev/spi*` → expect `/dev/spidev0.0`.
- `i2cdetect -y 1` → expect `0x57` if PiSugar is connected.
- `hostname -I` → confirm Pi has an IP on the hotspot LAN.
- `nmcli dev wifi list` → confirm hotspot is visible.

## Layout

```
apps/pi/
├── flightpaper/              ← the package
│   ├── api/                  ← FastAPI routes, secure envelope, auth, background tasks
│   ├── aircraft/             ← filtering, sorting, enrichment
│   ├── opensky/              ← REST client, parser, rate limiter, provider abstraction
│   ├── location/             ← LocationManager, providers, freshness states
│   ├── security/             ← PyNaCl wrappers, pairing state machine, key store, replay
│   ├── display/              ← Pillow renderer + Waveshare driver + QR builder
│   ├── ui/                   ← page state machine + button input
│   ├── hardware/             ← PiSugar 3, GPIO buttons, Wi-Fi, power
│   ├── utils/                ← geo, units, time, validators, cache
│   ├── config.py             ← Pydantic AppConfig + YAML loader
│   ├── logging_setup.py      ← rotating file + journald + redaction
│   └── main.py               ← uvicorn entry point
├── scripts/                  ← dev + ops tools (render_preview, reset_pairing, mocks)
├── systemd/flightpaper.service
├── tests/                    ← 315 pytest cases
├── config.example.yml        ← default config + every documented knob
├── install.sh  uninstall.sh
├── pyproject.toml  requirements.txt
└── README.md                 (this file)
```
