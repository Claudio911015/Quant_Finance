import type { Snapshot } from '../api/types';
import { NO_CSA_TEXT } from '../lib/csaLabels';
import { fmtNumber } from '../lib/format';
import { asOfText, kindText } from '../lib/provenance';
import './CsaPanel.css';

const PB_PER_UNIT = 10000; // el diferencial viaja en decimal y se muestra en puntos base

const TITLE = 'Descuento MXN con colateral en USD';

/** Solo lee las cotizaciones y el cotejo; así se prueba sin armar un snapshot completo. */
type CsaSnapshot = Pick<Snapshot, 'csa' | 'fx_forwards' | 'xccy_basis'>;

/**
 * Descuento MXN con colateral en USD: cotizaciones que arman la curva `MXN-USD` y su cotejo.
 * Solo presenta lo que trae el snapshot; sin `csa` (snapshot viejo) no pinta nada.
 */
export default function CsaPanel({ snapshot }: { snapshot: CsaSnapshot }) {
  const csa = snapshot.csa;
  if (!csa) return null;

  if (!csa.available) {
    return (
      <section className="csa" aria-labelledby="csa-title">
        <header className="csa__head">
          <h2 id="csa-title">{TITLE}</h2>
        </header>
        <p className="csa__banner">{csa.message ?? NO_CSA_TEXT}</p>
      </section>
    );
  }

  const forwards = snapshot.fx_forwards ?? [];
  const basis = snapshot.xccy_basis ?? [];
  const implied = csa.implied_vs_quoted;
  const quotedForward = (days: number) => implied.find((r) => r.days === days)?.quoted_forward;

  return (
    <section className="csa" aria-labelledby="csa-title">
      <header className="csa__head">
        <h2 id="csa-title">{TITLE}</h2>
        <span className="csa__meta">cotizaciones de solo lectura</span>
        {csa.source && (
          <p className="csa__source">
            <span className={`csa__kind csa__kind--${csa.source.kind}`}>{kindText(csa.source.kind)}</span>
            <span>{csa.source.label}</span>
            <span className="csa__source-date">{asOfText(csa.source.as_of)}</span>
          </p>
        )}
      </header>

      <div className="csa__tables">
        {forwards.length > 0 && (
          <div className="csa__block">
            <h3>Puntos forward USDMXN</h3>
            <div className="csa__scroll">
              <table className="csa__table" aria-label="Puntos forward USDMXN">
                <thead>
                  <tr>
                    <th scope="col">Plazo</th>
                    <th scope="col" className="num">
                      Días
                    </th>
                    <th scope="col" className="num">
                      Puntos
                    </th>
                    <th scope="col" className="num">
                      Forward cotizado
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {forwards.map((q) => {
                    const quoted = quotedForward(q.days);
                    return (
                      <tr key={`${q.label}-${q.days}`}>
                        <th scope="row">{q.label}</th>
                        <td className="num">{q.days}</td>
                        <td className="num">{fmtNumber(q.points, 4)}</td>
                        <td className="num">{quoted == null ? '—' : fmtNumber(quoted, 4)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {basis.length > 0 && (
          <div className="csa__block">
            <h3>Base de cross currency swaps</h3>
            <div className="csa__scroll">
              <table className="csa__table" aria-label="Base de cross currency swaps">
                <thead>
                  <tr>
                    <th scope="col">Plazo</th>
                    <th scope="col" className="num">
                      Días
                    </th>
                    <th scope="col" className="num">
                      Diferencial (pb)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {basis.map((q) => (
                    <tr key={`${q.label}-${q.days}`}>
                      <th scope="row">{q.label}</th>
                      <td className="num">{q.days}</td>
                      <td className="num">{fmtNumber(q.spread * PB_PER_UNIT, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {implied.length > 0 && (
          <div className="csa__block csa__block--wide">
            <h3>Forward implícito vs cotizado</h3>
            <div className="csa__scroll">
              <table className="csa__table" aria-label="Forward implícito vs cotizado">
                <thead>
                  <tr>
                    <th scope="col">Plazo</th>
                    <th scope="col" className="num">
                      Cotizado
                    </th>
                    <th scope="col" className="num">
                      Implícito
                    </th>
                    <th scope="col" className="num">
                      Paridad TIIE-F/SOFR
                    </th>
                    <th scope="col" className="num">
                      Diferencia
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {implied.map((r) => (
                    <tr key={`${r.label}-${r.days}`}>
                      <th scope="row">{r.label}</th>
                      <td className="num">{fmtNumber(r.quoted_forward, 4)}</td>
                      <td className="num">{fmtNumber(r.implied_forward, 4)}</td>
                      <td className="num">{fmtNumber(r.parity_forward, 4)}</td>
                      <td className="num">{fmtNumber(r.diff, 6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
