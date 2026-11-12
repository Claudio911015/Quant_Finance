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

  it('la cascada convierte los flujos en dólares liquidados al spot de origen y manda la diferencia a Tipo de cambio', () => {
    renderScreen();
    const text = row('Orden de la cascada');
    expect(text).toContain('Los flujos en dólares liquidados en la ventana se convierten, en el primer paso, al tipo de cambio del snapshot de origen');
    expect(text).toContain('FIX de la fecha del flujo o, a falta de él, el spot final');
    expect(text).toContain('va al paso de tipo de cambio');
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
      expect(riskRow('Coherencia con la valuación')).toContain('términos envejecidos');
      expect(riskRow('Coherencia con la valuación')).toContain('cross currency');
      for (const stale of ['tasa fija efectiva', 'pagos diarios', 'escalón en el primer mes', '86 mil']) {
        expect(riskRow('Coherencia con la valuación'), stale).not.toContain(stale);
      }
      expect(riskRow('Crédito y XVA')).toContain('sección XVA');
      expect(riskRow('Crédito y XVA')).not.toContain('500 trayectorias');
    });

    it('ya no tiene las filas de crédito del escalón: el XVA las reemplaza', () => {
      renderScreen();
      const labels = Array.from(document.querySelectorAll('dt')).map((dt) => dt.textContent);
      expect(labels).not.toContain('Exposición y CVA');
      expect(labels).not.toContain('Supuestos de crédito');
      expect(labels).not.toContain('Alcance del crédito');
    });

    it('lista los escenarios históricos con sus choques y deja fuera de alcance el VaR completo', () => {
      renderScreen();
      expect(riskRow('Escenarios históricos')).toContain('Marzo 2020');
      expect(riskRow('Escenarios históricos')).toContain('+35 %');
      expect(riskRow('Fuera de alcance')).toContain('VaR por revaluación completa');
      expect(riskRow('Fuera de alcance')).not.toContain('DVA');
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
  // corte 9: sección XVA
  describe('XVA (corte 9)', () => {
    function xvaRow(label: string): string {
      const section = document.getElementById('meth-xva')!.closest('section')!;
      const term = Array.from(section.querySelectorAll('dt')).find((dt) => dt.textContent === label);
      return term?.nextElementSibling?.textContent ?? '';
    }

    it('tiene el encabezado XVA con sus filas', () => {
      renderScreen();
      expect(screen.getByRole('heading', { name: 'XVA' })).toBeTruthy();
      for (const label of [
        'Modelo y medida',
        'Parámetros del XVA',
        'Definiciones',
        'XVA incremental',
        'Curvas de crédito',
        'Convenciones del CDS',
        'Límites del XVA',
      ]) {
        expect(xvaRow(label), label).not.toBe('');
      }
    });

    it('declara el modelo, la medida y la deriva quanto', () => {
      renderScreen();
      expect(xvaRow('Modelo y medida')).toContain('Hull-White');
      expect(xvaRow('Modelo y medida')).toContain('riesgo neutral MXN');
      expect(xvaRow('Modelo y medida')).toContain('quanto');
      expect(xvaRow('Modelo y medida')).toContain('semilla fijas');
    });

    it('distingue parámetros de datos de los supuestos', () => {
      renderScreen();
      expect(xvaRow('Parámetros del XVA')).toContain('Supuestos');
      expect(xvaRow('Parámetros del XVA')).toContain('Correlaciones');
    });

    it('define CVA, DVA y FVA y el perfil que se compara con límites', () => {
      renderScreen();
      expect(xvaRow('Definiciones')).toContain('CVA');
      expect(xvaRow('Definiciones')).toContain('DVA');
      expect(xvaRow('Definiciones')).toContain('FVA');
      expect(xvaRow('Definiciones')).toContain('sin descontar');
    });

    it('explica el incremental como diferencia con y sin la operación', () => {
      renderScreen();
      expect(xvaRow('XVA incremental')).toContain('con y sin');
      expect(xvaRow('XVA incremental')).toContain('mismas trayectorias');
    });

    it('declara que el CVACalculator anterior quedó fuera de uso por un sesgo medido', () => {
      renderScreen();
      expect(xvaRow('Motor anterior retirado')).toContain('CVACalculator');
      expect(xvaRow('Motor anterior retirado')).toContain('+7 %');
      expect(xvaRow('Motor anterior retirado')).toContain('curva con pendiente');
    });

    it('declara que las curvas de crédito son sintéticas y su método', () => {
      renderScreen();
      expect(xvaRow('Curvas de crédito')).toContain('Sintéticas');
      expect(xvaRow('Curvas de crédito')).toContain('no son datos de mercado');
      expect(xvaRow('Curvas de crédito')).toContain('Bootstrap');
      expect(xvaRow('Curvas de crédito')).toContain('CDS');
    });

    it('declara las convenciones simplificadas del CDS', () => {
      renderScreen();
      const row = xvaRow('Convenciones del CDS');
      expect(row).toContain('trimestrales');
      expect(row).toContain('round(k·365/4)');
      expect(row).toContain('sin fechas IMM');
      expect(row).toContain('calendario');
      expect(row).toContain('ACT/360');
      expect(row).toContain('mitad de periodo');
      expect(row).toContain('prima devengada');
    });

    it('declara los límites: wrong-way, base determinista, productos excluidos y error de MC', () => {
      renderScreen();
      expect(xvaRow('Límites del XVA')).toContain('wrong-way');
      expect(xvaRow('Límites del XVA')).toContain('Base de cross currency determinista');
      expect(xvaRow('Límites del XVA')).toContain('opciones');
      expect(xvaRow('Límites del XVA')).toContain('error estándar del CVA');
    });
  });
  // fin corte 9
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
