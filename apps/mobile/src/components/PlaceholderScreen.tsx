/**
 * Single placeholder used by every screen until the real
 * implementation lands in Phase 8-10. Renders the screen name + a
 * "filled in Phase N" hint.
 */

import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useTheme } from '../app/theme';

interface Props {
  title: string;
  phase?: string;
  notes?: string;
}

export default function PlaceholderScreen({ title, phase, notes }: Props) {
  const theme = useTheme();
  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.container, { backgroundColor: theme.colors.background }]}
    >
      <View style={styles.body}>
        <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
          {title}
        </Text>
        {phase ? (
          <Text
            style={[
              theme.typography.body,
              { color: theme.colors.textSecondary, marginTop: theme.spacing.sm },
            ]}
          >
            Filled in {phase}.
          </Text>
        ) : null}
        {notes ? (
          <Text
            style={[
              theme.typography.callout,
              { color: theme.colors.textMuted, marginTop: theme.spacing.md },
            ]}
          >
            {notes}
          </Text>
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  body: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 24,
  },
});
