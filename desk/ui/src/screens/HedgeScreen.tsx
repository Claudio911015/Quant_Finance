import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ApiError,
  closeHedgePeriod,
  dedesignateHedge,
  getHedge,
  hedgeEffectiveness,
  hedgeReportCsvUrl,
  releaseHedgeReserve,
} from '../api/client';
import type {
  CriticalTerm,
  DedesignationCause,
  EffectivenessResponse,
  HedgeDetail,
  HedgePeriod,
  JournalEntry,
  ReleaseCause,
  ReserveReleaseData,
} from '../api/types';
import { AccountingNotice } from '../components/AccountingNotice';
import {
  DEDESIGNATION_CAUSE_LABEL,
  DOC_FIELD_LABEL,
  HEDGE_STATUS_LABEL,
  HEDGE_TYPE_LABEL,
  CONCLUDED_NOTE,
  ITEM_KIND_LABEL,
  RELEASE_CAUSE_LABEL,
  SIDE_LABEL,
  TERM_RESULT_LABEL,
  localizeMessage,
} from '../lib/hedgeLabels';
import { fmtDate, fmtMoney, fmtNumber, parseNumber } from '../lib/format';
import { useSnapshot } from '../state/SnapshotContext';
import { PRODUCT_SPECS } from './pricers/registry';
import './HedgeScreen.css';

const MXN = 'MXN';

