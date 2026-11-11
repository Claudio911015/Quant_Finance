import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, deleteTrade, listSnapshots, price, refreshMarket, riskVar, valuation } from './client';

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
});
