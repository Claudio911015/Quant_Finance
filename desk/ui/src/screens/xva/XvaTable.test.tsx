import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { XvaCounterparty } from '../../api/xvaTypes';
import { XVA_FIXTURE } from './fixtures';
import { XvaTable } from './XvaTable';

const [ALFA, BETA] = XVA_FIXTURE.counterparties;

const rowOf = (name: string) => screen.getByRole('button', { name }).closest('tr') as HTMLElement;

describe('XvaTable', () => {
  it('muestra una fila por contraparte con PV neto, CVA, DVA, FVA, total y exposiciones máximas', () => {
    render(<XvaTable counterparties={XVA_FIXTURE.counterparties} selected={ALFA.counterparty} onSelect={() => {}} />);
    const table = screen.getByRole('table', { name: 'XVA por contraparte' });
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Contraparte',
      'PV neto',
      'CVA',
      'DVA',
      'FVA',
      'Total XVA',
      'EPE máx.',
      'PFE máx.',
      'Operaciones',
    ]);
    expect(within(table).getAllByRole('row')).toHaveLength(1 + 3);

    const alfa = within(rowOf(ALFA.counterparty));
    expect(alfa.getByText('MXN -755,000.00')).toBeTruthy(); // PV neto
    expect(alfa.getByText('MXN 120,000.00')).toBeTruthy(); // CVA
    expect(alfa.getByText('± 4,000.00')).toBeTruthy(); // error estándar del CVA
    expect(alfa.getByText('MXN 30,000.00')).toBeTruthy(); // DVA
    expect(alfa.getByText('MXN 5,000.00')).toBeTruthy(); // FVA
    expect(alfa.getByText('MXN 95,000.00')).toBeTruthy(); // total
    expect(alfa.getByText('MXN 2,400,000.00')).toBeTruthy(); // EPE máx.
    expect(alfa.getByText('MXN 3,100,000.00')).toBeTruthy(); // PFE máx.
  });

  it('cuenta las operaciones incluidas y las excluidas', () => {
    render(<XvaTable counterparties={XVA_FIXTURE.counterparties} selected={null} onSelect={() => {}} />);
    expect(within(rowOf(ALFA.counterparty)).getByText('2 incluidas · 1 excluida')).toBeTruthy();
    expect(within(rowOf(BETA.counterparty)).getByText('3 incluidas')).toBeTruthy();
  });

  it('marca la contraparte elegida y avisa al elegir otra', () => {
    const onSelect = vi.fn();
    render(<XvaTable counterparties={XVA_FIXTURE.counterparties} selected={BETA.counterparty} onSelect={onSelect} />);
    expect(screen.getByRole('button', { name: BETA.counterparty }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: ALFA.counterparty }).getAttribute('aria-pressed')).toBe('false');
    expect(rowOf(BETA.counterparty).getAttribute('data-selected')).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: ALFA.counterparty }));
    expect(onSelect).toHaveBeenCalledWith(ALFA.counterparty);
  });

  it('rotula el origen del crédito: curva sintética, respaldo plano o supuesto', () => {
    const flat: XvaCounterparty = {
      ...BETA,
      counterparty: 'Banco Delta',
      credit: { kind: 'flat', recovery: 0.4, source: null, assumed: false, note: null },
    };
    const assumed: XvaCounterparty = {
      ...BETA,
      counterparty: 'Banco Epsilon',
      credit: {
        kind: 'assumed',
        recovery: 0.4,
        source: null,
        assumed: true,
        note: 'Supuesto: 1 % anual y recuperación 40 % (sin curva ni parámetros)',
      },
    };
    render(<XvaTable counterparties={[ALFA, flat, assumed]} selected={null} onSelect={() => {}} />);
    expect(within(rowOf(ALFA.counterparty)).getByText('Curva sintética')).toBeTruthy();
    expect(within(rowOf('Banco Delta')).getByText('Respaldo plano')).toBeTruthy();
    const tag = within(rowOf('Banco Epsilon')).getByText('Supuesto');
    expect(tag.getAttribute('title')).toBe('Supuesto: 1 % anual y recuperación 40 % (sin curva ni parámetros)');
  });

  it('sin contrapartes lo dice en lugar de pintar una tabla vacía', () => {
    render(<XvaTable counterparties={[]} selected={null} onSelect={() => {}} />);
    expect(screen.getByText('No hay contrapartes con operaciones vivas en este snapshot.')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });
});
