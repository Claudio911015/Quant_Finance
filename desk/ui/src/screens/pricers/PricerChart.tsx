import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, MarkLineComponent, TooltipComponent } from 'echarts/components';
import { init, use, type ECharts, type EChartsCoreOption } from 'echarts/core';
import { SVGRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';
import type { Cashflow, ProductId } from '../../api/types';
import { fmtNumber } from '../../lib/format';

use([BarChart, LineChart, GridComponent, MarkLineComponent, TooltipComponent, SVGRenderer]);

export type ChartData =
  | { kind: 'cashflows'; cashflows: Cashflow[]; currency: string }
  | {
      kind: 'payoff';
      product: ProductId;
      params: Record<string, unknown>;
      pv: number;
      currency: string;
      /** Días del periodo de pago de la curva (del snapshot); solo lo usan cap_floor y swaption. */
      periodDays?: number;
    };

type PayoffData = Extract<ChartData, { kind: 'payoff' }>;

/** Serie de una gráfica de payoff. `spots` es el eje horizontal: precio del subyacente o tasa, según el producto. */
export interface PayoffSeries {
  strike: number;
  spots: number[];
  pnl: number[];
}

/** Lee un token CSS; el valor por defecto solo cubre entornos sin hoja de estilos. */
function token(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

const PAYOFF_POINTS = 61;

/**
 * Payoff neto al vencimiento, solo para presentación: signo × valor intrínseco × tamaño − PV
 * (el PV es la prima: positivo si se compra, negativo si se vende). El PV viene del backend.
 */
export function payoffSeries(params: Record<string, unknown>, pv: number): PayoffSeries | null {
  const strike = Number(params.strike);
  const size = Number(params.notional_usd ?? params.quantity ?? 1);
  if (!(strike > 0) || !(size > 0)) return null;
  const sign = params.side === 'sell' ? -1 : 1;
  const call = params.option_type !== 'put';
  const spots: number[] = [];
  const pnl: number[] = [];
  for (let i = 0; i < PAYOFF_POINTS; i++) {
    const s = strike * (0.7 + (0.6 * i) / (PAYOFF_POINTS - 1));
    const intrinsic = call ? Math.max(s - strike, 0) : Math.max(strike - s, 0);
    spots.push(s);
    pnl.push(sign * intrinsic * size - pv);
  }
  return { strike, spots, pnl };
}

/**
 * Forward FX: pago a vencimiento en MXN = signo × (S_T − K) × nocional_usd, con S_T en ±15 % del
 * strike. No resta el PV: un forward no tiene prima.
 */
export function forwardPayoffSeries(params: Record<string, unknown>): PayoffSeries | null {
  const strike = Number(params.strike);
  const size = Number(params.notional_usd);
  if (!(strike > 0) || !(size > 0)) return null;
  const sign = params.side === 'sell' ? -1 : 1;
  const spots: number[] = [];
  const pnl: number[] = [];
  for (let i = 0; i < PAYOFF_POINTS; i++) {
    const s = strike * (0.85 + (0.3 * i) / (PAYOFF_POINTS - 1));
    spots.push(s);
    pnl.push(sign * (s - strike) * size);
  }
  return { strike, spots, pnl };
}

/** Tasas de max(0, K − 3 pp) a K + 3 pp, con el strike incluido para que el quiebre quede exacto. */
function rateGrid(strike: number): number[] {
  const lo = Math.max(0, strike - 0.03);
  const hi = strike + 0.03;
  const rates = Array.from({ length: PAYOFF_POINTS }, (_, i) => lo + ((hi - lo) * i) / (PAYOFF_POINTS - 1));
  if (!rates.some((r) => Math.abs(r - strike) < 1e-12)) {
    rates.push(strike);
    rates.sort((a, b) => a - b);
  }
  return rates;
}

/**
 * Cap/floor: pago de un periodo contra la tasa de referencia r = nocional × τ × max(±(r − K), 0),
 * con τ = días del periodo / 360 y + para cap, − para floor.
 */
export function capFloorPayoffSeries(params: Record<string, unknown>, periodDays: number | undefined): PayoffSeries | null {
  const strike = Number(params.strike);
  const notional = Number(params.notional);
  if (!(strike > 0) || !(notional > 0) || !(Number(periodDays) > 0)) return null;
  const sign = params.cap_type === 'floor' ? -1 : 1;
  const tau = Number(periodDays) / 360;
  const spots = rateGrid(strike);
  return { strike, spots, pnl: spots.map((r) => notional * tau * Math.max(sign * (r - strike), 0)) };
}

/**
 * Swaption: valor intrínseco al vencimiento = nocional × A × max(±(s − K), 0), con + para payer y
 * − para receiver. A es la anualidad con descuento plano a la tasa s: Σ_{j=1..n} τ / (1 + s·τ)^j,
 * τ = 1/frecuencia = días del periodo / 365 y n = plazo × frecuencia redondeado (como `Swaption`).
 * Es una aproximación: el PV exacto lo calcula el backend.
 */
export function swaptionPayoffSeries(params: Record<string, unknown>, periodDays: number | undefined): PayoffSeries | null {
  const strike = Number(params.strike);
  const notional = Number(params.notional);
  const tenor = Number(params.swap_tenor_years);
  if (!(strike > 0) || !(notional > 0) || !(tenor > 0) || !(Number(periodDays) > 0)) return null;
  const sign = params.swaption_type === 'receiver' ? -1 : 1;
  const tau = Number(periodDays) / 365;
  const n = Math.max(1, Math.round(tenor / tau));
  const annuity = (s: number) => {
    let a = 0;
    for (let j = 1; j <= n; j++) a += tau / (1 + s * tau) ** j;
    return a;
  };
  const spots = rateGrid(strike);
  return { strike, spots, pnl: spots.map((s) => notional * annuity(s) * Math.max(sign * (s - strike), 0)) };
}

interface PayoffText {
  title: string;
  xName: string;
  series: string;
  mark: string;
  note?: string;
}

/** Textos de cada gráfica de payoff; el título va en la tarjeta (PricerForm), el resto en el gráfico. */
export function payoffText(product: ProductId): PayoffText {
  switch (product) {
    case 'fx_forward':
      return {
        title: 'Resultado al vencimiento del forward',
        xName: 'Tipo de cambio al vencimiento (MXN por USD)',
        series: 'Resultado',
        mark: 'Precio pactado',
      };
    case 'cap_floor':
      return {
        title: 'Pago por periodo contra la tasa de referencia',
        xName: 'Tasa de referencia',
        series: 'Pago por periodo',
        mark: 'Strike',
      };
    case 'swaption':
      return {
        title: 'Valor intrínseco al vencimiento contra la tasa swap',
        xName: 'Tasa swap',
        series: 'Valor intrínseco',
        mark: 'Strike',
        note: 'Aproximación con descuento plano; el PV exacto es el de arriba.',
      };
    default:
      return {
        title: 'Resultado al vencimiento, neto de prima',
        xName: 'Subyacente al vencimiento',
        series: 'Resultado neto',
        mark: 'Strike',
      };
  }
}

const fmtSpot = (v: number) => fmtNumber(v, 2);
const fmtPct = (v: number) => `${fmtNumber(v * 100, 2)} %`;

function payoffFor(data: PayoffData): { series: PayoffSeries; fmtX: (v: number) => string } | null {
  let series: PayoffSeries | null;
  let fmtX = fmtSpot;
  switch (data.product) {
    case 'fx_forward':
      series = forwardPayoffSeries(data.params);
      break;
    case 'cap_floor':
      series = capFloorPayoffSeries(data.params, data.periodDays);
      fmtX = fmtPct;
      break;
    case 'swaption':
      series = swaptionPayoffSeries(data.params, data.periodDays);
      fmtX = fmtPct;
      break;
    default:
      series = payoffSeries(data.params, data.pv);
  }
  return series && { series, fmtX };
}

function buildOption(data: ChartData): EChartsCoreOption | null {
  const text = token('--text-dim', '#a59e90');
  const line = token('--border', '#332f29');
  const pos = token('--pos', '#3fb68b');
  const neg = token('--neg', '#e5534b');
  const accent = token('--accent', '#4c9aff');
  const axis = {
    axisLine: { lineStyle: { color: line } },
    axisLabel: { color: text, fontSize: 11 },
    splitLine: { lineStyle: { color: line } },
  };
  const base = {
    animation: false,
    textStyle: { fontFamily: token('--font-sans', 'sans-serif') },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: token('--bg-elev', '#221f1b'),
      borderColor: token('--border-strong', '#4a453c'),
      textStyle: { color: token('--text', '#e9e3d8'), fontSize: 12 },
    },
  };

  if (data.kind === 'cashflows') {
    return {
      ...base,
      xAxis: { type: 'category', data: data.cashflows.map((c) => c.date), ...axis, splitLine: { show: false } },
      yAxis: {
        type: 'value',
        ...axis,
        axisLabel: { ...axis.axisLabel, formatter: (v: number) => fmtNumber(v, 0) },
      },
      series: [
        {
          type: 'bar',
          name: `Flujo (${data.currency})`,
          data: data.cashflows.map((c) => ({
            value: c.amount,
            itemStyle: { color: c.amount >= 0 ? pos : neg },
          })),
        },
      ],
    };
  }

  const view = payoffFor(data);
  if (!view) return null;
  const { series, fmtX } = view;
  const labels = payoffText(data.product);
  const seriesName = `${labels.series} (${data.currency})`;
  return {
    ...base,
    // abajo cabe el nombre del eje, que con el margen de las demás gráficas quedaba recortado
    grid: { ...base.grid, bottom: 30 },
    tooltip: {
      ...base.tooltip,
      formatter: (ps: { value: [number, number] }[]) =>
        `${fmtX(ps[0].value[0])}<br/>${seriesName}: ${fmtNumber(ps[0].value[1], 2)}`,
    },
    xAxis: {
      type: 'value',
      min: series.spots[0],
      max: series.spots[series.spots.length - 1],
      name: labels.xName,
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { color: text, fontSize: 11 },
      ...axis,
      // los extremos no caen en valores redondos y chocan con la marca vecina
      axisLabel: { ...axis.axisLabel, formatter: fmtX, showMinLabel: false, showMaxLabel: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      ...axis,
      axisLabel: { ...axis.axisLabel, formatter: (v: number) => fmtNumber(v, 0) },
    },
    series: [
      {
        type: 'line',
        name: seriesName,
        data: series.spots.map((x, i) => [x, series.pnl[i]]),
        showSymbol: false,
        lineStyle: { color: accent, width: 2 },
        markLine: {
          silent: true,
          symbol: 'none',
          precision: 10, // por defecto redondea a 2 decimales y movía un strike de 7.5 % a 7 %
          lineStyle: { color: text, type: 'dashed' },
          label: { color: text, fontSize: 11 },
          data: [
            { yAxis: 0, label: { show: false } },
            { xAxis: series.strike, label: { formatter: labels.mark } },
          ],
        },
      },
    ],
  };
}

export function PricerChart({ data }: { data: ChartData }) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<ECharts | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const c = init(el, undefined, { renderer: 'svg' });
    chart.current = c;
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => c.resize());
    ro?.observe(el);
    return () => {
      ro?.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    const option = buildOption(data);
    if (option) chart.current?.setOption(option, true);
    else chart.current?.clear();
  }, [data]);

  return <div ref={host} className="pricer__chart" role="img" aria-label="Gráfica del resultado" />;
}
