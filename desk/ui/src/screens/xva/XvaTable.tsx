import type { XvaCounterparty, XvaCredit } from '../../api/xvaTypes';
import { fmtMoney, fmtNumber } from '../../lib/format';

/** Rótulo corto del origen del crédito de una contraparte. */
function creditTag(credit: XvaCredit): string {
  if (credit.kind === 'assumed') return 'Supuesto';
  if (credit.kind === 'flat') return 'Respaldo plano';
  return credit.source?.kind === 'synthetic' ? 'Curva sintética' : 'Curva';
}

function tradesText(cp: XvaCounterparty): string {
  const included = cp.included.length;
  const excluded = cp.excluded.length;
  const inc = `${included} ${included === 1 ? 'incluida' : 'incluidas'}`;
  return excluded === 0 ? inc : `${inc} · ${excluded} ${excluded === 1 ? 'excluida' : 'excluidas'}`;
}

interface Props {
  counterparties: XvaCounterparty[];
  selected: string | null;
  onSelect: (counterparty: string) => void;
}

export function XvaTable({ counterparties, selected, onSelect }: Props) {
  if (counterparties.length === 0) {
    return <p className="xva-note">No hay contrapartes con operaciones vivas en este snapshot.</p>;
  }
  return (
    <div className="xva-scroll">
      <table className="xva-table" aria-label="XVA por contraparte">
        <thead>
          <tr>
            <th>Contraparte</th>
            <th className="num">PV neto</th>
            <th className="num">CVA</th>
            <th className="num">DVA</th>
            <th className="num">FVA</th>
            <th className="num">Total XVA</th>
            <th className="num">EPE máx.</th>
            <th className="num">PFE máx.</th>
            <th>Operaciones</th>
          </tr>
        </thead>
        <tbody>
          {counterparties.map((cp) => (
            <tr key={cp.counterparty} data-selected={cp.counterparty === selected ? 'true' : undefined}>
              <td>
                <button
                  type="button"
                  className="xva-pick"
                  aria-pressed={cp.counterparty === selected}
                  onClick={() => onSelect(cp.counterparty)}
                >
                  {cp.counterparty}
                </button>
                <span
                  className={`xva-tag${cp.credit.kind === 'assumed' ? ' xva-tag--warn' : ''}`}
                  title={cp.credit.note ?? cp.credit.source?.label ?? undefined}
                >
                  {creditTag(cp.credit)}
                </span>
              </td>
              <td className="num">{fmtMoney(cp.pv_mxn, 'MXN')}</td>
              <td className="num">
                {fmtMoney(cp.cva_mxn, 'MXN')}
                <span className="xva-sub" title="Error estándar de Monte Carlo del CVA">
                  ± {fmtNumber(cp.cva_stderr_mxn, 2)}
                </span>
              </td>
              <td className="num">{fmtMoney(cp.dva_mxn, 'MXN')}</td>
              <td className="num">{fmtMoney(cp.fva_mxn, 'MXN')}</td>
              <td className="num xva-total">{fmtMoney(cp.total_mxn, 'MXN')}</td>
              <td className="num">{fmtMoney(cp.epe_max_mxn, 'MXN')}</td>
              <td className="num">{fmtMoney(cp.pfe_max_mxn, 'MXN')}</td>
              <td>{tradesText(cp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
