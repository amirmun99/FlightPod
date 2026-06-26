/**
 * Small visual primitives shared by Phase 10 screens. Just enough to
 * avoid repeating the same StyleSheet five times.
 */

import { ReactNode } from 'react';
import { StyleSheet, Text, View, ViewStyle } from 'react-native';

import { useTheme } from '../app/theme';

export function Card({
  children,
  style,
}: {
  children: ReactNode;
  style?: ViewStyle;
}) {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: theme.colors.surface,
          borderRadius: theme.radius.md,
          padding: theme.spacing.md,
          gap: theme.spacing.sm,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function CardTitle({ children }: { children: ReactNode }) {
  const theme = useTheme();
  return (
    <Text style={[theme.typography.bodyEmphasis, { color: theme.colors.textPrimary }]}>
      {children}
    </Text>
  );
}

export function KeyValue({
  label,
  value,
  valueColor,
  mono,
}: {
  label: string;
  value: string;
  valueColor?: string;
  mono?: boolean;
}) {
  const theme = useTheme();
  return (
    <View style={styles.kv}>
      <Text
        style={[theme.typography.callout, { color: theme.colors.textSecondary }]}
        numberOfLines={1}
      >
        {label}
      </Text>
      <Text
        style={[
          mono ? theme.typography.mono : theme.typography.bodyEmphasis,
          { color: valueColor ?? theme.colors.textPrimary },
        ]}
        numberOfLines={1}
      >
        {value}
      </Text>
    </View>
  );
}

export function StatusBadge({
  label,
  tone,
}: {
  label: string;
  tone: 'good' | 'warn' | 'bad' | 'muted';
}) {
  const theme = useTheme();
  const bg =
    tone === 'good'
      ? theme.colors.good
      : tone === 'warn'
        ? theme.colors.warn
        : tone === 'bad'
          ? theme.colors.bad
          : theme.colors.textMuted;
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[theme.typography.caption, { color: '#fff', fontWeight: '600' }]}>
        {label.toUpperCase()}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    shadowColor: 'rgba(0,0,0,0.04)',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 1,
    shadowRadius: 2,
  },
  kv: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: 8,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
    alignSelf: 'flex-start',
  },
});
