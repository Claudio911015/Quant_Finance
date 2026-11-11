import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import OpsScreen from './OpsScreen';

// El panel real de Flujos tiene su propia prueba; aquí solo importa que la pestaña monte su panel.
vi.mock('./CashflowsPanel', () => ({ CashflowsPanel: () => <section data-testid="cashflows-stub" /> }));
// Ídem para Conciliación (su prueba propia está en ReconciliationPanel.test.tsx).
vi.mock('./ReconciliationPanel', () => ({
  ReconciliationPanel: () => <section data-testid="reconciliation-stub" />,
}));

function Where() {
  return <div data-testid="search">{useLocation().search}</div>;
}

function renderOps(initial = '/operaciones') {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <OpsScreen />
      <Where />
    </MemoryRouter>,
  );
}

describe('OpsScreen', () => {
  it('muestra el título y las pestañas Flujos y Conciliación', () => {
    renderOps();
    expect(screen.getByRole('heading', { name: 'Operaciones' })).toBeTruthy();
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((t) => t.textContent)).toEqual(['Flujos', 'Conciliación']);
    expect(screen.getByRole('tablist')).toBeTruthy();
  });

  it('abre en Flujos por omisión', () => {
    renderOps();
    expect(screen.getByRole('tab', { name: 'Flujos' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tab', { name: 'Conciliación' }).getAttribute('aria-selected')).toBe('false');
    expect(screen.getByTestId('cashflows-stub')).toBeTruthy();
    expect(screen.queryByTestId('reconciliation-stub')).toBeNull();
  });

  it('?tab=conciliacion monta el panel de conciliación', () => {
    renderOps('/operaciones?tab=conciliacion');
    expect(screen.getByRole('tab', { name: 'Conciliación' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('reconciliation-stub')).toBeTruthy();
    expect(screen.queryByTestId('cashflows-stub')).toBeNull();
  });

  it('un valor de tab desconocido cae en Flujos', () => {
    renderOps('/operaciones?tab=otra');
    expect(screen.getByTestId('cashflows-stub')).toBeTruthy();
  });

  it('cambiar de pestaña actualiza la dirección y el panel', () => {
    renderOps();
    fireEvent.click(screen.getByRole('tab', { name: 'Conciliación' }));
    expect(screen.getByTestId('search').textContent).toBe('?tab=conciliacion');
    expect(screen.getByTestId('reconciliation-stub')).toBeTruthy();

    fireEvent.click(screen.getByRole('tab', { name: 'Flujos' }));
    expect(screen.getByTestId('search').textContent).toBe('?tab=flujos');
    expect(screen.getByTestId('cashflows-stub')).toBeTruthy();
  });
});
