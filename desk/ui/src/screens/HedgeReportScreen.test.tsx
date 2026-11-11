import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { EffectivenessResponse, HedgeReport } from '../api/types';
import HedgeReportScreen from './HedgeReportScreen';

const mocks = vi.hoisted(() => ({ hedgeReport: vi.fn() }));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return { ...actual, hedgeReport: mocks.hedgeReport };
});

const NOTICE =
  'Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9';

const PROSPECTIVE: EffectivenessResponse = {
  id: 1,
  snapshot: 'MX-DEMO',
  as_of: '2026-11-10',
  critical_terms: [
    { term: 'notional', label: 'Nocional', instrument: 500000000, item: 500000000, result: 'match' },
    { term: 'maturity_date', label: 'Vencimiento', instrument: '2027-11-09', item: '2027-12-07', result: 'mismatch' },
  ],
  scenarios: [
    { name: 'TIIE-F +50 pb', d_inst: 2400000, d_hypo: 2400000, ratio: 1 },
    { name: 'SOFR +50 pb', d_inst: 0, d_hypo: 0, ratio: null },
  ],
  economic_relationship: true,
  in_reference_range: 1,
  scenarios_counted: 1,
  reference_note: 'IFRS 9 no fija un umbral de efectividad: el rango 80 %–125 % se informa solo como referencia',
  warnings: [],
};

const REPORT: HedgeReport = {
  id: 1,
  generated_at: '2026-11-11T18:00:00+00:00',
  notice: NOTICE,
  relationship: {
    id: 1,
    trade_id: 8,
    product: 'irs',
    counterparty: 'Banco Alfa (sintético)',
    fraction: 1,
    hedge_type: 'cash_flow',
    item_kind: 'floating_loan',
    item_terms: {
      index: 'TIIE-F',
      notional: 500000000,
      start_date: '2026-11-10',
      maturity_date: '2027-11-09',
      side: 'pays_floating',
    },
    hedge_ratio: 1,
    designation_date: '2026-11-10',
    designation_snapshot: 'MX-DEMO',
    documentation: {
      risk_management_objective: 'Fijar el costo del crédito sindicado',
      hedged_risk: 'Variabilidad de los intereses por TIIE de Fondeo',
      effectiveness_method: 'Términos críticos y escenarios con derivado hipotético',
      ineffectiveness_sources: 'Diferencias de fechas y nocional',
    },
    hypothetical: {
      product: 'irs',
      trade_date: '2026-11-10',
      start_date: '2026-11-10',
      maturity_date: '2027-11-09',
      params: {},
    },
    designation: { snapshot: 'MX-DEMO', as_of: '2026-11-10', data_quality: 'synthetic', pv_inst: 0, pv_hypo: 0 },
    status: 'activa',
    dedesignation: null,
    warnings: [],
    oci_balance: -125000,
    last_close: '2026-12-15',
    created_at: '2026-11-11T18:00:00+00:00',
  },
  documentation: {
    risk_management_objective: 'Fijar el costo del crédito sindicado',
    hedged_risk: 'Variabilidad de los intereses por TIIE de Fondeo',
    hedged_item: {
      item_kind: 'floating_loan',
      item_terms: {
        index: 'TIIE-F',
        notional: 500000000,
        start_date: '2026-11-10',
        maturity_date: '2027-11-09',
        side: 'pays_floating',
      },
    },
    hedging_instrument: {
      trade_id: 8,
      product: 'irs',
      counterparty: 'Banco Alfa (sintético)',
      fraction: 1,
      notional: 500000000,
      currency: 'MXN',
      start_date: '2026-11-10',
      maturity_date: '2027-11-09',
    },
    hedge_ratio: 1,
    effectiveness_method: 'Términos críticos y escenarios con derivado hipotético',
    ineffectiveness_sources: 'Diferencias de fechas y nocional',
  },
  prospective: PROSPECTIVE,
  periods: [
    {
      id: 1,
      snapshot: 'D1',
      as_of: '2026-12-15',
      data_quality: 'mixed',
      inst_cum: -125000,
      hypo_cum: -125000,
      oci: -125000,
      d_oci: -125000,
      ineffectiveness: 0,
      recycled: 31000,
      item_adjustment: 0,
      fv_result: 0,
      settled_period: 31000,
    },
  ],
  entries_by_period: [
    {
      period_id: 1,
      as_of: '2026-12-15',
      entries: [
        { account: 'Derivado (valor razonable)', debit: 0, credit: 125000, memo: 'Cambio de valor razonable del derivado (fracción designada)' },
        { account: 'ORI — reserva de cobertura', debit: 125000, credit: 0, memo: 'Porción efectiva a la reserva de cobertura' },
        { account: 'Efectivo', debit: 31000, credit: 0, memo: 'Liquidación del derivado en el periodo' },
        { account: 'Resultados — partida cubierta (reciclaje)', debit: 0, credit: 31000, memo: 'Reciclaje: flujo cubierto ocurrido en el periodo' },
      ],
    },
  ],
  entries_total: [
    { account: 'Derivado (valor razonable)', debit: 0, credit: 125000 },
    { account: 'ORI — reserva de cobertura', debit: 125000, credit: 0 },
    { account: 'Efectivo', debit: 31000, credit: 0 },
    { account: 'Resultados — partida cubierta (reciclaje)', debit: 0, credit: 31000 },
  ],
  fair_value_hierarchy: {
    level: 2,
    basis: 'Nivel 2: insumos observables (curvas, tipo de cambio y volatilidades del snapshot)',
    snapshots: [
      { role: 'designation', snapshot: 'MX-DEMO', as_of: '2026-11-10', data_quality: 'synthetic' },
      { role: 'period', snapshot: 'D1', as_of: '2026-12-15', data_quality: 'mixed' },
    ],
  },
  reserve_releases: [],
  reserve: { balance: -125000, frozen: false, note: null, released: 0 },
};

