import { describe, expect, it } from 'vitest';
import { fmtDate, fmtMoney, fmtNumber, fmtRate } from './format';

describe('format', () => {
  it('fmtRate muestra la tasa en % con 4 decimales', () => {
    expect(fmtRate(0.0725)).toBe('7.2500 %');
    expect(fmtRate(-0.005)).toBe('-0.5000 %');
  });

  it('fmtMoney usa coma de miles y 2 decimales', () => {
    expect(fmtMoney(1234567.891, 'MXN')).toBe('MXN 1,234,567.89');
    expect(fmtMoney(0, 'USD')).toBe('USD 0.00');
  });

  it('fmtNumber respeta los decimales pedidos', () => {
    expect(fmtNumber(1234.5, 0)).toBe('1,235');
    expect(fmtNumber(0.5, 3)).toBe('0.500');
  });

  it('fmtDate devuelve el ISO tal cual', () => {
    expect(fmtDate('2026-11-10')).toBe('2026-11-10');
  });
});
