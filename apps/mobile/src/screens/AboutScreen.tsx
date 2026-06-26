import { ScrollView, StyleSheet, Text } from 'react-native';

import { useTheme } from '../app/theme';

const DISCLAIMER = `FlightPaper is informational only.

Not for navigation, flight safety, emergency use, aircraft separation, or operational aviation decisions.

Aircraft data may be delayed, incomplete, inaccurate, or unavailable.`;

export default function AboutScreen() {
  const theme = useTheme();

  return (
    <ScrollView
      style={[styles.scroll, { backgroundColor: theme.colors.background }]}
      contentContainerStyle={[
        styles.content,
        {
          padding: theme.spacing.lg,
          gap: theme.spacing.md,
        },
      ]}
    >
      <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
        FlightPaper
      </Text>
      <Text style={[theme.typography.body, { color: theme.colors.textSecondary }]}>
        Version 0.1.0 (Phase 10)
      </Text>
      <Text
        style={[
          theme.typography.body,
          {
            color: theme.colors.textPrimary,
            marginTop: theme.spacing.lg,
            lineHeight: 22,
          },
        ]}
      >
        {DISCLAIMER}
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1 },
  content: {},
});
