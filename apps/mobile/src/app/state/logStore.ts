/**
 * Tiny in-memory log buffer surfaced on the Logs screen.
 *
 * Holds the most recent ~50 connection-level events (HTTP errors,
 * pairing failures, queued sends). NO secrets, NO location, NO PII —
 * the spec is explicit about this on §35 and the README.
 */

import { create } from 'zustand';

import { nowTs } from '../../utils/time';

export type LogLevel = 'info' | 'warn' | 'error';

export interface LogEntry {
  id: number;
  ts: number;
  level: LogLevel;
  message: string;
  /** Tag like ``api`` / ``pair`` / ``location`` for visual grouping. */
  tag?: string;
}

const MAX_LOGS = 50;

interface LogState {
  entries: LogEntry[];
  append: (level: LogLevel, message: string, tag?: string) => void;
  clear: () => void;
}

let _nextId = 1;

export const useLogStore = create<LogState>((set) => ({
  entries: [],
  append: (level, message, tag) =>
    set((s) => {
      const entry: LogEntry = {
        id: _nextId++,
        ts: nowTs(),
        level,
        message,
        tag,
      };
      const next = [entry, ...s.entries];
      return { entries: next.length > MAX_LOGS ? next.slice(0, MAX_LOGS) : next };
    }),
  clear: () => set({ entries: [] }),
}));

/** Convenience to drop a log entry from non-React code. */
export const logEvent = (
  level: LogLevel,
  message: string,
  tag?: string,
): void => {
  useLogStore.getState().append(level, message, tag);
};
