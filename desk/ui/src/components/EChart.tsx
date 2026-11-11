import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import type { ECharts, EChartsCoreOption } from 'echarts/core';
import { HeatmapChart, LineChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  LineChart,
  HeatmapChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

/** ECharts pinta en canvas y no entiende `var(--x)`: se leen los tokens ya resueltos. */
export function cssColor(token: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim();
}

interface EChartProps {
  option: EChartsCoreOption;
  height?: number;
  ariaLabel?: string;
}

/** Wrapper mínimo: `init` al montar, `setOption` al cambiar `option`, `dispose` al desmontar. */
export function EChart({ option, height = 260, ariaLabel }: EChartProps) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<ECharts | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const instance = echarts.init(el);
    chart.current = instance;
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(el);
    return () => {
      observer.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    // Canvas no hereda la fuente de la página: se fija la de la interfaz para los ejes y leyendas.
    chart.current?.setOption(
      { textStyle: { fontFamily: cssColor('--font-sans') }, ...option },
      { notMerge: true },
    );
  }, [option]);

  return <div ref={host} role="img" aria-label={ariaLabel} style={{ width: '100%', height }} />;
}
