'use client';

import { create } from 'zustand';
import type { Node, Edge, Connection, NodeChange, EdgeChange } from '@xyflow/react';
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react';

export type NodeKind =
  | 'prompt'
  | 'image'
  | 'video'
  | 'chat'
  | 'character'
  | 'scene'
  | 'pipeline';

export type NodeStatus = 'idle' | 'queued' | 'generating' | 'ready' | 'error';

export interface StudioNodeData extends Record<string, unknown> {
  kind: NodeKind;
  label: string;
  status: NodeStatus;
  prompt?: string;
  imageUrl?: string;
  videoUrl?: string;
  chatText?: string;
  model?: string;
  styleId?: string;
  provider?: string;
  error?: string;
}

export type StudioNode = Node<StudioNodeData>;

interface CanvasState {
  nodes: StudioNode[];
  edges: Edge[];
  selectedId: string | null;
  runningCount: number;

  setNodes: (nodes: StudioNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: (changes: NodeChange<StudioNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  addNode: (node: StudioNode) => void;
  updateNodeData: (id: string, patch: Partial<StudioNodeData>) => void;
  removeNode: (id: string) => void;
  setSelected: (id: string | null) => void;
  clear: () => void;
}

let counter = 0;
export const nextNodeId = (kind: NodeKind) => `${kind}-${Date.now()}-${counter++}`;

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedId: null,
  runningCount: 0,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  onNodesChange: (changes) =>
    set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) =>
    set({ edges: applyEdgeChanges(changes, get().edges) }),
  onConnect: (connection) =>
    set({ edges: addEdge({ ...connection, animated: true }, get().edges) }),

  addNode: (node) => set({ nodes: [...get().nodes, node], selectedId: node.id }),

  updateNodeData: (id, patch) =>
    set({
      nodes: get().nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...patch } } : n
      ),
    }),

  removeNode: (id) =>
    set({
      nodes: get().nodes.filter((n) => n.id !== id),
      edges: get().edges.filter((e) => e.source !== id && e.target !== id),
      selectedId: get().selectedId === id ? null : get().selectedId,
    }),

  setSelected: (id) => set({ selectedId: id }),

  clear: () => set({ nodes: [], edges: [], selectedId: null }),
}));

/** Count of nodes currently generating (for the queue badge). */
export const selectRunningCount = (nodes: StudioNode[]) =>
  nodes.filter(
    (n) => n.data.status === 'generating' || n.data.status === 'queued'
  ).length;
