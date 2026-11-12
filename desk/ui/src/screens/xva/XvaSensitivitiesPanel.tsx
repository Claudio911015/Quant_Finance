import { useEffect, useRef, useState } from 'react';
import { BarChart } from 'echarts/charts';
import { use, type EChartsCoreOption } from 'echarts/core';
import { getXvaSensitivities } from '../../api/xvaClient';
import type {
  XvaSensCredit,
  XvaSensCurve,
  XvaSensRow,
  XvaSensitivitiesResponse,
} from '../../api/xvaTypes';
import { EChart, cssColor } from '../../components/EChart';
import { fmtMoney, fmtNumber } from '../../lib/format';
import { toApiError } from './common';
import './XvaSensitivitiesPanel.css';

// `EChart` solo registra líneas y mapas de calor; el CVA por pilar necesita barras.
use([BarChart]);

/** Pilares de todas las curvas por plazo en días (pilares con los mismos días comparten categoría). */
function pillarCategories(curves: XvaSensCurve[]): { days: number; name: string }[] {
  const byDays = new Map<number, Set<string>>();
  for (const c of curves) {
    for (const p of c.pillars) byDays.set(p.days, (byDays.get(p.days) ?? new Set<string>()).add(p.label));
  }
  // El plazo en días va en el nombre: dos pilares con la misma etiqueta y días distintos (1M a 28 y a 30 días) no chocan.
  return [...byDays]
    .sort(([a], [b]) => a - b)
    .map(([days, labels]) => ({ days, name: `${[...labels].join(' / ')} (${days} d)` }));
}

/** CVA por pilar, una serie de barras por curva; donde una curva no tiene pilar, sin barra. */
export function sensitivityOption(curves: XvaSensCurve[]): EChartsCoreOption {
  const cats = pillarCategories(curves);
  const dim = cssColor('--text-dim');
  const colors = [cssColor('--accent'), cssColor('--pos'), cssColor('--warn')];
  return {
    animation: false,
    grid: { left: 72, right: 16, top: 40, bottom: 84 },
    legend: { top: 0, right: 0, textStyle: { color: dim } },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number | null) => (v === null || v === undefined ? '—' : fmtMoney(v, 'MXN')),
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
    },
    xAxis: {
      type: 'category',
      data: cats.map((c) => c.name),
      axisLine: { lineStyle: { color: cssColor('--border-strong') } },
      axisLabel: { color: dim, rotate: 45, interval: 0, formatter: (v: string) => v.replace(/ \(\d+ d\)$/, '') },
    },
    yAxis: {
      type: 'value',
      name: 'CVA, MXN por pb',
      nameTextStyle: { color: dim },
      axisLabel: { color: dim, formatter: (v: number) => fmtNumber(v, 0) },
      axisLine: { lineStyle: { color: cssColor('--border-strong') } },
      splitLine: { lineStyle: { color: cssColor('--border') } },
    },
    series: curves.map((c, i) => {
      const cvaAt = new Map(c.pillars.map((p) => [p.days, p.cva]));
      return {
        name: c.curve,
        type: 'bar',
        data: cats.map((cat) => cvaAt.get(cat.days) ?? null),
        itemStyle: { color: colors[i % colors.length] },
      };
    }),
  };
}

function Cells({ row }: { row: XvaSensRow }) {
  return (
    <>
      <td className="num">{fmtMoney(row.cva, 'MXN')}</td>
      <td className="num">{fmtMoney(row.dva, 'MXN')}</td>
      <td className="num">{fmtMoney(row.fva, 'MXN')}</td>
      <td className="num">{fmtMoney(row.total, 'MXN')}</td>
    </>
  );
}

function Head({ first }: { first: string }) {
  return (
    <thead>
      <tr>
        <th>{first}</th>
        <th className="num">CVA</th>
        <th className="num">DVA</th>
        <th className="num">FVA</th>
        <th className="num">Total</th>
      </tr>
    </thead>
  );
}

