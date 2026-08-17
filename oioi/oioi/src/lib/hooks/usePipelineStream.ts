'use client';

import { useCallback, useRef, useState } from 'react';
import { pipelineStreamUrl } from '@/lib/api';

export interface PipelineArtifact {
  agent: string;
  kind: string;
  uri?: string;
  name?: string;
  title?: string;
  scene?: number;
  shot?: number;
  duration_seconds?: number;
}

export interface AgentStatus {
  agent: string;
  status: 'queued' | 'working' | 'complete' | 'failed';
  error?: string;
}

export interface PipelineState {
  connected: boolean;
  running: boolean;
  complete: boolean;
  failed: boolean;
  error: string | null;
  agents: Record<string, AgentStatus>;
  artifacts: PipelineArtifact[];
  finalVideoUri: string | null;
}

const initialState: PipelineState = {
  connected: false,
  running: false,
  complete: false,
  failed: false,
  error: null,
  agents: {},
  artifacts: [],
  finalVideoUri: null,
};

/**
 * Hook that subscribes to a project's pipeline SSE stream and accumulates
 * agent status updates + generated artifacts in real time.
 */
export function usePipelineStream() {
  const [state, setState] = useState<PipelineState>(initialState);
  const abortRef = useRef<AbortController | null>(null);

  const subscribe = useCallback(async (projectId: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ ...initialState, running: true });

    try {
      const res = await fetch(pipelineStreamUrl(projectId), {
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`Pipeline stream failed: ${res.status}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split('\n\n');
        buffer = frames.pop() || '';
        for (const frame of frames) {
          const line = frame.trim();
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6);
          if (payload === '[DONE]') continue;
          try {
            const ev = JSON.parse(payload);
            applyEvent(ev);
          } catch {
            /* partial frame */
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setState((prev) => ({
          ...prev,
          running: false,
          failed: true,
          error: (err as Error).message || 'Stream failed',
        }));
      }
    }
  }, []);

  const applyEvent = (ev: Record<string, unknown>) => {
    const type = ev.type as string;
    setState((prev) => {
      switch (type) {
        case 'stream.connected':
          return { ...prev, connected: true };
        case 'pipeline.started':
          return { ...prev, running: true };
        case 'agent.status': {
          const agent = ev.agent as string;
          return {
            ...prev,
            agents: {
              ...prev.agents,
              [agent]: {
                agent,
                status: (ev.status as AgentStatus['status']) || 'working',
                error: ev.error as string | undefined,
              },
            },
          };
        }
        case 'agent.artifact':
          return {
            ...prev,
            artifacts: [
              ...prev.artifacts,
              {
                agent: ev.agent as string,
                kind: ev.kind as string,
                uri: ev.uri as string | undefined,
                name: ev.name as string | undefined,
                title: ev.title as string | undefined,
                scene: ev.scene as number | undefined,
                shot: ev.shot as number | undefined,
                duration_seconds: ev.duration_seconds as number | undefined,
              },
            ],
          };
        case 'agent.warning':
          return prev;
        case 'pipeline.complete':
          return {
            ...prev,
            running: false,
            complete: true,
            finalVideoUri: (ev.final_video_uri as string) || null,
          };
        case 'pipeline.failed':
          return {
            ...prev,
            running: false,
            failed: true,
            error: (ev.error as string) || 'Pipeline failed',
          };
        default:
          return prev;
      }
    });
  };

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => ({ ...prev, running: false }));
  }, []);

  const reset = useCallback(() => setState(initialState), []);

  return { state, subscribe, stop, reset };
}
