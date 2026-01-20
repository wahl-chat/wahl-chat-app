'use client';

import {
  type AgentState,
  type AgentStore,
  createAgentStore,
} from '@/lib/stores/agent-store';
import { type ReactNode, createContext, useContext, useRef } from 'react';
import { useStore } from 'zustand';

export type AgentStoreApi = ReturnType<typeof createAgentStore>;

export const AgentStoreContext = createContext<AgentStoreApi | undefined>(
  undefined,
);

export interface AgentStoreProviderProps {
  children: ReactNode;
  initialState?: Partial<AgentState>;
}

export function AgentStoreProvider({
  children,
  initialState,
}: AgentStoreProviderProps) {
  const storeRef = useRef<AgentStoreApi | null>(null);

  if (storeRef.current === null) {
    storeRef.current = createAgentStore(initialState);
  }

  return (
    <AgentStoreContext.Provider value={storeRef.current}>
      {children}
    </AgentStoreContext.Provider>
  );
}

export function useAgentStore<T>(selector: (store: AgentStore) => T): T {
  const agentStoreContext = useContext(AgentStoreContext);

  if (!agentStoreContext) {
    throw new Error('useAgentStore must be used within AgentStoreProvider');
  }

  return useStore(agentStoreContext, selector);
}
