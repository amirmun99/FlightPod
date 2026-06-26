/** Typed endpoint table mirroring ``apps/pi/flightpaper/api/routes_*.py``. */

export const ApiEndpoints = {
  publicHealth: { method: 'GET', path: '/api/public/health' },
  pairingStatus: { method: 'GET', path: '/api/public/pairing-status' },
  pair: { method: 'POST', path: '/api/public/pair' },

  location: { method: 'POST', path: '/api/secure/location' },
  status: { method: 'GET', path: '/api/secure/status' },
  aircraft: { method: 'GET', path: '/api/secure/aircraft' },
  getConfig: { method: 'GET', path: '/api/secure/config' },
  patchConfig: { method: 'PATCH', path: '/api/secure/config' },
  displayPage: { method: 'POST', path: '/api/secure/display/page' },
  refresh: { method: 'POST', path: '/api/secure/refresh' },
  shutdown: { method: 'POST', path: '/api/secure/system/shutdown' },
  reboot: { method: 'POST', path: '/api/secure/system/reboot' },
  resetPairing: { method: 'POST', path: '/api/secure/pairing/reset' },
} as const;

export type ApiEndpointKey = keyof typeof ApiEndpoints;
