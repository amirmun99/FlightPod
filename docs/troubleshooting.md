# Troubleshooting

A grab-bag of the things that go wrong on a real Pi + iPhone setup
and what to do about them.

## ePaper

### Stays blank after install

Likely the wrong driver variant. The Waveshare 2.13" family has at
least four silicon revisions over the years.

```bash
sudo nano /etc/flightpaper/config.yml
# display:
#   driver: waveshare_2in13_rev2_1   # try rev2_2, v3, rev2 if blank

sudo systemctl restart flightpaper
journalctl -u flightpaper -n 100 --no-pager
```

The driver registry is in
[`apps/pi/flightpaper/display/waveshare_driver.py`](../apps/pi/flightpaper/display/waveshare_driver.py).

### Heavy ghosting / faint past frames

ePaper accumulates ghosting after many partial refreshes. Try:

```yaml
display:
  partial_refresh: false      # forces a full refresh every cycle
# or
  full_refresh_every: 5       # more frequent flushes
```

### Drifted alignment / wrong orientation

```yaml
display:
  rotation: 0    # try 90, 180, 270
```

## Battery / PiSugar

### `BAT --` on every page

`pisugar-server` isn't running. FlightPaper degrades gracefully — no
crash, but the battery glyph stays blank.

```bash
systemctl status pisugar-server
# Not installed? Install the official one-liner:
curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
```

### Battery saver kicks in at the wrong threshold

```yaml
battery:
  low_percent: 25
  critical_percent: 10
  battery_saver_below_percent: 30
```

Companion app → Settings → Battery thresholds.

## Network

### `NO WIFI`

The iPhone hotspot dropped or the SSID changed.

```bash
nmcli dev wifi list
nmcli connection show          # shows saved networks
sudo nmcli connection up "Your Hotspot SSID"
```

If the hotspot has Maximize Compatibility off, the Pi Zero 2 W's
2.4 GHz radio is fine. If iOS is forcing 5 GHz only, you have to flip
that toggle.

### `NO INTERNET`

Wi-Fi associated but no connectivity. Almost always the hotspot's
upstream data is off, or the iPhone has hit its cellular cap.
`hostname -I` showing an IP confirms Wi-Fi is up; `ping -c 2 1.1.1.1`
confirms internet.

## Pairing

### `PAIR REQUIRED` after a reboot

A previous reset wiped `paired_clients.json`. Open the iPhone app,
scan the QR. See [`pairing.md`](pairing.md).

### Phone says `bad_envelope` on first try

The QR was scanned while the Pi was rotating it. The fresh QR will be
on screen in a few seconds — re-scan.

### Phone says `attempt_limit`

Five bad pairs in a row. The Pi rotates the secret. Wait for the next
ePaper refresh and re-scan.

## Location

### `NO LOCATION` on the ePaper

Open the iPhone app → Location → ensure Always permission is granted,
then start Live GPS. The first fix arrives within ~30 s.

If the permission state shows `denied`, open iOS Settings →
FlightPaper → Location → switch to Always. Re-open the app — the
Location screen re-reads permissions on focus.

### `Live GPS` button is greyed out

The "Always" permission is required for background delivery. Tap
**Allow Always (background)** first. If iOS already denied it once,
use **Open iOS Settings**.

### Location stays stale after walking 100 m

Did you force-quit the app? iOS suspends background location for
force-quit apps permanently until reopen. Re-open the app once.

## OpenSky

### `API LIMITED`

OpenSky returned 429. We back off automatically. The page will return
to `OK` when the rate-limit clears (typically within a minute).

To raise your limit, configure auth (see [`opensky.md`](opensky.md)).

### `API ERROR`

OpenSky 5xx. We keep the last good batch until they recover.

## Logs

### Where to look

```bash
sudo journalctl -u flightpaper -f
sudo journalctl -u flightpaper -p err
tail -f /var/log/flightpaper/flightpaper.log     # rotated by the package
tail -f /var/log/flightpaper/flightpaper.err
```

### What's redacted

The logging filter in
[`apps/pi/flightpaper/logging_setup.py`](../apps/pi/flightpaper/logging_setup.py)
redacts known secret keys (`pairing_secret`, `session_key`,
`private_key`, `Authorization`). The iPhone app's in-app Logs screen
only stores connection-level events (HTTP code + error message). No
location, no callsign, no secret ever lands in either log.

## Useful commands

```bash
# Service
sudo systemctl status flightpaper
sudo systemctl restart flightpaper
sudo systemctl stop flightpaper

# Reset pairing without rebooting
sudo /opt/flightpaper/.venv/bin/python /opt/flightpaper/scripts/reset_pairing.py
sudo systemctl restart flightpaper

# Network
hostname -I
ping -c 2 1.1.1.1
nmcli dev wifi list

# SPI / I2C
ls /dev/spi*
i2cdetect -y 1

# Filesystem
df -h /
sudo du -sh /var/log/flightpaper
```

## Rebuild a clean install

```bash
sudo apps/pi/uninstall.sh --purge   # also drops /etc/flightpaper
sudo apps/pi/install.sh
```

This wipes the device identity too — pair a fresh QR on the next
boot.
