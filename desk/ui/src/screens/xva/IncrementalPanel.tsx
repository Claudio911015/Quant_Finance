import { useEffect, useState, type FormEvent } from 'react';
import { ApiError, createTrade } from '../../api/client';
import type { ProductId } from '../../api/types';
import { xvaIncremental } from '../../api/xvaClient';
import type { XvaIncrementalBody, XvaIncrementalResponse } from '../../api/xvaTypes';
import { fmtMoney, fmtNumber } from '../../lib/format';
import { Field, initialText, parseParams } from '../pricers/PricerForm';
import { PRODUCT_SPECS, productTitle } from '../pricers/registry';
import { toApiError } from './common';
import { IncrementalChart } from './XvaProfileChart';
import './IncrementalPanel.css';

/** Los únicos productos con XVA: swaps de tasa y cross currency swaps. */
const PRODUCTS = ['irs', 'xccy_swap'] as const;
type CoveredProduct = (typeof PRODUCTS)[number];

const defaultsOf = (product: CoveredProduct): Record<string, string> =>
  Object.fromEntries(PRODUCT_SPECS[product].fields.map((f) => [f.name, initialText(f)]));

interface Calculated {
  /** El cuerpo exacto que se envió: es el que se pacta, aunque el formulario cambie después. */
  body: XvaIncrementalBody;
  response: XvaIncrementalResponse;
}

const COMPONENTS = [
  { key: 'cva', field: 'cva_mxn', label: 'CVA' },
  { key: 'dva', field: 'dva_mxn', label: 'DVA' },
  { key: 'fva', field: 'fva_mxn', label: 'FVA' },
  { key: 'total', field: 'total_mxn', label: 'XVA total' },
] as const;

