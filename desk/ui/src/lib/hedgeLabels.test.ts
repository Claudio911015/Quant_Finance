import { describe, expect, it } from 'vitest';
import { HEDGE_STATUS_LABEL, localizeMessage } from './hedgeLabels';

// Mensajes tal como los emite el backend real (validation.py y hedges.py).
describe('localizeMessage', () => {
  it('cambia las claves entre comillas por el nombre del campo en pantalla', () => {
    expect(localizeMessage("'maturity_date' debe ser posterior a 'start_date'")).toBe(
      'Vencimiento debe ser posterior a inicio',
    );
    expect(localizeMessage("'hedged_risk' no puede estar vacío")).toBe('Riesgo cubierto no puede estar vacío');
    expect(localizeMessage("'date' debe ser una fecha válida AAAA-MM-DD")).toBe(
      'Fecha debe ser una fecha válida AAAA-MM-DD',
    );
  });

  it('rotula las claves de desdesignar y liberar la reserva', () => {
    expect(localizeMessage("'amount' debe ser de al menos un centavo")).toBe('Monto debe ser de al menos un centavo');
    expect(localizeMessage("'cause' debe ser texto")).toBe('Causa debe ser texto');
    expect(localizeMessage("'snapshot' no puede estar vacío")).toBe('Snapshot no puede estar vacío');
  });

  it('cambia los identificadores sueltos por su nombre en español', () => {
    expect(localizeMessage('La partida floating_loan se cubre con un irs, no con un fx_forward')).toBe(
      'La partida crédito a tasa variable se cubre con un swap de tasas, no con un forward FX',
    );
    expect(localizeMessage('Una cobertura de fair_value no admite la partida floating_loan')).toBe(
      'Una cobertura de valor razonable no admite la partida crédito a tasa variable',
    );
  });

  it('deja intactos los mensajes que ya están en español y las claves que no conoce', () => {
    const ok = 'La operación ya tiene designado 80 % de su nocional: la nueva fracción excede 100 %';
    expect(localizeMessage(ok)).toBe(ok);
    expect(localizeMessage("'otra_clave' no es válida")).toBe("'otra_clave' no es válida");
  });
});

describe('estados de la relación', () => {
  it('rotula los tres estados', () => {
    expect(HEDGE_STATUS_LABEL).toEqual({ activa: 'Activa', concluida: 'Concluida', desdesignada: 'Desdesignada' });
  });

  it('deja intactos los 409 de causa contrastada, que ya vienen en español', () => {
    const ended = 'La operación sigue viva al 2026-12-15: la causa «El instrumento venció, se vendió o se terminó» solo aplica si ya no lo está';
    const occurred =
      'El flujo cubierto aún no ocurre al 2026-11-15 (su primera fecha es 2026-11-30): si ya no se espera, la causa es «El flujo cubierto ya no se espera»';
    expect(localizeMessage(ended)).toBe(ended);
    expect(localizeMessage(occurred)).toBe(occurred);
  });
});
