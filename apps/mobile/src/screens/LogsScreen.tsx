/**
 * Live tail of the in-memory log buffer (see ``app/state/logStore``).
 *
 * Connection-level events only — pair failures, HTTP error codes,
 * location-send retries. NO secrets, NO location, NO PII.
 */

import {
  Button,
  FlatList,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useLogStore } from '../app/state';
import { useTheme } from '../app/theme';
import { Card } from '../components/ui';
import type { LogEntry, LogLevel } from '../app/state/logStore';

const toneFor = (level: LogLevel): string | null => {
  switch (level) {
    case 'error':
      return 'bad';
    case 'warn':
      return 'warn';
    default:
      return null;
  }
};

export default function LogsScreen() {
  const theme = useTheme();
  const entries = useLogStore((s) => s.entries);
  const clear = useLogStore((s) => s.clear);

  const renderItem = ({ item }: { item: LogEntry }) => {
    const tone = toneFor(item.level);
    const color =
      tone === 'bad'
        ? theme.colors.bad
        : tone === 'warn'
          ? theme.colors.warn
          : theme.colors.textSecondary;
    const ts = new Date(item.ts * 1000).toLocaleTimeString();
    return (
      <View
        style={[
          styles.row,
          { borderBottomColor: theme.colors.border, padding: theme.spacing.md, gap: 4 },
        ]}
      >
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
          <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
            {ts} {item.tag ? `· ${item.tag}` : ''}
          </Text>
          <Text style={[theme.typography.caption, { color, fontWeight: '700' }]}>
            {item.level.toUpperCase()}
          </Text>
        </View>
        <Text style={[theme.typography.callout, { color: theme.colors.textPrimary }]}>
          {item.message}
        </Text>
      </View>
    );
  };

  return (
    <SafeAreaView
      edges={['bottom']}
      style={[styles.root, { backgroundColor: theme.colors.background }]}
    >
      <View
        style={{
          paddingHorizontal: theme.spacing.lg,
          paddingTop: theme.spacing.md,
          paddingBottom: theme.spacing.sm,
          gap: theme.spacing.xs,
        }}
      >
        <Text style={[theme.typography.title, { color: theme.colors.textPrimary }]}>
          Logs
        </Text>
        <Text style={[theme.typography.callout, { color: theme.colors.textSecondary }]}>
          Most recent connection events (last 50). No location data, no secrets.
        </Text>
        <View style={{ flexDirection: 'row', justifyContent: 'flex-end' }}>
          <Button title="Clear" onPress={clear} disabled={entries.length === 0} />
        </View>
      </View>
      <FlatList
        data={entries}
        keyExtractor={(e) => String(e.id)}
        renderItem={renderItem}
        ListEmptyComponent={
          <View style={{ paddingHorizontal: theme.spacing.lg }}>
            <Card>
              <Text style={[theme.typography.callout, { color: theme.colors.textMuted, textAlign: 'center' }]}>
                No events yet.
              </Text>
            </Card>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  row: {
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
});
