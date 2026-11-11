import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError, createHedge, listHedges, listTrades } from '../api/client';
import type {
  CreateHedgeBody,
  HedgeDocumentation,
  HedgeSummary,
  HedgeType,
  ItemKind,
  ItemTerms,
  Trade,
} from '../api/types';
import { AccountingNotice } from '../components/AccountingNotice';
import {
  DEFAULT_EFFECTIVENESS_METHOD,
  DOC_FIELD_LABEL,
  HEDGE_STATUS_LABEL,
  HEDGE_TYPE_LABEL,
  ITEM_KIND_LABEL,
  SIDE_LABEL,
  VALID_ITEM_KINDS,
} from '../lib/hedgeLabels';
import { fmtDate, fmtMoney, fmtNumber } from '../lib/format';
import { useSnapshot } from '../state/SnapshotContext';
import { productTitle } from './pricers/registry';
import './HedgesScreen.css';

const LOAN_INDICES = ['TIIE-F', 'SOFR'] as const;

/** Lados que admite cada partida (los mismos que valida el backend). */
const SIDES: Record<ItemKind, string[]> = {
  floating_loan: ['pays_floating', 'receives_floating'],
  fixed_loan: ['pays_fixed', 'receives_fixed'],
  forecast_fx: ['buy_usd', 'sell_usd'],
};

const DOC_KEYS = Object.keys(DOC_FIELD_LABEL) as (keyof HedgeDocumentation)[];

