import { describe, expect, it } from 'vitest';
import { payoffSeries } from './PricerChart';

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
