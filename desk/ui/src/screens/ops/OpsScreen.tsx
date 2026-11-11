import { useSearchParams } from 'react-router-dom';
import { CashflowsPanel } from './CashflowsPanel';
import { ReconciliationPanel } from './ReconciliationPanel';
import './OpsScreen.css';

type Tab = 'flujos' | 'conciliacion';

const TABS: { id: Tab; label: string }[] = [
  { id: 'flujos', label: 'Flujos' },
  { id: 'conciliacion', label: 'Conciliación' },
];

export default function OpsScreen() {
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get('tab') === 'conciliacion' ? 'conciliacion' : 'flujos';

  return (
    <section className="ops">
      <h1>Operaciones</h1>
      <div className="ops__tabs" role="tablist" aria-label="Vistas de operaciones">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`ops-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`ops-panel-${t.id}`}
            className="ops__tab"
            onClick={() => setParams({ tab: t.id })}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`ops-panel-${tab}`}
        aria-labelledby={`ops-tab-${tab}`}
        className="ops__panel"
      >
        {tab === 'flujos' ? <CashflowsPanel /> : <ReconciliationPanel />}
      </div>
    </section>
  );
}
