/**
 * FlightPaper iPhone companion app entry point.
 *
 * Phase 8 wires:
 *   - ``react-native-get-random-values`` polyfill so ``crypto.getRandomValues``
 *     exists before any crypto code runs (must be imported first).
 *   - Safe-area provider, theme context, status bar.
 *   - Rehydrate the paired device from SecureStore on launch so we don't
 *     bounce the user back to the pair screen every time they reopen.
 *
 * Phase 9 attaches ``TaskManager.defineTask`` for the background
 * location task at module top level (via the
 * ``services/location/backgroundLocationTask`` import-side-effect) so
 * the OS can resume the task between launches.
 */

import 'react-native-get-random-values';
// Import-side-effect: registers the background location TaskManager
// task so iOS can resume the JS runtime for a fix without the app being
// in the foreground.
import './services/location/backgroundLocationTask';

import { useEffect, useState } from 'react';
import { View, useColorScheme } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import RootNavigator from './app/navigation/RootNavigator';
import { useDeviceStore } from './app/state';
import { ThemeContext, buildTheme } from './app/theme';
import { loadPairedDevice } from './services/storage/secureStore';

export default function App() {
  const systemScheme = useColorScheme();
  const mode = systemScheme === 'dark' ? 'dark' : 'light';
  const theme = buildTheme(mode);

  const setDevice = useDeviceStore((s) => s.setDevice);
  const [rehydrated, setRehydrated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const device = await loadPairedDevice();
        if (!cancelled && device) {
          setDevice(device);
        }
      } catch {
        // SecureStore can throw on a cold start; swallow so the user can
        // still pair fresh.
      } finally {
        if (!cancelled) setRehydrated(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setDevice]);

  return (
    <SafeAreaProvider>
      <ThemeContext.Provider value={theme}>
        <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
        {rehydrated ? (
          <RootNavigator />
        ) : (
          <View style={{ flex: 1, backgroundColor: theme.colors.background }} />
        )}
      </ThemeContext.Provider>
    </SafeAreaProvider>
  );
}
