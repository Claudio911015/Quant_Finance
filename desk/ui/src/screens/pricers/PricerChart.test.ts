import { describe, expect, it } from 'vitest';
import { capFloorPayoffSeries, forwardPayoffSeries, payoffSeries, swaptionPayoffSeries } from './PricerChart';

describe('payoffSeries', () => {
  const at = (s: { spots: number[]; pnl: number[] }, spot: number) =>
    s.pnl[s.spots.findIndex((x) => Math.abs(x - spot) < 1e-9)];

  it('call comprada: neto = intrínseco × nocional − prima', () => {
    const s = payoffSeries({ side: 'buy', option_type: 'call', notional_usd: 1_000_000, strike: 20 }, 500_000)!;
    expect(at(s, 20)).toBeCloseTo(-500_000); // en el strike solo se pierde la prima
    expect(at(s, 22)).toBeCloseTo(2 * 1_000_000 - 500_000);
    expect(at(s, 14)).toBeCloseTo(-500_000); // fuera del dinero
  });

  it('put vendida (PV negativo = prima cobrada): el resultado es el espejo', () => {
    const s = payoffSeries({ side: 'sell', option_type: 'put', notional_usd: 1_000_000, strike: 20 }, -300_000)!;
    expect(at(s, 20)).toBeCloseTo(300_000);
    expect(at(s, 18)).toBeCloseTo(-2 * 1_000_000 + 300_000);
  });

  it('opción sobre acción: sin side es larga y el tamaño es la cantidad', () => {
    const s = payoffSeries({ option_type: 'call', quantity: 1000, strike: 55 }, 4_000)!;
    expect(s.strike).toBe(55);
    expect(at(s, 55 * 1.3)).toBeCloseTo(0.3 * 55 * 1000 - 4_000);
  });

  it('sin strike o tamaño válidos no hay serie', () => {
    expect(payoffSeries({ option_type: 'call', quantity: 1, strike: 0 }, 1)).toBeNull();
    expect(payoffSeries({ option_type: 'call', strike: 10, quantity: -1 }, 1)).toBeNull();
  });
});

describe('forwardPayoffSeries', () => {
  const at = (s: { spots: number[]; pnl: number[] }, spot: number) =>
    s.pnl[s.spots.findIndex((x) => Math.abs(x - spot) < 1e-9)];
  const buy = { side: 'buy', notional_usd: 1_000_000, strike: 18.9 };

  it('compra de USD: signo × (S − K) × nocional, sin restar prima (en el strike vale 0)', () => {
    const s = forwardPayoffSeries(buy)!;
    expect(at(s, 18.9)).toBeCloseTo(0); // una opción ahí perdería su prima; el forward no tiene
    expect(at(s, 18.9 * 1.15)).toBeCloseTo(2_835_000); // 1.15 × 18.9 − 18.9 = 2.835 MXN × 1,000,000
    expect(at(s, 18.9 * 0.85)).toBeCloseTo(-2_835_000);
  });

  it('venta de USD: el resultado es el espejo (gana si el dólar baja)', () => {
    const s = forwardPayoffSeries({ ...buy, side: 'sell' })!;
    expect(at(s, 18.9 * 0.85)).toBeCloseTo(2_835_000);
    expect(at(s, 18.9 * 1.15)).toBeCloseTo(-2_835_000);
  });

  it('S_T recorre ±15 % del strike', () => {
    const s = forwardPayoffSeries(buy)!;
    expect(s.strike).toBe(18.9);
    expect(s.spots[0]).toBeCloseTo(18.9 * 0.85);
    expect(s.spots[s.spots.length - 1]).toBeCloseTo(18.9 * 1.15);
  });

  it('sin strike o nocional válidos no hay serie', () => {
    expect(forwardPayoffSeries({ ...buy, strike: 0 })).toBeNull();
    expect(forwardPayoffSeries({ ...buy, notional_usd: -1 })).toBeNull();
  });
});

