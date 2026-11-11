import type { DataQuality, Source, SourceKey, SourceKind } from '../api/types';

const QUALITY_TEXT: Record<DataQuality, string> = {
  synthetic: 'Datos sintéticos',
  mixed: 'Datos mixtos',
  live: 'Datos de mercado',
};

const KIND_TEXT: Record<SourceKind, string> = {
  live: 'En vivo',
  proxy: 'Aproximada',
  synthetic: 'Sintética',
  mixed: 'Mixta',
};

// El orden de las llaves es el orden de las líneas del tooltip.
const COMPONENT_NAME: Record<SourceKey, string> = {
  'curve:TIIE-F': 'Curva TIIE-F',
  'curve:SOFR': 'Curva SOFR',
  spot: 'Spot USDMXN',
  surface: 'Superficie de volatilidad',
  hw: 'Parámetros Hull-White',
  factor_vols: 'Volatilidades de factores',
  factor_corr: 'Correlaciones de factores',
};

export const SOURCE_KEYS = Object.keys(COMPONENT_NAME) as SourceKey[];

export const qualityText = (quality: DataQuality): string => QUALITY_TEXT[quality];

export const kindText = (kind: SourceKind): string => KIND_TEXT[kind];

export const componentName = (key: SourceKey): string => COMPONENT_NAME[key];

export const asOfText = (asOf: string | null): string => asOf ?? 'sin fecha';

/** Una línea por componente: "<Nombre>: <Tipo> — <rótulo> (<fecha>)". */
export function sourcesTooltip(sources: Record<SourceKey, Source>): string {
  return SOURCE_KEYS.map((key) => {
    const { kind, label, as_of } = sources[key];
    return `${componentName(key)}: ${kindText(kind)} — ${label} (${asOfText(as_of)})`;
  }).join('\n');
}
