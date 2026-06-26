/**
 * Multi-device index. v1 only supports one paired device but the schema is
 * forward-compatible so we can drop this in once needed.
 */

import type { PairedDevice } from '../../types';

export interface DeviceRegistry {
  list(): Promise<PairedDevice[]>;
  add(device: PairedDevice): Promise<void>;
  remove(deviceId: string): Promise<void>;
  current(): Promise<PairedDevice | null>;
  setCurrent(deviceId: string | null): Promise<void>;
}

export const createDeviceRegistry = (): DeviceRegistry => {
  const unimplemented = () => {
    throw new Error('DeviceRegistry not implemented yet (Phase 8)');
  };
  return {
    list: unimplemented as DeviceRegistry['list'],
    add: unimplemented as DeviceRegistry['add'],
    remove: unimplemented as DeviceRegistry['remove'],
    current: unimplemented as DeviceRegistry['current'],
    setCurrent: unimplemented as DeviceRegistry['setCurrent'],
  };
};
