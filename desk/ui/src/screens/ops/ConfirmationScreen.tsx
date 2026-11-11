import { useEffect, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { getConfirmation, getSettings, putSettings } from '../../api/opsClient';
import type { Confirmation, ConfirmationRow } from '../../api/opsTypes';
import { fmtDate, fmtDateTime, fmtMoney, fmtNumber, fmtRate } from '../../lib/format';
import './ConfirmationScreen.css';

function describe(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

/** Entero sin decimales; si no, hasta 6 decimales sin ceros sobrantes (mínimo 2): 19.5 → "19.50". */
function fmtPlain(v: number): string {
  if (Number.isInteger(v)) return fmtNumber(v, 0);
  return fmtNumber(v, 6).replace(/(\.\d{2}\d*?)0+$/, '$1');
}

/** El valor de un término o convención según su `format` (el backend ya lo clasifica). */
function formatRow(row: ConfirmationRow): string {
  const v = row.value;
  if (typeof v === 'number') {
    switch (row.format) {
      case 'amount':
        return row.currency ? fmtMoney(v, row.currency) : fmtNumber(v, 2);
      case 'rate':
        return fmtRate(v);
      case 'number':
        return fmtPlain(v);
      default:
        return String(v);
    }
  }
  return row.format === 'date' ? fmtDate(v) : v;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="ops-confirm__section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="ops-confirm__facts">
      {rows.map(([label, value]) => (
        <div key={label} className="ops-confirm__fact">
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function RowFacts({ rows }: { rows: ConfirmationRow[] }) {
  return <Facts rows={rows.map((r) => [r.label, <span className="num">{formatRow(r)}</span>])} />;
}

export default function ConfirmationScreen() {
  const { id: idParam } = useParams();
  const id = idParam != null && /^\d+$/.test(idParam) ? Number(idParam) : null;
  const [doc, setDoc] = useState<Confirmation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloads, setReloads] = useState(0);
  // Editor del nombre de la empresa (barra no imprimible). `null` = aún sin valor cargado.
  const [name, setName] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (id == null) return;
    let live = true;
    setDoc(null);
    setError(null);
    getConfirmation(id).then(
      (c) => {
        if (live) setDoc(c);
      },
      (e: unknown) => {
        if (live) setError(describe(e));
      },
    );
    return () => {
      live = false;
    };
  }, [id, reloads]);

  useEffect(() => {
    let live = true;
    getSettings().then(
      (s) => {
        if (live) setName(s.company_name);
      },
      () => {
        // Sin ajustes el editor parte del nombre que muestra la confirmación (ver `nameValue`).
      },
    );
    return () => {
      live = false;
    };
  }, []);

  const nameValue = name ?? doc?.parties.company ?? '';

  async function saveName() {
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await putSettings({ company_name: nameValue.trim() });
      setName(saved.company_name);
      setReloads((n) => n + 1);
    } catch (e: unknown) {
      setSaveError(describe(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="ops-confirm">
      <div className="ops-confirm__bar ops-no-print">
        <div className="ops-confirm__actions">
          <Link to={id != null ? `/portafolio/${id}` : '/portafolio'}>← Volver a la operación</Link>
          <button type="button" className="ops-confirm__btn" onClick={() => window.print()}>
            Imprimir
          </button>
        </div>
        <form
          className="ops-confirm__company"
          onSubmit={(e) => {
            e.preventDefault();
            void saveName();
          }}
        >
          <label htmlFor="ops-confirm-company">Nombre de la empresa</label>
          <input
            id="ops-confirm-company"
            type="text"
            value={nameValue}
            maxLength={200}
            onChange={(e) => setName(e.target.value)}
          />
          <button
            type="submit"
            className="ops-confirm__btn"
            disabled={saving || nameValue.trim() === ''}
          >
            Guardar
          </button>
        </form>
        {saveError && (
          <div className="ops-confirm__banner" role="alert">
            {saveError}
          </div>
        )}
      </div>

      <header className="ops-confirm__head">
        <h1>Confirmación de operación</h1>
        {doc && (
          <p className="ops-confirm__meta">
            {doc.product_label} · Operación {doc.trade_id} · Generada {fmtDateTime(doc.generated_at)}
          </p>
        )}
      </header>

      {id == null && (
        <div className="ops-confirm__banner" role="alert">
          Operación inválida
        </div>
      )}
      {error && (
        <div className="ops-confirm__banner" role="alert">
          {error}
        </div>
      )}

      {doc && (
        <>
          <Section title="Partes">
            <Facts
              rows={[
                ['Empresa', `${doc.parties.company} (${doc.parties.company_role})`],
                ['Contraparte', `${doc.parties.counterparty} (${doc.parties.counterparty_role})`],
                ['Referencia del banco', doc.bank_ref ?? '—'],
              ]}
            />
          </Section>

          <Section title="Fechas">
            <Facts
              rows={[
                ['Fecha de pacto', <span className="num">{fmtDate(doc.dates.trade_date)}</span>],
                ['Fecha de inicio', <span className="num">{fmtDate(doc.dates.start_date)}</span>],
                [
                  'Fecha de vencimiento',
                  <span className="num">{fmtDate(doc.dates.maturity_date)}</span>,
                ],
              ]}
            />
          </Section>

          <Section title="Términos económicos">
            <RowFacts rows={doc.terms} />
          </Section>

          <Section title="Convenciones">
            <RowFacts rows={doc.conventions} />
          </Section>

          <Section title="Calendario de pagos previsto">
            {doc.schedule.length === 0 ? (
              <p className="ops-confirm__dim">Sin pagos previstos.</p>
            ) : (
              <div className="ops-confirm__scroll">
                <table className="ops-confirm__table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Concepto</th>
                      <th className="num">Monto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {doc.schedule.map((s, i) => (
                      <tr key={`${s.date}-${i}`}>
                        <td className="num">{fmtDate(s.date)}</td>
                        <td>{s.description}</td>
                        <td className="num">
                          {s.amount == null ? 'Por determinar' : fmtMoney(s.amount, s.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {doc.events_note && <p className="ops-confirm__note">{doc.events_note}</p>}
          </Section>

          <Section title="Avisos">
            <ul className="ops-confirm__notices">
              {doc.notices.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </Section>
        </>
      )}
    </article>
  );
}
