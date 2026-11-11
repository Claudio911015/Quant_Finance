import { describe, expect, it } from 'vitest';
import { fmtDate, fmtDateTime, fmtMoney, fmtNumber, fmtRate, parseNumber } from './format';

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

  it('nunca muestra un cero negativo: -0 y los negativos que redondean a cero salen sin signo', () => {
    expect(fmtNumber(-0, 2)).toBe('0.00');
    expect(fmtNumber(-0.001, 2)).toBe('0.00');
    expect(fmtNumber(-0.4, 0)).toBe('0');
    expect(fmtMoney(-0, 'MXN')).toBe('MXN 0.00');
    expect(fmtRate(-0.0000000001)).toBe('0.0000 %');
    // los negativos reales conservan el signo
    expect(fmtNumber(-0.01, 2)).toBe('-0.01');
    expect(fmtNumber(-1234.5, 2)).toBe('-1,234.50');
  });

  it('fmtDate devuelve el ISO tal cual', () => {
    expect(fmtDate('2026-11-10')).toBe('2026-11-10');
  });

  it('fmtDateTime muestra fecha ISO, hora y zona, y devuelve tal cual lo que no puede leer', () => {
    expect(fmtDateTime('2026-11-11T18:00:00+00:00')).toBe('2026-11-11 18:00 UTC');
    // una marca con otra zona se lleva a UTC para que la etiqueta no mienta
    expect(fmtDateTime('2026-11-11T12:30:45-06:00')).toBe('2026-11-11 18:30 UTC');
    expect(fmtDateTime('no es una fecha')).toBe('no es una fecha');
  });

  it('parseNumber acepta comas y espacios y rechaza lo vacío o no finito', () => {
    expect(parseNumber('1,250,000.5')).toBe(1250000.5);
    expect(parseNumber(' 50 ')).toBe(50);
    expect(parseNumber('')).toBeNull();
    expect(parseNumber('abc')).toBeNull();
    expect(parseNumber('Infinity')).toBeNull();
  });
});
