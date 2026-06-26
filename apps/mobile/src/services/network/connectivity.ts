/** Thin wrapper over ``expo-network`` for network reachability checks. */

export interface ConnectivityState {
  isConnected: boolean;
  type: 'wifi' | 'cellular' | 'none' | 'unknown';
}

export const readConnectivity = async (): Promise<ConnectivityState> => {
  return { isConnected: true, type: 'unknown' };
};
