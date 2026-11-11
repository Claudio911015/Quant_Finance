import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MethodologyScreen } from './MethodologyScreen';

/** Texto de la fila `label` de la sección de ciclo de vida. */
function row(label: string): string {
  const term = screen.getByText(label, { selector: 'dt' });
  return term.nextElementSibling?.textContent ?? '';
}

describe('MethodologyScreen', () => {
  it('describe la aproximación de bono y cap/floor como es, sin decir que omite el cupón en curso', () => {
    render(<MethodologyScreen />);
    const text = row('Aproximaciones');
    expect(text).toContain('periodos enteros restantes');
    expect(text).toContain('dentro de un periodo no envejecen');
    expect(text).toContain('corte 3');
    expect(text).not.toContain('se omite');
  });

  it('explica la regla de fines de semana y que los feriados todavía avisan', () => {
    render(<MethodologyScreen />);
    expect(row('Fines de semana')).toContain('la del viernes devenga también sábado y domingo (3 días)');
    expect(row('Fines de semana')).toContain('no avisan');
    expect(row('Fijación faltante')).toContain('Los feriados todavía avisan');
    expect(row('Fijación faltante')).toContain('lunes a viernes');
  });

  it('dice que un swap sin tasa fija nace a la par', () => {
    render(<MethodologyScreen />);
    expect(row('Alta a la par')).toContain('nace a la par');
    expect(row('Alta a la par')).toContain('PV en la fecha de pacto es cero');
  });
});
