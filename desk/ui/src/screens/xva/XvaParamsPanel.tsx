import { useEffect, useState, type FormEvent } from 'react';
import type { ApiError } from '../../api/client';
import { getXvaParams, putXvaParams } from '../../api/xvaClient';
import type { XvaParamsBody, XvaParamsResponse } from '../../api/xvaTypes';
import { fmtNumber } from '../../lib/format';
import { fromPb, fromPercent, readNumber, toApiError, toPbText, toPercentText } from './common';

type Key = 'funding_spread' | 'n_paths' | 'seed' | 'pfe_quantile';

interface FieldDef {
  key: Key;
  id: string;
  label: string;
  /** Texto del campo a partir del valor de la API. */
  show: (v: number) => string;
  /** Valor de la API a partir de lo tecleado. */
  send: (n: number) => number;
  /** Lo que se dice como valor por omisión. */
  hint: (v: number) => string;
}

const FIELDS: FieldDef[] = [
  {
    key: 'funding_spread',
    id: 'xvaparams-funding',
    label: 'Spread de fondeo (pb)',
    show: toPbText,
    send: fromPb,
    hint: (v) => `${toPbText(v)} pb`,
  },
  {
    key: 'n_paths',
    id: 'xvaparams-paths',
    label: 'Trayectorias',
    show: String,
    send: (n) => n,
    hint: (v) => fmtNumber(v, 0),
  },
  { key: 'seed', id: 'xvaparams-seed', label: 'Semilla', show: String, send: (n) => n, hint: String },
  {
    key: 'pfe_quantile',
    id: 'xvaparams-quantile',
    label: 'Percentil de PFE (%)',
    show: toPercentText,
    send: fromPercent,
    hint: (v) => `${toPercentText(v)} %`,
  },
];

type Inputs = Record<Key, string>;

const inputsOf = (p: XvaParamsResponse): Inputs =>
  Object.fromEntries(FIELDS.map((f) => [f.key, f.show(p[f.key])])) as Inputs;

/** Fondeo, trayectorias, semilla y percentil de PFE; guardar pide recalcular el XVA. */
export function XvaParamsPanel({ onSaved }: { onSaved: () => void }) {
  const [params, setParams] = useState<XvaParamsResponse | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [inputs, setInputs] = useState<Inputs | null>(null);
  const [errors, setErrors] = useState<Partial<Record<Key, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    getXvaParams().then(
      (p) => {
        if (!live) return;
        setParams(p);
        setInputs(inputsOf(p));
      },
      (e) => {
        if (live) setLoadError(toApiError(e));
      },
    );
    return () => {
      live = false;
    };
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!inputs) return;
    const found: Partial<Record<Key, string>> = {};
    const body = {} as Record<Key, number>;
    for (const f of FIELDS) {
      const n = readNumber(inputs[f.key]);
      if (n === null) found[f.key] = 'Ingresa un número válido';
      else body[f.key] = f.send(n);
    }
    setSaved(false);
    setFormError(null);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setSaving(true);
    try {
      const next = await putXvaParams(body as XvaParamsBody);
      setParams(next);
      setInputs(inputsOf(next));
      setSaved(true);
      onSaved();
    } catch (err) {
      const apiError = toApiError(err);
      const field = FIELDS.find((f) => f.key === apiError.field)?.key;
      if (field) setErrors({ [field]: apiError.message });
      else setFormError(apiError.message);
    } finally {
      setSaving(false);
    }
  };

  const edit = (key: Key, value: string) => {
    setInputs((cur) => (cur ? { ...cur, [key]: value } : cur));
    setSaved(false);
    setErrors(({ [key]: _gone, ...rest }) => rest);
  };

  return (
    <section className="xva-card" aria-labelledby="xvaparams-title">
      <h2 id="xvaparams-title">Parámetros de simulación</h2>
      {loadError && (
        <p className="xva-note xva-note--error" role="alert">
          {loadError.message}
        </p>
      )}
      {params && inputs && (
        <form className="xva-form" onSubmit={submit} noValidate>
          {FIELDS.map((f) => {
            const message = errors[f.key];
            const messageId = `${f.id}-error`;
            return (
              <div className="xva-field" key={f.key}>
                <div className="xva-field__head">
                  <label htmlFor={f.id}>{f.label}</label>
                  {f.key === 'funding_spread' && params.assumed.funding_spread && (
                    <span className="xva-tag xva-tag--warn" title="Sin valor guardado: se usa el de omisión">
                      Supuesto
                    </span>
                  )}
                </div>
                <input
                  id={f.id}
                  type="text"
                  inputMode="decimal"
                  autoComplete="off"
                  value={inputs[f.key]}
                  aria-invalid={message ? true : undefined}
                  aria-describedby={message ? messageId : undefined}
                  onChange={(e) => edit(f.key, e.target.value)}
                />
                {message ? (
                  <span className="xva-field__error" id={messageId} role="alert">
                    {message}
                  </span>
                ) : (
                  <span className="xva-field__hint">Por omisión: {f.hint(params.defaults[f.key])}</span>
                )}
              </div>
            );
          })}
          <button type="submit" className="xva-btn xva-btn--primary" disabled={saving}>
            Guardar parámetros
          </button>
        </form>
      )}
      {formError && (
        <p className="xva-note xva-note--error" role="alert">
          {formError}
        </p>
      )}
      {saved && (
        <p className="xva-note" role="status">
          Parámetros guardados; el XVA se recalcula.
        </p>
      )}
    </section>
  );
}
