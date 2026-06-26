/**
 * Phase 10 pure-logic verifier (no RN runtime required).
 *
 * Mirrors the small validators / reducers we ship so we can assert
 * behavior under bare Node 25 (jest + ts-jest hang on this host —
 * see Phase 8 notes). When the real source drifts, mirror the change
 * here.
 *
 * Coverage:
 *   - pairing-URI parser (happy + edge cases)
 *   - pairing-QR runtime validator
 *   - location queue cap (drop-oldest, max=20)
 *   - settings buildPatch (only changed keys, manual lat/lon guard)
 *   - settings validatePatch (range enforcement)
 *   - device store transitions: setDevice / clear / mockDevice toggle
 *   - log store append + cap
 *   - mock device patch applies in-range; out-of-range silently dropped
 */

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const decodeTable = new Int8Array(256).fill(-1);
for (let i = 0; i < ALPHABET.length; i++) decodeTable[ALPHABET.charCodeAt(i)] = i;

const b64uEncode = (data) => {
  let out = '';
  const len = data.length; let i = 0;
  for (; i + 3 <= len; i += 3) {
    const a = data[i], b = data[i + 1], c = data[i + 2];
    out += ALPHABET[a >> 2] + ALPHABET[((a & 3) << 4) | (b >> 4)] + ALPHABET[((b & 15) << 2) | (c >> 6)] + ALPHABET[c & 63];
  }
  if (i < len) {
    const a = data[i];
    if (i + 1 === len) out += ALPHABET[a >> 2] + ALPHABET[(a & 3) << 4];
    else { const b = data[i + 1]; out += ALPHABET[a >> 2] + ALPHABET[((a & 3) << 4) | (b >> 4)] + ALPHABET[(b & 15) << 2]; }
  }
  return out;
};

const assert = (cond, label) => {
  const tag = cond ? '  ok  ' : '  FAIL';
  console.log(`${tag} ${label}`);
  if (!cond) process.exitCode = 1;
};

// =====================================================================
// 1. Pairing URI parser (reproduces parsePairingUri)
// =====================================================================

const DEVICE_ID_RE = /^fp_[0-9a-f]{8}$/;
const B64U_43 = /^[A-Za-z0-9_-]{43}$/;

const isPairingQrPayload = (v) => {
  if (typeof v !== 'object' || v === null) return false;
  return (
    v.v === 1 &&
    typeof v.host === 'string' &&
    typeof v.port === 'number' &&
    typeof v.device_id === 'string' && DEVICE_ID_RE.test(v.device_id) &&
    typeof v.device_name === 'string' &&
    typeof v.device_pub === 'string' && B64U_43.test(v.device_pub) &&
    typeof v.pairing_secret === 'string' && B64U_43.test(v.pairing_secret) &&
    typeof v.expires_at === 'number'
  );
};

const parsePairingUri = (uri) => {
  try {
    if (!uri.startsWith('flightpaper://pair?')) return null;
    const url = new URL(uri.replace('flightpaper://pair', 'http://pair/'));
    const p = url.searchParams.get('p');
    if (!p) return null;
    const json = Buffer.from(b64uToBase64(p), 'base64').toString('utf-8');
    const decoded = JSON.parse(json);
    if (!isPairingQrPayload(decoded)) return null;
    return decoded;
  } catch {
    return null;
  }
};

const b64uToBase64 = (s) => s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4);

(() => {
  const payload = {
    v: 1,
    host: '172.20.10.4',
    port: 9077,
    device_id: 'fp_b89a3daa',
    device_name: 'FlightPaper',
    device_pub: 'A'.repeat(43),
    pairing_secret: 'B'.repeat(43),
    expires_at: 1_900_000_000,
  };
  const encoded = b64uEncode(Buffer.from(JSON.stringify(payload), 'utf-8'));
  const uri = `flightpaper://pair?p=${encoded}`;
  const parsed = parsePairingUri(uri);
  assert(parsed !== null, 'parsePairingUri: valid payload round-trips');
  assert(parsed?.device_id === payload.device_id, 'parsePairingUri: device_id matches');
  assert(parsePairingUri('not-a-uri') === null, 'parsePairingUri: rejects non-URI');
  assert(parsePairingUri('flightpaper://other?p=xx') === null, 'parsePairingUri: rejects wrong path');
  assert(parsePairingUri('flightpaper://pair?q=zz') === null, 'parsePairingUri: rejects missing p param');

  const bad = { ...payload, device_id: 'wrong_id' };
  const badEnc = b64uEncode(Buffer.from(JSON.stringify(bad), 'utf-8'));
  assert(parsePairingUri(`flightpaper://pair?p=${badEnc}`) === null, 'parsePairingUri: rejects bad device_id');
})();

