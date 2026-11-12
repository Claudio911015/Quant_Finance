import { useMemo, useState } from 'react';
import { getXva } from '../api/xvaClient';
import type { XvaCounterparty, XvaModel, XvaOwnCredit, XvaResponse } from '../api/xvaTypes';
import { fmtMoney, fmtNumber } from '../lib/format';
import { useSnapshot } from '../state/SnapshotContext';
import { productTitle } from './pricers/registry';
import { COLLATERAL_NOTE, XVA_NOTICE, useLoad } from './xva/common';
import { CreditCurvesPanel } from './xva/CreditCurvesPanel';
import { IncrementalPanel } from './xva/IncrementalPanel';
import { XvaParamsPanel } from './xva/XvaParamsPanel';
import { XvaProfileChart } from './xva/XvaProfileChart';
import { XvaTable } from './xva/XvaTable';
import './XvaScreen.css';

const FX_VOL_SOURCE: Record<XvaModel['fx_vol_source'], string> = {
  surface_atm_1y: 'ATM a 1 año de la superficie',
  factor_daily_vol: 'volatilidad diaria de los factores × √252',
};

const pct = (dec: number) => `${fmtNumber(dec * 100, 2)} %`;

function TradesCard({ cp }: { cp: XvaCounterparty }) {
  return (
    <section className="xva-card" aria-labelledby="xva-trades-title">
      <h2 id="xva-trades-title">Operaciones de {cp.counterparty}</h2>
      <h3 className="xva-subtitle">Incluidas en el XVA</h3>
      {cp.included.length === 0 ? (
        <p className="xva-note xva-note--plain">Ninguna.</p>
      ) : (
        <ul className="xva-list">
          {cp.included.map((t) => (
            <li key={t.id}>
              #{t.id} {productTitle(t.product)} · PV {fmtMoney(t.pv_mxn, 'MXN')}
            </li>
          ))}
        </ul>
      )}
      {cp.excluded.length > 0 && (
        <div className="xva-note xva-note--warn" role="status">
          <strong>Excluidas del XVA</strong>
          <ul className="xva-list">
            {cp.excluded.map((t) => (
              <li key={t.id}>
                #{t.id} {productTitle(t.product)}: {t.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function OwnCredit({ own }: { own: XvaOwnCredit }) {
  return (
    <p className="xva-note xva-note--plain">
      Curva propia (DVA y FVA): {own.source?.label ?? 'sin fuente'}; recuperación {pct(own.recovery)}.
      {own.note ? ` ${own.note}` : ''}
    </p>
  );
}

function ModelCard({ data }: { data: XvaResponse }) {
  const { model, params } = data;
  const rows: [string, string, string?][] = [
    ...Object.entries(model.hw).map(([curve, p]): [string, string] => [
      `Hull-White ${curve}`,
      `a = ${fmtNumber(p.a, 4)} · σ = ${pct(p.sigma)}`,
    ]),
    ['Correlación TIIE-F / SOFR', fmtNumber(model.correlations.mxn_usd, 2)],
    ['Correlación TIIE-F / USDMXN', fmtNumber(model.correlations.mxn_fx, 2)],
    ['Correlación SOFR / USDMXN', fmtNumber(model.correlations.usd_fx, 2)],
  ];
  return (
    <section className="xva-card" aria-labelledby="xva-model-title">
      <h2 id="xva-model-title">Supuestos y modelo</h2>
      <div className="xva-scroll">
        <table className="xva-table" aria-label="Parámetros del modelo">
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td>{value}</td>
              </tr>
            ))}
            <tr>
              <th scope="row">Volatilidad USDMXN</th>
              <td>
                <span>{pct(model.fx_vol)}</span>
                <span className="xva-sub">{FX_VOL_SOURCE[model.fx_vol_source]}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <OwnCredit own={data.own_credit} />
      {data.assumptions.length > 0 && (
        <ul className="xva-list">
          {data.assumptions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
      <p className="xva-foot">
        {fmtNumber(params.n_paths, 0)} trayectorias, semilla {params.seed}, PFE al {pct(params.pfe_quantile)}; spread
        de fondeo {fmtNumber(params.funding_spread * 1e4, 0)} pb.
      </p>
    </section>
  );
}

export function XvaScreen() {
  const { snapshotId } = useSnapshot();
  const [selected, setSelected] = useState<string | null>(null);
  // Guardar parámetros o curvas, o pactar una operación, cambia el XVA: se vuelve a pedir sin cambiar de snapshot.
  const [reloadTick, setReloadTick] = useState(0);
  const reload = () => setReloadTick((t) => t + 1);
  const { data, error, loading } = useLoad(() => getXva(snapshotId), snapshotId, reloadTick);

  // Por omisión, la primera; si la elegida ya no está (otro snapshot, o se pactó con otra), también la primera.
  const cp = data ? (data.counterparties.find((c) => c.counterparty === selected) ?? data.counterparties[0]) : undefined;
  const names = useMemo(() => (data ? data.counterparties.map((c) => c.counterparty) : []), [data]);

  return (
    <div className="xva">
      <h1>XVA</h1>
      <p className="xva-notice" role="note">
        {data?.notice ?? XVA_NOTICE}
      </p>
      <p className="xva-collateral">{data?.collateral_note ?? COLLATERAL_NOTE}</p>

      {loading && !data && (
        <p className="xva-note xva-note--plain" role="status">
          Calculando XVA…
        </p>
      )}
      {error && (
        <p className="xva-note xva-note--error" role="alert">
          {error.message}
        </p>
      )}

      {data && (
        <div className={`xva-body${loading ? ' is-loading' : ''}`}>
          {data.warnings.length > 0 && (
            <div className="xva-note xva-note--warn" role="status">
              <ul className="xva-list">
                {data.warnings.map((w, i) => (
                  <li key={i}>{w.message}</li>
                ))}
              </ul>
            </div>
          )}
          <section className="xva-card" aria-labelledby="xva-table-title">
            <h2 id="xva-table-title">XVA por contraparte</h2>
            <XvaTable counterparties={data.counterparties} selected={cp?.counterparty ?? null} onSelect={setSelected} />
            <p className="xva-foot">
              Total XVA = CVA − DVA + FVA. Bajo el CVA, el error estándar de Monte Carlo. PV neto, EPE y PFE son del
              perfil sin descontar.
            </p>
          </section>
          {cp && (
            <div className="xva-grid2">
              <section className="xva-card" aria-labelledby="xva-profile-title">
                <h2 id="xva-profile-title">Perfil de {cp.counterparty}</h2>
                {cp.profile.length === 0 ? (
                  <p className="xva-note xva-note--plain">Sin operaciones incluidas: no hay perfil que simular.</p>
                ) : (
                  <XvaProfileChart cp={cp} pfeQuantile={data.params.pfe_quantile} />
                )}
              </section>
              <TradesCard cp={cp} />
            </div>
          )}
        </div>
      )}

      <div className="xva-grid2">
        {data ? <ModelCard data={data} /> : <div />}
        <XvaParamsPanel onSaved={reload} />
      </div>
      {data && <IncrementalPanel snapshotId={snapshotId} counterparties={names} onTraded={reload} />}
      <CreditCurvesPanel snapshotId={snapshotId} onSaved={reload} />
    </div>
  );
}

export default XvaScreen;
