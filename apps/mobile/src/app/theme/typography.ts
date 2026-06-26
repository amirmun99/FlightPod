/**
 * Typography presets. We don't ship a custom font; SF (iOS) and Roboto
 * (Android) are appropriate for a utility app.
 */

import type { TextStyle } from 'react-native';

export const fontSizes = {
  xs: 11,
  sm: 13,
  md: 15,
  lg: 17,
  xl: 20,
  xxl: 24,
  display: 32,
} as const;

export const fontWeights = {
  regular: '400',
  medium: '500',
  semibold: '600',
  bold: '700',
} as const satisfies Record<string, TextStyle['fontWeight']>;

export const typography = {
  display: {
    fontSize: fontSizes.display,
    fontWeight: fontWeights.bold,
    letterSpacing: -0.5,
  },
  title: {
    fontSize: fontSizes.xxl,
    fontWeight: fontWeights.semibold,
    letterSpacing: -0.3,
  },
  heading: {
    fontSize: fontSizes.xl,
    fontWeight: fontWeights.semibold,
  },
  body: {
    fontSize: fontSizes.md,
    fontWeight: fontWeights.regular,
  },
  bodyEmphasis: {
    fontSize: fontSizes.md,
    fontWeight: fontWeights.semibold,
  },
  callout: {
    fontSize: fontSizes.sm,
    fontWeight: fontWeights.regular,
  },
  caption: {
    fontSize: fontSizes.xs,
    fontWeight: fontWeights.regular,
    letterSpacing: 0.1,
  },
  mono: {
    fontFamily: 'Menlo',
    fontSize: fontSizes.sm,
  },
} as const satisfies Record<string, TextStyle>;
