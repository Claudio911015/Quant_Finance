import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RiskTabs } from './RiskTabs';

// Las pestañas reales las prueba cada tarea; aquí se aísla el contenedor con stubs propios.
vi.mock('./VarTab', () => ({ VarTab: () => <section data-testid="var-stub" /> }));
vi.mock('./PnlExplainTab', () => ({ PnlExplainTab: () => <section data-testid="pnl-stub" /> }));
vi.mock('./LimitsTab', () => ({ LimitsTab: () => <section data-testid="limites-stub" /> }));
vi.mock('./ScenarioLibraryTab', () => ({ ScenarioLibraryTab: () => <section data-testid="escenarios-stub" /> }));

const LABELS = ['Sensibilidades', 'VaR', 'P&L explicado', 'Límites', 'Crédito', 'Escenarios'];

function renderTabs() {
  return render(
    <MemoryRouter>
      <RiskTabs sensitivities={<p>contenido de sensibilidades</p>} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.history.replaceState(null, '', '/riesgo');
});

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('RiskTabs', () => {
  it('muestra las seis pestañas en orden y con su texto', () => {
    renderTabs();
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((t) => t.textContent)).toEqual(LABELS);
    expect(screen.getByRole('tablist').getAttribute('aria-label')).toBe('Vistas de riesgo');
  });

  it('por omisión abre Sensibilidades con el contenido recibido', () => {
    renderTabs();
    expect(screen.getByRole('tab', { name: 'Sensibilidades' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tabpanel').textContent).toContain('contenido de sensibilidades');
    expect(screen.queryByTestId('var-stub')).toBeNull();
  });

  it('clic en VaR monta su pestaña, desmonta la anterior y deja ?tab=var en la URL', () => {
    renderTabs();
    fireEvent.click(screen.getByRole('tab', { name: 'VaR' }));
    expect(screen.getByTestId('var-stub')).toBeTruthy();
    expect(screen.queryByText('contenido de sensibilidades')).toBeNull();
    expect(screen.getByRole('tab', { name: 'VaR' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tab', { name: 'Sensibilidades' }).getAttribute('aria-selected')).toBe('false');
    expect(window.location.search).toBe('?tab=var');
    expect(window.location.pathname).toBe('/riesgo');
  });

  it('cada pestaña monta solo su contenido', () => {
    renderTabs();
    const expected: [string, string][] = [
      ['P&L explicado', 'pnl-stub'],
      ['Límites', 'limites-stub'],
      ['Escenarios', 'escenarios-stub'],
    ];
    for (const [label, testId] of expected) {
      fireEvent.click(screen.getByRole('tab', { name: label }));
      expect(screen.getByTestId(testId)).toBeTruthy();
      expect(screen.getAllByTestId(/-stub$/)).toHaveLength(1);
    }
  });

  it('cambiar de pestaña conserva el resto de la consulta', () => {
    window.history.replaceState(null, '', '/riesgo?x=1&tab=var#abajo');
    renderTabs();
    fireEvent.click(screen.getByRole('tab', { name: 'Límites' }));
    expect(new URLSearchParams(window.location.search).get('x')).toBe('1');
    expect(new URLSearchParams(window.location.search).get('tab')).toBe('limites');
    expect(window.location.hash).toBe('#abajo');
  });

  it('?tab=credito inicial abre Crédito, que remite a la pantalla XVA', () => {
    window.history.replaceState(null, '', '/riesgo?tab=credito');
    renderTabs();
    expect(screen.getByRole('tab', { name: 'Crédito' }).getAttribute('aria-selected')).toBe('true');
    const panel = screen.getByRole('tabpanel');
    expect(panel.textContent).toContain('El crédito, la exposición y el XVA están en la pantalla XVA');
    expect(panel.textContent).toContain('los límites siguen en Límites');
    expect(within(panel).getByRole('link', { name: 'XVA' }).getAttribute('href')).toBe('/xva');
  });

  it('la pestaña Crédito ya no monta ninguna pantalla propia', () => {
    renderTabs();
    fireEvent.click(screen.getByRole('tab', { name: 'Crédito' }));
    expect(screen.queryAllByTestId(/-stub$/)).toHaveLength(0);
  });

  it('un ?tab= inválido cae en Sensibilidades', () => {
    window.history.replaceState(null, '', '/riesgo?tab=nada');
    renderTabs();
    expect(screen.getByRole('tab', { name: 'Sensibilidades' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tabpanel').textContent).toContain('contenido de sensibilidades');
  });
});
