'use client';

import { generateImage, generateVideo, chatCompletion } from '@/lib/api';
import {
  useCanvasStore,
  nextNodeId,
  type StudioNode,
  type NodeKind,
} from '@/lib/stores/canvas-store';

/**
 * Generation controller: creates nodes on the canvas and drives real backend
 * calls (image / video / chat) with optimistic status updates + failover
 * errors surfaced on the node.
 */

export function useGeneration() {
  const { addNode, updateNodeData, nodes } = useCanvasStore();

  const spawnNode = (
    kind: NodeKind,
    position: { x: number; y: number },
    data: Partial<StudioNode['data']> = {}
  ): StudioNode => {
    const id = nextNodeId(kind);
    const node: StudioNode = {
      id,
      type: 'studio',
      position,
      data: {
        kind,
        label: data.label || defaultLabel(kind),
        status: 'idle',
        ...data,
      },
    };
    addNode(node);
    return node;
  };

  const generateImageNode = async (
    opts: { prompt: string; model?: string; styleId?: string; size?: string },
    position: { x: number; y: number }
  ) => {
    const node = spawnNode('image', position, {
      prompt: opts.prompt,
      model: opts.model,
      styleId: opts.styleId,
      status: 'generating',
      label: 'Image',
    });
    try {
      const res = await generateImage({
        prompt: opts.prompt,
        model: opts.model,
        style_id: opts.styleId,
        size: opts.size || '1024x1024',
      });
      updateNodeData(node.id, {
        status: 'ready',
        imageUrl: res.data[0]?.url,
        provider: res.provider,
        model: res.model,
      });
    } catch (err) {
      updateNodeData(node.id, {
        status: 'error',
        error: (err as Error).message,
      });
    }
  };

  const generateVideoNode = async (
    opts: {
      prompt: string;
      model?: string;
      firstFrameUrl?: string;
      durationSeconds?: number;
    },
    position: { x: number; y: number }
  ) => {
    const node = spawnNode('video', position, {
      prompt: opts.prompt,
      model: opts.model,
      status: 'generating',
      label: 'Video',
    });
    try {
      const res = await generateVideo({
        prompt: opts.prompt,
        model: opts.model,
        first_frame_url: opts.firstFrameUrl,
        duration_seconds: opts.durationSeconds || 5,
      });
      updateNodeData(node.id, {
        status: 'ready',
        videoUrl: res.video_url,
        provider: res.provider,
        model: res.model,
      });
    } catch (err) {
      updateNodeData(node.id, {
        status: 'error',
        error: (err as Error).message,
      });
    }
  };

  const generateChatNode = async (
    opts: { prompt: string; model?: string },
    position: { x: number; y: number }
  ) => {
    const node = spawnNode('chat', position, {
      prompt: opts.prompt,
      model: opts.model,
      status: 'generating',
      label: 'Chat',
    });
    try {
      const res = await chatCompletion({
        messages: [{ role: 'user', content: opts.prompt }],
        model: opts.model,
      });
      updateNodeData(node.id, {
        status: 'ready',
        chatText: res.choices[0]?.message?.content || '',
        provider: res.provider,
        model: res.model,
      });
    } catch (err) {
      updateNodeData(node.id, {
        status: 'error',
        error: (err as Error).message,
      });
    }
  };

  const regenerate = async (nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId);
    if (!node || !node.data.prompt) return;
    const { kind, prompt, model, styleId, imageUrl } = node.data;
    updateNodeData(nodeId, { status: 'generating', error: undefined });

    try {
      if (kind === 'image' || kind === 'character' || kind === 'scene') {
        const res = await generateImage({ prompt, model, style_id: styleId });
        updateNodeData(nodeId, {
          status: 'ready',
          imageUrl: res.data[0]?.url,
          provider: res.provider,
        });
      } else if (kind === 'video') {
        const res = await generateVideo({ prompt, model, first_frame_url: imageUrl });
        updateNodeData(nodeId, { status: 'ready', videoUrl: res.video_url, provider: res.provider });
      } else if (kind === 'chat') {
        const res = await chatCompletion({
          messages: [{ role: 'user', content: prompt }],
          model,
        });
        updateNodeData(nodeId, {
          status: 'ready',
          chatText: res.choices[0]?.message?.content || '',
        });
      }
    } catch (err) {
      updateNodeData(nodeId, { status: 'error', error: (err as Error).message });
    }
  };

  return {
    spawnNode,
    generateImageNode,
    generateVideoNode,
    generateChatNode,
    regenerate,
  };
}

function defaultLabel(kind: NodeKind): string {
  switch (kind) {
    case 'image':
      return 'Image';
    case 'video':
      return 'Video';
    case 'chat':
      return 'Chat';
    case 'character':
      return 'Character';
    case 'scene':
      return 'Scene';
    case 'pipeline':
      return 'Pipeline';
    default:
      return 'Prompt';
  }
}
