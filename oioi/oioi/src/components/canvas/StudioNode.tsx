'use client';

import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import {
  Image as ImageIcon,
  Video,
  MessageSquare,
  User,
  Mountain,
  Clapperboard,
  RefreshCw,
  Trash2,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StudioNode, StudioNodeData, NodeKind } from '@/lib/stores/canvas-store';

const KIND_META: Record<NodeKind, { icon: React.ElementType; accent: string; label: string }> = {
  prompt: { icon: Clapperboard, accent: 'text-accent-400', label: 'Prompt' },
  image: { icon: ImageIcon, accent: 'text-cyan-400', label: 'Image' },
  video: { icon: Video, accent: 'text-indigo-400', label: 'Video' },
  chat: { icon: MessageSquare, accent: 'text-emerald-400', label: 'Chat' },
  character: { icon: User, accent: 'text-fuchsia-400', label: 'Character' },
  scene: { icon: Mountain, accent: 'text-amber-400', label: 'Scene' },
  pipeline: { icon: Clapperboard, accent: 'text-accent-400', label: 'Pipeline' },
};

const STATUS_DOT: Record<string, string> = {
  idle: 'bg-fg-muted',
  queued: 'bg-warning',
  generating: 'bg-info animate-pulse',
  ready: 'bg-success',
  error: 'bg-danger',
};

interface Props extends NodeProps<StudioNode> {}

function StudioNodeInner({ data, selected, id }: Props) {
  const meta = KIND_META[data.kind] || KIND_META.prompt;
  const Icon = meta.icon;
  const isBusy = data.status === 'generating' || data.status === 'queued';
  // Action handlers are injected into node data by InfiniteCanvas (React Flow
  // only forwards `data`/`selected` to custom node components).
  const onRegenerate = data.onRegenerate as ((id: string) => void) | undefined;
  const onDelete = data.onDelete as ((id: string) => void) | undefined;

  return (
    <div
      className={cn(
        'w-60 rounded-lg border bg-bg-surface shadow-elevated transition-all',
        selected
          ? 'border-accent-500 shadow-glow'
          : 'border-border-subtle hover:border-border-strong',
        data.status === 'error' && 'border-danger'
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-accent-500 !w-2.5 !h-2.5" />
      <Handle type="source" position={Position.Right} className="!bg-accent-500 !w-2.5 !h-2.5" />

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-subtle">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className={cn('w-3.5 h-3.5 shrink-0', meta.accent)} />
          <span className="text-[11px] font-mono text-fg-secondary truncate">{data.label}</span>
        </div>
        <span
          className={cn('w-2 h-2 rounded-full shrink-0', STATUS_DOT[data.status])}
          title={data.status}
        />
      </div>

      {/* Body */}
      <div className="p-2">
        {data.kind === 'image' || data.kind === 'character' || data.kind === 'scene' ? (
          <div className="aspect-video rounded-md overflow-hidden bg-bg-canvas">
            {isBusy ? (
              <div className="w-full h-full shimmer" />
            ) : data.imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={data.imageUrl} alt={data.label} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-fg-muted">
                <ImageIcon className="w-6 h-6" />
              </div>
            )}
          </div>
        ) : data.kind === 'video' ? (
          <div className="aspect-video rounded-md overflow-hidden bg-bg-canvas">
            {isBusy ? (
              <div className="w-full h-full shimmer" />
            ) : data.videoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <video src={data.videoUrl} controls className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-fg-muted">
                <Video className="w-6 h-6" />
              </div>
            )}
          </div>
        ) : data.kind === 'chat' ? (
          <div className="min-h-[60px] max-h-32 overflow-y-auto rounded-md bg-bg-canvas p-2 text-xs text-fg-secondary whitespace-pre-wrap">
            {isBusy ? <div className="h-4 w-3/4 shimmer rounded" /> : data.chatText || 'No response yet.'}
          </div>
        ) : (
          <div className="min-h-[48px] rounded-md bg-bg-canvas p-2 text-xs text-fg-secondary">
            {data.prompt ? (
              <span className="line-clamp-3">{data.prompt}</span>
            ) : (
              <span className="text-fg-muted">Empty prompt</span>
            )}
          </div>
        )}

        {data.error && (
          <div className="mt-2 flex items-start gap-1.5 text-[11px] text-danger">
            <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
            <span className="line-clamp-2">{data.error}</span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-border-subtle">
        <span className="text-[10px] text-fg-muted truncate max-w-[120px]">
          {data.model || data.provider || '—'}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onRegenerate?.(id)}
            disabled={isBusy}
            className="p-1 rounded hover:bg-bg-elevated text-fg-secondary disabled:opacity-40"
            aria-label="Regenerate"
            title="Regenerate"
          >
            <RefreshCw className={cn('w-3 h-3', isBusy && 'animate-spin')} />
          </button>
          <button
            onClick={() => onDelete?.(id)}
            className="p-1 rounded hover:bg-bg-elevated text-danger"
            aria-label="Delete node"
            title="Delete"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
}

export const StudioNodeComponent = memo(StudioNodeInner);