function describe(e: unknown): string {
  return e instanceof ApiError ? localizeMessage(e.message) : 'No se pudo conectar con el backend';
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

/** Saldo mínimo de reserva (media centésima) que se considera distinto de cero. */
const HALF_CENT = 0.005;

/**
 * Primer snapshot (por fecha) con fecha posterior a `after` —o igual o posterior si `inclusive`—, que es con el
 * que el backend acepta la acción; `''` si no hay ninguno. El snapshot global de la barra suele ser anterior
 * al último evento de la relación y daría un 409 al primer intento.
 */
function firstSnapshotAfter(options: SnapshotOption[], after: string, inclusive: boolean): string {
  const later = options
    .filter((o) => o.as_of != null && (inclusive ? o.as_of >= after : o.as_of > after))
    .sort((a, b) => (a.as_of as string).localeCompare(b.as_of as string));
  return later.length > 0 ? later[0].id : '';
}

function noSnapshotNote(after: string, inclusive: boolean): string {
  const rel = inclusive ? 'de' : 'posterior a';
  return `No hay ningún snapshot con fecha ${rel} ${fmtDate(after)}: crea uno rodando el actual en Mercado.`;
}

type FormName = 'close' | 'dedesignate' | 'release';

/** Lo que comparten las acciones de la relación: quién está en uso, el snapshot activo y cómo recargar. */
interface ActionProps {
  hedgeId: number;
  options: SnapshotOption[];
  /** Snapshot con el que arranca el selector (el primero aceptable); `''` si no hay ninguno. */
  defaultId: string;
  /** Nota que se muestra cuando no hay snapshot aceptable. */
  emptyNote: string;
  /** Este es el formulario que el usuario está usando; los demás borran sus errores. */
  active: boolean;
  onUse(): void;
  onDone(): Promise<void>;
  onBanner(message: string | null): void;
}

interface FieldErrorProps {
  message?: string;
}

function FieldError({ message }: FieldErrorProps) {
  if (!message) return null;
  return (
    <div className="hedge__error" role="alert">
      {message}
    </div>
  );
}

interface SnapshotSelectProps {
  id: string;
  label: string;
  options: SnapshotOption[];
  value: string;
  invalid: boolean;
  onChange(value: string): void;
}

function SnapshotSelect({ id, label, options, value, invalid, onChange }: SnapshotSelectProps) {
  return (
    <div className="hedge__field">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        className="hedge__input"
        value={value}
        aria-invalid={invalid ? true : undefined}
        onChange={(e) => onChange(e.target.value)}
      >
        {value === '' && <option value="">Elige el snapshot</option>}
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.as_of ? `${o.label} · ${o.as_of}` : o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Cierra un periodo con el snapshot elegido (por omisión el activo). */
function CloseForm(p: ActionProps) {
  const [choice, setChoice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const value = choice ?? p.defaultId;

  useEffect(() => {
    if (!p.active) setError(null);
  }, [p.active]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    p.onUse();
    if (value === '') {
      setError('Indica el snapshot');
      return;
    }
    setError(null);
    p.onBanner(null);
    setBusy(true);
    try {
      await closeHedgePeriod(p.hedgeId, value);
      await p.onDone();
    } catch (err) {
      if (err instanceof ApiError && err.field === 'snapshot') setError(localizeMessage(err.message));
      else p.onBanner(describe(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="hedge__form"
      onSubmit={submit}
      onFocus={p.onUse}
      noValidate
      aria-label="Cerrar periodo"
    >
      <h3>Cerrar periodo</h3>
      <SnapshotSelect
        id="hedge-close-snapshot"
        label="Snapshot del cierre"
        options={p.options}
        value={value}
        invalid={error != null}
        onChange={setChoice}
      />
      {value === '' && <span className="hedge__hint">{p.emptyNote}</span>}
      <FieldError message={error ?? undefined} />
      <button type="submit" className="hedge__btn" disabled={busy}>
        Cerrar periodo
      </button>
    </form>
  );
}

interface DedesignateFormProps extends ActionProps {
  /** Snapshot con el que siempre se puede desdesignar: el del último cierre o, sin cierres, el de la designación. */
  fallback: { id: string; kind: 'del último cierre' | 'de la designación' };
}

type DedesignateField = 'snapshot' | 'cause' | 'reason';

/**
 * Desdesignación: snapshot (su fecha es la de la desdesignación; si es posterior al último cierre el
 * backend mide hasta ella), causa (IFRS 9 6.5.6 no admite desdesignar sin causa) y motivo.
 */
function DedesignateForm(p: DedesignateFormProps) {
  const [choice, setChoice] = useState<string | null>(null);
  const [cause, setCause] = useState<DedesignationCause | ''>('');
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<Partial<Record<DedesignateField, string>>>({});
  const [busy, setBusy] = useState(false);
  const snapshot = choice ?? p.defaultId;

  useEffect(() => {
    if (!p.active) setErrors({});
  }, [p.active]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    p.onUse();
    const local: typeof errors = {};
    if (snapshot === '') local.snapshot = 'Indica el snapshot';
    if (cause === '') local.cause = 'Indica la causa';
    if (reason.trim() === '') local.reason = 'Indica el motivo';
    if (cause === '' || Object.keys(local).length > 0) {
      setErrors(local);
      return;
    }
    setErrors({});
    p.onBanner(null);
    setBusy(true);
    try {
      await dedesignateHedge(p.hedgeId, { snapshot, reason: reason.trim(), cause });
      await p.onDone();
    } catch (err) {
      if (err instanceof ApiError && (err.field === 'snapshot' || err.field === 'cause' || err.field === 'reason')) {
        setErrors({ [err.field]: localizeMessage(err.message) });
      } else {
        p.onBanner(describe(err));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="hedge__form"
      onSubmit={submit}
      onFocus={p.onUse}
      noValidate
      aria-label="Desdesignar"
    >
      <h3>Desdesignar</h3>
      <SnapshotSelect
        id="hedge-dedesignate-snapshot"
        label="Snapshot de la desdesignación"
        options={p.options}
        value={snapshot}
        invalid={errors.snapshot != null}
        onChange={setChoice}
      />
      {snapshot === '' && <span className="hedge__hint">{p.emptyNote}</span>}
      <FieldError message={errors.snapshot} />
      {errors.snapshot && snapshot !== p.fallback.id && (
        <button type="button" className="hedge__link-btn" onClick={() => setChoice(p.fallback.id)}>
          {`Usar el snapshot ${p.fallback.kind} (${p.fallback.id})`}
        </button>
      )}
      <div className="hedge__field">
        <label htmlFor="hedge-dedesignate-cause">Causa</label>
        <select
          id="hedge-dedesignate-cause"
          className="hedge__input"
          value={cause}
          aria-invalid={errors.cause ? true : undefined}
          onChange={(e) => setCause(e.target.value as DedesignationCause | '')}
        >
          <option value="">Elige la causa</option>
          {(Object.keys(DEDESIGNATION_CAUSE_LABEL) as DedesignationCause[]).map((c) => (
            <option key={c} value={c}>
              {DEDESIGNATION_CAUSE_LABEL[c]}
            </option>
          ))}
        </select>
        <FieldError message={errors.cause} />
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
        <FieldError message={errors.reason} />
      </div>
      <button type="submit" className="hedge__btn" disabled={busy}>
        Desdesignar
      </button>
    </form>
  );
}

interface ReleaseFormProps extends ActionProps {
  /** Reserva vigente (con signo): lo que queda por liberar. */
  balance: number;
}

type ReleaseField = 'snapshot' | 'cause' | 'amount';

/**
 * Liberación de la reserva congelada de una relación desdesignada o concluida. El monto se teclea sin signo (vacío =
 * todo el saldo); al enviarlo lleva el signo del saldo, que es lo que el backend exige.
 */
function ReleaseForm(p: ReleaseFormProps) {
  const [choice, setChoice] = useState<string | null>(null);
  const [cause, setCause] = useState<ReleaseCause | ''>('');
  const [amount, setAmount] = useState('');
  const [errors, setErrors] = useState<Partial<Record<ReleaseField, string>>>({});
  const [busy, setBusy] = useState(false);
  const snapshot = choice ?? p.defaultId;

  useEffect(() => {
    if (!p.active) setErrors({});
  }, [p.active]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    p.onUse();
    const local: typeof errors = {};
    if (snapshot === '') local.snapshot = 'Indica el snapshot';
    if (cause === '') local.cause = 'Indica la causa';
    const typed = amount.trim() === '' ? null : parseNumber(amount);
    if (amount.trim() !== '' && typed == null) local.amount = 'Indica un número';
    if (cause === '' || Object.keys(local).length > 0) {
      setErrors(local);
      return;
    }
    setErrors({});
    p.onBanner(null);
    setBusy(true);
    try {
      const body: { snapshot: string; cause: ReleaseCause; amount?: number } = { snapshot, cause };
      // El backend pide el monto con el signo del saldo: se teclea la magnitud y aquí se le da ese signo.
      if (typed != null) body.amount = Math.sign(p.balance) * Math.abs(typed);
      await releaseHedgeReserve(p.hedgeId, body);
      await p.onDone();
    } catch (err) {
      if (err instanceof ApiError && (err.field === 'snapshot' || err.field === 'cause' || err.field === 'amount')) {
        setErrors({ [err.field]: localizeMessage(err.message) });
      } else {
        p.onBanner(describe(err));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="hedge__form"
      onSubmit={submit}
      onFocus={p.onUse}
      noValidate
      aria-label="Liberar reserva"
    >
      <h3>Liberar reserva</h3>
      <SnapshotSelect
        id="hedge-release-snapshot"
        label="Snapshot de la liberación"
        options={p.options}
        value={snapshot}
        invalid={errors.snapshot != null}
        onChange={setChoice}
      />
      {snapshot === '' && <span className="hedge__hint">{p.emptyNote}</span>}
      <FieldError message={errors.snapshot} />
      <div className="hedge__field">
        <label htmlFor="hedge-release-cause">Causa de la liberación</label>
        <select
          id="hedge-release-cause"
          className="hedge__input"
          value={cause}
          aria-invalid={errors.cause ? true : undefined}
          onChange={(e) => setCause(e.target.value as ReleaseCause | '')}
        >
          <option value="">Elige la causa</option>
          {(Object.keys(RELEASE_CAUSE_LABEL) as ReleaseCause[]).map((c) => (
            <option key={c} value={c}>
              {RELEASE_CAUSE_LABEL[c]}
            </option>
          ))}
        </select>
        <FieldError message={errors.cause} />
      </div>
      <div className="hedge__field">
        <label htmlFor="hedge-release-amount">Monto a liberar</label>
        <input
          id="hedge-release-amount"
          type="text"
          inputMode="decimal"
          autoComplete="off"
          className="hedge__input num"
          value={amount}
          aria-invalid={errors.amount ? true : undefined}
          onChange={(e) => setAmount(e.target.value)}
        />
        <span className="hedge__hint">{`Vacío libera todo el saldo (${money(p.balance)})`}</span>
        <FieldError message={errors.amount} />
      </div>
      <button type="submit" className="hedge__btn" disabled={busy}>
        Liberar reserva
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

/** Asientos con el total de cargos y abonos; sirve para un cierre de periodo y para una liberación de reserva. */
function EntriesTable(p: { entries: JournalEntry[]; label: string; totalLabel: string }) {
  const { entries } = p;
  return (
    <div className="hedge__table-wrap">
      <table className="hedge__table" aria-label={p.label}>
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
            <th>{p.totalLabel}</th>
            <td className="num">{money(sum(entries.map((en) => en.debit)))}</td>
            <td className="num">{money(sum(entries.map((en) => en.credit)))}</td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function JournalTable({ period }: { period: HedgePeriod }) {
  return (
    <EntriesTable entries={period.entries} label={`Asientos ${period.as_of}`} totalLabel="Total del periodo" />
  );
}

/** Liberación de la reserva congelada: la causa, lo liberado, lo que queda y su asiento. */
function ReleaseJournal({ event }: { event: HedgeDetail['events'][number] }) {
  const d = event.data as unknown as ReserveReleaseData;
  return (
    <div className="hedge__journal">
      <h3>{`Liberación de reserva al ${fmtDate(event.event_date)}`}</h3>
      <p className="hedge__meta">
        {`${RELEASE_CAUSE_LABEL[d.cause]} · Monto ${money(d.amount)} · Reserva restante ${money(d.reserve_after)}`}
      </p>
      <EntriesTable
        entries={d.entries}
        label={`Asientos de liberación ${event.event_date}`}
        totalLabel="Total de la liberación"
      />
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
  // Formulario en uso: los errores de los demás se borran para que no queden mensajes de otra acción.
  const [activeForm, setActiveForm] = useState<FormName | null>(null);
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

  const use = (name: FormName) => () => {
    if (name === activeForm) return;
    setActiveForm(name);
    setActionError(null);
  };

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
  const concluded = hedge?.status === 'concluida';
  const pendingReserve = hedge != null && Math.abs(hedge.oci_balance) >= HALF_CENT;
  // La reserva de una relación desdesignada o concluida se libera a mano; la activa aún se mueve con los cierres.
  const canRelease = (frozen || concluded) && pendingReserve;
  const lastPeriod = hedge && hedge.periods.length > 0 ? hedge.periods[hedge.periods.length - 1] : null;
  const releases = hedge ? hedge.events.filter((e) => e.type === 'reserve_release') : [];
  // Cerrar y desdesignar arrancan en el primer snapshot posterior al último cierre (o a la designación); liberar,
  // en el primero que no sea anterior al último evento.
  const sinceDate = hedge ? (hedge.last_close ?? hedge.designation_date) : '';
  const lastEventDate = hedge ? hedge.events.reduce((m, e) => (e.event_date > m ? e.event_date : m), hedge.designation_date) : '';
  const closeDefault = hedge ? firstSnapshotAfter(options, sinceDate, false) : '';
  const releaseDefault = hedge ? firstSnapshotAfter(options, lastEventDate, true) : '';

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
            <div>
              <dt>Documentada el</dt>
              <dd className="num">{fmtDate(hedge.created_at.slice(0, 10))}</dd>
            </div>
            {frozen && hedge.dedesignation ? (
              <>
                <div>
                  <dt>Reserva congelada</dt>
                  <dd className="num">{money(hedge.dedesignation.frozen_oci)}</dd>
                </div>
                <div>
                  <dt>Reserva vigente</dt>
                  <dd className="num">{money(hedge.oci_balance)}</dd>
                </div>
                <div>
                  <dt>Desdesignada el</dt>
                  <dd className="num">{fmtDate(hedge.dedesignation.date)}</dd>
                </div>
                {hedge.dedesignation.cause && (
                  <div>
                    <dt>Causa</dt>
                    <dd>{DEDESIGNATION_CAUSE_LABEL[hedge.dedesignation.cause]}</dd>
                  </div>
                )}
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

          {concluded && pendingReserve && <p className="hedge__meta">{CONCLUDED_NOTE}</p>}

          {hedge.warnings.length > 0 && (
            <section className="hedge__block hedge__warnings" aria-label="Avisos de designación">
              <h2>Avisos de designación</h2>
              <ul>
                {hedge.warnings.map((w) => (
                  <li key={w.code}>{w.message}</li>
                ))}
              </ul>
            </section>
          )}

          {(hedge.status === 'activa' || canRelease) && asOf != null && (
            <section className="hedge__block" aria-label="Acciones">
              <h2>Acciones</h2>
              {actionError && (
                <div className="hedge__banner" role="alert">
                  {actionError}
                </div>
              )}
              <div className="hedge__actions">
                {hedge.status === 'activa' ? (
                  <>
                    <CloseForm
                      hedgeId={hedge.id}
                      options={options}
                      defaultId={closeDefault}
                      emptyNote={noSnapshotNote(sinceDate, false)}
                      active={activeForm === 'close'}
                      onUse={use('close')}
                      onDone={reload}
                      onBanner={setActionError}
                    />
                    <DedesignateForm
                      hedgeId={hedge.id}
                      options={options}
                      defaultId={closeDefault}
                      emptyNote={noSnapshotNote(sinceDate, false)}
                      active={activeForm === 'dedesignate'}
                      onUse={use('dedesignate')}
                      onDone={reload}
                      onBanner={setActionError}
                      fallback={
                        lastPeriod
                          ? { id: lastPeriod.snapshot, kind: 'del último cierre' }
                          : { id: hedge.designation_snapshot, kind: 'de la designación' }
                      }
                    />
                  </>
                ) : (
                  <ReleaseForm
                    hedgeId={hedge.id}
                    options={options}
                    defaultId={releaseDefault}
                    emptyNote={noSnapshotNote(lastEventDate, true)}
                    active={activeForm === 'release'}
                    onUse={use('release')}
                    onDone={reload}
                    onBanner={setActionError}
                    balance={hedge.oci_balance}
                  />
                )}
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
            {hedge.periods.length === 0 && releases.length === 0 ? (
              <p className="hedge__meta">Sin asientos</p>
            ) : (
              <>
                {hedge.periods.map((p) => (
                  <div key={p.id} className="hedge__journal">
                    <h3>{`Periodo al ${fmtDate(p.as_of)}`}</h3>
                    <JournalTable period={p} />
                  </div>
                ))}
                {releases.map((e) => (
                  <ReleaseJournal key={e.id} event={e} />
                ))}
              </>
            )}
          </section>
        </>
      )}
    </section>
  );
}
