/**
 * 4-pt grid. The keys are intentionally short — they appear in styles
 * everywhere and a 1-letter alias would be more confusing than helpful.
 */

export const spacing = {
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export type SpacingKey = keyof typeof spacing;

/** Minimum touch target. iOS HIG asks for 44x44 pt. */
export const minHitSlop = { top: 8, bottom: 8, left: 8, right: 8 } as const;

export const radius = {
  sm: 6,
  md: 10,
  lg: 14,
  pill: 999,
} as const;
