/**
 * Top-level navigator. Switches between the unpaired stack (only the
 * Pairing screen) and the paired stack (Home + everything else).
 *
 * Switching by ``device !== null`` keeps the navigation tree small and
 * lets reauth (Reset Pairing) cleanly pop back to the QR scanner.
 */

import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { useDeviceStore } from '../state/deviceStore';
import { useTheme } from '../theme';
import AboutScreen from '../../screens/AboutScreen';
import AircraftListScreen from '../../screens/AircraftListScreen';
import DeviceHomeScreen from '../../screens/DeviceHomeScreen';
import DeviceStatusScreen from '../../screens/DeviceStatusScreen';
import LocationScreen from '../../screens/LocationScreen';
import LogsScreen from '../../screens/LogsScreen';
import PairingScreen from '../../screens/PairingScreen';
import RadarScreen from '../../screens/RadarScreen';
import SecurityScreen from '../../screens/SecurityScreen';
import SettingsScreen from '../../screens/SettingsScreen';
import WifiScreen from '../../screens/WifiScreen';

export type RootStackParamList = {
  // Unpaired
  Pairing: undefined;

  // Paired
  DeviceHome: undefined;
  Radar: undefined;
  AircraftList: undefined;
  Settings: undefined;
  Location: undefined;
  DeviceStatus: undefined;
  Security: undefined;
  Wifi: undefined;
  Logs: undefined;
  About: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function RootNavigator() {
  const device = useDeviceStore((s) => s.device);
  const mockDevice = useDeviceStore((s) => s.mockDevice);
  const theme = useTheme();

  const isPaired = device !== null || mockDevice;

  return (
    <NavigationContainer>
      <Stack.Navigator
        screenOptions={{
          headerLargeTitle: false,
          headerStyle: { backgroundColor: theme.colors.background },
          headerTintColor: theme.colors.textPrimary,
          contentStyle: { backgroundColor: theme.colors.background },
        }}
      >
        {!isPaired ? (
          <Stack.Screen
            name="Pairing"
            component={PairingScreen}
            options={{ title: 'Pair FlightPaper' }}
          />
        ) : (
          <>
            <Stack.Screen
              name="DeviceHome"
              component={DeviceHomeScreen}
              options={{ title: 'FlightPaper' }}
            />
            <Stack.Screen
              name="Radar"
              component={RadarScreen}
              options={{ title: 'Radar' }}
            />
            <Stack.Screen
              name="AircraftList"
              component={AircraftListScreen}
              options={{ title: 'Nearby Aircraft' }}
            />
            <Stack.Screen
              name="Settings"
              component={SettingsScreen}
              options={{ title: 'Settings' }}
            />
            <Stack.Screen
              name="Location"
              component={LocationScreen}
              options={{ title: 'Location' }}
            />
            <Stack.Screen
              name="DeviceStatus"
              component={DeviceStatusScreen}
              options={{ title: 'Device Status' }}
            />
            <Stack.Screen
              name="Security"
              component={SecurityScreen}
              options={{ title: 'Security' }}
            />
            <Stack.Screen
              name="Wifi"
              component={WifiScreen}
              options={{ title: 'Wi-Fi' }}
            />
            <Stack.Screen
              name="Logs"
              component={LogsScreen}
              options={{ title: 'Logs' }}
            />
            <Stack.Screen
              name="About"
              component={AboutScreen}
              options={{ title: 'About' }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