function renderScreen(path = '/coberturas/1/reporte') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/coberturas/:id/reporte" element={<HedgeReportScreen />} />
        <Route path="/coberturas/:id" element={<div>detalle</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mocks.hedgeReport.mockReset();
  mocks.hedgeReport.mockResolvedValue(REPORT);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('HedgeReportScreen', () => {
  it('pide el reporte de la relación y muestra el título y la banda contable', async () => {
    renderScreen();
    expect(await screen.findByRole('heading', { level: 1, name: 'Reporte de relación de cobertura #1' })).toBeTruthy();
    expect(mocks.hedgeReport).toHaveBeenCalledWith(1);
    expect(screen.getByRole('note').textContent).toBe(NOTICE);
  });

  it('muestra todas las secciones del documento', async () => {
    renderScreen();
    await screen.findByText('Documentación de designación');
    for (const title of [
      'Documentación de designación',
      'Prueba prospectiva',
      'Periodos',
      'Asientos por periodo',
      'Acumulado',
      'Jerarquía de valor razonable',
      'Reserva',
      'Supuestos de la metodología',
    ]) {
      expect(screen.getByRole('heading', { level: 2, name: title })).toBeTruthy();
    }
    expect(screen.queryByRole('heading', { level: 2, name: 'Liberaciones de reserva' })).toBeNull();
  });

  it('"Generado" muestra la fecha y la hora legibles, con la zona', async () => {
    renderScreen();
    expect(await screen.findByText('Generado: 2026-11-11 18:00 UTC')).toBeTruthy();
    expect(screen.queryByText(/T18:00:00/)).toBeNull();
  });

  it('declara los supuestos contables de la metodología', async () => {
    renderScreen();
    const section = (await screen.findByRole('heading', { level: 2, name: 'Supuestos de la metodología' })).closest('section')!;
    const text = section.textContent ?? '';
    expect(text).toContain('flujo cubierto proxy');
    expect(text).toContain('componente de tasa de referencia');
    expect(text).toContain('no se amortiza');
    expect(text).toContain('no en gasto por intereses');
    expect(text).toContain('Desdesignar exige una causa');
    expect(text).toContain('fuente de inefectividad');
    expect(text).toContain('devengo del cupón en curso'); // el ajuste de valor razonable no es un valor limpio
    expect(text).toContain('no puede comprobar que la documentación existiera');
  });

  it('muestra la fecha de designación y la de documentación', async () => {
    renderScreen();
    expect(await screen.findByText('Designación al 2026-11-10 · documentada el 2026-11-11')).toBeTruthy();
  });

  it('una cobertura documentada tarde muestra ambas fechas y su aviso', async () => {
    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      relationship: {
        ...REPORT.relationship,
        created_at: '2026-11-20T09:00:00+00:00',
        warnings: [
          { code: 'designation_backdated', message: 'La cobertura se documenta el 2026-11-20, 10 días después de su fecha de designación (2026-11-10)' },
        ],
      },
    });
    renderScreen();
    expect(await screen.findByText('Designación al 2026-11-10 · documentada el 2026-11-20')).toBeTruthy();
    expect(screen.getByText(/se documenta el 2026-11-20, 10 días después/)).toBeTruthy();
  });

  it('una relación concluida muestra la nota de su reserva pendiente', async () => {
    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      relationship: { ...REPORT.relationship, status: 'concluida' },
      reserve: {
        balance: 2500000,
        frozen: true,
        note: 'Instrumento vencido antes que la partida: la reserva se reciclará a resultados cuando ocurra el flujo cubierto',
        released: 0,
      },
    });
    renderScreen();
    expect(await screen.findByText(/^Instrumento vencido antes que la partida/)).toBeTruthy();
  });

  it('el resumen de la prueba prospectiva va en un bloque que no se parte al imprimir', async () => {
    renderScreen();
    const summary = (await screen.findByText('Relación económica: sí')).closest('.hedge-report__summary')!;
    expect(summary).toBeTruthy();
    expect(summary.textContent).toContain('En 80 %–125 %: 1 de 1');
    expect(summary.textContent).toContain(PROSPECTIVE.reference_note);
  });

  it('muestra los avisos de la designación y la desdesignación con su causa', async () => {
    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      relationship: {
        ...REPORT.relationship,
        status: 'desdesignada',
        warnings: [
          { code: 'instrument_off_market', message: 'El instrumento vale MXN 12,500.00 al designar' },
        ],
        dedesignation: {
          date: '2027-01-10',
          reason: 'Prepago del crédito',
          cause: 'instrument_ended',
          snapshot: 'D2',
          frozen_oci: -125000,
        },
      },
    });
    renderScreen();
    const facts = (await screen.findByText('Avisos de la designación')).closest('dl')!;
    expect(facts.textContent).toContain('El instrumento vale MXN 12,500.00 al designar');
    expect(facts.textContent).toContain(
      '2027-01-10 · El instrumento venció, se vendió o se terminó · Prepago del crédito',
    );
  });

  it('sin avisos ni desdesignación no hay esas filas', async () => {
    renderScreen();
    await screen.findByText('Documentación de designación');
    expect(screen.queryByText('Avisos de la designación')).toBeNull();
    expect(screen.queryByText('Desdesignación')).toBeNull();
  });

  it('lista las liberaciones de reserva con su causa, su asiento y la reserva liberada', async () => {
    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      reserve_releases: [
        {
          id: 9,
          snapshot: 'D2',
          as_of: '2027-01-20',
          cause: 'flow_no_longer_expected',
          amount: -40000,
          reserve_after: -85000,
          entries: [
            { account: 'ORI — reserva de cobertura', debit: 0, credit: 40000, memo: 'Liberación de la reserva de cobertura congelada' },
            { account: 'Resultados — inefectividad de cobertura', debit: 40000, credit: 0, memo: 'Reserva a resultados: el flujo cubierto ya no se espera' },
          ],
        },
      ],
      reserve: { balance: -85000, frozen: true, note: 'Reserva congelada al desdesignar', released: -40000 },
    });
    renderScreen();
    const section = (await screen.findByRole('heading', { level: 2, name: 'Liberaciones de reserva' })).closest('section')!;
    expect(within(section).getByRole('heading', { level: 3, name: 'Liberación al 2027-01-20' })).toBeTruthy();
    expect(section.textContent).toContain('El flujo cubierto ya no se espera · Snapshot D2 · Monto MXN -40,000.00 · Reserva restante MXN -85,000.00');
    expect(within(section).getByText('Reserva a resultados: el flujo cubierto ya no se espera')).toBeTruthy();
    expect(screen.getByText('Reserva liberada: MXN -40,000.00')).toBeTruthy();
    expect(screen.getByText('Saldo de la reserva de cobertura: MXN -85,000.00')).toBeTruthy();
  });

  it('con la reserva liberada por completo no repite la nota de congelada', async () => {
    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      reserve: { balance: 0, frozen: true, note: null, released: -125000 },
    });
    renderScreen();
    expect(await screen.findByText('Saldo de la reserva de cobertura: MXN 0.00')).toBeTruthy();
    expect(screen.getByText('Reserva liberada: MXN -125,000.00')).toBeTruthy();
    expect(screen.queryByText(/Reserva congelada/)).toBeNull();
  });

  it('describe la partida y el instrumento con los rótulos de coberturas', async () => {
    renderScreen();
    await screen.findByText('Documentación de designación');
    expect(screen.getByText('Flujo de efectivo')).toBeTruthy();
    expect(
      screen.getByText('Crédito a tasa variable · TIIE-F · MXN 500,000,000.00 · Paga variable · 2026-11-10 a 2027-11-09'),
    ).toBeTruthy();
    expect(screen.getByText(/^Operación #8 · .*Banco Alfa \(sintético\) · 100\.00 % designado/)).toBeTruthy();
    expect(screen.getByText('Fijar el costo del crédito sindicado')).toBeTruthy();
  });

  it('muestra la jerarquía de valor razonable con la procedencia de cada snapshot', async () => {
    renderScreen();
    await screen.findByText('Nivel 2');
    expect(screen.getByText(/^Nivel 2: insumos observables/)).toBeTruthy();
    const section = screen.getByRole('heading', { name: 'Jerarquía de valor razonable' }).closest('section')!;
    const rows = within(section).getAllByRole('row');
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText('Datos sintéticos')).toBeTruthy();
    expect(within(rows[1]).getByText('Designación')).toBeTruthy();
    expect(within(rows[2]).getByText('Datos mixtos')).toBeTruthy();
    expect(within(rows[2]).getByText('Cierre de periodo')).toBeTruthy();
  });

  it('muestra la prueba prospectiva: términos, escenarios y resumen', async () => {
    renderScreen();
    await screen.findByText('Prueba prospectiva');
    expect(screen.getByText('No coincide')).toBeTruthy();
    expect(screen.getByText('Coincide')).toBeTruthy();
    expect(screen.getByText('TIIE-F +50 pb')).toBeTruthy();
    // La razón 1.0000 también aparece como razón de cobertura en la documentación.
    const section = screen.getByRole('heading', { name: 'Prueba prospectiva' }).closest('section')!;
    expect(within(section).getByText('1.0000')).toBeTruthy();
    expect(within(section).getByText('—')).toBeTruthy();
    expect(screen.getByText('Relación económica: sí')).toBeTruthy();
    expect(screen.getByText('En 80 %–125 %: 1 de 1')).toBeTruthy();
    expect(screen.getByText(PROSPECTIVE.reference_note)).toBeTruthy();
  });

  it('un reporte con prospective.error lo muestra como texto', async () => {
    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      prospective: { error: 'La operación ya no está viva al 2028-01-10' },
    });
    renderScreen();
    expect(await screen.findByText('La operación ya no está viva al 2028-01-10')).toBeTruthy();
    expect(screen.queryByText('Términos críticos')).toBeNull();
  });

  it('muestra los asientos por periodo y el acumulado, con totales que cuadran', async () => {
    renderScreen();
    await screen.findByText('Asientos por periodo');
    expect(screen.getByRole('heading', { name: 'Periodo al 2026-12-15' })).toBeTruthy();
    expect(screen.getByText('Porción efectiva a la reserva de cobertura')).toBeTruthy();
    const totals = screen.getAllByRole('row').filter((r) => within(r).queryByText('Total'));
    expect(totals).toHaveLength(2);
    for (const row of totals) {
      const cells = within(row).getAllByRole('columnheader');
      expect(cells[1].textContent).toBe('156,000.00');
      expect(cells[2].textContent).toBe('156,000.00');
    }
  });

  it('en flujo de efectivo los periodos llevan columnas de ORI; en valor razonable no', async () => {
    const { unmount } = renderScreen();
    await screen.findByText('Saldo ORI');
    expect(screen.getByText('Reciclaje')).toBeTruthy();
    unmount();

    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      relationship: { ...REPORT.relationship, hedge_type: 'fair_value' },
    });
    renderScreen();
    await screen.findByText('Ajuste de partida');
    expect(screen.getByText('Resultado del periodo')).toBeTruthy();
    expect(screen.queryByText('Saldo ORI')).toBeNull();
    expect(screen.queryByText('Δ ORI')).toBeNull();
  });

  it('muestra el saldo de la reserva y la nota si está congelada', async () => {
    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      reserve: {
        balance: -125000,
        frozen: true,
        note: 'Reserva congelada al desdesignar: se reciclará a resultados cuando ocurra el flujo cubierto',
        released: 0,
      },
    });
    renderScreen();
    expect(await screen.findByText('Saldo de la reserva de cobertura: MXN -125,000.00')).toBeTruthy();
    expect(screen.getByText(/^Reserva congelada al desdesignar/)).toBeTruthy();
  });

  it('sin periodos ni asientos lo dice, sin tablas vacías', async () => {
    mocks.hedgeReport.mockResolvedValue({
      ...REPORT,
      periods: [],
      entries_by_period: [],
      entries_total: [],
    });
    renderScreen();
    expect(await screen.findByText('Sin cierres de periodo')).toBeTruthy();
    expect(screen.getAllByText('Sin asientos')).toHaveLength(2);
  });

  it('el botón Imprimir llama a window.print y Volver lleva al detalle', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    renderScreen();
    await screen.findByText('Documentación de designación');
    fireEvent.click(screen.getByRole('button', { name: 'Imprimir' }));
    expect(print).toHaveBeenCalledTimes(1);
    const back = screen.getByRole('link', { name: 'Volver' });
    expect(back.getAttribute('href')).toBe('/coberturas/1');
  });

  it('un error del backend se muestra como alerta, con la banda contable', async () => {
    mocks.hedgeReport.mockRejectedValue(new ApiError(404, 'Relación de cobertura inexistente', 'id'));
    renderScreen();
    expect((await screen.findByRole('alert')).textContent).toBe('Relación de cobertura inexistente');
    expect(screen.getByRole('note').textContent).toBe(NOTICE);
  });

  it('un id inválido no pide nada', async () => {
    renderScreen('/coberturas/abc/reporte');
    expect((await screen.findByRole('alert')).textContent).toBe('Cobertura inválida');
    expect(mocks.hedgeReport).not.toHaveBeenCalled();
  });
});
