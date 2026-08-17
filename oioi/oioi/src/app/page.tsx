'use client';

import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Wand2, Clapperboard, MessageSquare, LayoutGrid } from 'lucide-react';
import { Toaster } from '@/components/ui/toaster';
import { TopBar } from '@/components/layout/TopBar';
import { InfiniteCanvas } from '@/components/canvas/InfiniteCanvas';
import { CreatePanel } from '@/components/panels/CreatePanel';
import { PipelinePanel } from '@/components/panels/PipelinePanel';
import { ChatPanel } from '@/components/panels/ChatPanel';
import { useCanvasStore, selectRunningCount } from '@/lib/stores/canvas-store';
import { cn } from '@/lib/utils';

type Tab = 'create' | 'pipeline' | 'chat';

const TABS: { id: Tab; icon: React.ElementType; label: string }[] = [
  { id: 'create', icon: Wand2, label: 'Create' },
  { id: 'pipeline', icon: Clapperboard, label: 'Film' },
  { id: 'chat', icon: MessageSquare, label: 'Chat' },
];

function Studio() {
  const [tab, setTab] = useState<Tab>('create');
  const nodes = useCanvasStore((s) => s.nodes);
  const running = selectRunningCount(nodes);

  return (
    <div className="h-screen flex flex-col bg-bg-base text-fg-primary overflow-hidden">
      <TopBar />
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left sidebar */}
        <aside className="w-80 shrink-0 border-r border-border-subtle bg-bg-surface flex flex-col">
          <nav className="flex border-b border-border-subtle" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors border-b-2',
                  tab === t.id
                    ? 'border-accent-500 text-accent-400'
                    : 'border-transparent text-fg-muted hover:text-fg-secondary'
                )}
              >
                <t.icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            ))}
          </nav>
          <div className="flex-1 overflow-y-auto">
            {tab === 'create' && <CreatePanel />}
            {tab === 'pipeline' && <PipelinePanel />}
            {tab === 'chat' && <ChatPanel />}
          </div>
        </aside>

{/* Canvas */}
        <main className="flex-1 relative h-full">
          <InfiniteCanvas />
          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center space-y-2 max-w-sm px-6">
                <LayoutGrid className="w-10 h-10 text-fg-muted mx-auto" />
                <p className="text-sm text-fg-secondary font-medium">
                  Your animation canvas is empty
                </p>
                <p className="text-xs text-fg-muted">
                  Describe an idea in the Create panel, or run the 7-agent Film
                  pipeline to generate a full short.
                </p>
              </div>
            </div>
          )}
          {/* Queue badge */}
          {running > 0 && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-surface border border-border-subtle shadow-elevated">
              <span className="w-2 h-2 rounded-full bg-info animate-pulse" />
              <span className="text-[11px] text-fg-secondary">
                {running} generation{running > 1 ? 's' : ''} running
              </span>
            </div>
          )}
        </main>
      </div>
      <Toaster />
    </div>
  );
}

export default function Home() {
  // One QueryClient per mounted page instance (avoids stale cache leaking
  // across HMR reloads and test renders).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 1, staleTime: 60_000 } },
      })
  );
  return (
    <QueryClientProvider client={queryClient}>
      <Studio />
    </QueryClientProvider>
  );
}
