import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { CsaInfo, Snapshot } from '../api/types';
import CsaPanel from './CsaPanel';

const CSA: CsaInfo = {
  available: true,
  curve: 'MXN-USD',
  source: { kind: 'synthetic', label: 'Sintético (inventado para demostración)', as_of: null },
  message: null,
  implied_vs_quoted: [
    {
      label: '1M',
      days: 28,
      quoted_points: 0.0438,
      quoted_forward: 18.6438,
      implied_forward: 18.6438,
      parity_forward: 18.645095,
      diff: 0,
    },
    {
      label: '3M',
      days: 84,
      quoted_points: 0.1317,
      quoted_forward: 18.7317,
      implied_forward: 18.731704,
      parity_forward: 18.7351,
      diff: 0.000004,
    },
  ],
};

const SNAPSHOT: Pick<Snapshot, 'csa' | 'fx_forwards' | 'xccy_basis'> = {
  csa: CSA,
  fx_forwards: [
    { days: 28, points: 0.0438, label: '1M' },
    { days: 84, points: 0.1317, label: '3M' },
  ],
  xccy_basis: [
    { days: 728, spread: -0.001, label: '2Y' },
    { days: 1092, spread: -0.0012, label: '3Y' },
  ],
};

const NO_CURVE =
  'El snapshot no trae puntos forward ni base de cross currency swaps: la curva MXN-USD no existe y todo se descuenta con TIIE-F';

describe('CsaPanel', () => {
  it('con curva muestra procedencia sintética y las tres tablas', () => {
    render(<CsaPanel snapshot={SNAPSHOT} />);

    const region = screen.getByRole('region', { name: 'Descuento MXN con colateral en USD' });
    expect(within(region).getByText('Sintética')).toBeTruthy();
    expect(within(region).getByText('Sintético (inventado para demostración)')).toBeTruthy();
    expect(within(region).getByText('sin fecha')).toBeTruthy();

    const forwards = within(region).getByRole('table', { name: 'Puntos forward USDMXN' });
    expect(within(forwards).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Plazo',
      'Días',
      'Puntos',
      'Forward cotizado',
    ]);
    const row1m = within(forwards).getByRole('row', { name: /1M/ });
    expect(within(row1m).getAllByRole('cell').map((c) => c.textContent)).toEqual(['28', '0.0438', '18.6438']);

    const basis = within(region).getByRole('table', { name: 'Base de cross currency swaps' });
    expect(within(basis).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Plazo',
      'Días',
      'Diferencial (pb)',
    ]);
    const row2y = within(basis).getByRole('row', { name: /2Y/ });
    expect(within(row2y).getAllByRole('cell').map((c) => c.textContent)).toEqual(['728', '-10.0']);
    expect(within(within(basis).getByRole('row', { name: /3Y/ })).getAllByRole('cell')[1].textContent).toBe('-12.0');

    const implied = within(region).getByRole('table', { name: 'Forward implícito vs cotizado' });
    expect(within(implied).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Plazo',
      'Cotizado',
      'Implícito',
      'Paridad TIIE-F/SOFR',
      'Diferencia',
    ]);
    const impliedRow = within(implied).getByRole('row', { name: /3M/ });
    expect(within(impliedRow).getAllByRole('cell').map((c) => c.textContent)).toEqual([
      '18.7317',
      '18.7317',
      '18.7351',
      '0.000004',
    ]);
    expect(screen.queryByText(NO_CURVE)).toBeNull();
  });

  it('sin curva muestra el mensaje del backend y ninguna tabla', () => {
    render(
      <CsaPanel
        snapshot={{
          csa: { available: false, curve: 'MXN-USD', source: null, message: NO_CURVE, implied_vs_quoted: [] },
          fx_forwards: null,
          xccy_basis: null,
        }}
      />,
    );

    expect(screen.getByText(NO_CURVE)).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Descuento MXN con colateral en USD' })).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('un snapshot viejo sin csa no pinta nada ni rompe', () => {
    const { container } = render(<CsaPanel snapshot={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('si una lista de cotizaciones viene vacía omite su tabla y las demás siguen', () => {
    render(<CsaPanel snapshot={{ ...SNAPSHOT, xccy_basis: null }} />);

    expect(screen.queryByRole('table', { name: 'Base de cross currency swaps' })).toBeNull();
    expect(screen.getByRole('table', { name: 'Puntos forward USDMXN' })).toBeTruthy();
    expect(screen.getByRole('table', { name: 'Forward implícito vs cotizado' })).toBeTruthy();
  });

  it('un punto forward sin fila de cotejo muestra raya en el forward cotizado', () => {
    render(
      <CsaPanel
        snapshot={{
          ...SNAPSHOT,
          fx_forwards: [{ days: 364, points: 0.5745, label: '1Y' }],
          csa: { ...CSA, implied_vs_quoted: [] },
        }}
      />,
    );

    const row = within(screen.getByRole('table', { name: 'Puntos forward USDMXN' })).getByRole('row', { name: /1Y/ });
    expect(within(row).getAllByRole('cell').map((c) => c.textContent)).toEqual(['364', '0.5745', '—']);
  });
});
