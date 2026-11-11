import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { MethodologyScreen } from './MethodologyScreen';

/** La pantalla enlaza con `Link` (React Router), así que necesita un enrutador. */
const renderScreen = () =>
  render(
    <MemoryRouter>
      <MethodologyScreen />
    </MemoryRouter>,
  );

/** Texto de la fila `label` de la sección de ciclo de vida. */
function row(label: string): string {
  const term = screen.getByText(label, { selector: 'dt' });
  return term.nextElementSibling?.textContent ?? '';
}

describe('MethodologyScreen', () => {
  it('describe el envejecimiento exacto de bono y cap/floor', () => {
    renderScreen();
    const text = row('Bono y cap/floor envejecidos');
    expect(text).toContain('envejecido día a día');
    expect(text).toContain('se liquidan');
    expect(text).toContain('el caplet ya fijado no entra en el valor');
    expect(text).not.toContain('periodos enteros restantes');
    expect(text).not.toContain('corte 3');
  });

  it('explica la regla de fines de semana y que un inhábil del índice no es faltante', () => {
    renderScreen();
    expect(row('Fines de semana')).toContain('la del viernes devenga también sábado y domingo (3 días)');
    expect(row('Fines de semana')).toContain('no avisan');
    expect(row('Fijación faltante')).toContain('Un día inhábil de su índice no es faltante');
    expect(row('Fijación faltante')).toContain('lunes a viernes');
  });

  it('no conserva frases de "hasta el corte 3" ni "sin calendario de inhábiles"', () => {
    const { container } = renderScreen();
    const text = container.textContent ?? '';
    expect(text).not.toContain('hasta el corte 3');
    expect(text).not.toContain('sin calendario de inhábiles');
  });

  it('la cascada del P&L explicado nombra el paso de los puntos forward y la base de MXN-USD', () => {
    renderScreen();
    expect(row('Orden de la cascada')).toContain('puntos forward y la base que calibran la curva MXN-USD');
  });

  it('usa los mismos rótulos de producto que Pricers', () => {
    const { container } = renderScreen();
    const titles = [...container.querySelectorAll('h3, h2')].map((h) => h.textContent);
    for (const t of ['Forward FX', 'Opción FX', 'Cap / Floor', 'Opción sobre acción']) expect(titles).toContain(t);
  });

  it('describe la sección de colateral y curvas MXN con sus conceptos', () => {
    renderScreen();
    expect(document.getElementById('meth-csa')).not.toBeNull();
    expect(row('Curva MXN-USD')).toContain('Sin cotizaciones no existe');
    expect(row('Efecto del colateral')).toContain('MXN-USD');
    expect(row('Cross currency swap')).toContain('Nocional constante');
    expect(row('Calendarios')).toContain('no se ajustan por inhábil');
  });

  it('declara las limitaciones que dejó la auditoría del corte 3', () => {
    renderScreen();
    // R2: la paridad con TIIE-F es exacta solo con los días de cotización en los pilares de TIIE-F.
    expect(row('Curva MXN-USD')).toContain('solo si los días de cotización coinciden con los pilares de TIIE-F');
    expect(row('Curva MXN-USD')).toContain('No tiene pilar a un día');
    // D7: el forward FX bajo colateral USD casi no reacciona a SOFR.
    expect(row('Efecto del colateral')).toContain('apenas reacciona a un choque de SOFR');
    // D1: el intercambio inicial se liquida al salir del PV (en Estados no se promete que no haya pago inicial).
    expect(row('Cross currency swap')).toContain('se liquida en el P&L');
    expect(row('Estados')).toContain('salvo el intercambio inicial del cross currency swap');
    // D5/D6: cupón corrido a medio día y caplet fijado sin liquidación.
    expect(row('Bono y cap/floor envejecidos')).toContain('medio día');
    expect(row('Bono y cap/floor envejecidos')).toContain('su pago conocido deja de contar');
    // D2: la suma por plazo contra el paralelo, en términos relativos, en portafolios casi neutros.
    expect(row('DV01 por plazo')).toContain('casi neutro');
  });

  it('dice que un swap sin tasa fija nace a la par', () => {
    renderScreen();
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
      renderScreen();
      expect(hedgeRow('Revisión contable')).toContain(
        'Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9',
      );
      expect(hedgeRow('Revisión contable')).toContain('Nadie la ha hecho aún');
    });

    it('describe la regla del menor, el valor razonable, el reciclaje y las simplificaciones', () => {
      renderScreen();
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
      renderScreen();
      expect(hedgeRow('Regla del menor')).toContain('desde la designación');
      expect(hedgeRow('Regla del menor')).toContain('lo ya liquidado');
      const recycling = hedgeRow('Reciclaje');
      expect(recycling).toContain('flujo cubierto proxy');
      expect(recycling).toContain('misma fecha');
      expect(recycling).toContain('reserva queda en 0');
      expect(hedgeRow('Asientos sugeridos')).toContain('saldos acumulados ya redondeados');
    });

    it('declara el componente de tasa, la presentación del cupón y que el ajuste no se amortiza', () => {
      renderScreen();
      const fv = hedgeRow('Valor razonable');
      expect(fv).toContain('componente de tasa de referencia');
      expect(fv).toContain('no por su cupón contractual');
      expect(fv).toContain('no se amortiza');
      expect(fv).toContain('no en gasto por intereses');
    });

    it('declara la reserva con respaldo, el vencimiento del instrumento antes que la partida y el devengo del ajuste', () => {
      renderScreen();
      const least = hedgeRow('Regla del menor');
      expect(least).toContain('mientras no haya parte efectiva');
      expect(least).toContain('6.5.11(a)');
      const recycling = hedgeRow('Reciclaje');
      expect(recycling).toContain('vencen juntos');
      expect(recycling).toContain('Concluida');
      expect(recycling).toContain('6.5.12(a)');
      const fv = hedgeRow('Valor razonable');
      expect(fv).toContain('devengo del cupón en curso');
      expect(fv).toContain('no es un valor limpio');
    });

    it('la desdesignación contrasta la causa con el estado de la operación y mide la terminación', () => {
      renderScreen();
      const ded = hedgeRow('Desdesignación');
      expect(ded).toContain('se contrasta con el estado de la operación');
      expect(ded).toContain('pago de la terminación');
      expect(hedgeRow('Liberación de la reserva')).toContain('desdesignada o concluida');
      expect(hedgeRow('Liberación de la reserva')).toContain('primera fecha de flujo');
    });

    it('la desdesignación exige una causa, mide hasta su fecha y la reserva se libera a mano', () => {
      renderScreen();
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
      renderScreen();
      expect(hedgeRow('Derivado fuera de mercado')).toContain('fuente de inefectividad');
      expect(hedgeRow('Derivado fuera de mercado')).toContain('fin de semana');
      const date = hedgeRow('Fecha de designación');
      expect(date).not.toContain('no es retroactiva'); // el sistema no puede garantizarlo
      expect(date).toContain('orden cronológico');
      expect(date).toContain('no puede comprobar que la documentación existiera');
      expect(date).toContain('más de un día después');
      expect(hedgeRow('Derivado fuera de mercado')).toContain('documentada más de un día después');
      expect(hedgeRow('Efectividad prospectiva')).toContain('sentido');
    });

    it('ya no deja fuera de alcance la designación de componentes de riesgo', () => {
      renderScreen();
      expect(hedgeRow('Fuera de alcance')).not.toContain('componentes de riesgo');
      expect(hedgeRow('Fuera de alcance')).toContain('libro mayor');
    });

    it('incluye las filas de cambios de nocional y derivado hipotético', () => {
      renderScreen();
      expect(hedgeRow('Cambios de nocional')).toContain('nocional vigente');
      expect(hedgeRow('Derivado hipotético')).toContain('swap a la par');
    });
  });

  // --- corte 6: pruebas del grupo de riesgo avanzado ---
  describe('riesgo avanzado (corte 6)', () => {
    function riskRow(label: string): string {
      const section = document.getElementById('meth-riesgo-avanzado')!.closest('section')!;
      const term = Array.from(section.querySelectorAll('dt')).find((dt) => dt.textContent === label);
      return term?.nextElementSibling?.textContent ?? '';
    }

    it('describe la cascada, el residuo y el VaR histórico como sensibilidades', () => {
      renderScreen();
      expect(riskRow('Residuo')).toContain('orden');
      expect(riskRow('VaR histórico')).toContain('sensibilidades');
    });

    it('declara la semilla de la historia sintética y el CVA informativo', () => {
      renderScreen();
      expect(riskRow('Historia sintética de MX-DEMO')).toContain('20261110');
      expect(riskRow('CVA informativo')).toContain('no entra al PV');
      expect(riskRow('Coherencia con la valuación')).toContain('PV del desk');
      expect(riskRow('Alcance del crédito')).toContain('t = 0');
      expect(riskRow('Exposición y CVA')).toContain('máximo entre el PV de la contraparte y cero');
    });

    it('lista los escenarios históricos con sus choques y excluye DVA del alcance', () => {
      renderScreen();
      expect(riskRow('Escenarios históricos')).toContain('Marzo 2020');
      expect(riskRow('Escenarios históricos')).toContain('+35 %');
      expect(riskRow('Fuera de alcance')).toContain('DVA');
    });

    it('"Límites de este corte" ya no dice "Sin XVA": el CVA informativo existe', () => {
      renderScreen();
      const term = Array.from(document.querySelectorAll('dt')).filter((dt) => dt.textContent === 'Alcance').pop();
      const text = term?.nextElementSibling?.textContent ?? '';
      expect(text).toContain('CVA informativo');
      expect(text).not.toContain('Sin XVA');
    });
  });
  // --- fin corte 6 ---
  // corte 7
  describe('validación contra QuantLib', () => {
    it('da las tolerancias y la regla de curvas idénticas', () => {
      renderScreen();
      expect(row('Tolerancias')).toContain('5e-4');
      expect(row('Tolerancias')).toContain('1e-8');
      expect(row('Curvas idénticas')).toContain('lineal en tasa cero');
    });

    it('declara qué no se compara', () => {
      renderScreen();
      expect(row('Qué no se compara')).toContain('VaR');
      expect(row('Qué no se compara')).toContain('contabilidad de coberturas');
    });

    it('enlaza la pantalla Validación', () => {
      renderScreen();
      expect(screen.getByRole('link', { name: 'pantalla Validación' }).getAttribute('href')).toBe(
        '/validacion',
      );
    });
  });
  // fin corte 7
});
