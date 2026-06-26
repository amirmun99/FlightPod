/**
 * Theme entry point. A tiny React context exposes the active palette so
 * components can react to light / dark switches without prop drilling.
 */

import { createContext, useContext } from 'react';

import { ColorScheme, ThemeMode, colorsFor, lightColors } from './colors';
import { minHitSlop, radius, spacing } from './spacing';
import { typography } from './typography';

export interface Theme {
  mode: ThemeMode;
  colors: ColorScheme;
  spacing: typeof spacing;
  radius: typeof radius;
  minHitSlop: typeof minHitSlop;
  typography: typeof typography;
}

export const buildTheme = (mode: ThemeMode): Theme => ({
  mode,
  colors: colorsFor(mode),
  spacing,
  radius,
  minHitSlop,
  typography,
});

const defaultTheme: Theme = buildTheme('light');
defaultTheme.colors = lightColors;

export const ThemeContext = createContext<Theme>(defaultTheme);

export const useTheme = (): Theme => useContext(ThemeContext);

export * from './colors';
export * from './spacing';
export * from './typography';
