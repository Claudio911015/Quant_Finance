import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, MarkLineComponent, TooltipComponent } from 'echarts/components';
import { init, use, type ECharts, type EChartsCoreOption } from 'echarts/core';
import { SVGRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';
import type { Cashflow } from '../../api/types';
import { fmtNumber } from '../../lib/format';

use([BarChart, LineChart, GridComponent, MarkLineComponent, TooltipComponent, SVGRenderer]);

export type ChartData =
  | { kind: 'cashflows'; cashflows: Cashflow[]; currency: string }
  | {
      kind: 'payoff';
      params: Record<string, unknown>;
      pv: number;
      currency: string;
    };

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
export function payoffSeries(
  params: Record<string, unknown>,
  pv: number,
): { strike: number; spots: number[]; pnl: number[] } | null {
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

function buildOption(data: ChartData): EChartsCoreOption | null {
  const text = token('--text-dim', '#8b95a5');
  const line = token('--border', '#262d38');
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
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: token('--bg-elev', '#161b22'),
      borderColor: token('--border-strong', '#354050'),
      textStyle: { color: token('--text', '#d8dee9'), fontSize: 12 },
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

  const series = payoffSeries(data.params, data.pv);
  if (!series) return null;
  return {
    ...base,
    xAxis: {
      type: 'category',
      data: series.spots.map((s) => fmtNumber(s, 2)),
      name: 'Subyacente al vencimiento',
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { color: text, fontSize: 11 },
      ...axis,
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
        name: `Resultado neto (${data.currency})`,
        data: series.pnl,
        showSymbol: false,
        lineStyle: { color: accent, width: 2 },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: text, type: 'dashed' },
          label: { color: text, fontSize: 11 },
          data: [
            { yAxis: 0, label: { show: false } },
            { xAxis: fmtNumber(series.strike, 2), label: { formatter: 'Strike' } },
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
