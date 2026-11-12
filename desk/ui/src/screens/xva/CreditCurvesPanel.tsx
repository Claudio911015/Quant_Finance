import { useState, type FormEvent } from 'react';
import type { EChartsCoreOption } from 'echarts/core';
import { getCreditCurves, putCreditCurve } from '../../api/xvaClient';
import type { CreditCurve } from '../../api/xvaTypes';
import { EChart, cssColor } from '../../components/EChart';
import { fmtDate, fmtNumber } from '../../lib/format';
import { fromPb, fromPercent, readNumber, toApiError, toPbText, toPercentText, useLoad } from './common';
import './CreditCurvesPanel.css';

const DEFAULT_RECOVERY = 0.4;
const pct = (dec: number) => `${fmtNumber(dec * 100, 2)} %`;

/** Supervivencia por año (el año 0 vale 1) de una curva. */
export function survivalOption(curve: CreditCurve): EChartsCoreOption {
  const grid = curve.grid ?? [];
  const axis = {
    axisLine: { lineStyle: { color: cssColor('--border-strong') } },
    axisLabel: { color: cssColor('--text-dim') },
  };
  return {
    animation: false,
    grid: { left: 56, right: 16, top: 16, bottom: 36 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number) => pct(v),
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
    },
    xAxis: { type: 'category', data: ['0', ...grid.map((g) => String(g.year))], name: 'años', ...axis },
    yAxis: {
      type: 'value',
      scale: true,
      max: 1,
      axisLabel: { color: cssColor('--text-dim'), formatter: (v: number) => `${fmtNumber(v * 100, 0)} %` },
      axisLine: axis.axisLine,
      splitLine: { lineStyle: { color: cssColor('--border') } },
    },
    series: [
      {
        name: 'Supervivencia',
        type: 'line',
        data: [1, ...grid.map((g) => g.survival)],
        symbolSize: 4,
        lineStyle: { color: cssColor('--accent'), width: 2 },
        itemStyle: { color: cssColor('--accent') },
      },
    ],
  };
}

interface Row {
  tenor: string;
  spread: string;
}

