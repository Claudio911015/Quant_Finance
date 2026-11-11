import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './client';
import {
  addLimitEvent,
  checkLimits,
  createLimit,
  createScenarioSet,
  creditExposure,
  deriveFactorHistory,
  factorHistorySummary,
  importFactorHistoryCsv,
  limitUsage,
  listBreaches,
  listCreditParams,
  listLimits,
  listScenarioSets,
  pnlExplain,
  retireScenarioSet,
  riskVarHistorical,
  runScenarioSet,
  setCreditParams,
} from './riskClient';

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

/** Método, ruta y cuerpo JSON (o `undefined`) de la única llamada hecha a `fetch`. */
function sent(fn: ReturnType<typeof mockFetch>) {
  expect(fn).toHaveBeenCalledTimes(1);
  const [url, init] = fn.mock.calls[0];
  return { url, method: init.method, body: init.body === undefined ? undefined : JSON.parse(init.body) };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('cliente de riesgo avanzado', () => {
  it('pnlExplain: GET con from y to codificados', async () => {
    const fn = mockFetch(200, { steps: [] });
    await pnlExplain('MX-DEMO', 'D 1&x');
    expect(sent(fn)).toEqual({ url: '/api/pnl/explain?from=MX-DEMO&to=D%201%26x', method: 'GET', body: undefined });
  });

  it('riskVarHistorical: POST /risk/var con method historical y los parámetros', async () => {
    const fn = mockFetch(200, {});
    await riskVarHistorical('MX-DEMO', { horizon_days: 10, confidence: 0.99, window_days: 250, history_source: 'observed' });
    expect(sent(fn)).toEqual({
      url: '/api/risk/var',
      method: 'POST',
      body: {
        snapshot: 'MX-DEMO',
        method: 'historical',
        horizon_days: 10,
        confidence: 0.99,
        window_days: 250,
        history_source: 'observed',
      },
    });
  });

  it('riskVarHistorical: omite window_days e history_source si no se dan', async () => {
    const fn = mockFetch(200, {});
    await riskVarHistorical('MX-DEMO', { horizon_days: 1, confidence: 0.95 });
    expect(sent(fn).body).toEqual({ snapshot: 'MX-DEMO', method: 'historical', horizon_days: 1, confidence: 0.95 });
  });

  it('historia de factores: resumen, CSV y derivación', async () => {
    let fn = mockFetch(200, { factors: [] });
    await factorHistorySummary();
    expect(sent(fn)).toEqual({ url: '/api/factor-history', method: 'GET', body: undefined });

    fn = mockFetch(200, { inserted: 2, unchanged: 0 });
    await importFactorHistoryCsv('factor,date,value\nTIIE-F,2026-11-09,1.5');
    expect(sent(fn)).toEqual({
      url: '/api/factor-history/csv',
      method: 'POST',
      body: { csv: 'factor,date,value\nTIIE-F,2026-11-09,1.5' },
    });

    fn = mockFetch(200, { source: 'fixings', inserted: 1, unchanged: 0, skipped_gaps: 0 });
    await deriveFactorHistory('fixings');
    expect(sent(fn)).toEqual({ url: '/api/factor-history/derive', method: 'POST', body: { source: 'fixings' } });
  });

  it('listLimits y listBreaches desenvuelven la lista', async () => {
    mockFetch(200, { limits: [{ id: 1 }, { id: 2 }] });
    expect((await listLimits()).map((l) => l.id)).toEqual([1, 2]);
    const fn = mockFetch(200, { breaches: [{ id: 9 }] });
    expect((await listBreaches()).map((b) => b.id)).toEqual([9]);
    expect(sent(fn)).toEqual({ url: '/api/limits/breaches', method: 'GET', body: undefined });
  });

  it('createLimit y addLimitEvent: POST con el cuerpo tal cual', async () => {
    const limit = { id: 3 };
    let fn = mockFetch(201, limit);
    const create = { scope: 'counterparty', key: 'Banco A', metric: 'pv_exposure', amount: 5e7, reason: 'Política' } as const;
    await expect(createLimit(create)).resolves.toEqual(limit);
    expect(sent(fn)).toEqual({ url: '/api/limits', method: 'POST', body: create });

    fn = mockFetch(201, limit);
    await addLimitEvent(3, { type: 'change', amount: 6e7, reason: 'Revisión' });
    expect(sent(fn)).toEqual({
      url: '/api/limits/3/events',
      method: 'POST',
      body: { type: 'change', amount: 6e7, reason: 'Revisión' },
    });
  });

  it('limitUsage (GET) y checkLimits (POST sin cuerpo) llevan el snapshot en la consulta', async () => {
    let fn = mockFetch(200, { usage: [] });
    await limitUsage('MX DEMO');
    expect(sent(fn)).toEqual({ url: '/api/limits/usage?snapshot=MX%20DEMO', method: 'GET', body: undefined });

    fn = mockFetch(200, { usage: [], new_breaches: [] });
    await checkLimits('MX-DEMO');
    expect(sent(fn)).toEqual({ url: '/api/limits/check?snapshot=MX-DEMO', method: 'POST', body: undefined });
  });

  it('crédito: exposición, parámetros (lista desenvuelta) y alta de parámetros', async () => {
    let fn = mockFetch(200, { counterparties: [] });
    await creditExposure('MX-DEMO');
    expect(sent(fn)).toEqual({ url: '/api/credit/exposure?snapshot=MX-DEMO', method: 'GET', body: undefined });

    fn = mockFetch(200, { params: [{ counterparty: 'Banco A' }] });
    expect((await listCreditParams()).map((p) => p.counterparty)).toEqual(['Banco A']);
    expect(sent(fn)).toEqual({ url: '/api/credit/params', method: 'GET', body: undefined });

    const body = { counterparty: 'Banco A', hazard_rate: 0.02, recovery: 0.35 };
    fn = mockFetch(201, { counterparty: 'Banco A' });
    await setCreditParams(body);
    expect(sent(fn)).toEqual({ url: '/api/credit/params', method: 'POST', body });
  });

  it('conjuntos de escenarios: lista desenvuelta, alta, baja y corrida', async () => {
    let fn = mockFetch(200, { sets: [{ name: 'Marzo 2020' }, { name: 'Otro' }] });
    expect((await listScenarioSets()).map((s) => s.name)).toEqual(['Marzo 2020', 'Otro']);
    expect(sent(fn)).toEqual({ url: '/api/scenario-sets', method: 'GET', body: undefined });

    const body = {
      name: 'Choque Banxico',
      description: 'x',
      scenarios: [{ name: 'TIIE-F +100', type: 'parallel', curve: 'TIIE-F', bp: 100 }],
    } as const;
    fn = mockFetch(201, { id: 5 });
    await createScenarioSet({ ...body, scenarios: [...body.scenarios] });
    expect(sent(fn)).toEqual({ url: '/api/scenario-sets', method: 'POST', body });

    fn = mockFetch(200, { id: 5, status: 'baja' });
    await retireScenarioSet(5);
    expect(sent(fn)).toEqual({ url: '/api/scenario-sets/5/retire', method: 'POST', body: undefined });

    fn = mockFetch(200, { set: 'Marzo 2020', snapshot: 'MX-DEMO', scenarios: [] });
    await runScenarioSet('MX-DEMO', 'Marzo 2020');
    expect(sent(fn)).toEqual({
      url: '/api/risk/scenarios',
      method: 'POST',
      body: { snapshot: 'MX-DEMO', set: 'Marzo 2020' },
    });
  });

  it('un 400 con error y field llega como ApiError con field', async () => {
    mockFetch(400, { error: 'Historia insuficiente', field: 'window_days' });
    const err = await riskVarHistorical('MX-DEMO', { horizon_days: 10, confidence: 0.99 }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.message).toBe('Historia insuficiente');
    expect(err.field).toBe('window_days');
  });

  it('un 409 conserva status y field; una lista que falla no se desenvuelve', async () => {
    mockFetch(409, { error: 'Ya hay un límite activo', field: 'key' });
    const err = await createLimit({ scope: 'portfolio', metric: 'var', amount: 1 }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.field).toBe('key');

    mockFetch(500);
    const err2 = await listScenarioSets().catch((e) => e);
    expect(err2).toBeInstanceOf(ApiError);
    expect(err2.status).toBe(500);
    expect(err2.field).toBeNull();
  });
});
