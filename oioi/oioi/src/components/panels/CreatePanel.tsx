'use client';

import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Wand2, Cpu, Palette, ImageIcon, Video, MessageSquare } from 'lucide-react';
import { getModels, getStyles } from '@/lib/api';
import { useGeneration } from '@/lib/hooks/useGeneration';
import { useCanvasStore } from '@/lib/stores/canvas-store';
import { cn } from '@/lib/utils';

type GenMode = 'image' | 'video' | 'chat';

export function CreatePanel() {
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState<GenMode>('image');
  const [modelId, setModelId] = useState('');
  const [styleId, setStyleId] = useState('');
  const { nodes } = useCanvasStore();
  const { generateImageNode, generateVideoNode, generateChatNode } = useGeneration();

  const { data: models } = useQuery({ queryKey: ['models'], queryFn: getModels });
  const { data: styles } = useQuery({ queryKey: ['styles'], queryFn: getStyles });

  const modelOptions = useMemo(() => {
    if (!models) return [];
    if (mode === 'image') return models.image_models;
    if (mode === 'video') return models.video_models;
    return models.llm_models;
  }, [models, mode]);

  const handleGenerate = () => {
    if (!prompt.trim()) return;
    // Place new nodes in a grid offset by current node count.
    const i = nodes.length;
    const position = { x: 80 + (i % 3) * 300, y: 80 + Math.floor(i / 3) * 260 };
    const opts = { prompt: prompt.trim(), model: modelId || undefined, styleId: styleId || undefined };

    if (mode === 'image') generateImageNode(opts, position);
    else if (mode === 'video') generateVideoNode(opts, position);
    else generateChatNode(opts, position);
  };

  return (
    <div className="p-4 space-y-4">
      <div>
        <label className="text-xs font-semibold text-fg-secondary flex items-center gap-1.5 mb-2">
          <Wand2 className="w-3.5 h-3.5 text-accent-400" />
          Prompt
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          className="w-full bg-bg-canvas border border-border-subtle rounded-md p-2.5 text-xs text-fg-primary focus:outline-none focus:border-accent-500 transition-colors resize-none placeholder:text-fg-muted"
          placeholder="Describe what you want to create…"
        />
      </div>

      {/* Generation mode */}
      <div className="grid grid-cols-3 gap-1.5">
        {(
          [
            { id: 'image', icon: ImageIcon, label: 'Image' },
            { id: 'video', icon: Video, label: 'Video' },
            { id: 'chat', icon: MessageSquare, label: 'Chat' },
          ] as const
        ).map((m) => (
          <button
            key={m.id}
            onClick={() => {
              setMode(m.id);
              setModelId('');
            }}
            className={cn(
              'flex flex-col items-center gap-1 py-2 rounded-md border text-[11px] font-medium transition-colors',
              mode === m.id
                ? 'bg-accent-500/15 border-accent-500 text-accent-400'
                : 'bg-bg-canvas border-border-subtle text-fg-secondary hover:border-border-strong'
            )}
          >
            <m.icon className="w-4 h-4" />
            {m.label}
          </button>
        ))}
      </div>

      {/* Model picker — real registry */}
      <div>
        <label className="text-xs font-semibold text-fg-secondary flex items-center gap-1.5 mb-2">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          Model
        </label>
        <select
          value={modelId}
          onChange={(e) => setModelId(e.target.value)}
          className="w-full bg-bg-canvas border border-border-subtle rounded-md p-2 text-xs text-fg-primary focus:outline-none focus:border-accent-500"
        >
          <option value="">Auto (best available)</option>
          {modelOptions.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name} · {m.provider}
            </option>
          ))}
        </select>
      </div>

      {/* Style picker — only for image/video */}
      {mode !== 'chat' && (
        <div>
          <label className="text-xs font-semibold text-fg-secondary flex items-center gap-1.5 mb-2">
            <Palette className="w-3.5 h-3.5 text-fuchsia-400" />
            Style {styles ? `(${styles.total})` : ''}
          </label>
          <select
            value={styleId}
            onChange={(e) => setStyleId(e.target.value)}
            className="w-full bg-bg-canvas border border-border-subtle rounded-md p-2 text-xs text-fg-primary focus:outline-none focus:border-accent-500"
          >
            <option value="">No style</option>
            {styles?.styles.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} · {s.category}
              </option>
            ))}
          </select>
        </div>
      )}

      <button
        onClick={handleGenerate}
        disabled={!prompt.trim()}
        className="w-full py-2.5 px-4 rounded-md bg-gradient-to-r from-accent-500 to-fuchsia-600 hover:opacity-90 transition-opacity font-semibold text-xs text-white shadow-lg flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <Wand2 className="w-4 h-4" />
        Generate {mode === 'image' ? 'Image' : mode === 'video' ? 'Video' : 'Chat'}
      </button>
    </div>
  );
}