function ResultTable({ response }: { response: XvaIncrementalResponse }) {
  const { before, after, delta, delta_bp: bp } = response;
  return (
    <div className="xva-scroll">
      <table className="xva-table" aria-label="XVA antes y después">
        <thead>
          <tr>
            <th>Componente</th>
            <th className="num">Antes (MXN)</th>
            <th className="num">Después (MXN)</th>
            <th className="num">Incremental (MXN)</th>
            <th className="num">Incremental (pb)</th>
          </tr>
        </thead>
        <tbody>
          {COMPONENTS.map(({ key, field, label }) => (
            <tr key={key}>
              <td>{label}</td>
              <td className="num">{fmtMoney(before[field], 'MXN')}</td>
              <td className="num">{fmtMoney(after[field], 'MXN')}</td>
              <td className="num">{fmtMoney(delta[field], 'MXN')}</td>
              <td className="num">{fmtNumber(bp[key], 3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface Props {
  snapshotId: string;
  counterparties: string[];
  /** Tras pactar: el XVA del portafolio cambió y hay que volver a pedirlo. */
  onTraded: () => void;
}

/** XVA incremental: lo que cambia el XVA de una contraparte si se pacta una operación nueva. */
export function IncrementalPanel({ snapshotId, counterparties, onTraded }: Props) {
  const [counterparty, setCounterparty] = useState(counterparties[0] ?? '');
  const [product, setProduct] = useState<CoveredProduct>('irs');
  const [values, setValues] = useState<Record<string, string>>(() => defaultsOf('irs'));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [trading, setTrading] = useState(false);
  const [result, setResult] = useState<Calculated | null>(null);
  const [traded, setTraded] = useState<string | null>(null);

  // Si la contraparte elegida ya no está en la lista (otro snapshot), se vuelve a la primera.
  useEffect(() => {
    if (!counterparties.includes(counterparty)) setCounterparty(counterparties[0] ?? '');
  }, [counterparties, counterparty]);

  // Otro snapshot: el resultado calculado ya no aplica.
  useEffect(() => {
    setResult(null);
  }, [snapshotId]);

  const spec = PRODUCT_SPECS[product];
  const fieldNames = spec.fields.map((f) => f.name);

  /** El error de la API va junto al campo que nombra; si no lo reconocemos, en un aviso general. */
  const report = (e: unknown) => {
    const apiError = toApiError(e);
    const known = apiError.field !== null && (['counterparty', 'product'].includes(apiError.field) || fieldNames.includes(apiError.field));
    if (known) setErrors({ [apiError.field as string]: apiError.message });
    else setBanner(apiError.message);
  };

  const changeProduct = (next: CoveredProduct) => {
    setProduct(next);
    setValues(defaultsOf(next));
    setErrors({});
    setBanner(null);
  };

  const setValue = (name: string, v: string) => {
    setValues((prev) => ({ ...prev, [name]: v }));
    setErrors(({ [name]: _gone, ...rest }) => rest);
  };

  const calculate = async (e: FormEvent) => {
    e.preventDefault();
    setTraded(null);
    setBanner(null);
    const { params, errors: invalid } = parseParams(spec, values);
    setErrors(invalid);
    if (Object.keys(invalid).length > 0) return;
    const body: XvaIncrementalBody = { snapshot: snapshotId, counterparty, product, params };
    setCalculating(true);
    try {
      const response = await xvaIncremental(body);
      setResult({ body, response });
    } catch (err) {
      setResult(null);
      report(err);
    } finally {
      setCalculating(false);
    }
  };

  const trade = async () => {
    if (!result) return;
    setBanner(null);
    setTrading(true);
    try {
      const created = await createTrade({
        snapshot: result.body.snapshot,
        counterparty: result.body.counterparty,
        product: result.body.product as ProductId,
        params: result.body.params,
      });
      setResult(null);
      setTraded(`Operación #${created.id} pactada con ${result.body.counterparty}.`);
      onTraded();
    } catch (err) {
      // Pactar usa el mismo cuerpo: sus errores se leen como avisos, no se cuelgan de un campo ya calculado.
      setBanner(err instanceof ApiError ? err.message : 'No se pudo conectar con el backend');
    } finally {
      setTrading(false);
    }
  };

  const cand = result?.response.candidate;
  const idCounterparty = 'xva-inc-counterparty';
  const idProduct = 'xva-inc-product';

  return (
    <section className="xva-card" aria-labelledby="xva-inc-title">
      <h2 id="xva-inc-title">XVA incremental</h2>
      <p className="xva-note xva-note--plain">
        Diferencia del XVA de la contraparte con y sin la operación candidata, sobre las mismas trayectorias. No inserta
        nada hasta que se pacta.
      </p>
      <form className="xva-inc" onSubmit={calculate} noValidate aria-label="Operación candidata">
        <div className="xva-inc__fields">
          <div className="pricer__field">
            <label htmlFor={idCounterparty}>Contraparte</label>
            <select
              id={idCounterparty}
              className="pricer__input"
              value={counterparty}
              aria-invalid={errors.counterparty ? true : undefined}
              aria-describedby={errors.counterparty ? `${idCounterparty}-note` : undefined}
              onChange={(e) => {
                setCounterparty(e.target.value);
                setErrors(({ counterparty: _gone, ...rest }) => rest);
              }}
            >
              {counterparties.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            {errors.counterparty && (
              <div id={`${idCounterparty}-note`} className="pricer__error" role="alert">
                {errors.counterparty}
              </div>
            )}
          </div>
          <div className="pricer__field">
            <label htmlFor={idProduct}>Producto</label>
            <select
              id={idProduct}
              className="pricer__input"
              value={product}
              aria-invalid={errors.product ? true : undefined}
              aria-describedby={errors.product ? `${idProduct}-note` : undefined}
              onChange={(e) => changeProduct(e.target.value as CoveredProduct)}
            >
              {PRODUCTS.map((p) => (
                <option key={p} value={p}>
                  {productTitle(p)}
                </option>
              ))}
            </select>
            {errors.product && (
              <div id={`${idProduct}-note`} className="pricer__error" role="alert">
                {errors.product}
              </div>
            )}
          </div>
          {spec.fields.map((f) => (
            <Field
              key={`${product}:${f.name}`}
              spec={spec}
              field={f}
              value={values[f.name] ?? ''}
              error={errors[f.name]}
              onChange={(v) => setValue(f.name, v)}
            />
          ))}
        </div>
        <div className="xva-actions">
          <button type="submit" className="xva-btn xva-btn--primary" disabled={calculating || counterparties.length === 0}>
            {calculating ? 'Calculando…' : 'Calcular'}
          </button>
        </div>
      </form>

      {banner && (
        <p className="xva-note xva-note--error" role="alert">
          {banner}
        </p>
      )}
      {traded && (
        <p className="xva-note" role="status">
          {traded} El XVA de la tabla se recalcula.
        </p>
      )}

      {result && cand && (
        <div className="xva-inc__result">
          <p className="xva-note xva-note--plain">
            Candidata: {cand.label} · nocional {fmtMoney(cand.notional_mxn, 'MXN')} · PV {fmtMoney(cand.pv_mxn, 'MXN')} ·
            vence {cand.maturity_date}
          </p>
          <ResultTable response={result.response} />
          <IncrementalChart profile={result.response.profile} />
          {result.response.warnings.length > 0 && (
            <ul className="xva-list">
              {result.response.warnings.map((w, i) => (
                <li key={i}>{w.message}</li>
              ))}
            </ul>
          )}
          <div className="xva-actions">
            <button type="button" className="xva-btn" onClick={trade} disabled={trading}>
              {trading ? 'Pactando…' : 'Pactar'}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
