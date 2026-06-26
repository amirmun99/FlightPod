/**
 * Phone-side monotonic sequence counter.
 *
 * The persistent slot is owned by ``services/storage/secureStore.ts``
 * (so it survives app restarts). This file is the thin wrapper the
 * device client uses to claim the next ``seq`` for an outgoing
 * envelope.
 */

import { claimNextSeqOut } from '../storage/secureStore';

export const nextSeq = async (): Promise<number> => claimNextSeqOut();
