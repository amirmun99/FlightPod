import { registerRootComponent } from 'expo';

import App from './src/App';

// Registers FlightPaper as the root React component. Wrapping with
// `registerRootComponent` is what Expo's pre-built JS entry would do —
// we just do it ourselves so the entry point is the same file in dev
// (Expo Go), Metro builds, and EAS dev clients.
registerRootComponent(App);