// =====================================================================
// 2. Location queue cap + retry behavior (from locationStore)
// =====================================================================

const makeLocationStore = () => {
  let state = { lastFix: null, pendingQueue: [], backgroundTaskRegistered: false };
  return {
    enqueue: (payload, max = 20) => {
      const next = [...state.pendingQueue, payload];
      const trimmed = next.length > max ? next.slice(-max) : next;
      state = { ...state, pendingQueue: trimmed };
    },
    drain: () => {
      const q = state.pendingQueue;
      state = { ...state, pendingQueue: [] };
      return q;
    },
    get: () => state,
  };
};

(() => {
  const s = makeLocationStore();
  for (let i = 0; i < 25; i++) s.enqueue({ id: i });
  assert(s.get().pendingQueue.length === 20, 'locationStore: caps at 20');
  assert(s.get().pendingQueue[0].id === 5, 'locationStore: drops oldest');
  const drained = s.drain();
  assert(drained.length === 20, 'locationStore: drain returns all');
  assert(s.get().pendingQueue.length === 0, 'locationStore: drain empties queue');
})();

// =====================================================================
// 3. Settings buildPatch (from SettingsScreen)
// =====================================================================

const baseCfg = () => ({
  ui: { radius_km: 40, overhead_threshold_km: 3, distance_units: 'km', altitude_units: 'ft', speed_units: 'kt' },
  opensky: { update_interval_seconds: 30, battery_saver_interval_seconds: 120, max_aircraft_age_seconds: 90, include_ground_aircraft: false },
  display: { partial_refresh: true, full_refresh_every: 20, default_page: 'radar' },
  battery: { low_percent: 25, critical_percent: 10, battery_saver_below_percent: 30 },
  location: { manual: { enabled: false, lat: null, lon: null, label: '' } },
});

const buildPatch = (orig, draft) => {
  const patch = {};
  if (orig.ui.radius_km !== draft.ui.radius_km) patch.ui_radius_km = draft.ui.radius_km;
  if (orig.ui.overhead_threshold_km !== draft.ui.overhead_threshold_km) patch.ui_overhead_threshold_km = draft.ui.overhead_threshold_km;
  if (orig.ui.distance_units !== draft.ui.distance_units) patch.ui_distance_units = draft.ui.distance_units;
  if (orig.opensky.update_interval_seconds !== draft.opensky.update_interval_seconds) patch.opensky_update_interval_seconds = draft.opensky.update_interval_seconds;
  if (orig.opensky.include_ground_aircraft !== draft.opensky.include_ground_aircraft) patch.opensky_include_ground_aircraft = draft.opensky.include_ground_aircraft;
  if (orig.display.default_page !== draft.display.default_page) patch.display_default_page = draft.display.default_page;
  if (orig.battery.low_percent !== draft.battery.low_percent) patch.battery_low_percent = draft.battery.low_percent;
  if (orig.location.manual.enabled !== draft.location.manual.enabled) patch.location_manual_enabled = draft.location.manual.enabled;
  if (orig.location.manual.lat !== draft.location.manual.lat && draft.location.manual.lat !== null) patch.location_manual_lat = draft.location.manual.lat;
  if (orig.location.manual.label !== draft.location.manual.label) patch.location_manual_label = draft.location.manual.label;
  return patch;
};

const validatePatch = (patch) => {
  if (patch.ui_radius_km !== undefined && !(patch.ui_radius_km > 0 && patch.ui_radius_km <= 500)) return 'radius';
  if (patch.opensky_update_interval_seconds !== undefined && (patch.opensky_update_interval_seconds < 10 || patch.opensky_update_interval_seconds > 600)) return 'interval';
  if (patch.battery_low_percent !== undefined && (patch.battery_low_percent < 1 || patch.battery_low_percent > 99)) return 'battery';
  return null;
};

