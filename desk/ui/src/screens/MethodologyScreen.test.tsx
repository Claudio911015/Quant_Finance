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

  describe('contabilidad de coberturas', () => {
    /** Texto de la fila `label` dentro de la sección de coberturas (la etiqueta "Cambios de nocional" también existe en ciclo de vida). */
    function hedgeRow(label: string): string {
      const section = document.getElementById('meth-coberturas')!.closest('section')!;
      const term = Array.from(section.querySelectorAll('dt')).find((dt) => dt.textContent === label);
      return term?.nextElementSibling?.textContent ?? '';
    }

    it('muestra la revisión contable con el texto exacto de la banda', () => {
      render(<MethodologyScreen />);
      expect(hedgeRow('Revisión contable')).toContain(
        'Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9',
      );
      expect(hedgeRow('Revisión contable')).toContain('Nadie la ha hecho aún');
    });

    it('describe la regla del menor, el valor razonable, el reciclaje y las simplificaciones', () => {
      render(<MethodologyScreen />);
      expect(hedgeRow('Regla del menor')).toContain('menor');
      expect(hedgeRow('Valor razonable')).toContain('tasa fija');
      expect(hedgeRow('Reciclaje')).toContain('liquidaciones');
      const simp = hedgeRow('Simplificaciones');
      expect(simp).toContain('costo de cobertura');
      expect(simp).toContain('riesgo de crédito');
      expect(simp).toContain('ajuste de base');
      expect(simp).toContain('reequilibrio');
    });

    it('incluye las filas de cambios de nocional y derivado hipotético', () => {
      render(<MethodologyScreen />);
      expect(hedgeRow('Cambios de nocional')).toContain('nocional vigente');
      expect(hedgeRow('Derivado hipotético')).toContain('swap a la par');
    });
  });
});