function CurveEditor({
  curve,
  snapshotId,
  onSaved,
}: {
  curve: CreditCurve;
  snapshotId: string;
  onSaved: () => void;
}) {
  const [rows, setRows] = useState<Row[]>(() =>
    curve.quotes.map((q) => ({ tenor: String(q.tenor_years), spread: toPbText(q.spread) })),
  );
  const [recovery, setRecovery] = useState(toPercentText(curve.recovery ?? DEFAULT_RECOVERY));
  const [quotesError, setQuotesError] = useState<string | null>(null);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const setCell = (i: number, key: keyof Row, value: string) => {
    setRows((cur) => cur.map((r, j) => (j === i ? { ...r, [key]: value } : r)));
    setQuotesError(null);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setQuotesError(null);
    setRecoveryError(null);
    const rec = readNumber(recovery);
    const quotes = rows.map((r) => ({ tenor: readNumber(r.tenor), spread: readNumber(r.spread) }));
    let blocked = false;
    if (rec === null) {
      setRecoveryError('Ingresa un número válido');
      blocked = true;
    }
    if (quotes.length === 0) {
      setQuotesError('Agrega al menos una cotización');
      blocked = true;
    } else if (quotes.some((q) => q.tenor === null || q.spread === null)) {
      setQuotesError('Ingresa un número válido en cada plazo y spread');
      blocked = true;
    }
    if (blocked || rec === null) return;
    setSaving(true);
    try {
      await putCreditCurve(curve.entity, {
        recovery: fromPercent(rec),
        quotes: quotes.map((q) => ({ tenor_years: q.tenor as number, spread: fromPb(q.spread as number) })),
        snapshot: snapshotId,
      });
      onSaved();
    } catch (err) {
      const apiError = toApiError(err);
      if (apiError.field === 'quotes') setQuotesError(apiError.message);
      else if (apiError.field === 'recovery') setRecoveryError(apiError.message);
      else setFormError(apiError.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="xva-curves__editor" onSubmit={submit} noValidate>
      <div className="xva-field xva-field--narrow">
        <label htmlFor="credit-recovery">Recuperación (%)</label>
        <input
          id="credit-recovery"
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={recovery}
          aria-invalid={recoveryError ? true : undefined}
          aria-describedby={recoveryError ? 'credit-recovery-error' : undefined}
          onChange={(e) => {
            setRecovery(e.target.value);
            setRecoveryError(null);
          }}
        />
        {recoveryError && (
          <span className="xva-field__error" id="credit-recovery-error" role="alert">
            {recoveryError}
          </span>
        )}
      </div>

      <div className="xva-scroll">
        <table className="xva-table" aria-label="Cotizaciones de CDS">
          <thead>
            <tr>
              <th className="num">Plazo (años)</th>
              <th className="num">Spread (pb)</th>
              <th>
                <span className="xva-sr">Quitar</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="num">
                  <input
                    className="xva-cell"
                    type="text"
                    inputMode="decimal"
                    aria-label={`Plazo ${i + 1} (años)`}
                    value={r.tenor}
                    aria-invalid={quotesError ? true : undefined}
                    aria-describedby={quotesError ? 'credit-quotes-error' : undefined}
                    onChange={(e) => setCell(i, 'tenor', e.target.value)}
                  />
                </td>
                <td className="num">
                  <input
                    className="xva-cell"
                    type="text"
                    inputMode="decimal"
                    aria-label={`Spread ${i + 1} (pb)`}
                    value={r.spread}
                    aria-invalid={quotesError ? true : undefined}
                    aria-describedby={quotesError ? 'credit-quotes-error' : undefined}
                    onChange={(e) => setCell(i, 'spread', e.target.value)}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="xva-btn xva-btn--ghost"
                    aria-label={`Quitar cotización ${i + 1}`}
                    onClick={() => {
                      setRows((cur) => cur.filter((_, j) => j !== i));
                      setQuotesError(null);
                    }}
                  >
                    Quitar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {quotesError && (
        <p className="xva-note xva-note--error" id="credit-quotes-error" role="alert">
          {quotesError}
        </p>
      )}
      <div className="xva-actions">
        <button
          type="button"
          className="xva-btn"
          onClick={() => setRows((cur) => [...cur, { tenor: '', spread: '' }])}
        >
          Agregar cotización
        </button>
        <button type="submit" className="xva-btn xva-btn--primary" disabled={saving}>
          Guardar curva
        </button>
      </div>
      {formError && (
        <p className="xva-note xva-note--error" role="alert">
          {formError}
        </p>
      )}
    </form>
  );
}

function PdTable({ curve }: { curve: CreditCurve }) {
  const grid = curve.grid ?? [];
  return (
    <div className="xva-scroll">
      <table className="xva-table" aria-label="Probabilidad de incumplimiento por año">
        <thead>
          <tr>
            <th className="num">Año</th>
            <th className="num">Supervivencia</th>
            <th className="num">PD acumulada</th>
            <th className="num">PD del año</th>
          </tr>
        </thead>
        <tbody>
          {grid.map((g) => (
            <tr key={g.year}>
              <td className="num">{g.year}</td>
              <td className="num">{pct(g.survival)}</td>
              <td className="num">{pct(g.cumulative_pd)}</td>
              <td className="num">{pct(g.marginal_pd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Curvas de crédito sintéticas: cotizaciones de CDS editables y las probabilidades que implican. */
export function CreditCurvesPanel({ snapshotId, onSaved }: { snapshotId: string; onSaved: () => void }) {
  const [tick, setTick] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const { data, error, loading } = useLoad(() => getCreditCurves(snapshotId), snapshotId, tick);

  const curve = data ? (data.curves.find((c) => c.entity === selected) ?? data.curves[0]) : undefined;

  return (
    <section className="xva-card" aria-labelledby="credit-curves-title">
      <div className="xva-card__head">
        <h2 id="credit-curves-title">Curvas de crédito</h2>
        <span className="xva-tag xva-tag--warn">Sintética</span>
      </div>
      {error && (
        <p className="xva-note xva-note--error" role="alert">
          {error.message}
        </p>
      )}
      {data && curve && (
        <div className={loading ? 'is-loading' : undefined}>
          <p className="xva-note xva-note--plain">
            <span>{data.source.label}</span>. Ajuste por tramos contra la curva {data.discount_curve} del snapshot.
          </p>
          <div className="xva-field xva-field--narrow">
            <label htmlFor="credit-entity">Entidad</label>
            <select id="credit-entity" value={curve.entity} onChange={(e) => setSelected(e.target.value)}>
              {data.curves.map((c) => (
                <option key={c.entity} value={c.entity}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          {curve.id === null && curve.kind === 'counterparty' && (
            <p className="xva-note xva-note--plain">Sin curva: el XVA usa el respaldo plano de esta contraparte.</p>
          )}
          {curve.id !== null && (
            <p className="xva-note xva-note--plain">
              Versión vigente #{curve.id}
              {curve.as_of ? ` del ${fmtDate(curve.as_of)}` : ''} · {curve.history.length}{' '}
              {curve.history.length === 1 ? 'versión' : 'versiones'} en el historial.
            </p>
          )}
          <div className="xva-curves">
            {/* La clave reinicia el borrador al cambiar de entidad o al guardar una versión nueva. */}
            <CurveEditor
              key={`${curve.entity}:${curve.id}`}
              curve={curve}
              snapshotId={snapshotId}
              onSaved={() => {
                setTick((t) => t + 1);
                onSaved();
              }}
            />
            <div className="xva-curves__result">
              {curve.error ? (
                <p className="xva-note xva-note--error" role="alert">
                  No se pudo ajustar la curva: {curve.error}
                </p>
              ) : curve.grid ? (
                <>
                  <EChart option={survivalOption(curve)} height={200} ariaLabel="Curva de supervivencia" />
                  <PdTable curve={curve} />
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
