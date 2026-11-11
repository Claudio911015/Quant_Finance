import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { ApiError, getSnapshot, listSnapshots } from '../api/client';
import type { Snapshot, SnapshotSummary } from '../api/types';

const DEFAULT_SNAPSHOT_ID = 'MX-DEMO';

interface SnapshotState {
  snapshotId: string;
  setSnapshotId(id: string): void;
  snapshot: Snapshot | null;
  snapshots: SnapshotSummary[];
  reload(): Promise<void>;
  setSnapshot(s: Snapshot): void;
  /** Último fallo al cargar la lista o el snapshot activo; `null` si todo cargó. */
  error: string | null;
}

const SnapshotContext = createContext<SnapshotState | null>(null);

function describeError(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

export function SnapshotProvider({ children }: { children: ReactNode }) {
  const [snapshotId, setSnapshotId] = useState(DEFAULT_SNAPSHOT_ID);
  const [snapshot, setSnapshotState] = useState<Snapshot | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Cada carga toma un número; solo la última puede escribir estado (evita que una
  // respuesta lenta de un snapshot anterior pise al que el usuario eligió después).
  const latest = useRef(0);

  const refreshList = useCallback(async () => {
    try {
      setSnapshots(await listSnapshots());
    } catch (e) {
      setError(describeError(e));
    }
  }, []);

  const refreshSnapshot = useCallback(async (id: string) => {
    const ticket = ++latest.current;
    try {
      const s = await getSnapshot(id);
      if (ticket !== latest.current) return;
      setSnapshotState(s);
      setError(null);
    } catch (e) {
      if (ticket !== latest.current) return;
      setSnapshotState(null);
      setError(describeError(e));
    }
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    setSnapshotState(null);
    void refreshSnapshot(snapshotId);
  }, [snapshotId, refreshSnapshot]);

  const reload = useCallback(async () => {
    await Promise.all([refreshList(), refreshSnapshot(snapshotId)]);
  }, [refreshList, refreshSnapshot, snapshotId]);

  const setSnapshot = useCallback((s: Snapshot) => {
    latest.current++;
    setSnapshotState(s);
    setError(null);
  }, []);

  const value = useMemo<SnapshotState>(
    () => ({ snapshotId, setSnapshotId, snapshot, snapshots, reload, setSnapshot, error }),
    [snapshotId, snapshot, snapshots, reload, setSnapshot, error],
  );

  return <SnapshotContext.Provider value={value}>{children}</SnapshotContext.Provider>;
}

export function useSnapshot(): SnapshotState {
  const ctx = useContext(SnapshotContext);
  if (!ctx) throw new Error('useSnapshot requiere SnapshotProvider');
  return ctx;
}
