import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, listTrades } from '../../api/client';
import {
  createReconciliation,
  getReconciliation,
  listReconciliations,
  reconciliationCsvUrl,
} from '../../api/opsClient';
import type { ReconRow, Reconciliation, ReconciliationSummary } from '../../api/opsTypes';
import { fmtDate, fmtDateTime, fmtMoney, fmtNumber, parseNumber } from '../../lib/format';
import { useSnapshot } from '../../state/SnapshotContext';
import { FilePicker } from './FilePicker';
import { productTitle } from '../pricers/registry';
import { CSV_TEMPLATE, RECON_STATUS_LABEL } from './opsLabels';
import './ReconciliationPanel.css';

const DEFAULT_TOLERANCE_PCT = '0.01';

function describeError(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

/** Signo explícito: "+5.0" / "-3.2". */
function signed(v: number, decimals: number): string {
  const s = fmtNumber(v, decimals);
  return s.startsWith('-') ? s : `+${s}`;
}

/** Fracción (0.0001) como porcentaje legible sin ceros de sobra: "0.01 %". */
function fmtFractionPct(frac: number): string {
  return `${Number((frac * 100).toPrecision(6))} %`;
}

function num(v: number | null): string {
  return v === null ? '—' : fmtNumber(v, 2);
}

function curveCell(row: ReconRow): string {
  const curve = row.decomposition?.curve;
  if (!curve || curve.bp === null) return '—';
  return `${signed(curve.bp, 1)} pb`;
}

function fxCell(row: ReconRow): string {
  const fx = row.decomposition?.fx;
  if (!fx || fx.spot === null) return '—';
  const base = fmtNumber(fx.spot, 2);
  return fx.pct === null ? base : `${base} (${signed(fx.pct, 2)} %)`;
}

function dateTitle(row: ReconRow): string | undefined {
  const d = row.decomposition?.date;
  if (!d) return undefined;
  return `${fmtDate(d.prev_date)}: ${fmtNumber(d.pv_prev, 2)} · ${fmtDate(d.next_date)}: ${fmtNumber(d.pv_next, 2)}`;
}

export function ReconciliationPanel() {
  const { snapshotId, snapshot } = useSnapshot();
  const [counterparties, setCounterparties] = useState<string[]>([]);
  const [counterparty, setCounterparty] = useState('');
  const [tolerancePct, setTolerancePct] = useState(DEFAULT_TOLERANCE_PCT);
  const [csv, setCsv] = useState('');
  const [run, setRun] = useState<Reconciliation | null>(null);
  const [history, setHistory] = useState<ReconciliationSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Cada consulta del historial toma un número; solo la última escribe (cambio rápido de contraparte).
  const historyTicket = useRef(0);

  useEffect(() => {
    let alive = true;
    listTrades()
      .then((trades) => {
        if (!alive) return;
        const names = Array.from(new Set(trades.map((t) => t.counterparty))).sort((a, b) =>
          a.localeCompare(b),
        );
        setCounterparties(names);
        setCounterparty((cur) => cur || names[0] || '');
      })
      .catch((e: unknown) => {
        if (alive) setError(describeError(e));
      });
    return () => {
      alive = false;
    };
  }, []);

  const loadHistory = useCallback(async (name: string) => {
    const ticket = ++historyTicket.current;
    if (!name) {
      setHistory([]);
      return;
    }
    try {
      const list = await listReconciliations({ counterparty: name });
      if (ticket === historyTicket.current) setHistory(list);
    } catch (e) {
      if (ticket === historyTicket.current) setError(describeError(e));
    }
  }, []);

  useEffect(() => {
    void loadHistory(counterparty);
  }, [counterparty, loadHistory]);

  function onCounterparty(name: string) {
    setCounterparty(name);
    setRun(null);
    setError(null);
  }

  async function onFile(file: File) {
    try {
      setCsv(await file.text());
      setError(null);
    } catch {
      setError('No se pudo leer el archivo');
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const pct = parseNumber(tolerancePct);
    if (pct === null || pct < 0) {
      setError('La tolerancia debe ser un número mayor o igual a cero');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // La interfaz pide el %; el backend recibe fracción del nocional (0.01 % -> 0.0001).
      const result = await createReconciliation({
        snapshot: snapshotId,
        counterparty,
        csv,
        tolerance: Number((pct / 100).toPrecision(12)),
      });
      setRun(result);
      void loadHistory(counterparty);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function openRun(id: number) {
    setError(null);
    try {
      setRun(await getReconciliation(id));
    } catch (err) {
      setError(describeError(err));
    }
  }

  return (
    <section className="ops-recon" data-testid="reconciliation-panel">
      <form className="ops-recon__form" onSubmit={(e) => void onSubmit(e)} aria-label="Nueva conciliación">
        <div className="ops-recon__fields">
          <label className="ops-recon__field">
            Contraparte
            <select
              className="ops-recon__input"
              value={counterparty}
              onChange={(e) => onCounterparty(e.target.value)}
            >
              {counterparties.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <div className="ops-recon__field">
            Snapshot
            <span className="ops-recon__static" data-testid="recon-snapshot">
              {snapshotId}
              {snapshot ? ` · ${fmtDate(snapshot.as_of)}` : ''}
            </span>
          </div>
          <label className="ops-recon__field">
            Tolerancia (% del nocional)
            <input
              className="ops-recon__input ops-recon__input--narrow num"
              inputMode="decimal"
              value={tolerancePct}
              onChange={(e) => setTolerancePct(e.target.value)}
            />
          </label>
          <div className="ops-recon__field">
            Archivo CSV
            <FilePicker label="Archivo CSV" accept=".csv,text/csv" onFile={(f) => void onFile(f)} />
          </div>
        </div>
        <label className="ops-recon__field ops-recon__field--col">
          CSV del banco
          <textarea
            className="ops-recon__input ops-recon__csv"
            rows={6}
            spellCheck={false}
            placeholder={CSV_TEMPLATE}
            value={csv}
            onChange={(e) => setCsv(e.target.value)}
          />
        </label>
        <div className="ops-recon__actions">
          <button type="submit" className="ops-recon__btn" disabled={busy || !counterparty || !snapshotId}>
            {busy ? 'Conciliando…' : 'Conciliar'}
          </button>
          <span className="ops-recon__hint">
            El PV del banco va con el signo de la empresa: positivo = activo.
          </span>
        </div>
        {error && (
          <p role="alert" className="ops-recon__error">
            {error}
          </p>
        )}
      </form>

      {run && <RunResult run={run} />}

      <section className="ops-recon__history" aria-label="Historial de conciliaciones">
        <h3>Historial{counterparty ? ` · ${counterparty}` : ''}</h3>
        {history.length === 0 ? (
          <p className="ops-recon__muted">Sin conciliaciones guardadas para esta contraparte.</p>
        ) : (
          <ul className="ops-recon__history-list">
            {history.map((h) => (
              <li key={h.id}>
                <button
                  type="button"
                  className={`ops-recon__history-item${run?.id === h.id ? ' is-active' : ''}`}
                  onClick={() => void openRun(h.id)}
                >
                  <span className="ops-recon__history-date">{fmtDateTime(h.created_at)}</span>
                  <span>{h.snapshot}</span>
                  <span className="ops-recon__muted">
                    {h.summary.conciliada} {h.summary.conciliada === 1 ? 'conciliada' : 'conciliadas'} ·{' '}
                    {h.summary.explicable} {h.summary.explicable === 1 ? 'explicable' : 'explicables'} ·{' '}
                    {h.summary.revisar} por revisar · {h.summary.bank_only} solo en el banco ·{' '}
                    {h.summary.own_only} solo en QF Desk
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

function RunResult({ run }: { run: Reconciliation }) {
  const s = run.summary;
  return (
    <section className="ops-recon__result" aria-label="Resultado de la conciliación">
      <header className="ops-recon__result-head">
        <h2>
          Conciliación #{run.id} · {run.counterparty}
        </h2>
        <a className="ops-recon__link" href={reconciliationCsvUrl(run.id)} download>
          Exportar CSV
        </a>
      </header>
      <p className="ops-recon__meta">
        Snapshot {run.snapshot} · {fmtDate(run.as_of)} · tolerancia {fmtFractionPct(run.tolerance)} del nocional ·{' '}
        {fmtDateTime(run.created_at)}
      </p>
      <p className="ops-recon__disclaimer" data-testid="recon-disclaimer">
        {run.disclaimer}
      </p>

      <dl className="ops-recon__summary" aria-label="Resumen">
        <div>
          <dt>Emparejadas</dt>
          <dd className="num">{s.matched}</dd>
        </div>
        <div>
          <dt>Conciliadas</dt>
          <dd className="num">{s.conciliada}</dd>
        </div>
        <div>
          <dt>Explicables</dt>
          <dd className="num">{s.explicable}</dd>
        </div>
        <div>
          <dt>Por revisar</dt>
          <dd className="num">{s.revisar}</dd>
        </div>
        <div>
          <dt>Solo en el banco</dt>
          <dd className="num">{s.bank_only}</dd>
        </div>
        <div>
          <dt>Solo en QF Desk</dt>
          <dd className="num">{s.own_only}</dd>
        </div>
        <div>
          <dt>PV propio</dt>
          <dd className="num">{fmtMoney(s.own_pv_mxn, 'MXN')}</dd>
        </div>
        <div>
          <dt>PV banco</dt>
          <dd className="num">{fmtMoney(s.bank_pv_mxn, 'MXN')}</dd>
        </div>
        <div>
          <dt>Diferencia</dt>
          <dd className="num">{fmtMoney(s.difference_mxn, 'MXN')}</dd>
        </div>
      </dl>

      <div className="ops-recon__scroll">
        <table className="ops-recon__table">
          <thead>
            <tr>
              <th>Operación</th>
              <th>Producto</th>
              <th className="num">PV propio MXN</th>
              <th className="num">PV banco</th>
              <th>Moneda</th>
              <th className="num">PV banco MXN</th>
              <th className="num">Diferencia</th>
              <th className="num">Dif./nocional</th>
              <th>Estado</th>
              <th>Fecha</th>
              <th className="num">Curva</th>
              <th className="num">Tipo de cambio</th>
            </tr>
          </thead>
          <tbody>
            {run.rows.length === 0 && (
              <tr>
                <td colSpan={12} className="ops-recon__muted">
                  Ninguna fila del CSV se emparejó con una operación.
                </td>
              </tr>
            )}
            {run.rows.map((r) => (
              <tr key={r.line} data-testid={`recon-row-${r.line}`}>
                <td>
                  <Link to={`/portafolio/${r.trade_id}`}>#{r.trade_id}</Link>
                  {r.bank_ref && <span className="ops-recon__muted"> · {r.bank_ref}</span>}
                </td>
                <td>{productTitle(r.product)}</td>
                <td className="num">{num(r.own_pv_mxn)}</td>
                <td className="num">{fmtNumber(r.bank_pv, 2)}</td>
                <td>{r.bank_currency}</td>
                <td className="num">{fmtNumber(r.bank_pv_mxn, 2)}</td>
                <td className="num">{num(r.difference_mxn)}</td>
                <td className="num">
                  {r.difference_rel === null ? '—' : `${fmtNumber(r.difference_rel * 100, 4)} %`}
                </td>
                <td>
                  <span className={`ops-recon__badge ops-recon__badge--${r.status}`}>
                    {RECON_STATUS_LABEL[r.status]}
                  </span>
                  {r.terms_flag && <span className="ops-recon__flag">Revisar términos</span>}
                  {r.error && <span className="ops-recon__row-error">{r.error}</span>}
                </td>
                <td title={dateTitle(r)}>{r.decomposition?.date?.attributed ? 'Atribuible' : '—'}</td>
                <td className="num">{curveCell(r)}</td>
                <td className="num">{fxCell(r)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {run.bank_only.length > 0 && (
        <section aria-label="Solo en el banco">
          <h3>Solo en el banco</h3>
          <div className="ops-recon__scroll">
            <table className="ops-recon__table">
              <thead>
                <tr>
                  <th className="num">Línea</th>
                  <th>Operación</th>
                  <th>Referencia</th>
                  <th className="num">PV banco</th>
                  <th>Moneda</th>
                  <th>Motivo</th>
                </tr>
              </thead>
              <tbody>
                {run.bank_only.map((b) => (
                  <tr key={b.line}>
                    <td className="num">{b.line}</td>
                    <td>{b.trade_id === null ? '—' : `#${b.trade_id}`}</td>
                    <td>{b.bank_ref ?? '—'}</td>
                    <td className="num">{fmtNumber(b.bank_pv, 2)}</td>
                    <td>{b.currency}</td>
                    <td>{b.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {run.own_only.length > 0 && (
        <section aria-label="Solo en QF Desk">
          <h3>Solo en QF Desk</h3>
          <div className="ops-recon__scroll">
            <table className="ops-recon__table">
              <thead>
                <tr>
                  <th>Operación</th>
                  <th>Producto</th>
                  <th className="num">PV propio MXN</th>
                </tr>
              </thead>
              <tbody>
                {run.own_only.map((o) => (
                  <tr key={o.trade_id}>
                    <td>
                      <Link to={`/portafolio/${o.trade_id}`}>#{o.trade_id}</Link>
                    </td>
                    <td>{productTitle(o.product)}</td>
                    <td className="num">{num(o.own_pv_mxn)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </section>
  );
}
