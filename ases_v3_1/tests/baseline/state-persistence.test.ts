import { describe, it, expect } from 'vitest';

export interface StateStore {
  saveSessionState(sessionId: string, state: Record<string, unknown>, idempotencyKey: string): Promise<void>;
  getSessionState(sessionId: string): Promise<Record<string, unknown> | null>;
}

export class InMemoryIsolatedStateStore implements StateStore {
  private store = new Map<string, Record<string, unknown>>();
  private processedKeys = new Set<string>();

  async saveSessionState(sessionId: string, state: Record<string, unknown>, idempotencyKey: string): Promise<void> {
    if (this.processedKeys.has(idempotencyKey)) {
      return; // Idempotent skip
    }
    this.processedKeys.add(idempotencyKey);
    const existing = this.store.get(sessionId) || {};
    this.store.set(sessionId, { ...existing, ...state });
  }

  async getSessionState(sessionId: string): Promise<Record<string, unknown> | null> {
    return this.store.get(sessionId) || null;
  }
}

describe('ASES v3.1 Baseline: State Persistence & Isolation', () => {
  it('should maintain state isolation across concurrent sessions via Dependency Injection', async () => {
    const storeA = new InMemoryIsolatedStateStore();
    const storeB = new InMemoryIsolatedStateStore();

    await storeA.saveSessionState('session-1', { agent: 'Planner', step: 1 }, 'idem-1');
    await storeB.saveSessionState('session-2', { agent: 'Coder', step: 2 }, 'idem-2');

    const stateA = await storeA.getSessionState('session-1');
    const stateB = await storeB.getSessionState('session-2');
    const crossState = await storeA.getSessionState('session-2');

    expect(stateA).toEqual({ agent: 'Planner', step: 1 });
    expect(stateB).toEqual({ agent: 'Coder', step: 2 });
    expect(crossState).toBeNull();
  });

  it('should reject duplicate writes using idempotency key constraints', async () => {
    const store = new InMemoryIsolatedStateStore();

    await store.saveSessionState('session-1', { status: 'INITIAL' }, 'idem-key-100');
    await store.saveSessionState('session-1', { status: 'OVERWRITTEN' }, 'idem-key-100');

    const state = await store.getSessionState('session-1');
    expect(state).toEqual({ status: 'INITIAL' });
  });
});
