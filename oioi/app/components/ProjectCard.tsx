import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

type Project = {
  name?: string;
  description?: string;
  status?: string;
};

type Props = {
  project: Project;
};

function getStatusColor(status?: string): string {
  if (!status) return '#94a3b8';
  const normalized = status.toLowerCase();
  if (normalized === 'active' || normalized === 'in progress') return '#38bdf8';
  if (normalized === 'completed' || normalized === 'done') return '#22c55e';
  if (normalized === 'paused' || normalized === 'on hold') return '#f59e0b';
  if (normalized === 'archived' || normalized === 'cancelled') return '#64748b';
  return '#94a3b8';
}

export default function ProjectCard({ project }: Props) {
  const { name, description, status } = project;
  const statusColor = getStatusColor(status);

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.name} numberOfLines={1}>
          {name ?? 'Untitled Project'}
        </Text>
        {status ? (
          <View style={[styles.statusBadge, { borderColor: statusColor }]}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusText, { color: statusColor }]}>
              {status}
            </Text>
          </View>
        ) : null}
      </View>

      {description ? (
        <Text style={styles.description} numberOfLines={3}>
          {description}
        </Text>
      ) : (
        <Text style={[styles.description, styles.placeholder]}>
          No description provided.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    marginVertical: 8,
    marginHorizontal: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  name: {
    flex: 1,
    fontSize: 18,
    fontWeight: '600',
    color: '#f1f5f9',
    marginRight: 8,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    backgroundColor: '#0f172a',
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  description: {
    fontSize: 14,
    color: '#cbd5e1',
    lineHeight: 20,
  },
  placeholder: {
    color: '#64748b',
    fontStyle: 'italic',
  },
});