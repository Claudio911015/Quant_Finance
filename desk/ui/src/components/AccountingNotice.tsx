import './AccountingNotice.css';

export const ACCOUNTING_NOTICE =
  'Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9';

/** Banda siempre visible (también al imprimir) en las pantallas de coberturas. */
export function AccountingNotice() {
  return (
    <div className="accounting-notice" role="note">
      {ACCOUNTING_NOTICE}
    </div>
  );
}
