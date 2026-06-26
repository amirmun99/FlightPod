/**
 * Expo configuration for the FlightPaper iPhone companion app.
 *
 * Why `.ts` instead of `.json`:
 *  - Background location and local-network access need exact Info.plist
 *    strings (spec §9). Keeping them in TypeScript means we can run typed
 *    checks on plist edits without inventing a custom schema.
 *  - The bundle id and host overrides are easy to swap per build profile.
 */

import type { ExpoConfig } from 'expo/config';

const BUNDLE_IDENTIFIER = 'com.flightpaper.companion'; // placeholder — rename before EAS submit
const TASK_NAME = 'flightpaper-background-location';

const config: ExpoConfig = {
  name: 'FlightPaper',
  slug: 'flightpaper-mobile',
  scheme: 'flightpaper',
  version: '0.1.0',
  orientation: 'portrait',
  userInterfaceStyle: 'automatic',
  icon: './assets/icon.png',
  splash: {
    image: './assets/splash.png',
    resizeMode: 'contain',
    backgroundColor: '#0F1115',
  },
  assetBundlePatterns: ['**/*'],
  jsEngine: 'hermes',

  ios: {
    bundleIdentifier: BUNDLE_IDENTIFIER,
    supportsTablet: false,
    buildNumber: '1',

    // ---- Info.plist (spec §9) -------------------------------------------
    infoPlist: {
      // Location permissions.
      NSLocationWhenInUseUsageDescription:
        'FlightPaper uses your location while open to send your position to your paired FlightPaper device, which displays nearby aircraft around you.',
      NSLocationAlwaysAndWhenInUseUsageDescription:
        'FlightPaper sends your location to your paired FlightPaper device in the background while Live GPS is on, so the device can keep showing nearby aircraft when the app is not in the foreground.',
      NSLocationAlwaysUsageDescription:
        'FlightPaper sends your location to your paired FlightPaper device in the background while Live GPS is on.',

      // Camera (QR scanner during pairing).
      NSCameraUsageDescription:
        'FlightPaper uses the camera to scan the pairing QR code shown on your FlightPaper device.',

      // Local network access — FlightPaper talks to the Pi on the iPhone hotspot.
      NSLocalNetworkUsageDescription:
        'FlightPaper needs to talk to your paired FlightPaper device over your local Wi-Fi or iPhone hotspot.',

      // The Pi exposes plain HTTP under application-layer encryption.
      NSAppTransportSecurity: {
        NSAllowsLocalNetworking: true,
      },

      // Background modes: location is required for background GPS delivery.
      UIBackgroundModes: ['location'],

      // Make sure Hermes / RN aren't blocked from local IPv4 hosts.
      ITSAppUsesNonExemptEncryption: false,
    },

    // EAS profiles can override entitlements / capabilities if needed.
    config: {
      usesNonExemptEncryption: false,
    },
  },

  android: {
    package: BUNDLE_IDENTIFIER,
    adaptiveIcon: {
      foregroundImage: './assets/icon.png',
      backgroundColor: '#0F1115',
    },
    permissions: [
      'ACCESS_FINE_LOCATION',
      'ACCESS_COARSE_LOCATION',
      'ACCESS_BACKGROUND_LOCATION',
      'CAMERA',
      'INTERNET',
      'ACCESS_NETWORK_STATE',
    ],
  },

  // ---- Plugins ----------------------------------------------------------
  plugins: [
    [
      'expo-location',
      {
        locationAlwaysAndWhenInUsePermission:
          'FlightPaper sends your location to your paired FlightPaper device in the background while Live GPS is on.',
        isIosBackgroundLocationEnabled: true,
        isAndroidBackgroundLocationEnabled: true,
      },
    ],
    [
      'expo-camera',
      {
        cameraPermission:
          'FlightPaper uses the camera to scan the pairing QR code shown on your FlightPaper device.',
      },
    ],
  ],

  extra: {
    // Exposed to runtime via `Constants.expoConfig?.extra`. Override per
    // EAS profile (eas.json) for staging vs. production.
    backgroundTaskName: TASK_NAME,
    eas: {
      projectId: undefined, // populated after `eas init`
    },
  },

  experiments: {
    typedRoutes: false,
  },
};

export default config;
