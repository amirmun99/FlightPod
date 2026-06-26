/**
 * Types for paired-device identity + the status response from the Pi.
 *
 * The wire shape lives in ``packages/protocol/api-contract.md``. When the
 * protocol bumps version we update these in lockstep with
 * ``apps/pi/flightpaper/api/schemas.py``.
 */

export type PairedDevice = {
  deviceId: string; // matches ``fp_[0-9a-f]{8}``
  name: string;
  host: string;
  port: number;
  clientId: string; // matches ``iphone_[0-9a-f]{12}``
  protocolVersion: number;
  pairedAt: number; // unix seconds
  lastSeenAt?: number;
};

export type PairingState = 'unpaired' | 'pairing_pending' | 'paired';

export type PiHealth = {
  ok: boolean;
  device_id: string;
  version: string;
  uptime_seconds: number;
};

export type PiPairingStatus = {
  state: PairingState;
  device_id: string;
  device_name: string;
  pairing_expires_at?: number | null;
  protocol_version: number;
};

export type StatusResponse = {
  device: {
    id: string;
    name: string;
    version: string;
    uptime_seconds: number;
  };
  network: {
    wifi_ssid: string | null;
    ip_address: string;
    internet_ok: boolean;
  };
  battery: {
    percent: number | null;
    charging: boolean | null;
    external_power: boolean | null;
    battery_saver: boolean;
  };
  location: {
    source: string | null;
    age_seconds: number | null;
    accuracy_m: number | null;
    fresh: boolean;
    state: 'none' | 'fresh' | 'stale' | 'expired';
  };
  opensky: {
    status: string;
    last_update_age_seconds: number | null;
    aircraft_count: number;
    rate_limit_remaining: number | null;
  };
  display: {
    page: string;
    last_refresh_age_seconds: number | null;
  };
};
