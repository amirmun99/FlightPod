/**
 * Phase 9 pure-logic verifier (no RN runtime needed).
 *
 * Reproduces the queue-trim, payload-sanitize, and newest-wins helpers
 * so we can assert their behavior with vanilla Node. The actual TS
 * sources rely on RN-targeted modules (zustand, expo-*) which won't
 * run under bare Node, but the logic itself is plain JS — mirror it
 * here byte-for-byte and trip an assertion if it ever drifts.
 *
 * If you tweak the real implementation, mirror the change here too —
 * `verify-crypto.cjs` is the precedent for this pattern.
 */

const MAX_RETRY_QUEUE = 20;

const enqueueTrim = (queue, payload, max = MAX_RETRY_QUEUE) => {
  const next = [...queue, payload];
  return next.length > max ? next.slice(-max) : next;
};

const cleanHeading = (h) =>
  h === null || !Number.isFinite(h) || h < 0 || h >= 360 ? null : h;
const cleanNonNegative = (v) =>
  v === null || !Number.isFinite(v) || v < 0 ? null : v;

const fixToPayload = (fix) => ({
  lat: fix.lat,
  lon: fix.lon,
  accuracy_m: cleanNonNegative(fix.accuracyM),
  altitude_m: fix.altitudeM,
  heading_deg: cleanHeading(fix.headingDeg),
  speed_mps: cleanNonNegative(fix.speedMps),
  source: fix.source,
  timestamp: fix.timestamp,
});

const newest = (batch) =>
  batch.reduce((acc, cur) => (cur.timestamp > acc.timestamp ? cur : acc));

const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const assert = (cond, label) => {
  const tag = cond ? '  ok  ' : '  FAIL';
  console.log(`${tag} ${label}`);
  if (!cond) process.exitCode = 1;
};

// ---- queue trim --------------------------------------------------------

(() => {
  let q = [];
  for (let i = 0; i < 25; i++) q = enqueueTrim(q, { id: i });
  assert(q.length === MAX_RETRY_QUEUE, 'queue trims to max (20)');
  assert(q[0].id === 5, 'queue keeps newest (first item id=5)');
  assert(q[q.length - 1].id === 24, 'queue keeps newest (last item id=24)');
})();

(() => {
  let q = [];
  q = enqueueTrim(q, { id: 'a' });
  q = enqueueTrim(q, { id: 'b' });
  assert(equal(q, [{ id: 'a' }, { id: 'b' }]), 'queue preserves order under cap');
})();

// ---- payload sanitization ---------------------------------------------

(() => {
  const sample = {
    lat: 37.7749,
    lon: -122.4194,
    accuracyM: 12.4,
    altitudeM: 5.0,
    headingDeg: 87.3,
    speedMps: 1.5,
    timestamp: 1_750_000_000,
    source: 'iphone_foreground',
  };
  const wire = fixToPayload(sample);
  assert(wire.lat === sample.lat, 'lat preserved');
  assert(wire.lon === sample.lon, 'lon preserved');
  assert(wire.accuracy_m === sample.accuracyM, 'accuracy preserved');
  assert(wire.heading_deg === sample.headingDeg, 'heading preserved');
  assert(wire.source === 'iphone_foreground', 'source preserved');
})();

(() => {
  const dirty = {
    lat: 0,
    lon: 0,
    accuracyM: -1,
    altitudeM: null,
    headingDeg: -1,
    speedMps: -1,
    timestamp: 1,
    source: 'iphone_background',
  };
  const wire = fixToPayload(dirty);
  assert(wire.accuracy_m === null, 'accuracy_m -1 → null');
  assert(wire.heading_deg === null, 'heading_deg -1 → null');
  assert(wire.speed_mps === null, 'speed_mps -1 → null');
})();

(() => {
  assert(cleanHeading(360) === null, 'heading 360 → null (must be < 360)');
  assert(cleanHeading(359.9999) === 359.9999, 'heading 359.9999 stays');
  assert(cleanHeading(0) === 0, 'heading 0 stays');
  assert(cleanHeading(NaN) === null, 'heading NaN → null');
})();

// ---- newest-wins (background batch coalescing) ------------------------

(() => {
  const batch = [
    { coords: {}, timestamp: 1000 },
    { coords: {}, timestamp: 4000 },
    { coords: {}, timestamp: 2000 },
  ];
  const top = newest(batch);
  assert(top.timestamp === 4000, 'newest() picks the freshest timestamp');
})();

console.log(process.exitCode ? '\nFAILED' : '\nall checks passed');
