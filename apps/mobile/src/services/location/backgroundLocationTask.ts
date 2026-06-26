/**
 * Background-location task definition + start/stop helpers.
 *
 * The task is registered with :mod:`expo-task-manager` at module-import
 * time so iOS can resume the app in the background when a location
 * update arrives. :func:`startBackgroundLocation` then hands the task
 * name to :func:`Location.startLocationUpdatesAsync` with the spec §8
 * cadence (background 30–60 s / 25–100 m).
 *
 * Each delivered batch from the OS is a list of :type:`LocationObject`.
 * We pick the *newest* fix in the batch (CL can deliver coalesced
 * updates) and hand it to :func:`sendLocationToPi`. The sender owns
 * the queue, so the task body stays small and won't block CL's
 * execution budget.
 */

import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';

import { sendLocationToPi, flushLocationQueue } from './locationSender';
import { toLocationFix } from './foregroundLocation';
import { useLocationStore } from '../../app/state/locationStore';
import type { LocationFix } from '../../types';

export const BACKGROUND_TASK_NAME = 'flightpaper-background-location';

const BACKGROUND_DISTANCE_INTERVAL_METERS = 50;
const BACKGROUND_TIME_INTERVAL_MS = 45_000;

interface LocationTaskPayload {
  locations: Location.LocationObject[];
}

const handleBackgroundUpdate = async (locations: Location.LocationObject[]): Promise<void> => {
  if (locations.length === 0) return;
  // Pick the freshest fix in the batch — CL coalesces while the app is
  // suspended, so older entries can be way out of date by the time the
  // task fires.
  const newest = locations.reduce((acc, cur) =>
    cur.timestamp > acc.timestamp ? cur : acc,
  );
  const fix: LocationFix = toLocationFix(newest, 'iphone_background');
  await sendLocationToPi(fix);
  // Opportunistic flush — if a previous run queued, drain while we
  // already have a network window.
  await flushLocationQueue();
};

// Register the task at module-import time. The Expo guidance is clear:
// this MUST be top-level so the OS can resume the JS runtime and find
// the handler.
if (!TaskManager.isTaskDefined(BACKGROUND_TASK_NAME)) {
  TaskManager.defineTask<LocationTaskPayload>(
    BACKGROUND_TASK_NAME,
    ({ data, error }) => {
      if (error) {
        // Surface but don't throw — CL won't see the rejection anyway.
        // eslint-disable-next-line no-console
        console.warn('[flightpaper bg-location] task error', error);
        return;
      }
      if (!data || !Array.isArray(data.locations)) return;
      // CL invokes us synchronously, but our send is async. We
      // intentionally don't await — CL gives us a short budget and a
      // hung promise would kill future deliveries.
      void handleBackgroundUpdate(data.locations);
    },
  );
}

export const isBackgroundLocationRunning = async (): Promise<boolean> => {
  try {
    return await Location.hasStartedLocationUpdatesAsync(BACKGROUND_TASK_NAME);
  } catch {
    return false;
  }
};

export const startBackgroundLocation = async (): Promise<void> => {
  const already = await isBackgroundLocationRunning();
  if (already) return;
  await Location.startLocationUpdatesAsync(BACKGROUND_TASK_NAME, {
    accuracy: Location.Accuracy.Balanced,
    activityType: Location.ActivityType.Other,
    distanceInterval: BACKGROUND_DISTANCE_INTERVAL_METERS,
    timeInterval: BACKGROUND_TIME_INTERVAL_MS,
    showsBackgroundLocationIndicator: false,
    pausesUpdatesAutomatically: false,
    foregroundService: {
      notificationTitle: 'FlightPaper Live GPS',
      notificationBody: 'Sending your location to your FlightPaper.',
      killServiceOnDestroy: true,
    },
  });
  useLocationStore.getState().setBackgroundTaskRegistered(true);
};

export const stopBackgroundLocation = async (): Promise<void> => {
  const running = await isBackgroundLocationRunning();
  if (running) {
    await Location.stopLocationUpdatesAsync(BACKGROUND_TASK_NAME);
  }
  useLocationStore.getState().setBackgroundTaskRegistered(false);
};