(() => {
  const orig = baseCfg();
  const draft = baseCfg();
  assert(Object.keys(buildPatch(orig, draft)).length === 0, 'buildPatch: identical → empty patch');

  draft.ui.radius_km = 80;
  draft.opensky.include_ground_aircraft = true;
  const patch = buildPatch(orig, draft);
  assert(patch.ui_radius_km === 80, 'buildPatch: radius diff included');
  assert(patch.opensky_include_ground_aircraft === true, 'buildPatch: boolean diff included');
  assert(Object.keys(patch).length === 2, 'buildPatch: only changed fields');

  const draft2 = baseCfg();
  draft2.location.manual.lat = null; // never sent even if "different"
  assert(buildPatch(orig, draft2).location_manual_lat === undefined, 'buildPatch: null lat not sent');

  assert(validatePatch({ ui_radius_km: 0 }) === 'radius', 'validatePatch: radius 0 rejected');
  assert(validatePatch({ ui_radius_km: 500 }) === null, 'validatePatch: radius 500 OK');
  assert(validatePatch({ ui_radius_km: 501 }) === 'radius', 'validatePatch: radius 501 rejected');
  assert(validatePatch({ opensky_update_interval_seconds: 9 }) === 'interval', 'validatePatch: interval 9 rejected');
  assert(validatePatch({ opensky_update_interval_seconds: 600 }) === null, 'validatePatch: interval 600 OK');
  assert(validatePatch({ battery_low_percent: 0 }) === 'battery', 'validatePatch: battery 0 rejected');
  assert(validatePatch({ battery_low_percent: 100 }) === 'battery', 'validatePatch: battery 100 rejected');
})();

// =====================================================================
// 4. Device store transitions (from deviceStore)
// =====================================================================

const makeDeviceStore = () => {
  let state = { device: null, mockDevice: false, lastStatus: null, lastStatusError: null };
  return {
    setDevice: (d) => { state = { ...state, device: d, lastStatusError: null }; },
    setMockDevice: (m) => { state = { ...state, mockDevice: m }; },
    clear: () => { state = { ...state, device: null, lastStatus: null, lastStatusError: null }; },
    get: () => state,
  };
};

(() => {
  const ds = makeDeviceStore();
  assert(ds.get().device === null, 'deviceStore: initial device is null');
  ds.setDevice({ deviceId: 'fp_abc12345' });
  assert(ds.get().device?.deviceId === 'fp_abc12345', 'deviceStore: setDevice persists');
  ds.setMockDevice(true);
  assert(ds.get().mockDevice === true, 'deviceStore: setMockDevice flips');
  ds.clear();
  assert(ds.get().device === null, 'deviceStore: clear drops device');
  assert(ds.get().mockDevice === true, 'deviceStore: clear preserves mockDevice flag');
})();

// =====================================================================
// 5. Log store cap (from logStore)
// =====================================================================

const makeLogStore = (max = 50) => {
  let entries = [];
  let nextId = 1;
  return {
    append: (level, msg, tag) => {
      entries = [{ id: nextId++, ts: Math.floor(Date.now() / 1000), level, message: msg, tag }, ...entries];
      if (entries.length > max) entries = entries.slice(0, max);
    },
    clear: () => { entries = []; },
    get: () => entries,
  };
};

(() => {
  const ls = makeLogStore(50);
  for (let i = 0; i < 60; i++) ls.append('warn', `msg-${i}`, 'api');
  assert(ls.get().length === 50, 'logStore: capped at 50');
  assert(ls.get()[0].message === 'msg-59', 'logStore: newest at index 0');
  ls.clear();
  assert(ls.get().length === 0, 'logStore: clear empties');
})();

// =====================================================================
// 6. Mock device patch path: out-of-range silently dropped
// =====================================================================

const applyMockPatch = (cfg, patch) => {
  const next = structuredClone(cfg);
  if (patch.ui_radius_km !== undefined && patch.ui_radius_km > 0 && patch.ui_radius_km <= 500) {
    next.ui.radius_km = patch.ui_radius_km;
  }
  if (patch.battery_low_percent !== undefined && patch.battery_low_percent >= 1 && patch.battery_low_percent <= 99) {
    next.battery.low_percent = patch.battery_low_percent;
  }
  return next;
};

(() => {
  const cfg = baseCfg();
  const ok = applyMockPatch(cfg, { ui_radius_km: 60 });
  assert(ok.ui.radius_km === 60, 'mockPatch: in-range applied');
  const dropped = applyMockPatch(cfg, { ui_radius_km: 0 });
  assert(dropped.ui.radius_km === cfg.ui.radius_km, 'mockPatch: out-of-range dropped');
  const battOk = applyMockPatch(cfg, { battery_low_percent: 99 });
  assert(battOk.battery.low_percent === 99, 'mockPatch: battery 99 applied');
  const battDrop = applyMockPatch(cfg, { battery_low_percent: 100 });
  assert(battDrop.battery.low_percent === cfg.battery.low_percent, 'mockPatch: battery 100 dropped');
})();

console.log(process.exitCode ? '\nFAILED' : '\nall checks passed');
