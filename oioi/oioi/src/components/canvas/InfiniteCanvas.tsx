'use client';

import React, { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useCanvasStore, type StudioNode } from '@/lib/stores/canvas-store';
import { StudioNodeComponent } from './StudioNode';
import { useGeneration } from '@/lib/hooks/useGeneration';

function CanvasInner() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, setSelected, removeNode } =
    useCanvasStore();
  const { regenerate } = useGeneration();

  const nodeTypes = useMemo<NodeTypes>(
    () => ({ studio: StudioNodeComponent as unknown as NodeTypes['studio'] }),
    []
  );

  const handleRegenerate = useCallback(
    (id: string) => {
      regenerate(id);
    },
    [regenerate]
  );

  const handleDelete = useCallback(
    (id: string) => {
      removeNode(id);
    },
    [removeNode]
  );

  // Inject action handlers into each node's props via a wrapper.
  const nodesWithHandlers = useMemo(
    () =>
      nodes.map((n) => ({
        ...n,
        data: { ...n.data, onRegenerate: handleRegenerate, onDelete: handleDelete },
      })) as StudioNode[],
    [nodes, handleRegenerate, handleDelete]
  );

  return (
    <div className="w-full h-full canvas-grid">
      <ReactFlow
        nodes={nodesWithHandlers}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => setSelected(node.id)}
        onPaneClick={() => setSelected(null)}
        minZoom={0.25}
        maxZoom={2}
        fitView
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ animated: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#27272a" />
        <Controls
          position="bottom-right"
          showInteractive={false}
          className="!bg-bg-surface !border-border-subtle !rounded-lg !shadow-elevated"
        />
        <MiniMap
          position="bottom-left"
          pannable
          zoomable
          className="!bg-bg-surface !border-border-subtle !rounded-lg"
          maskColor="rgba(10,10,11,0.7)"
          nodeColor={(n) => {
            const status = (n.data as { status?: string })?.status;
            if (status === 'generating' || status === 'queued') return '#3b82f6';
            if (status === 'ready') return '#22c55e';
            if (status === 'error') return '#ef4444';
            return '#3f3f46';
          }}
        />
      </ReactFlow>
    </div>
  );
}

export function InfiniteCanvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}
