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

    it('declara las reglas de la regla del menor y del reciclaje tras la auditoría', () => {
      render(<MethodologyScreen />);
      expect(hedgeRow('Regla del menor')).toContain('desde la designación');
      expect(hedgeRow('Regla del menor')).toContain('lo ya liquidado');
      const recycling = hedgeRow('Reciclaje');
      expect(recycling).toContain('flujo cubierto proxy');
      expect(recycling).toContain('misma fecha');
      expect(recycling).toContain('reserva queda en 0');
      expect(hedgeRow('Asientos sugeridos')).toContain('saldos acumulados ya redondeados');
    });

    it('declara el componente de tasa, la presentación del cupón y que el ajuste no se amortiza', () => {
      render(<MethodologyScreen />);
      const fv = hedgeRow('Valor razonable');
      expect(fv).toContain('componente de tasa de referencia');
      expect(fv).toContain('no por su cupón contractual');
      expect(fv).toContain('no se amortiza');
      expect(fv).toContain('no en gasto por intereses');
    });

    it('la desdesignación exige una causa, mide hasta su fecha y la reserva se libera a mano', () => {
      render(<MethodologyScreen />);
      const ded = hedgeRow('Desdesignación');
      expect(ded).toContain('exige una causa');
      expect(ded).toContain('6.5.6');
      expect(ded).toContain('se mide primero');
      const rel = hedgeRow('Liberación de la reserva');
      expect(rel).toContain('el flujo cubierto ocurrió');
      expect(rel).toContain('ya no se espera');
      expect(rel).toContain('lo congelado menos lo liberado');
    });

    it('declara el derivado fuera de mercado, los avisos del alta y la fecha de designación', () => {
      render(<MethodologyScreen />);
      expect(hedgeRow('Derivado fuera de mercado')).toContain('fuente de inefectividad');
      expect(hedgeRow('Derivado fuera de mercado')).toContain('fin de semana');
      expect(hedgeRow('Fecha de designación')).toContain('no es retroactiva');
      expect(hedgeRow('Efectividad prospectiva')).toContain('sentido');
    });

    it('ya no deja fuera de alcance la designación de componentes de riesgo', () => {
      render(<MethodologyScreen />);
      expect(hedgeRow('Fuera de alcance')).not.toContain('componentes de riesgo');
      expect(hedgeRow('Fuera de alcance')).toContain('libro mayor');
    });

    it('incluye las filas de cambios de nocional y derivado hipotético', () => {
      render(<MethodologyScreen />);
      expect(hedgeRow('Cambios de nocional')).toContain('nocional vigente');
      expect(hedgeRow('Derivado hipotético')).toContain('swap a la par');
    });
  });

  // corte 7
  describe('validación contra QuantLib', () => {
    it('da las tolerancias y la regla de curvas idénticas', () => {
      render(<MethodologyScreen />);
      expect(row('Tolerancias')).toContain('5e-4');
      expect(row('Tolerancias')).toContain('1e-8');
      expect(row('Curvas idénticas')).toContain('lineal en tasa cero');
    });

    it('declara qué no se compara', () => {
      render(<MethodologyScreen />);
      expect(row('Qué no se compara')).toContain('VaR');
      expect(row('Qué no se compara')).toContain('contabilidad de coberturas');
    });

    it('enlaza la pantalla Validación', () => {
      render(<MethodologyScreen />);
      expect(screen.getByRole('link', { name: 'pantalla Validación' }).getAttribute('href')).toBe(
        '/validacion',
      );
    });
  });
  // fin corte 7
});
