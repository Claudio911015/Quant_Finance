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

// Se abre en MKT-LIVE si la lista lo trae; si no, en el primero. MX-DEMO es solo el
// marcador mientras llega la lista y el respaldo si la lista viene vacía o falla.
const LIVE_SNAPSHOT_ID = 'MKT-LIVE';
const FALLBACK_SNAPSHOT_ID = 'MX-DEMO';

function initialChoice(list: SnapshotSummary[]): string {
  if (list.some((s) => s.id === LIVE_SNAPSHOT_ID)) return LIVE_SNAPSHOT_ID;
  return list[0]?.id ?? FALLBACK_SNAPSHOT_ID;
}

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
  const [snapshotId, setSnapshotIdState] = useState(FALLBACK_SNAPSHOT_ID);
  // No se pide ningún snapshot completo hasta que la primera carga de la lista termina
  // (o el usuario elige uno): así no se carga uno que enseguida se cambia por MKT-LIVE.
  const [ready, setReady] = useState(false);
  // Ya hay elección (automática o del usuario); recargar la lista no la pisa.
  const chosen = useRef(false);
  const [snapshot, setSnapshotState] = useState<Snapshot | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Cada carga toma un número; solo la última puede escribir estado (evita que una
  // respuesta lenta de un snapshot anterior pise al que el usuario eligió después).
  const latest = useRef(0);

  const setSnapshotId = useCallback((id: string) => {
    chosen.current = true;
    setSnapshotIdState(id);
    setReady(true);
  }, []);

  const refreshList = useCallback(async () => {
    try {
      const list = await listSnapshots();
      setSnapshots(list);
      if (!chosen.current) {
        chosen.current = true;
        setSnapshotIdState(initialChoice(list));
      }
    } catch (e) {
      setError(describeError(e));
    } finally {
      setReady(true);
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
    if (!ready) return;
    setSnapshotState(null);
    void refreshSnapshot(snapshotId);
  }, [ready, snapshotId, refreshSnapshot]);

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
    [snapshotId, setSnapshotId, snapshot, snapshots, reload, setSnapshot, error],
  );

  return <SnapshotContext.Provider value={value}>{children}</SnapshotContext.Provider>;
}

export function useSnapshot(): SnapshotState {
  const ctx = useContext(SnapshotContext);
  if (!ctx) throw new Error('useSnapshot requiere SnapshotProvider');
  return ctx;
}
