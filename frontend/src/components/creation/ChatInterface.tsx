import React, { useState, useEffect, useRef } from 'react';
// ChatInterface component for dual-mode UX shell - handles SSE streaming for agent status bubbles
import { View, Text, StyleSheet, FlatList, ActivityIndicator, ScrollView } from 'react-native';
import { useCreationSession } from '../../hooks/useCreationSession';
import { AgentStatus } from '../../types/agent';
import { formatTimeAgo } from '../../utils/formatters';
import { useTheme } from '../../hooks/useTheme';

// Agent status bubble component
const AgentStatusBubble: React.FC<{ agent: AgentStatus }> = ({ agent }) => {
  const { theme } = useTheme();
  return (
    <View style={[styles.agentBubble, { backgroundColor: theme.agentBubbleBg }]}>
      <View style={styles.agentHeader}>
        <Text style={[styles.agentName, { color: theme.primary }]}>{agent.name</Text>
        <Text style={styles.agentTime}>{formatTimeAgo(agent.lastUpdate)}</Text>
     </View>
      <View style={styles.agentContent}>
        {agent.isStreaming ? (
          <ActivityIndicator size="small" color={theme.primary} />
        ) : null}
        <Text style={[styles.agentMessage, { color: theme.text }]}>{agent.message</Text>
     </View>
   </View>
  );
};

// Main ChatInterface component - consumes SSE stream from /v1/chat/stream
export const ChatInterface: React.FC = () => {
  const { sessionId, mode, addAgentStatus } = useCreationSession();
  const { theme } = useTheme();
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const sseRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    const url = `/v1/chat/stream?session_id=${sessionId}`;
    const eventSource = new EventSource(url);
    sseRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'agent_status') {
          setAgents((prev) => {
            const idx = prev.findIndex((a) => a.id === data.agent.id);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = data.agent;
              return next;
            }
            return [...prev, data.agent];
          });
          addAgentStatus(data.agent);
        }
      } catch (err) {
        console.warn('Failed to parse SSE message:', err);
      }
    };

    eventSource.onopen = () => setIsStreaming(true);
    eventSource.onerror = () => setIsStreaming(false);

    return () => {
      eventSource.close();
      sseRef.current = null;
    };
  }, [sessionId, addAgentStatus]);

  return (
    <View style={[styles.container, { backgroundColor: theme.panelBg }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.text }]}>Chat</Text>
        {isStreaming ? (
          <Text style={[styles.streamingBadge, { color: theme.success }]}>Live</Text>
        ) : null}
     </View>
      <FlatList
        data={agents}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <AgentStatusBubble agent={item} />}
        contentContainerStyle={styles.list}
      />
   </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 12,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    paddingBottom: 8,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
  },
  streamingBadge: {
    fontSize: 12,
    fontWeight: '600',
  },
  list: {
    paddingBottom: 24,
  },
  agentBubble: {
    borderRadius: 12,
    padding: 12,
    marginVertical: 4,
    borderWidth: 1,
    borderColor: '#FFFFFF14',
  },
  agentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  agentName: {
    fontSize: 13,
    fontWeight: '600',
  },
  agentTime: {
    fontSize: 11,
    color: '#9CA3AF',
  },
  agentContent: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  agentMessage: {
    fontSize: 13,
    flex: 1,
    lineHeight: 18,
  },
});

export default ChatInterface;
