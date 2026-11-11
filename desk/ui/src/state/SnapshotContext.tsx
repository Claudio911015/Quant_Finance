import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Snapshot, SnapshotSummary } from '../api/types';

interface SnapshotState {
  snapshotId: string;
  setSnapshotId(id: string): void;
  snapshot: Snapshot | null;
  snapshots: SnapshotSummary[];
  reload(): Promise<void>;
  setSnapshot(s: Snapshot): void;
}

const SnapshotContext = createContext<SnapshotState | null>(null);

export function SnapshotProvider({ children }: { children: ReactNode }) {
  const [snapshotId, setSnapshotId] = useState('MX-DEMO');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [snapshots] = useState<SnapshotSummary[]>([]);

  const value: SnapshotState = {
    snapshotId,
    setSnapshotId,
    snapshot,
    snapshots,
    reload: async () => {},
    setSnapshot,
  };

  return <SnapshotContext.Provider value={value}>{children}</SnapshotContext.Provider>;
}

export function useSnapshot(): SnapshotState {
  const ctx = useContext(SnapshotContext);
  if (!ctx) throw new Error('useSnapshot requiere SnapshotProvider');
  return ctx;
}
