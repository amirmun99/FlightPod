/**
 * FlightPaper colors. Neutral, system-feel, both modes supported. Aim is
 * legibility over expressiveness — operators glance at this app between
 * looking at the sky.
 */

export type ThemeMode = 'light' | 'dark';

export const palette = {
  // Brand
  ink: '#0F1115',
  paper: '#F7F7F4', // ePaper-ish off-white
  accent: '#2D7DD2',
  accentMuted: '#1F4E79',

  // Status
  good: '#2E933C',
  warn: '#D08B22',
  bad: '#C0392B',

  // Greys
  grey900: '#1A1D22',
  grey800: '#2B2F36',
  grey700: '#3F454D',
  grey500: '#7E848B',
  grey300: '#C7CACD',
  grey200: '#E4E6E8',
  grey100: '#F1F2F3',
  white: '#FFFFFF',
  black: '#000000',
};

export interface ColorScheme {
  background: string;
  surface: string;
  surfaceElevated: string;
  border: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  accent: string;
  good: string;
  warn: string;
  bad: string;
  destructive: string;
}

export const lightColors: ColorScheme = {
  background: palette.paper,
  surface: palette.white,
  surfaceElevated: palette.grey100,
  border: palette.grey200,
  textPrimary: palette.ink,
  textSecondary: palette.grey700,
  textMuted: palette.grey500,
  accent: palette.accent,
  good: palette.good,
  warn: palette.warn,
  bad: palette.bad,
  destructive: palette.bad,
};

export const darkColors: ColorScheme = {
  background: palette.ink,
  surface: palette.grey900,
  surfaceElevated: palette.grey800,
  border: palette.grey700,
  textPrimary: palette.white,
  textSecondary: palette.grey300,
  textMuted: palette.grey500,
  accent: palette.accent,
  good: palette.good,
  warn: palette.warn,
  bad: palette.bad,
  destructive: palette.bad,
};

export const colorsFor = (mode: ThemeMode): ColorScheme =>
  mode === 'dark' ? darkColors : lightColors;
