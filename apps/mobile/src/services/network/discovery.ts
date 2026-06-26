/**
 * Locate the paired Pi on the current network.
 *
 * MVP: the QR carries the IP, so discovery is a no-op. Later we may
 * add Bonjour / mDNS probing here.
 */

export const findPi = async (_lastKnownHost?: string): Promise<string | null> => {
  // Phase 8 may use the last known host from SecureStore. For now: caller
  // already has it from the QR.
  return _lastKnownHost ?? null;
};
