import { useState, type ReactNode } from 'react';
import { CreditTab } from './CreditTab';
import { LimitsTab } from './LimitsTab';
import { PnlExplainTab } from './PnlExplainTab';
import { ScenarioLibraryTab } from './ScenarioLibraryTab';
import { VarTab } from './VarTab';
import { RISK_TABS, type RiskTabId } from './labels';
import './risk-adv.css';

const DEFAULT_TAB: RiskTabId = 'sensibilidades';

function isTabId(value: string | null): value is RiskTabId {
  return RISK_TABS.some((t) => t.id === value);
}

/** Pestaña inicial: `?tab=` si es válida; sin router, se lee de la URL actual. */
function initialTab(): RiskTabId {
  const value = new URLSearchParams(window.location.search).get('tab');
  return isTabId(value) ? value : DEFAULT_TAB;
}

/** Deja `?tab=<id>` en la URL sin tocar el resto de la consulta ni el historial. */
function writeTab(id: RiskTabId) {
  const params = new URLSearchParams(window.location.search);
  params.set('tab', id);
  window.history.replaceState(window.history.state, '', `?${params.toString()}${window.location.hash}`);
}

function renderTab(id: RiskTabId, sensitivities: ReactNode): ReactNode {
  switch (id) {
    case 'sensibilidades':
      return sensitivities;
    case 'var':
      return <VarTab />;
    case 'pnl':
      return <PnlExplainTab />;
    case 'limites':
      return <LimitsTab />;
    case 'credito':
      return <CreditTab />;
    case 'escenarios':
      return <ScenarioLibraryTab />;
  }
}

export function RiskTabs({ sensitivities }: { sensitivities: ReactNode }) {
  const [tab, setTab] = useState<RiskTabId>(initialTab);

  const select = (id: RiskTabId) => {
    setTab(id);
    writeTab(id);
  };

  return (
    <>
      <div className="radv-tabs" role="tablist" aria-label="Vistas de riesgo">
        {RISK_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`risk-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="risk-panel"
            className="radv-tab"
            onClick={() => select(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {/* Solo se monta la pestaña activa: cada una pide sus datos al abrirse. */}
      <div role="tabpanel" id="risk-panel" aria-labelledby={`risk-tab-${tab}`} className="radv-panel">
        {renderTab(tab, sensitivities)}
      </div>
    </>
  );
}
