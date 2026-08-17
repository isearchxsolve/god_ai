'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sparkles, Activity } from 'lucide-react';
import { getProvidersHealth, type ProviderInfo } from '@/lib/api';
import { cn } from '@/lib/utils';

const STATUS_COLOR: Record<string, string> = {
  healthy: 'bg-success',
  degraded: 'bg-warning',
  unhealthy: 'bg-danger',
  unknown: 'bg-fg-muted',
};

function ProviderBadge({ p }: { p: ProviderInfo }) {
  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-bg-elevated border border-border-subtle"
      title={`${p.name}: ${p.status}${p.in_cooldown ? ' (cooldown)' : ''} — ${p.capabilities.join(', ')}`}
    >
      <span
        className={cn(
          'w-1.5 h-1.5 rounded-full',
          STATUS_COLOR[p.status] || STATUS_COLOR.unknown,
          p.status === 'healthy' && 'animate-pulse'
        )}
      />
      <span className="text-[10px] font-medium text-fg-secondary capitalize">{p.name}</span>
    </div>
  );
}

export function TopBar() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['providers-health'],
    queryFn: getProvidersHealth,
    refetchInterval: 15000,
  });

  return (
    <header className="h-14 shrink-0 border-b border-border-subtle bg-bg-surface flex items-center justify-between px-4 z-20">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-accent-500 to-fuchsia-500 flex items-center justify-center shadow-lg">
          <Sparkles className="w-4.5 h-4.5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold bg-clip-text text-transparent bg-gradient-to-r from-accent-400 to-fuchsia-400 leading-tight">
            OiiOii Studio
          </h1>
          <p className="text-[10px] text-fg-muted leading-tight">
            7-Agent AI Animation Engine
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Activity className="w-3.5 h-3.5 text-fg-muted" aria-hidden />
        {isLoading && <span className="text-[11px] text-fg-muted">Checking providers…</span>}
        {isError && (
          <span className="text-[11px] text-danger">Backend offline</span>
        )}
        {data?.providers.map((p) => (
          <ProviderBadge key={p.name} p={p} />
        ))}
      </div>
    </header>
  );
}
