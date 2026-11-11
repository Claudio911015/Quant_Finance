import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './client';
import {
  cashflowsCsvUrl,
  confirmSettlement,
  createReconciliation,
  fpmlUrl,
  getCashflows,
  getConfirmation,
  getReconciliation,
  getSettings,
  getTradeRef,
  importFpml,
  listReconciliations,
  putSettings,
  putTradeRef,
  reconciliationCsvUrl,
} from './opsClient';

function mockFetch(status: number, body?: unknown) {
  const fn = vi.fn().mockResolvedValue({
    status,
    json: async () => {
      if (body === undefined) throw new Error('sin cuerpo');
      return body;
    },
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('cliente de operaciones: calendario de flujos', () => {
  it('getCashflows arma la consulta sin claves vacías', async () => {
    const fn = mockFetch(200, { rows: [] });
    await getCashflows({ snapshot: 'MX-DEMO', currency: 'USD' });
    expect(fn).toHaveBeenCalledWith('/api/cashflows?snapshot=MX-DEMO&currency=USD', { method: 'GET' });
  });

  it('getCashflows omite los filtros vacíos y codifica la contraparte', async () => {
    const fn = mockFetch(200, { rows: [] });
    await getCashflows({
      snapshot: 'MX-DEMO',
      from: '2026-08-12',
      to: '',
      counterparty: 'Banco Alfa (sintético)',
    });
    const params = new URLSearchParams(String(fn.mock.calls[0][0]).split('?')[1]);
    expect([...params.keys()]).toEqual(['snapshot', 'from', 'counterparty']);
    expect(params.get('counterparty')).toBe('Banco Alfa (sintético)');
  });

  it('cashflowsCsvUrl añade format=csv', () => {
    expect(cashflowsCsvUrl({ snapshot: 'MX-DEMO', currency: 'USD' })).toBe(
      '/api/cashflows?snapshot=MX-DEMO&currency=USD&format=csv',
    );
    expect(cashflowsCsvUrl({ snapshot: 'MX-DEMO' })).toBe('/api/cashflows?snapshot=MX-DEMO&format=csv');
  });
});

describe('cliente de operaciones: liquidación, confirmación y ajustes', () => {
  it('confirmSettlement hace POST con el cuerpo', async () => {
    const body = { date: '2026-12-08', amount: 30990, currency: 'MXN' as const, snapshot: 'MX-DEMO' };
    const fn = mockFetch(201, { difference: -10 });
    await confirmSettlement(1, body);
    expect(fn).toHaveBeenCalledWith('/api/trades/1/settlements', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  });

  it('getConfirmation pide la confirmación de la operación', async () => {
    const fn = mockFetch(200, { trade_id: 4 });
    await getConfirmation(4);
    expect(fn).toHaveBeenCalledWith('/api/trades/4/confirmation', { method: 'GET' });
  });

  it('getSettings y putSettings usan /api/settings', async () => {
    const fn = mockFetch(200, { company_name: 'X' });
    await getSettings();
    await putSettings({ company_name: 'Tesorería X' });
    expect(fn).toHaveBeenNthCalledWith(1, '/api/settings', { method: 'GET' });
    expect(fn).toHaveBeenNthCalledWith(2, '/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_name: 'Tesorería X' }),
    });
  });

  it('getTradeRef lee y putTradeRef(null) envía {"ref": null} con PUT', async () => {
    const fn = mockFetch(200, { trade_id: 3, ref: null });
    await getTradeRef(3);
    await putTradeRef(3, null);
    expect(fn).toHaveBeenNthCalledWith(1, '/api/trades/3/ref', { method: 'GET' });
    expect(fn).toHaveBeenNthCalledWith(2, '/api/trades/3/ref', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: '{"ref":null}',
    });
  });
});

describe('cliente de operaciones: FpML', () => {
  it('fpmlUrl apunta a la descarga de la operación', () => {
    expect(fpmlUrl(4)).toBe('/api/trades/4/fpml');
  });

  it('importFpml envía el texto tal cual con Content-Type application/xml', async () => {
    const fn = mockFetch(201, { trade: { id: 9 }, warnings: [] });
    await importFpml('<x/>');
    expect(fn).toHaveBeenCalledWith('/api/trades/fpml', {
      method: 'POST',
      headers: { 'Content-Type': 'application/xml' },
      body: '<x/>',
    });
  });
});

describe('cliente de operaciones: conciliación', () => {
  it('createReconciliation hace POST con el cuerpo', async () => {
    const body = {
      snapshot: 'MX-DEMO',
      counterparty: 'Banco Alfa (sintético)',
      csv: 'trade_id,bank_pv,currency,bank_ref\n1,10,MXN,\n',
      tolerance: 0.0001,
    };
    const fn = mockFetch(201, { id: 2 });
    await createReconciliation(body);
    expect(fn).toHaveBeenCalledWith('/api/reconciliations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  });

  it('listReconciliations devuelve el arreglo y filtra por contraparte', async () => {
    const list = [{ id: 2 }, { id: 1 }];
    const fn = mockFetch(200, { reconciliations: list });
    await expect(listReconciliations({ counterparty: 'Banco Alfa (sintético)' })).resolves.toEqual(list);
    const qs = new URLSearchParams({ counterparty: 'Banco Alfa (sintético)' }).toString();
    expect(fn).toHaveBeenCalledWith(`/api/reconciliations?${qs}`, { method: 'GET' });
  });

  it('listReconciliations sin filtro no añade consulta', async () => {
    const fn = mockFetch(200, { reconciliations: [] });
    await listReconciliations();
    expect(fn).toHaveBeenCalledWith('/api/reconciliations', { method: 'GET' });
  });

  it('getReconciliation pide el detalle y reconciliationCsvUrl el CSV', async () => {
    const fn = mockFetch(200, { id: 2 });
    await getReconciliation(2);
    expect(fn).toHaveBeenCalledWith('/api/reconciliations/2', { method: 'GET' });
    expect(reconciliationCsvUrl(2)).toBe('/api/reconciliations/2?format=csv');
  });
});

describe('cliente de operaciones: errores', () => {
  it('un 409 se convierte en ApiError con status y field', async () => {
    mockFetch(409, { error: 'Esa referencia ya existe', field: 'ref' });
    const err = await putTradeRef(4, 'BA-1').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.field).toBe('ref');
    expect(err.message).toBe('Esa referencia ya existe');
  });

  it('un error sin cuerpo JSON conserva el status, field null y un mensaje genérico', async () => {
    mockFetch(500);
    const err = await importFpml('<x/>').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
    expect(err.field).toBeNull();
    expect(err.message).toBe('Error 500');
  });
});
