import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import App from './App';
import { ScreenLoading } from './components/ScreenLoading';
import { SnapshotProvider } from './state/SnapshotContext';

describe('App', () => {
  it('renderiza /metodologia sin lanzar', async () => {
    render(
      <SnapshotProvider>
        <MemoryRouter initialEntries={['/metodologia']}>
          <App />
        </MemoryRouter>
      </SnapshotProvider>,
    );
    // La pantalla llega por React.lazy: el encabezado aparece cuando el trozo carga.
    expect(await screen.findByRole('heading', { name: 'Metodología' })).toBeTruthy();
  });

  it('el estado de carga es un status anunciable', () => {
    render(<ScreenLoading />);
    const status = screen.getByRole('status');
    expect(status.textContent).toBe('Cargando…');
    expect(status.getAttribute('aria-live')).toBe('polite');
  });
});