function Group({ title, unit, children }: { title: string; unit?: string; children: React.ReactNode }) {
  return (
    <tbody>
      <tr className="xva-sens__group">
        <th colSpan={5} scope="rowgroup">
          {title}
          {unit && <span className="xva-sens__unit"> · {unit}</span>}
        </th>
      </tr>
      {children}
    </tbody>
  );
}

function Line({ label, row, strong }: { label: string; row: XvaSensRow; strong?: boolean }) {
  return (
    <tr className={strong ? 'xva-sens__dv01' : undefined}>
      <th scope="row">{label}</th>
      <Cells row={row} />
    </tr>
  );
}

/** Sin CDS cotizados (curva plana o supuesta) la sensibilidad de crédito es la de la intensidad de cada tramo. */
function creditLines(credit: XvaSensCredit): { unit: string; lines: { label: string; row: XvaSensRow }[] } {
  if (credit.cds.length > 0) {
    return { unit: 'MXN por pb de cotización de CDS', lines: credit.cds.map((c) => ({ label: `CDS ${c.tenor}`, row: c })) };
  }
  return {
    unit: 'MXN por pb de intensidad',
    lines: credit.hazards.map((h) => ({
      label: h.to_years === null ? 'Intensidad (tramo único)' : `Intensidad hasta ${fmtNumber(h.to_years, 2)} años`,
      row: h,
    })),
  };
}

function CurvesTable({ curves }: { curves: XvaSensCurve[] }) {
  return (
    <div className="xva-scroll">
      <table className="xva-table" aria-label="Sensibilidad por curva y pilar">
        <Head first="Pilar" />
        {curves.map((c) => (
          <Group key={c.curve} title={c.curve}>
            {c.pillars.map((p) => (
              <Line key={p.days} label={p.label} row={p} />
            ))}
            <Line label="DV01 paralelo" row={c.dv01} strong />
          </Group>
        ))}
      </table>
    </div>
  );
}

function FactorsTable({ r }: { r: XvaSensitivitiesResponse }) {
  const entities = [
    { title: `Crédito de ${r.counterparty}`, ...creditLines(r.credit.counterparty) },
    { title: 'Crédito propio', ...creditLines(r.credit.own) },
  ].filter((e) => e.lines.length > 0);
  return (
    <div className="xva-scroll">
      <table className="xva-table" aria-label="Sensibilidad a tipo de cambio, volatilidades, crédito y fondeo">
        <Head first="Factor" />
        <Group title="Tipo de cambio" unit={r.units.fx}>
          <Line label={r.fx.label} row={r.fx} />
        </Group>
        <Group title="Volatilidades" unit={r.units.vols}>
          {r.vols.map((v) => (
            <Line key={v.param} label={v.label} row={v} />
          ))}
        </Group>
        {entities.map((e) => (
          <Group key={e.title} title={e.title} unit={e.unit}>
            {e.lines.map((l) => (
              <Line key={l.label} label={l.label} row={l.row} />
            ))}
          </Group>
        ))}
        <Group title="Fondeo" unit={r.units.funding}>
          <Line label="Diferencial de fondeo" row={r.funding} />
        </Group>
      </table>
    </div>
  );
}

