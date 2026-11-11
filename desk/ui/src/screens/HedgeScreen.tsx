import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ApiError,
  closeHedgePeriod,
  dedesignateHedge,
  getHedge,
  hedgeEffectiveness,
  hedgeReportCsvUrl,
} from '../api/client';
import type {
  CriticalTerm,
  EffectivenessResponse,
  HedgeDetail,
  HedgePeriod,
  JournalEntry,
} from '../api/types';
import { AccountingNotice } from '../components/AccountingNotice';
import {
  DOC_FIELD_LABEL,
  HEDGE_STATUS_LABEL,
  HEDGE_TYPE_LABEL,
  ITEM_KIND_LABEL,
  SIDE_LABEL,
  TERM_RESULT_LABEL,
} from '../lib/hedgeLabels';
import { fmtDate, fmtMoney, fmtNumber } from '../lib/format';
import { useSnapshot } from '../state/SnapshotContext';
import { PRODUCT_SPECS } from './pricers/registry';
import './HedgeScreen.css';

const MXN = 'MXN';

function describe(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

function money(v: number): string {
  return fmtMoney(v, MXN);
}

function percent(fraction: number): string {
  return `${fmtNumber(fraction * 100, 2)} %`;
}

/** Valor de un término crítico: los lados se rotulan, los montos llevan separador de miles. */
function termValue(t: CriticalTerm, v: string | number): string {
  if (t.term === 'side') return SIDE_LABEL[String(v)] ?? String(v);
  if (typeof v === 'number') return fmtNumber(v, 2);
  return fmtDate(v);
}

function sum(values: number[]): number {
  return values.reduce((a, b) => a + b, 0);
}

interface SnapshotOption {
  id: string;
  label: string;
  as_of: string | null;
}

interface CloseFormProps {
  hedgeId: number;
  options: SnapshotOption[];
  activeId: string;
  onDone(): Promise<void>;
  onBanner(message: string | null): void;
}

/** Cierra un periodo con el snapshot elegido (por omisión el activo). */
function CloseForm(p: CloseFormProps) {
  const [choice, setChoice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const value = choice ?? p.activeId;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    p.onBanner(null);
    setBusy(true);
    try {
      await closeHedgePeriod(p.hedgeId, value);
      await p.onDone();
    } catch (err) {
      if (err instanceof ApiError && err.field === 'snapshot') setError(err.message);
      else p.onBanner(describe(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="hedge__form" onSubmit={submit} noValidate aria-label="Cerrar periodo">
      <h3>Cerrar periodo</h3>
      <div className="hedge__field">
        <label htmlFor="hedge-close-snapshot">Snapshot del cierre</label>
        <select
          id="hedge-close-snapshot"
          className="hedge__input"
          value={value}
          aria-invalid={error ? true : undefined}
          onChange={(e) => setChoice(e.target.value)}
        >
          {p.options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.as_of ? `${o.label} · ${o.as_of}` : o.label}
            </option>
          ))}
        </select>
        {error && (
          <div className="hedge__error" role="alert">
            {error}
          </div>
        )}
      </div>
      <button type="submit" className="hedge__btn" disabled={busy}>
        Cerrar periodo
      </button>
    </form>
  );
}

interface DedesignateFormProps {
  hedgeId: number;
  defaultDate: string;
  onDone(): Promise<void>;
  onBanner(message: string | null): void;
}

/** Desdesignación: fecha y motivo; los errores del backend van bajo su campo. */
function DedesignateForm(p: DedesignateFormProps) {
  const [date, setDate] = useState(p.defaultDate);
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<Partial<Record<'date' | 'reason', string>>>({});
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const local: typeof errors = {};
    if (!date) local.date = 'Indica la fecha';
    if (reason.trim() === '') local.reason = 'Indica el motivo';
    if (Object.keys(local).length > 0) {
      setErrors(local);
      return;
    }
    setErrors({});
    p.onBanner(null);
    setBusy(true);
    try {
      await dedesignateHedge(p.hedgeId, { date, reason: reason.trim() });
      await p.onDone();
    } catch (err) {
      if (err instanceof ApiError && (err.field === 'date' || err.field === 'reason')) {
        setErrors({ [err.field]: err.message });
      } else {
        p.onBanner(describe(err));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="hedge__form" onSubmit={submit} noValidate aria-label="Desdesignar">
      <h3>Desdesignar</h3>
      <div className="hedge__field">
        <label htmlFor="hedge-dedesignate-date">Fecha</label>
        <input
          id="hedge-dedesignate-date"
          type="date"
          className="hedge__input"
          value={date}
          aria-invalid={errors.date ? true : undefined}
          onChange={(e) => setDate(e.target.value)}
        />
        {errors.date && (
          <div className="hedge__error" role="alert">
            {errors.date}
          </div>
        )}
      </div>
      <div className="hedge__field">
        <label htmlFor="hedge-dedesignate-reason">Motivo</label>
        <input
          id="hedge-dedesignate-reason"
          type="text"
          autoComplete="off"
          className="hedge__input"
          value={reason}
          aria-invalid={errors.reason ? true : undefined}
          onChange={(e) => setReason(e.target.value)}
        />
        {errors.reason && (
          <div className="hedge__error" role="alert">
            {errors.reason}
          </div>
        )}
      </div>
      <button type="submit" className="hedge__btn" disabled={busy}>
        Desdesignar
      </button>
    </form>
  );
}

function PeriodsTable({ hedge }: { hedge: HedgeDetail }) {
  const cashFlow = hedge.hedge_type === 'cash_flow';
  return (
    <div className="hedge__table-wrap">
      <table className="hedge__table" aria-label="Periodos">
        <thead>
          <tr>
            <th className="num">Fecha</th>
            <th>Snapshot</th>
            <th className="num">Δ instrumento</th>
            {cashFlow ? (
              <>
                <th className="num">Δ ORI</th>
                <th className="num">Inefectividad</th>
                <th className="num">Reciclaje</th>
                <th className="num">Saldo ORI</th>
              </>
            ) : (
              <>
                <th className="num">Ajuste de partida</th>
                <th className="num">Inefectividad</th>
                <th className="num">Liquidado</th>
                <th className="num">Resultado del periodo</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {hedge.periods.map((p: HedgePeriod) => (
            <tr key={p.id}>
              <td className="num">{fmtDate(p.as_of)}</td>
              <td>{p.snapshot}</td>
              <td className="num">{money(p.d_inst_cum)}</td>
              {cashFlow ? (
                <>
                  <td className="num">{money(p.d_oci)}</td>
                  <td className="num">{money(p.ineffectiveness)}</td>
                  <td className="num">{money(p.recycled)}</td>
                  <td className="num">{money(p.oci)}</td>
                </>
              ) : (
                <>
                  <td className="num">{money(p.item_adjustment)}</td>
                  <td className="num">{money(p.ineffectiveness)}</td>
                  <td className="num">{money(p.settled_period)}</td>
                  <td className="num">{money(p.fv_result)}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function JournalTable({ period }: { period: HedgePeriod }) {
  const entries: JournalEntry[] = period.entries;
  return (
    <div className="hedge__table-wrap">
      <table className="hedge__table" aria-label={`Asientos ${period.as_of}`}>
        <thead>
          <tr>
            <th>Cuenta</th>
            <th className="num">Cargo</th>
            <th className="num">Abono</th>
            <th>Memo</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((en, i) => (
            <tr key={`${en.account}-${i}`}>
              <td>{en.account}</td>
              <td className="num">{money(en.debit)}</td>
              <td className="num">{money(en.credit)}</td>
              <td>{en.memo}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th>Total del periodo</th>
            <td className="num">{money(sum(entries.map((en) => en.debit)))}</td>
            <td className="num">{money(sum(entries.map((en) => en.credit)))}</td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function CriticalTermsTable({ terms }: { terms: CriticalTerm[] }) {
  return (
    <div className="hedge__table-wrap">
      <table className="hedge__table" aria-label="Términos críticos">
        <thead>
          <tr>
            <th>Término</th>
            <th className="num">Instrumento</th>
            <th className="num">Partida</th>
            <th>Resultado</th>
          </tr>
        </thead>
        <tbody>
          {terms.map((t) => (
            <tr key={t.term}>
              <td>{t.label}</td>
              <td className="num">{termValue(t, t.instrument)}</td>
              <td className="num">{termValue(t, t.item)}</td>
              <td className={`hedge__result hedge__result--${t.result}`}>{TERM_RESULT_LABEL[t.result]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScenariosTable({ eff }: { eff: EffectivenessResponse }) {
  return (
    <div className="hedge__table-wrap">
      <table className="hedge__table" aria-label="Escenarios">
        <thead>
          <tr>
            <th>Escenario</th>
            <th className="num">Δ instrumento</th>
            <th className="num">Δ partida</th>
            <th className="num">Razón</th>
          </tr>
        </thead>
        <tbody>
          {eff.scenarios.map((s) => (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td className="num">{money(s.d_inst)}</td>
              <td className="num">{money(s.d_hypo)}</td>
              <td className="num">{s.ratio == null ? '—' : fmtNumber(s.ratio, 4)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={4}>{`Relación económica: ${eff.economic_relationship ? 'sí' : 'no'}`}</td>
          </tr>
          <tr>
            <td colSpan={4}>{`En 80 %–125 %: ${eff.in_reference_range} de ${eff.scenarios_counted}`}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

export default function HedgeScreen() {
  const { id: idParam } = useParams();
  const id = idParam != null && /^\d+$/.test(idParam) ? Number(idParam) : null;
  const { snapshotId, snapshot, snapshots, error: snapshotError } = useSnapshot();
  // El snapshot completo llega después de elegir el id: sin él no hay fecha de valuación.
  const asOf = snapshot && snapshot.id === snapshotId ? snapshot.as_of : null;

  const [hedge, setHedge] = useState<HedgeDetail | null>(null);
  const [hedgeError, setHedgeError] = useState<string | null>(null);
  const [eff, setEff] = useState<EffectivenessResponse | null>(null);
  const [effError, setEffError] = useState<string | null>(null);
  const [effLoading, setEffLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  // Cada carga toma un número; solo la última escribe estado (una respuesta lenta de un
  // snapshot anterior no debe pisar la del que el usuario eligió después).
  const latestHedge = useRef(0);
  const latestEff = useRef(0);

  const loadHedge = useCallback(async () => {
    if (id == null) return;
    const ticket = ++latestHedge.current;
    try {
      const h = await getHedge(id);
      if (ticket !== latestHedge.current) return;
      setHedge(h);
      setHedgeError(null);
    } catch (e) {
      if (ticket !== latestHedge.current) return;
      setHedge(null);
      setHedgeError(describe(e));
    }
  }, [id]);

  const hasAsOf = asOf != null;
  const loadEff = useCallback(async () => {
    if (id == null || !hasAsOf) return;
    const ticket = ++latestEff.current;
    setEff(null);
    setEffError(null);
    setEffLoading(true);
    try {
      const r = await hedgeEffectiveness(id, snapshotId);
      if (ticket !== latestEff.current) return;
      setEff(r);
    } catch (e) {
      if (ticket !== latestEff.current) return;
      setEffError(describe(e));
    } finally {
      if (ticket === latestEff.current) setEffLoading(false);
    }
  }, [id, snapshotId, hasAsOf]);

  useEffect(() => {
    void loadHedge();
  }, [loadHedge]);

  useEffect(() => {
    void loadEff();
  }, [loadEff]);

  const reload = useCallback(async () => {
    setActionError(null);
    await Promise.all([loadHedge(), loadEff()]);
  }, [loadHedge, loadEff]);

  if (id == null) {
    return (
      <section className="hedge">
        <Link to="/coberturas" className="hedge__back">
          Volver a coberturas
        </Link>
        <AccountingNotice />
        <div className="hedge__banner" role="alert">
          Cobertura inválida
        </div>
      </section>
    );
  }

  const options: SnapshotOption[] = snapshots.some((s) => s.id === snapshotId)
    ? snapshots
    : [{ id: snapshotId, label: snapshotId, as_of: asOf }, ...snapshots];
  const spec = hedge ? PRODUCT_SPECS[hedge.product] : null;
  const frozen = hedge?.status === 'desdesignada';

  return (
    <section className="hedge">
      <Link to="/coberturas" className="hedge__back">
        Volver a coberturas
      </Link>
      <AccountingNotice />

      {(hedgeError ?? (asOf == null ? snapshotError : null)) && (
        <div className="hedge__banner" role="alert">
          {hedgeError ?? snapshotError}
        </div>
      )}
      {!hedge && !hedgeError && <div className="hedge__meta">Cargando…</div>}

      {hedge && (
        <>
          <header className="hedge__head">
            <h1>Cobertura {hedge.id}</h1>
            <span className={`hedge__status hedge__status--${hedge.status}`}>
              {HEDGE_STATUS_LABEL[hedge.status]}
            </span>
            <span className="hedge__links">
              <a href={hedgeReportCsvUrl(hedge.id)} download>
                Exportar asientos (CSV)
              </a>
              <Link to={`/coberturas/${hedge.id}/reporte`}>Vista imprimible</Link>
            </span>
          </header>

          <dl className="hedge__facts">
            <div>
              <dt>Tipo</dt>
              <dd>{HEDGE_TYPE_LABEL[hedge.hedge_type]}</dd>
            </div>
            <div>
              <dt>Partida</dt>
              <dd>{ITEM_KIND_LABEL[hedge.item_kind]}</dd>
            </div>
            <div>
              <dt>Operación</dt>
              <dd>
                <Link to={`/portafolio/${hedge.trade_id}`}>
                  {`#${hedge.trade_id} · ${spec?.title ?? hedge.product} · ${hedge.counterparty}`}
                </Link>
              </dd>
            </div>
            <div>
              <dt>Fracción</dt>
              <dd className="num">{percent(hedge.fraction)}</dd>
            </div>
            <div>
              <dt>Razón de cobertura</dt>
              <dd className="num">{fmtNumber(hedge.hedge_ratio, 4)}</dd>
            </div>
            <div>
              <dt>Designación</dt>
              <dd className="num">{fmtDate(hedge.designation_date)}</dd>
            </div>
            {frozen && hedge.dedesignation ? (
              <>
                <div>
                  <dt>Reserva congelada</dt>
                  <dd className="num">{money(hedge.dedesignation.frozen_oci)}</dd>
                </div>
                <div>
                  <dt>Desdesignada el</dt>
                  <dd className="num">{fmtDate(hedge.dedesignation.date)}</dd>
                </div>
                <div>
                  <dt>Motivo</dt>
                  <dd>{hedge.dedesignation.reason}</dd>
                </div>
              </>
            ) : (
              <div>
                <dt>Saldo de reserva</dt>
                <dd className="num">{money(hedge.oci_balance)}</dd>
              </div>
            )}
          </dl>

          {hedge.status === 'activa' && asOf != null && (
            <section className="hedge__block" aria-label="Acciones">
              <h2>Acciones</h2>
              {actionError && (
                <div className="hedge__banner" role="alert">
                  {actionError}
                </div>
              )}
              <div className="hedge__actions">
                <CloseForm
                  hedgeId={hedge.id}
                  options={options}
                  activeId={snapshotId}
                  onDone={reload}
                  onBanner={setActionError}
                />
                <DedesignateForm
                  key={`dedesignate-${asOf}`}
                  hedgeId={hedge.id}
                  defaultDate={asOf}
                  onDone={reload}
                  onBanner={setActionError}
                />
              </div>
            </section>
          )}

          <section className="hedge__block" aria-label="Documentación">
            <h2>Documentación</h2>
            <dl className="hedge__doc">
              {(Object.keys(DOC_FIELD_LABEL) as (keyof typeof DOC_FIELD_LABEL)[]).map((k) => (
                <div key={k}>
                  <dt>{DOC_FIELD_LABEL[k]}</dt>
                  <dd>{hedge.documentation[k]}</dd>
                </div>
              ))}
            </dl>
          </section>

          {eff ? (
            <>
              <section className="hedge__block" aria-label="Términos críticos">
                <h2>Términos críticos</h2>
                <CriticalTermsTable terms={eff.critical_terms} />
              </section>
              <section className="hedge__block" aria-label="Escenarios">
                <h2>Escenarios</h2>
                <ScenariosTable eff={eff} />
                <p className="hedge__meta">{eff.reference_note}</p>
              </section>
            </>
          ) : (
            <section className="hedge__block" aria-label="Efectividad prospectiva">
              <h2>Efectividad prospectiva</h2>
              {effError ? (
                <p className="hedge__meta">{effError}</p>
              ) : (
                <p className="hedge__meta">{effLoading || !hasAsOf ? 'Cargando…' : ''}</p>
              )}
            </section>
          )}

          <section className="hedge__block" aria-label="Periodos">
            <h2>Periodos</h2>
            {hedge.periods.length === 0 ? (
              <p className="hedge__meta">Sin periodos cerrados</p>
            ) : (
              <PeriodsTable hedge={hedge} />
            )}
          </section>

          <section className="hedge__block" aria-label="Asientos">
            <h2>Asientos</h2>
            {hedge.periods.length === 0 ? (
              <p className="hedge__meta">Sin asientos</p>
            ) : (
              hedge.periods.map((p) => (
                <div key={p.id} className="hedge__journal">
                  <h3>{`Periodo al ${fmtDate(p.as_of)}`}</h3>
                  <JournalTable period={p} />
                </div>
              ))
            )}
          </section>
        </>
      )}
    </section>
  );
}
