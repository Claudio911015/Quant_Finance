import type { EChartsCoreOption } from 'echarts/core';
import type { XvaCounterparty, XvaIncrementalResponse } from '../../api/xvaTypes';
import { EChart, cssColor } from '../../components/EChart';
import { fmtDate, fmtMoney, fmtNumber } from '../../lib/format';

type Series = { name: string; data: number[]; color: string; dashed?: boolean };

/** Opción común de las gráficas de perfil: fechas en el eje X, MXN en millones en el Y. */
function lineOption(dates: string[], series: Series[]): EChartsCoreOption {
  const axis = {
    axisLine: { lineStyle: { color: cssColor('--border-strong') } },
    axisLabel: { color: cssColor('--text-dim') },
  };
  return {
    animation: false,
    grid: { left: 64, right: 16, top: 40, bottom: 40 },
    legend: { top: 0, right: 0, textStyle: { color: cssColor('--text-dim') } },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number) => fmtMoney(v, 'MXN'),
      backgroundColor: cssColor('--bg-elev'),
      borderColor: cssColor('--border-strong'),
      textStyle: { color: cssColor('--text') },
    },
    xAxis: { type: 'category', data: dates.map(fmtDate), ...axis },
    yAxis: {
      type: 'value',
      axisLabel: { color: cssColor('--text-dim'), formatter: (v: number) => `${fmtNumber(v / 1e6, 1)} M` },
      axisLine: axis.axisLine,
      splitLine: { lineStyle: { color: cssColor('--border') } },
    },
    series: series.map((s) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      symbolSize: 4,
      lineStyle: { color: s.color, width: 2, type: s.dashed ? 'dashed' : 'solid' },
      itemStyle: { color: s.color },
    })),
  };
}

/** Perfil de exposición sin descontar de una contraparte: EPE, ENE y PFE contra fecha, en MXN. */
export function profileOption(cp: XvaCounterparty, pfeQuantile?: number): EChartsCoreOption {
  const pfeName = pfeQuantile === undefined ? 'PFE' : `PFE ${parseFloat((pfeQuantile * 100).toFixed(4))} %`;
  return lineOption(
    cp.profile.map((p) => p.date),
    [
      { name: 'EPE', data: cp.profile.map((p) => p.epe_mxn), color: cssColor('--accent') },
      { name: 'ENE', data: cp.profile.map((p) => p.ene_mxn), color: cssColor('--pos') },
      { name: pfeName, data: cp.profile.map((p) => p.pfe_mxn), color: cssColor('--warn') },
    ],
  );
}

type IncrementalPoint = XvaIncrementalResponse['profile'][number];

/** EPE y ENE del conjunto antes y después de la operación candidata, superpuestos. */
export function incrementalOption(profile: IncrementalPoint[]): EChartsCoreOption {
  const accent = cssColor('--accent');
  const pos = cssColor('--pos');
  return lineOption(
    profile.map((p) => p.date),
    [
      { name: 'EPE antes', data: profile.map((p) => p.epe_before_mxn), color: accent, dashed: true },
      { name: 'EPE después', data: profile.map((p) => p.epe_after_mxn), color: accent },
      { name: 'ENE antes', data: profile.map((p) => p.ene_before_mxn), color: pos, dashed: true },
      { name: 'ENE después', data: profile.map((p) => p.ene_after_mxn), color: pos },
    ],
  );
}

export function XvaProfileChart({ cp, pfeQuantile }: { cp: XvaCounterparty; pfeQuantile: number }) {
  return <EChart option={profileOption(cp, pfeQuantile)} height={280} ariaLabel="Perfil de exposición" />;
}

export function IncrementalChart({ profile }: { profile: IncrementalPoint[] }) {
  return (
    <EChart
      option={incrementalOption(profile)}
      height={260}
      ariaLabel="EPE y ENE antes y después de la operación"
    />
  );
}
