import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  closeHedgePeriod,
  createHedge,
  dedesignateHedge,
  deleteTrade,
  hedgeEffectiveness,
  hedgeReportCsvUrl,
  importFixingsCsv,
  listHedges,
  listSnapshots,
  pnl,
  postEvent,
  price,
  refreshMarket,
  riskVar,
  valuation,
} from './client';
import type { CreateHedgeBody } from './types';

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

describe('cliente API', () => {
  it('convierte un 400 con error y field en ApiError', async () => {
    mockFetch(400, { error: 'x', field: 'notional' });
    const err = await price('irs', { snapshot: 'MX-DEMO' }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.message).toBe('x');
    expect(err.field).toBe('notional');
  });

  it('un error sin cuerpo JSON conserva el status y field null', async () => {
    mockFetch(404);
    const err = await valuation('MX-DEMO').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.field).toBeNull();
  });

  it('204 devuelve undefined', async () => {
    const fn = mockFetch(204);
    await expect(deleteTrade(7)).resolves.toBeUndefined();
    expect(fn).toHaveBeenCalledWith('/api/trades/7', { method: 'DELETE' });
  });

  it('listSnapshots desenvuelve la lista', async () => {
    mockFetch(200, { snapshots: [{ id: 'MX-DEMO', label: 'x', synthetic: true, as_of: '2026-11-10' }] });
    const list = await listSnapshots();
    expect(list.map((s) => s.id)).toEqual(['MX-DEMO']);
  });

  it('riskVar envía horizon_days y confidence en el cuerpo JSON', async () => {
    const fn = mockFetch(200, {});
    await riskVar('MX-DEMO', 10, 0.99);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe('/api/risk/var');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ snapshot: 'MX-DEMO', horizon_days: 10, confidence: 0.99 });
  });

  it('refreshMarket hace POST a /api/market/refresh sin cuerpo y devuelve la respuesta', async () => {
    const body = {
      ran_at: '2026-11-11T15:04:05+00:00',
      mdf_exit_code: 0,
      treasury_latest: '2026-11-10',
      sofr_latest: '2026-11-09',
      fred_latest: '2026-11-06',
      snapshot: { id: 'MKT-LIVE' },
    };
    const fn = mockFetch(200, body);
    await expect(refreshMarket()).resolves.toEqual(body);
    expect(fn).toHaveBeenCalledWith('/api/market/refresh', { method: 'POST' });
  });

  it.each([
    [502, 'FRED no respondió: tiempo agotado'],
    [409, 'Ya hay una actualización de datos en curso'],
  ])('refreshMarket convierte un %i en ApiError con su mensaje', async (status, message) => {
    mockFetch(status, { error: message, field: null });
    const err = await refreshMarket().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(status);
    expect(err.message).toBe(message);
    expect(err.field).toBeNull();
  });

  it('postEvent hace POST a /api/trades/3/events con el cuerpo y devuelve los eventos', async () => {
    const events = [{ id: 9, trade_id: 3, type: 'termination' }];
    const fn = mockFetch(201, { events });
    const body = { type: 'termination' as const, event_date: '2026-12-01', data: { amount: 1500 } };
    await expect(postEvent(3, body)).resolves.toEqual(events);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe('/api/trades/3/events');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual(body);
  });

  it('importFixingsCsv envía el texto en {"csv": ...}', async () => {
    const fn = mockFetch(200, { inserted: 1, unchanged: 0 });
    await importFixingsCsv('a');
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe('/api/fixings/csv');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"csv":"a"}');
  });

  it('pnl llama a /api/pnl con from y to', async () => {
    const fn = mockFetch(200, {});
    await pnl('A', 'B');
    expect(fn.mock.calls[0][0]).toBe('/api/pnl?from=A&to=B');
  });

  it('un 409 se convierte en ApiError con status 409 y field', async () => {
    mockFetch(409, { error: 'La operación no está viva en esa fecha', field: 'id' });
    const err = await postEvent(3, { type: 'termination', event_date: '2026-12-01', data: { amount: 0 } }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.field).toBe('id');
  });
});

describe('cliente API: coberturas', () => {
  it('listHedges con trade_id lo pasa en la consulta y desenvuelve la lista', async () => {
    const fn = mockFetch(200, { hedges: [{ id: 1 }] });
    await expect(listHedges({ trade_id: 3 })).resolves.toEqual([{ id: 1 }]);
    expect(fn.mock.calls[0][0]).toBe('/api/hedges?trade_id=3');
  });

  it('listHedges sin filtro llama a /api/hedges', async () => {
    const fn = mockFetch(200, { hedges: [] });
    await expect(listHedges()).resolves.toEqual([]);
    expect(fn.mock.calls[0][0]).toBe('/api/hedges');
  });

  it('createHedge hace POST a /api/hedges con el cuerpo', async () => {
    const fn = mockFetch(201, { id: 1 });
    const body: CreateHedgeBody = {
      trade_id: 8,
      snapshot: 'MX-DEMO',
      hedge_type: 'cash_flow',
      item_kind: 'forecast_fx',
      item_terms: { amount_usd: 10000000, date: '2027-05-11', side: 'buy_usd' },
      fraction: 1,
      documentation: {
        risk_management_objective: 'a',
        hedged_risk: 'b',
        effectiveness_method: 'c',
        ineffectiveness_sources: 'd',
      },
    };
    await createHedge(body);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe('/api/hedges');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual(body);
  });

  it('closeHedgePeriod envía {"snapshot"} a /api/hedges/1/periods', async () => {
    const fn = mockFetch(201, { id: 1 });
    await closeHedgePeriod(1, 'D1');
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe('/api/hedges/1/periods');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"snapshot":"D1"}');
  });

  it('dedesignateHedge hace POST a /api/hedges/1/dedesignate con fecha y motivo', async () => {
    const fn = mockFetch(201, { id: 1 });
    const body = { date: '2027-01-10', reason: 'Prepago del crédito' };
    await dedesignateHedge(1, body);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe('/api/hedges/1/dedesignate');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual(body);
  });

  it('hedgeEffectiveness pasa el snapshot en la consulta', async () => {
    const fn = mockFetch(200, {});
    await hedgeEffectiveness(1, 'MX-DEMO');
    expect(fn.mock.calls[0][0]).toBe('/api/hedges/1/effectiveness?snapshot=MX-DEMO');
  });

  it('hedgeReportCsvUrl es la URL del CSV, sin llamar a la red', () => {
    const fn = mockFetch(200, {});
    expect(hedgeReportCsvUrl(2)).toBe('/api/hedges/2/report?format=csv');
    expect(fn).not.toHaveBeenCalled();
  });

  it('un 409 al cerrar un periodo se convierte en ApiError con status 409 y field', async () => {
    mockFetch(409, { error: 'El periodo ya está cerrado', field: 'snapshot' });
    const err = await closeHedgePeriod(1, 'D1').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.field).toBe('snapshot');
  });
});
