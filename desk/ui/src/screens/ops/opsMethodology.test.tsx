import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { MethodologyScreen } from '../MethodologyScreen';

/** Texto de la fila `label` (sobre `<dt>`) de cualquier sección de Metodología. */
function row(label: string): string {
  const term = screen.getByText(label, { selector: 'dt' });
  return term.nextElementSibling?.textContent ?? '';
}

describe('Metodología de operaciones', () => {
  it('muestra las siete funciones de operaciones', () => {
    const { container } = render(
      <MemoryRouter>
        <MethodologyScreen />
      </MemoryRouter>,
    );
    // "Fuera de alcance" aparece también en "Límites de este corte": se acota a la sección.
    const section = container.querySelector('#meth-operaciones')?.closest('section');
    expect(section).toBeTruthy();
    for (const label of [
      'Calendario de flujos',
      'Liquidación confirmada',
      'Confirmación',
      'FpML',
      'Conciliación',
      'Descomposición indicativa',
      'Fuera de alcance',
    ]) {
      const terms = Array.from(section?.querySelectorAll('dt') ?? []).map((d) => d.textContent);
      expect(terms).toContain(label);
    }
  });

  it('FpML menciona la validación XSD', () => {
    render(
      <MemoryRouter>
        <MethodologyScreen />
      </MemoryRouter>,
    );
    expect(row('FpML')).toContain('XSD');
  });

  it('Conciliación menciona el umbral de 0.01 %', () => {
    render(
      <MemoryRouter>
        <MethodologyScreen />
      </MemoryRouter>,
    );
    expect(row('Conciliación')).toContain('0.01 %');
  });
});