describe('capFloorPayoffSeries', () => {
  const at = (s: { spots: number[]; pnl: number[] }, rate: number) =>
    s.pnl[s.spots.findIndex((x) => Math.abs(x - rate) < 1e-9)];
  const cap = { cap_type: 'cap', notional: 100_000_000, strike: 0.075 };

  it('cap TIIE-F (28 d): nocional × 28/360 × max(r − K, 0)', () => {
    const s = capFloorPayoffSeries(cap, 28)!;
    expect(at(s, 0.085)).toBeCloseTo(77_777.78, 2); // 1e8 × (28/360) × 0.01
    expect(at(s, 0.075)).toBe(0);
    expect(at(s, 0.065)).toBe(0); // por debajo del strike un cap no paga
  });

  it('floor: el signo contrario, paga cuando r < K', () => {
    const s = capFloorPayoffSeries({ ...cap, cap_type: 'floor' }, 28)!;
    expect(at(s, 0.065)).toBeCloseTo(77_777.78, 2);
    expect(at(s, 0.085)).toBe(0);
  });

  it('SOFR (365 d): τ = 365/360', () => {
    const s = capFloorPayoffSeries({ ...cap, strike: 0.04 }, 365)!;
    expect(at(s, 0.05)).toBeCloseTo(1_013_888.89, 2); // 1e8 × (365/360) × 0.01
  });

  it('el eje va de K − 3 pp a K + 3 pp', () => {
    const s = capFloorPayoffSeries(cap, 28)!;
    expect(s.spots).toHaveLength(61);
    expect(s.spots[0]).toBeCloseTo(0.045);
    expect(s.spots[60]).toBeCloseTo(0.105);
  });

  it('con K < 3 pp el eje arranca en 0 y el strike queda en la rejilla', () => {
    const s = capFloorPayoffSeries({ ...cap, cap_type: 'floor', strike: 0.0125 }, 28)!;
    expect(s.spots[0]).toBe(0);
    expect(s.spots[s.spots.length - 1]).toBeCloseTo(0.0425);
    expect(s.spots).toHaveLength(62); // 61 puntos + el strike, que no cae en la rejilla
    expect([...s.spots].sort((a, b) => a - b)).toEqual(s.spots);
    expect(at(s, 0.0125)).toBe(0);
    expect(at(s, 0)).toBeCloseTo(100_000_000 * (28 / 360) * 0.0125, 2); // floor en r = 0
  });

  it('sin periodo de pago, strike o nocional válidos no hay serie', () => {
    expect(capFloorPayoffSeries(cap, undefined)).toBeNull();
    expect(capFloorPayoffSeries(cap, 0)).toBeNull();
    expect(capFloorPayoffSeries({ ...cap, strike: -0.01 }, 28)).toBeNull();
    expect(capFloorPayoffSeries({ ...cap, notional: 0 }, 28)).toBeNull();
  });
});

describe('swaptionPayoffSeries', () => {
  const at = (s: { spots: number[]; pnl: number[] }, rate: number) =>
    s.pnl[s.spots.findIndex((x) => Math.abs(x - rate) < 1e-9)];
  // SOFR: periodo de 365 d → τ = 1, plazo 5 años → n = 5 pagos anuales
  const payer = { swaption_type: 'payer', notional: 100_000_000, strike: 0.07, swap_tenor_years: 5 };

  it('payer: nocional × A(s) × max(s − K, 0) con A = Σ 1/(1 + s)^j', () => {
    const s = swaptionPayoffSeries(payer, 365)!;
    // A(8 %) = (1 − 1.08^-5) / 0.08 = 3.99271004; × 1e8 × 0.01
    expect(at(s, 0.08)).toBeCloseTo(3_992_710.04, 1);
  });

  it('receiver: el signo contrario, paga cuando s < K, con la anualidad evaluada en s', () => {
    const s = swaptionPayoffSeries({ ...payer, swaption_type: 'receiver' }, 365)!;
    // A(6 %) = (1 − 1.06^-5) / 0.06 = 4.21236379; × 1e8 × 0.01
    expect(at(s, 0.06)).toBeCloseTo(4_212_363.79, 1);
  });

  it('fuera del dinero y en el strike el valor es 0', () => {
    const p = swaptionPayoffSeries(payer, 365)!;
    expect(at(p, 0.06)).toBe(0);
    expect(at(p, 0.07)).toBe(0);
    const r = swaptionPayoffSeries({ ...payer, swaption_type: 'receiver' }, 365)!;
    expect(at(r, 0.08)).toBe(0);
  });

  it('con s = 0 la anualidad es n·τ', () => {
    // receiver con K = 2 %: el eje arranca en 0; A(0) = 5 × 1 → 1e8 × 5 × 0.02
    const s = swaptionPayoffSeries({ ...payer, swaption_type: 'receiver', strike: 0.02 }, 365)!;
    expect(s.spots[0]).toBe(0);
    expect(s.pnl[0]).toBeCloseTo(10_000_000, 2);
  });

  it('TIIE-F (28 d): τ = 28/365 y n = round(plazo × 365/28) pagos', () => {
    // 2 años → n = round(26.07) = 26; A(9 %) = Σ_{j=1..26} (28/365) / (1 + 0.09 × 28/365)^j
    const s = swaptionPayoffSeries({ ...payer, swap_tenor_years: 2 }, 28)!;
    expect(at(s, 0.09)).toBeCloseTo(3_640_047.56, 1); // 1e8 × A × 0.02
  });

  it('sin periodo de pago o plazo válidos no hay serie', () => {
    expect(swaptionPayoffSeries(payer, undefined)).toBeNull();
    expect(swaptionPayoffSeries({ ...payer, swap_tenor_years: 0 }, 365)).toBeNull();
    expect(swaptionPayoffSeries({ ...payer, strike: 0 }, 365)).toBeNull();
  });
});
