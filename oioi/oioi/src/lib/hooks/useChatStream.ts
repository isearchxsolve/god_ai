'use client';

import { useCallback, useRef, useState } from 'react';
import { chatStreamUrl } from '@/lib/api';

/**
 * Hook for SSE streaming chat. Streams real tokens from the backend
 * `/api/v1/chat/stream` endpoint with abort support.
 */
export function useChatStream() {
  const [content, setContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stream = useCallback(async (prompt: string, model?: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsStreaming(true);
    setError(null);
    setContent('');

    try {
      const res = await fetch(chatStreamUrl(prompt, model), {
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`Stream failed: ${res.status}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse complete SSE frames out of the buffer.
        const frames = buffer.split('\n\n');
        buffer = frames.pop() || '';
        for (const frame of frames) {
          const line = frame.trim();
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6);
          if (payload === '[DONE]') continue;
          try {
            const parsed = JSON.parse(payload);
            if (parsed.error) {
              setError(parsed.error);
            } else if (parsed.delta?.content) {
              setContent((prev) => prev + parsed.delta.content);
            }
          } catch {
            /* partial frame — ignore */
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError((err as Error).message || 'Stream failed');
      }
    } finally {
      setIsStreaming(false);
    }
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  const reset = useCallback(() => {
    setContent('');
    setError(null);
  }, []);

  return { content, isStreaming, error, stream, stop, reset };
}