function Result({ r }: { r: XvaSensitivitiesResponse }) {
  const { xva } = r;
  return (
    <div className="xva-sens__result">
      {r.warnings.length > 0 && (
        <div className="xva-note xva-note--warn" role="status">
          <ul className="xva-list">
            {r.warnings.map((w, i) => (
              <li key={i}>{w.message}</li>
            ))}
          </ul>
        </div>
      )}
      {r.empty_reason ? (
        <p className="xva-note xva-note--warn" role="status">
          {r.empty_reason}
        </p>
      ) : (
        <>
          <p className="xva-note xva-note--plain">
            XVA de la contraparte: CVA {fmtMoney(xva.cva_mxn, 'MXN')} · DVA {fmtMoney(xva.dva_mxn, 'MXN')} · FVA{' '}
            {fmtMoney(xva.fva_mxn, 'MXN')} · total {fmtMoney(xva.total_mxn, 'MXN')}. Total = CVA − DVA + FVA.
          </p>
          <p className="xva-note xva-note--plain">
            Calculado en {fmtNumber(r.elapsed_s, 1)} s (una valuación del XVA tarda {fmtNumber(r.valuation_elapsed_s, 2)} s).
            Por choques sobre los {fmtNumber(r.n_inputs, 0)} insumos tardaría unos {fmtNumber(r.bump_cost_estimate_s, 1)} s.
          </p>
          <h3 className="xva-subtitle">Curvas de tasas ({r.units.curves})</h3>
          <CurvesTable curves={r.curves} />
          <div className="xva-sens__chart">
            <EChart
              option={sensitivityOption(r.curves)}
              height={320}
              ariaLabel="CVA por pilar de cada curva, en MXN por pb"
            />
          </div>
          <h3 className="xva-subtitle">Otros factores de riesgo</h3>
          <FactorsTable r={r} />
          <p className="xva-foot">
            Un pilar o plazo en cero queda más allá del último vencimiento de la contraparte: no influye en su
            exposición.
          </p>
        </>
      )}
      {r.assumptions.length > 0 && (
        <ul className="xva-list">
          {r.assumptions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
      <p className="xva-foot">
        {r.method}. Jacobiano de CDS: {r.cds_jacobian}. {fmtNumber(r.paths, 0)} trayectorias, semilla {r.seed}.
      </p>
    </div>
  );
}

interface Props {
  snapshotId: string;
  counterparty: string;
}

/** Sensibilidades del XVA de una contraparte, a petición: tardan segundos, no se piden con el resto de la pantalla. */
export function XvaSensitivitiesPanel({ snapshotId, counterparty }: Props) {
  const [calculating, setCalculating] = useState(false);
  const [result, setResult] = useState<XvaSensitivitiesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ticket = useRef(0);

  // Otra contraparte u otro snapshot: lo calculado ya no aplica y una respuesta en vuelo se descarta.
  useEffect(() => {
    setResult(null);
    setError(null);
    setCalculating(false);
    return () => {
      ticket.current++;
    };
  }, [snapshotId, counterparty]);

  const calculate = async () => {
    const mine = ++ticket.current;
    setError(null);
    setCalculating(true);
    try {
      const response = await getXvaSensitivities(snapshotId, counterparty);
      if (mine === ticket.current) setResult(response);
    } catch (e) {
      if (mine === ticket.current) {
        setResult(null);
        setError(toApiError(e).message);
      }
    } finally {
      if (mine === ticket.current) setCalculating(false);
    }
  };

  return (
    <section className="xva-card" aria-labelledby="xva-sens-title">
      <h2 id="xva-sens-title">Sensibilidades de {counterparty}</h2>
      <p className="xva-note xva-note--plain">
        Derivadas del CVA, DVA y FVA respecto de las curvas, el tipo de cambio, las volatilidades, el crédito y el
        fondeo, por diferenciación adjunta. Se calculan a petición y pueden tardar decenas de segundos en conjuntos
        largos (muchas operaciones o vencimientos a 10 años); al terminar se muestra el tiempo real y lo que habría
        tardado por choques.
      </p>
      <div className="xva-actions">
        <button type="button" className="xva-btn xva-btn--primary" onClick={calculate} disabled={calculating}>
          {calculating ? 'Calculando…' : 'Calcular sensibilidades'}
        </button>
      </div>
      {calculating && (
        <p className="xva-note xva-note--plain" aria-live="polite">
          Calculando las sensibilidades: puede tardar decenas de segundos. El resto de la pantalla sigue disponible.
        </p>
      )}
      {error && (
        <p className="xva-note xva-note--error" role="alert">
          {error}
        </p>
      )}
      {result && <Result r={result} />}
    </section>
  );
}
