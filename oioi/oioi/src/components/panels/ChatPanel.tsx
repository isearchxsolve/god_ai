'use client';

import React, { useState } from 'react';
import { MessageSquare, Send, Square, RotateCcw } from 'lucide-react';
import { useChatStream } from '@/lib/hooks/useChatStream';
import { cn } from '@/lib/utils';

export function ChatPanel() {
  const [prompt, setPrompt] = useState('');
  const { content, isStreaming, error, stream, stop, reset } = useChatStream();

  const handleSend = () => {
    if (!prompt.trim() || isStreaming) return;
    stream(prompt.trim());
  };

  return (
    <div className="p-4 space-y-3 flex flex-col h-full">
      <label className="text-xs font-semibold text-fg-secondary flex items-center gap-1.5">
        <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
        Director Chat (SSE streaming)
      </label>

      <div
        aria-live="polite"
        className="flex-1 min-h-[120px] max-h-64 overflow-y-auto rounded-md bg-bg-canvas border border-border-subtle p-3 text-xs text-fg-primary whitespace-pre-wrap"
      >
        {content ? (
          content
        ) : isStreaming ? (
          <span className="text-fg-muted">Streaming…</span>
        ) : (
          <span className="text-fg-muted">
            Ask the director anything about your animation.
          </span>
        )}
        {isStreaming && <span className="inline-block w-1.5 h-3 bg-accent-400 ml-0.5 animate-pulse align-middle" />}
      </div>

      {error && (
        <div className="text-[11px] text-danger bg-danger/10 border border-danger/30 rounded-md p-2">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          rows={2}
          className="flex-1 bg-bg-canvas border border-border-subtle rounded-md p-2 text-xs text-fg-primary focus:outline-none focus:border-accent-500 resize-none placeholder:text-fg-muted"
          placeholder="Message the director…"
        />
      </div>

      <div className="flex gap-2">
        {isStreaming ? (
          <button
            onClick={stop}
            className="flex-1 py-2 rounded-md bg-danger/20 border border-danger/40 text-danger text-xs font-semibold flex items-center justify-center gap-1.5 hover:bg-danger/30 transition-colors"
          >
            <Square className="w-3.5 h-3.5" /> Stop
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!prompt.trim()}
            className="flex-1 py-2 rounded-md bg-accent-500 hover:bg-accent-600 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40"
          >
            <Send className="w-3.5 h-3.5" /> Send
          </button>
        )}
        <button
          onClick={() => {
            reset();
            setPrompt('');
          }}
          className="px-3 py-2 rounded-md bg-bg-elevated border border-border-subtle text-fg-secondary hover:border-border-strong transition-colors"
          aria-label="Reset chat"
          title="Reset"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
