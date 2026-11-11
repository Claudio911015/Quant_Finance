import { useState, type ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { qualityText, sourcesTooltip } from '../lib/provenance';
import { useSnapshot } from '../state/SnapshotContext';
import { CommandPalette } from './CommandPalette';
import './Shell.css';

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      className="shell__icon"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const NAV_ITEMS = [
  {
    to: '/mercado',
    label: 'Mercado',
    icon: (
      <Icon>
        <path d="M2 2.5v11h12" />
        <path d="M4.5 10.5l3-3 2 2 3.5-4.5" />
      </Icon>
    ),
  },
  {
    to: '/pricers',
    label: 'Pricers',
    icon: (
      <Icon>
        <path d="M2 4h12M2 8h12M2 12h12" />
        <circle cx="6" cy="4" r="1.4" fill="currentColor" />
        <circle cx="10.5" cy="8" r="1.4" fill="currentColor" />
        <circle cx="5" cy="12" r="1.4" fill="currentColor" />
      </Icon>
    ),
  },
  {
    to: '/portafolio',
    label: 'Portafolio',
    icon: (
      <Icon>
        <rect x="2" y="3" width="12" height="10" rx="1" />
        <path d="M2 6.5h12M2 10h12" />
      </Icon>
    ),
  },
  {
    to: '/riesgo',
    label: 'Riesgo',
    icon: (
      <Icon>
        <path d="M8 2l5 2v4c0 3-2.2 5-5 6-2.8-1-5-3-5-6V4z" />
      </Icon>
    ),
  },
  {
    to: '/coberturas',
    label: 'Coberturas',
    icon: (
      <Icon>
        <circle cx="6" cy="8" r="3.5" />
        <circle cx="10" cy="8" r="3.5" />
      </Icon>
    ),
  },
  // --- corte 5 ---
  {
    to: '/operaciones',
    label: 'Operaciones',
    icon: (
      <Icon>
        <path d="M2.5 5.5h10M10 3l2.5 2.5L10 8" />
        <path d="M13.5 10.5h-10M6 8l-2.5 2.5L6 13" />
      </Icon>
    ),
  },
  // --- fin corte 5 ---
  {
    to: '/metodologia',
    label: 'Metodología',
    icon: (
      <Icon>
        <path d="M3 2.5h8a2 2 0 0 1 2 2v9H5a2 2 0 0 1-2-2z" />
        <path d="M3 11.5a2 2 0 0 1 2-2h8" />
      </Icon>
    ),
  },
  // corte 7
  {
    to: '/validacion',
    label: 'Validación',
    icon: (
      <Icon>
        <path d="M3 8.5l3 3 7-7" />
      </Icon>
    ),
  },
  // fin corte 7
];

export function Shell({ children }: { children: ReactNode }) {
  const { snapshotId, setSnapshotId, snapshot, snapshots, error } = useSnapshot();
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Mientras llega el snapshot completo se usa el resumen de la lista, para que el
  // distintivo y la fecha no parpadeen al cambiar de snapshot.
  const meta = snapshot ?? snapshots.find((s) => s.id === snapshotId) ?? null;
  const options = snapshots.length > 0 ? snapshots : [{ id: snapshotId, label: snapshotId }];

  return (
    <div className="shell">
      <aside className="shell__sidebar">
        <div className="shell__brand">
          <svg viewBox="0 0 16 16" width="18" height="18" fill="none" aria-hidden="true">
            <rect x="0.75" y="0.75" width="14.5" height="14.5" rx="2.5" stroke="var(--accent)" strokeWidth="1.5" />
            <path d="M3.5 11l3-3.5 2.5 2 3.5-4.5" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="shell__brand-name">QF Desk</span>
        </div>
        <nav className="shell__nav" aria-label="Navegación principal">
          <div className="shell__caption">Navegación</div>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} className="shell__link">
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="shell__body">
        <header className="shell__topbar">
          <div className="shell__field">
            <label htmlFor="shell-snapshot" className="shell__caption">
              Fecha de valuación
            </label>
            <select
              id="shell-snapshot"
              className="shell__select"
              value={snapshotId}
              onChange={(e) => setSnapshotId(e.target.value)}
            >
              {options.map((s) => (
                <option key={s.id} value={s.id}>
                  {'as_of' in s ? `${s.label} · ${s.as_of}` : s.label}
                </option>
              ))}
            </select>
          </div>
          {meta && (
            <span className="shell__meta">
              Valuación al <span className="num">{meta.as_of}</span>
            </span>
          )}
          {meta && (
            <span
              className={`shell__badge shell__badge--${meta.data_quality}`}
              title={sourcesTooltip(meta.sources)}
            >
              {qualityText(meta.data_quality)}
            </span>
          )}
          {error && (
            <span className="shell__error" role="alert">
              {error}
            </span>
          )}
          <button type="button" className="shell__palette-btn" onClick={() => setPaletteOpen(true)}>
            <span>Buscar o ir a…</span>
            <kbd className="shell__kbd">Ctrl K</kbd>
          </button>
        </header>
        <main className="shell__main">{children}</main>
      </div>

      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        screens={NAV_ITEMS.map(({ to, label }) => ({ to, label }))}
      />
    </div>
  );
}
