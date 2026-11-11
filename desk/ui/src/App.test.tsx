import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import App from './App';
import { SnapshotProvider } from './state/SnapshotContext';

describe('App', () => {
  it('renderiza /metodologia sin lanzar', () => {
    render(
      <SnapshotProvider>
        <MemoryRouter initialEntries={['/metodologia']}>
          <App />
        </MemoryRouter>
      </SnapshotProvider>,
    );
    expect(screen.getByRole('heading', { name: 'Metodología' })).toBeTruthy();
  });
});
