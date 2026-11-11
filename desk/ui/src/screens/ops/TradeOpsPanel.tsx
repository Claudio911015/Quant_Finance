// Fila de operaciones en la ficha: enlace a la confirmación, descarga FpML y referencia del banco.
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ProductId } from '../../api/types';
import { ApiError } from '../../api/client';
import { fpmlUrl, getTradeRef, putTradeRef } from '../../api/opsClient';
import { FPML_PRODUCTS, NO_CONFIRMATION_PRODUCTS } from './opsLabels';
import './TradeOps.css';

const REF_MAX = 64;

export function TradeOpsPanel({ tradeId, product }: { tradeId: number; product: ProductId }) {
  const [ref, setRef] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getTradeRef(tradeId)
      .then((r) => {
        if (alive) setRef(r.ref);
      })
      .catch(() => {
        if (alive) setRef(null);
      });
    return () => {
      alive = false;
    };
  }, [tradeId]);

  function startEdit() {
    setDraft(ref ?? '');
    setError(null);
    setEditing(true);
  }

  async function save() {
    const value = draft.trim();
    try {
      const saved = await putTradeRef(tradeId, value === '' ? null : value);
      setRef(saved.ref);
      setEditing(false);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'No se pudo guardar la referencia.');
    }
  }

  return (
    <div className="ops-trade" data-testid="trade-ops">
      {!NO_CONFIRMATION_PRODUCTS.includes(product) && (
        <Link to={`/portafolio/${tradeId}/confirmacion`}>Confirmación</Link>
      )}
      {FPML_PRODUCTS.includes(product) && (
        <a href={fpmlUrl(tradeId)} download>
          Descargar FpML
        </a>
      )}
      {editing ? (
        <div className="ops-trade__edit">
          <label>
            Referencia del banco
            <input
              type="text"
              className="ops-trade__input"
              maxLength={REF_MAX}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          </label>
          <button type="button" className="ops-trade__btn" onClick={save}>
            Guardar
          </button>
          <button type="button" className="ops-trade__btn" onClick={() => setEditing(false)}>
            Cancelar
          </button>
          {error && (
            <p className="ops-trade__error" role="alert">
              {error}
            </p>
          )}
        </div>
      ) : (
        <span className="ops-trade__ref">
          Referencia del banco: <strong>{ref ?? '—'}</strong>
          <button type="button" className="ops-trade__btn" onClick={startEdit}>
            Editar
          </button>
        </span>
      )}
    </div>
  );
}
