import { describe, expect, it } from 'vitest';
import type { Source, SourceKey, SourceKind } from '../api/types';
import {
  asOfText,
  componentName,
  kindText,
  qualityText,
  SOURCE_KEYS,
  sourcesTooltip,
} from './provenance';

const SOURCES: Record<SourceKey, Source> = {
  'curve:TIIE-F': { kind: 'synthetic', label: 'Sintética: sin datos libres', as_of: null },
  'curve:SOFR': { kind: 'proxy', label: 'Aproximada: Treasuries par', as_of: '2026-11-10' },
  spot: { kind: 'live', label: 'FRED DEXMXUS', as_of: '2026-11-06' },
  surface: { kind: 'synthetic', label: 'Sintética: sin datos de volatilidad', as_of: null },
  hw: { kind: 'synthetic', label: 'Sintéticos (heredados de MX-DEMO)', as_of: null },
  factor_vols: { kind: 'mixed', label: 'SOFR y USDMXN medidas; TIIE-F sintética', as_of: '2026-11-10' },
  factor_corr: { kind: 'synthetic', label: 'Sintéticas (heredadas de MX-DEMO)', as_of: null },
};

describe('provenance', () => {
  it('qualityText: un texto por calidad de datos', () => {
    expect(qualityText('synthetic')).toBe('Datos sintéticos');
    expect(qualityText('mixed')).toBe('Datos mixtos');
    expect(qualityText('live')).toBe('Datos de mercado');
  });

  it.each<[SourceKind, string]>([
    ['live', 'En vivo'],
    ['proxy', 'Aproximada'],
    ['synthetic', 'Sintética'],
    ['mixed', 'Mixta'],
  ])('kindText(%s) = %s', (kind, text) => {
    expect(kindText(kind)).toBe(text);
  });

  it('componentName nombra los siete componentes', () => {
    expect(SOURCE_KEYS.map(componentName)).toEqual([
      'Curva TIIE-F',
      'Curva SOFR',
      'Spot USDMXN',
      'Superficie de volatilidad',
      'Parámetros Hull-White',
      'Volatilidades de factores',
      'Correlaciones de factores',
    ]);
  });

  it('asOfText devuelve la fecha o "sin fecha"', () => {
    expect(asOfText('2026-11-10')).toBe('2026-11-10');
    expect(asOfText(null)).toBe('sin fecha');
  });

  it('sourcesTooltip: una línea por componente, en orden, con tipo, rótulo y fecha', () => {
    expect(sourcesTooltip(SOURCES).split('\n')).toEqual([
      'Curva TIIE-F: Sintética — Sintética: sin datos libres (sin fecha)',
      'Curva SOFR: Aproximada — Aproximada: Treasuries par (2026-11-10)',
      'Spot USDMXN: En vivo — FRED DEXMXUS (2026-11-06)',
      'Superficie de volatilidad: Sintética — Sintética: sin datos de volatilidad (sin fecha)',
      'Parámetros Hull-White: Sintética — Sintéticos (heredados de MX-DEMO) (sin fecha)',
      'Volatilidades de factores: Mixta — SOFR y USDMXN medidas; TIIE-F sintética (2026-11-10)',
      'Correlaciones de factores: Sintética — Sintéticas (heredadas de MX-DEMO) (sin fecha)',
    ]);
  });
});
