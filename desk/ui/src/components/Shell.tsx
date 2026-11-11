import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';

const LINKS = [
  { to: '/mercado', label: 'Mercado' },
  { to: '/pricers', label: 'Pricers' },
  { to: '/portafolio', label: 'Portafolio' },
  { to: '/riesgo', label: 'Riesgo' },
  { to: '/metodologia', label: 'Metodología' },
];

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div>
      <nav>
        {LINKS.map((l) => (
          <NavLink key={l.to} to={l.to}>
            {l.label}
          </NavLink>
        ))}
      </nav>
      <main>{children}</main>
    </div>
  );
}