function describe(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

function isLoan(kind: ItemKind): boolean {
  return kind !== 'forecast_fx';
}

/** Claves de error (`field` del backend) que tienen un campo visible en el formulario. */
function visibleFields(kind: ItemKind): string[] {
  const terms = isLoan(kind)
    ? ['index', 'notional', 'start_date', 'maturity_date', 'side']
    : ['amount_usd', 'date', 'side'];
  return ['trade_id', 'hedge_type', 'item_kind', ...terms, 'fraction', 'hedge_ratio', ...DOC_KEYS];
}

/** Número tecleado (acepta comas y espacios); `null` si está vacío o no es finito. */
function parseNumber(raw: string): number | null {
  const cleaned = raw.replace(/[,\s]/g, '');
  if (cleaned === '') return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

interface FormValues {
  tradeId: string;
  hedgeType: HedgeType;
  itemKind: ItemKind;
  index: string;
  notional: string;
  startDate: string;
  maturityDate: string;
  amountUsd: string;
  fxDate: string;
  side: string;
  fraction: string;
  hedgeRatio: string;
  documentation: HedgeDocumentation;
}

function initialValues(): FormValues {
  return {
    tradeId: '',
    hedgeType: 'cash_flow',
    itemKind: 'floating_loan',
    index: LOAN_INDICES[0],
    notional: '',
    startDate: '',
    maturityDate: '',
    amountUsd: '',
    fxDate: '',
    side: SIDES.floating_loan[0],
    fraction: '100',
    hedgeRatio: '1',
    documentation: {
      risk_management_objective: '',
      hedged_risk: '',
      effectiveness_method: DEFAULT_EFFECTIVENESS_METHOD,
      ineffectiveness_sources: '',
    },
  };
}

function operationLabel(t: { id: number; product: string; counterparty: string }): string {
  return `#${t.id} · ${productTitle(t.product)} · ${t.counterparty}`;
}

interface FieldProps {
  id: string;
  label: string;
  error?: string;
  suffix?: string;
  children: (invalid: true | undefined) => ReactNode;
}

/** Etiqueta, control y el error del backend (o local) de ese campo. */
function Field({ id, label, error, suffix, children }: FieldProps) {
  return (
    <div className="hedges__field">
      <label htmlFor={id}>{label}</label>
      <div className="hedges__control">
        {children(error ? true : undefined)}
        {suffix && <span className="hedges__suffix">{suffix}</span>}
      </div>
      {error && (
        <div className="hedges__error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

function NewHedgeForm({ snapshotId }: { snapshotId: string }) {
  const navigate = useNavigate();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [v, setV] = useState<FormValues>(initialValues);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listTrades().then(
      (list) => {
        if (cancelled) return;
        setTrades(list);
        // La primera operación queda elegida, salvo que ya se haya escogido otra.
        setV((cur) => (cur.tradeId === '' && list.length > 0 ? { ...cur, tradeId: String(list[0].id) } : cur));
      },
      (e) => {
        if (!cancelled) setTradesError(describe(e));
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) =>
    setV((cur) => ({ ...cur, [key]: value }));

  const changeType = (hedgeType: HedgeType) => {
    const itemKind = VALID_ITEM_KINDS[hedgeType][0];
    setV((cur) => ({ ...cur, hedgeType, itemKind, side: SIDES[itemKind][0] }));
  };

  const changeKind = (itemKind: ItemKind) =>
    setV((cur) => ({ ...cur, itemKind, side: SIDES[itemKind][0] }));

  const setDoc = (key: keyof HedgeDocumentation, value: string) =>
    setV((cur) => ({ ...cur, documentation: { ...cur.documentation, [key]: value } }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const local: Record<string, string> = {};
    const tradeId = parseNumber(v.tradeId);
    if (tradeId == null) local.trade_id = 'Elige una operación';

    let itemTerms: ItemTerms | null = null;
    if (isLoan(v.itemKind)) {
      const notional = parseNumber(v.notional);
      if (notional == null) local.notional = 'Indica un número';
      if (notional != null) {
        itemTerms = {
          index: v.index,
          notional,
          start_date: v.startDate,
          maturity_date: v.maturityDate,
          side: v.side,
        } as ItemTerms;
      }
    } else {
      const amount = parseNumber(v.amountUsd);
      if (amount == null) local.amount_usd = 'Indica un número';
      if (amount != null) {
        itemTerms = { amount_usd: amount, date: v.fxDate, side: v.side } as ItemTerms;
      }
    }

    const pct = parseNumber(v.fraction);
    if (pct == null) local.fraction = 'Indica un número';
    const ratio = parseNumber(v.hedgeRatio);
    if (ratio == null) local.hedge_ratio = 'Indica un número';

    if (Object.keys(local).length > 0 || tradeId == null || itemTerms == null || pct == null || ratio == null) {
      setErrors(local);
      setBanner(null);
      return;
    }

    const body: CreateHedgeBody = {
      trade_id: tradeId,
      snapshot: snapshotId,
      hedge_type: v.hedgeType,
      item_kind: v.itemKind,
      item_terms: itemTerms,
      // El formulario captura %; el backend recibe el decimal (sin ruido de coma flotante).
      fraction: Number((pct / 100).toPrecision(12)),
      hedge_ratio: ratio,
      documentation: v.documentation,
    };

    setErrors({});
    setBanner(null);
    setBusy(true);
    try {
      const created = await createHedge(body);
      navigate(`/coberturas/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.field != null && visibleFields(v.itemKind).includes(err.field)) {
        setErrors({ [err.field]: err.message });
      } else {
        setBanner(describe(err));
      }
    } finally {
      setBusy(false);
    }
  };

  const loan = isLoan(v.itemKind);

  return (
    <form className="hedges__form" onSubmit={submit} noValidate aria-label="Nueva relación de cobertura">
      <h2>Nueva relación</h2>
      {(banner ?? tradesError) && (
        <div className="hedges__banner" role="alert">
          {banner ?? tradesError}
        </div>
      )}

      <div className="hedges__grid">
        <Field id="hedge-trade" label="Operación" error={errors.trade_id}>
          {(invalid) => (
            <select
              id="hedge-trade"
              className="hedges__input"
              value={v.tradeId}
              aria-invalid={invalid}
              onChange={(e) => set('tradeId', e.target.value)}
            >
              {trades.map((t) => (
                <option key={t.id} value={t.id}>
                  {operationLabel(t)}
                </option>
              ))}
            </select>
          )}
        </Field>

        <Field id="hedge-type" label="Tipo" error={errors.hedge_type}>
          {(invalid) => (
            <select
              id="hedge-type"
              className="hedges__input"
              value={v.hedgeType}
              aria-invalid={invalid}
              onChange={(e) => changeType(e.target.value as HedgeType)}
            >
              {(Object.keys(HEDGE_TYPE_LABEL) as HedgeType[]).map((t) => (
                <option key={t} value={t}>
                  {HEDGE_TYPE_LABEL[t]}
                </option>
              ))}
            </select>
          )}
        </Field>

        <Field id="hedge-kind" label="Partida" error={errors.item_kind}>
          {(invalid) => (
            <select
              id="hedge-kind"
              className="hedges__input"
              value={v.itemKind}
              aria-invalid={invalid}
              onChange={(e) => changeKind(e.target.value as ItemKind)}
            >
              {VALID_ITEM_KINDS[v.hedgeType].map((k) => (
                <option key={k} value={k}>
                  {ITEM_KIND_LABEL[k]}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>

      <div className="hedges__grid">
        {loan && (
          <Field id="hedge-index" label="Índice" error={errors.index}>
            {(invalid) => (
              <select
                id="hedge-index"
                className="hedges__input"
                value={v.index}
                aria-invalid={invalid}
                onChange={(e) => set('index', e.target.value)}
              >
                {LOAN_INDICES.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        {loan ? (
          <Field id="hedge-notional" label="Nocional" error={errors.notional}>
            {(invalid) => (
              <input
                id="hedge-notional"
                type="text"
                inputMode="decimal"
                autoComplete="off"
                className="hedges__input num"
                value={v.notional}
                aria-invalid={invalid}
                onChange={(e) => set('notional', e.target.value)}
              />
            )}
          </Field>
        ) : (
          <Field id="hedge-amount" label="Monto USD" error={errors.amount_usd}>
            {(invalid) => (
              <input
                id="hedge-amount"
                type="text"
                inputMode="decimal"
                autoComplete="off"
                className="hedges__input num"
                value={v.amountUsd}
                aria-invalid={invalid}
                onChange={(e) => set('amountUsd', e.target.value)}
              />
            )}
          </Field>
        )}
        {loan ? (
          <>
            <Field id="hedge-start" label="Inicio" error={errors.start_date}>
              {(invalid) => (
                <input
                  id="hedge-start"
                  type="date"
                  className="hedges__input"
                  value={v.startDate}
                  aria-invalid={invalid}
                  onChange={(e) => set('startDate', e.target.value)}
                />
              )}
            </Field>
            <Field id="hedge-maturity" label="Vencimiento" error={errors.maturity_date}>
              {(invalid) => (
                <input
                  id="hedge-maturity"
                  type="date"
                  className="hedges__input"
                  value={v.maturityDate}
                  aria-invalid={invalid}
                  onChange={(e) => set('maturityDate', e.target.value)}
                />
              )}
            </Field>
          </>
        ) : (
          <Field id="hedge-fxdate" label="Fecha" error={errors.date}>
            {(invalid) => (
              <input
                id="hedge-fxdate"
                type="date"
                className="hedges__input"
                value={v.fxDate}
                aria-invalid={invalid}
                onChange={(e) => set('fxDate', e.target.value)}
              />
            )}
          </Field>
        )}
        <Field id="hedge-side" label="Lado" error={errors.side}>
          {(invalid) => (
            <select
              id="hedge-side"
              className="hedges__input"
              value={v.side}
              aria-invalid={invalid}
              onChange={(e) => set('side', e.target.value)}
            >
              {SIDES[v.itemKind].map((s) => (
                <option key={s} value={s}>
                  {SIDE_LABEL[s]}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>

      <div className="hedges__grid">
        <Field id="hedge-fraction" label="Fracción" error={errors.fraction} suffix="%">
          {(invalid) => (
            <input
              id="hedge-fraction"
              type="text"
              inputMode="decimal"
              autoComplete="off"
              className="hedges__input num"
              value={v.fraction}
              aria-invalid={invalid}
              onChange={(e) => set('fraction', e.target.value)}
            />
          )}
        </Field>
        <Field id="hedge-ratio" label="Razón de cobertura" error={errors.hedge_ratio}>
          {(invalid) => (
            <input
              id="hedge-ratio"
              type="text"
              inputMode="decimal"
              autoComplete="off"
              className="hedges__input num"
              value={v.hedgeRatio}
              aria-invalid={invalid}
              onChange={(e) => set('hedgeRatio', e.target.value)}
            />
          )}
        </Field>
      </div>

      <div className="hedges__docs">
        {DOC_KEYS.map((key) => (
          <Field key={key} id={`hedge-doc-${key}`} label={DOC_FIELD_LABEL[key]} error={errors[key]}>
            {(invalid) => (
              <textarea
                id={`hedge-doc-${key}`}
                className="hedges__input hedges__textarea"
                rows={2}
                value={v.documentation[key]}
                aria-invalid={invalid}
                onChange={(e) => setDoc(key, e.target.value)}
              />
            )}
          </Field>
        ))}
      </div>

      <div>
        <button type="submit" className="hedges__btn" disabled={busy}>
          Crear relación
        </button>
      </div>
    </form>
  );
}

export default function HedgesScreen() {
  const { snapshotId } = useSnapshot();
  const [hedges, setHedges] = useState<HedgeSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setHedges(await listHedges());
      setError(null);
    } catch (e) {
      setHedges(null);
      setError(describe(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="hedges" aria-label="Coberturas">
      <header className="hedges__head">
        <h1>Coberturas</h1>
        <button
          type="button"
          className="hedges__btn"
          aria-expanded={formOpen}
          onClick={() => setFormOpen((open) => !open)}
        >
          Nueva relación
        </button>
      </header>
      <AccountingNotice />

      {error && (
        <div className="hedges__banner" role="alert">
          {error}
        </div>
      )}

      {formOpen && <NewHedgeForm snapshotId={snapshotId} />}

      {hedges == null && !error && <p className="hedges__meta">Cargando…</p>}
      {hedges != null && hedges.length === 0 && <p className="hedges__meta">Sin relaciones de cobertura</p>}
      {hedges != null && hedges.length > 0 && (
        <div className="hedges__scroll">
          <table className="hedges__table">
            <thead>
              <tr>
                <th>Id</th>
                <th>Operación</th>
                <th>Tipo</th>
                <th>Partida</th>
                <th className="num">Fracción</th>
                <th>Estado</th>
                <th className="num">Último cierre</th>
                <th className="num">Saldo de reserva</th>
              </tr>
            </thead>
            <tbody>
              {hedges.map((h) => (
                <tr key={h.id}>
                  <td>
                    <Link to={`/coberturas/${h.id}`}>{h.id}</Link>
                  </td>
                  <td>
                    <Link to={`/portafolio/${h.trade_id}`}>{operationLabel({ id: h.trade_id, product: h.product, counterparty: h.counterparty })}</Link>
                  </td>
                  <td>{HEDGE_TYPE_LABEL[h.hedge_type]}</td>
                  <td>{ITEM_KIND_LABEL[h.item_kind]}</td>
                  <td className="num">{fmtNumber(h.fraction * 100, 2)} %</td>
                  <td>{HEDGE_STATUS_LABEL[h.status]}</td>
                  <td className="num">{h.last_close ? fmtDate(h.last_close) : '—'}</td>
                  <td className="num">{fmtMoney(h.oci_balance, 'MXN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
