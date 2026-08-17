'use client';

import React, { useState } from 'react';
import { Clapperboard, CheckCircle2, Loader2, XCircle, Circle, Play, Film } from 'lucide-react';
import { runPipeline } from '@/lib/api';
import { usePipelineStream, type AgentStatus } from '@/lib/hooks/usePipelineStream';
import { cn } from '@/lib/utils';

const AGENT_ORDER = [
  'scriptwriter',
  'art_director',
  'character_designer',
  'scene_designer',
  'storyboard_artist',
  'animator',
  'sound_director',
  'director',
];

const AGENT_LABELS: Record<string, string> = {
  scriptwriter: 'Scriptwriter',
  art_director: 'Art Director',
  character_designer: 'Character Designer',
  scene_designer: 'Scene Designer',
  storyboard_artist: 'Storyboard Artist',
  animator: 'Animator',
  sound_director: 'Sound Director',
  director: 'Director',
};

function AgentRow({ agent }: { agent?: AgentStatus }) {
  const status = agent?.status;
  return (
    <div className="flex items-center gap-2 py-1">
      {status === 'complete' ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />
      ) : status === 'working' ? (
        <Loader2 className="w-3.5 h-3.5 text-info animate-spin shrink-0" />
      ) : status === 'failed' ? (
        <XCircle className="w-3.5 h-3.5 text-danger shrink-0" />
      ) : (
        <Circle className="w-3.5 h-3.5 text-fg-muted shrink-0" />
      )}
      <span
        className={cn(
          'text-xs',
          status === 'working' && 'text-fg-primary font-medium',
          status === 'complete' && 'text-fg-secondary',
          status === 'failed' && 'text-danger',
          !status && 'text-fg-muted'
        )}
      >
        {agent ? AGENT_LABELS[agent.agent] || agent.agent : '—'}
      </span>
    </div>
  );
}

export function PipelinePanel() {
  const [idea, setIdea] = useState('');
  const [projectId, setProjectId] = useState('');
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const { state, subscribe } = usePipelineStream();

  const handleRun = async () => {
    if (!idea.trim()) return;
    setStarting(true);
    setStartError(null);
    try {
      const pid = projectId || `proj-${Date.now()}`;
      const res = await runPipeline({
        project_id: pid,
        idea: idea.trim(),
        wait: false,
      });
      setProjectId(res.project_id);
      // Subscribe to the SSE stream for live agent updates.
      subscribe(res.project_id);
    } catch (err) {
      setStartError((err as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const active = state.running || starting;

  return (
    <div className="p-4 space-y-4">
      <div>
        <label className="text-xs font-semibold text-fg-secondary flex items-center gap-1.5 mb-2">
          <Clapperboard className="w-3.5 h-3.5 text-accent-400" />
          Film Idea
        </label>
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          rows={3}
          disabled={active}
          className="w-full bg-bg-canvas border border-border-subtle rounded-md p-2.5 text-xs text-fg-primary focus:outline-none focus:border-accent-500 transition-colors resize-none placeholder:text-fg-muted disabled:opacity-60"
          placeholder="A robot finds a glowing blue flower on a dystopian planet…"
        />
      </div>

      <button
        onClick={handleRun}
        disabled={!idea.trim() || active}
        className="w-full py-2.5 px-4 rounded-md bg-gradient-to-r from-cyan-500 via-accent-500 to-fuchsia-600 hover:opacity-90 transition-opacity font-semibold text-xs text-white shadow-lg flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {starting ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Play className="w-4 h-4" />
        )}
        {starting ? 'Starting…' : 'Run 7-Agent Pipeline'}
      </button>

      {startError && (
        <div className="text-[11px] text-danger bg-danger/10 border border-danger/30 rounded-md p-2">
          {startError}
        </div>
      )}

      {/* Agent progress */}
      {(active || state.complete || state.failed) && (
        <div className="rounded-lg border border-border-subtle bg-bg-canvas p-3 space-y-0.5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-fg-secondary">Agent Team</span>
            {state.complete && (
              <span className="text-[10px] text-success font-medium">Complete</span>
            )}
            {state.failed && (
              <span className="text-[10px] text-danger font-medium">Failed</span>
            )}
          </div>
          {AGENT_ORDER.map((key) => (
            <AgentRow key={key} agent={state.agents[key]} />
          ))}
          {state.error && (
            <div className="mt-2 text-[11px] text-danger">{state.error}</div>
          )}
        </div>
      )}

      {/* Final film */}
      {state.complete && state.finalVideoUri && (
        <div className="rounded-lg border border-success/40 bg-success/5 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Film className="w-4 h-4 text-success" />
            <span className="text-xs font-semibold text-fg-primary">Final Film Ready</span>
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <video src={state.finalVideoUri} controls className="w-full rounded-md" />
        </div>
      )}

      {/* Generated artifacts preview */}
      {state.artifacts.filter((a) => a.uri && a.kind !== 'final_video').length > 0 && (
        <div>
          <span className="text-[11px] font-semibold text-fg-secondary">Artifacts</span>
          <div className="grid grid-cols-3 gap-1.5 mt-2">
            {state.artifacts
              .filter((a) => a.uri && (a.kind === 'character' || a.kind === 'scene' || a.kind === 'frame'))
              .map((a, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={i}
                  src={a.uri}
                  alt={a.name || a.kind}
                  className="aspect-square object-cover rounded-md border border-border-subtle"
                />
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
