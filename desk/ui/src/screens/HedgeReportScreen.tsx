import { useEffect, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, hedgeReport } from '../api/client';
import type {
  CriticalTerm,
  EffectivenessResponse,
  HedgeReport,
  ItemKind,
  ItemTerms,
  JournalEntry,
} from '../api/types';
import { AccountingNotice } from '../components/AccountingNotice';
import { HEDGE_DECLARATIONS } from '../lib/hedgeDeclarations';
import {
  DEDESIGNATION_CAUSE_LABEL,
  DOC_FIELD_LABEL,
  HEDGE_EVENT_LABEL,
  HEDGE_TYPE_LABEL,
  ITEM_KIND_LABEL,
  RELEASE_CAUSE_LABEL,
  SIDE_LABEL,
  TERM_RESULT_LABEL,
} from '../lib/hedgeLabels';
import { fmtDate, fmtDateTime, fmtMoney, fmtNumber } from '../lib/format';
import { qualityText } from '../lib/provenance';
import { productTitle } from './pricers/registry';
import './HedgeReportScreen.css';

function describe(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

const fmtPct = (fraction: number): string => `${fmtNumber(fraction * 100, 2)} %`;

/** La partida cubierta en una línea, con los rótulos de `hedgeLabels`. */
function describeItem(kind: ItemKind, terms: ItemTerms): string {
  const head = ITEM_KIND_LABEL[kind];
  if ('amount_usd' in terms) {
    return `${head} · ${fmtMoney(terms.amount_usd, 'USD')} · ${SIDE_LABEL[terms.side]} · ${fmtDate(terms.date)}`;
  }
  const ccy = terms.index === 'SOFR' ? 'USD' : 'MXN';
  return `${head} · ${terms.index} · ${fmtMoney(terms.notional, ccy)} · ${SIDE_LABEL[terms.side]} · ${fmtDate(terms.start_date)} a ${fmtDate(terms.maturity_date)}`;
}

function termValue(term: CriticalTerm['term'], v: string | number): string {
  if (typeof v === 'number') return fmtNumber(v, 2);
  return term === 'side' ? (SIDE_LABEL[v] ?? v) : v;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="hedge-report__section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Table({ children }: { children: ReactNode }) {
  return (
    <div className="hedge-report__scroll">
      <table className="hedge-report__table">{children}</table>
    </div>
  );
}

type JournalRow = Pick<JournalEntry, 'account' | 'debit' | 'credit'> & { memo?: string };

/** Asientos con total de cargos y abonos; `memo` solo existe en los asientos por periodo. */
function JournalTable({ rows, memo }: { rows: JournalRow[]; memo: boolean }) {
  const debit = rows.reduce((s, r) => s + r.debit, 0);
  const credit = rows.reduce((s, r) => s + r.credit, 0);
  return (
    <Table>
      <thead>
        <tr>
          <th>Cuenta</th>
          <th className="num">Cargo</th>
          <th className="num">Abono</th>
          {memo && <th>Concepto</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={`${r.account}-${i}`}>
            <td>{r.account}</td>
            <td className="num">{fmtNumber(r.debit, 2)}</td>
            <td className="num">{fmtNumber(r.credit, 2)}</td>
            {memo && <td>{r.memo}</td>}
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th>Total</th>
          <th className="num">{fmtNumber(debit, 2)}</th>
          <th className="num">{fmtNumber(credit, 2)}</th>
          {memo && <th />}
        </tr>
      </tfoot>
    </Table>
  );
}

function Prospective({ data }: { data: HedgeReport['prospective'] }) {
  if ('error' in data) return <p className="hedge-report__error">{data.error}</p>;
  const p: EffectivenessResponse = data;
  return (
    <>
      <p className="hedge-report__dim">
        Snapshot {p.snapshot} · {fmtDate(p.as_of)}
      </p>
      <h3>Términos críticos</h3>
      <Table>
        <thead>
          <tr>
            <th>Término</th>
            <th className="num">Instrumento</th>
            <th className="num">Partida</th>
            <th>Resultado</th>
          </tr>
        </thead>
        <tbody>
          {p.critical_terms.map((t) => (
            <tr key={t.term} className={t.result === 'mismatch' ? 'hedge-report__mismatch' : undefined}>
              <td>{t.label}</td>
              <td className="num">{termValue(t.term, t.instrument)}</td>
              <td className="num">{termValue(t.term, t.item)}</td>
              <td>{TERM_RESULT_LABEL[t.result]}</td>
            </tr>
          ))}
        </tbody>
      </Table>
      <h3>Escenarios</h3>
      <Table>
        <thead>
          <tr>
            <th>Escenario</th>
            <th className="num">Δ instrumento</th>
            <th className="num">Δ partida</th>
            <th className="num">Razón</th>
          </tr>
        </thead>
        <tbody>
          {p.scenarios.map((s) => (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td className="num">{fmtNumber(s.d_inst, 2)}</td>
              <td className="num">{fmtNumber(s.d_hypo, 2)}</td>
              <td className="num">{s.ratio == null ? '—' : fmtNumber(s.ratio, 4)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
      <div className="hedge-report__summary">
        <p>Relación económica: {p.economic_relationship ? 'sí' : 'no'}</p>
        <p>
          En 80 %–125 %: {p.in_reference_range} de {p.scenarios_counted}
        </p>
        <p className="hedge-report__dim">{p.reference_note}</p>
      </div>
    </>
  );
}

function Periods({ report }: { report: HedgeReport }) {
  if (report.periods.length === 0) return <p className="hedge-report__dim">Sin cierres de periodo</p>;
  const cashFlow = report.relationship.hedge_type === 'cash_flow';
  return (
    <Table>
      <thead>
        <tr>
          <th className="num">Fecha</th>
          <th>Snapshot</th>
          <th className="num">Instrumento acumulado</th>
          {cashFlow ? (
            <>
              <th className="num">Δ ORI</th>
              <th className="num">Inefectividad</th>
              <th className="num">Reciclaje</th>
              <th className="num">Saldo ORI</th>
            </>
          ) : (
            <>
              <th className="num">Ajuste de partida</th>
              <th className="num">Inefectividad</th>
              <th className="num">Liquidado</th>
              <th className="num">Resultado del periodo</th>
            </>
          )}
        </tr>
      </thead>
      <tbody>
        {report.periods.map((p) => (
          <tr key={p.id}>
            <td className="num">{fmtDate(p.as_of)}</td>
            <td>{p.snapshot}</td>
            <td className="num">{fmtNumber(p.inst_cum, 2)}</td>
            {cashFlow ? (
              <>
                <td className="num">{fmtNumber(p.d_oci, 2)}</td>
                <td className="num">{fmtNumber(p.ineffectiveness, 2)}</td>
                <td className="num">{fmtNumber(p.recycled, 2)}</td>
                <td className="num">{fmtNumber(p.oci, 2)}</td>
              </>
            ) : (
              <>
                <td className="num">{fmtNumber(p.item_adjustment, 2)}</td>
                <td className="num">{fmtNumber(p.ineffectiveness, 2)}</td>
                <td className="num">{fmtNumber(p.settled_period, 2)}</td>
                <td className="num">{fmtNumber(p.fv_result, 2)}</td>
              </>
            )}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function ReportBody({ report }: { report: HedgeReport }) {
  const { documentation: doc, relationship: rel, fair_value_hierarchy: hier, reserve } = report;
  const inst = doc.hedging_instrument;
  const ded = rel.dedesignation;
  return (
    <>
      <Section title="Documentación de designación">
        <dl className="hedge-report__facts">
          <dt>Tipo de cobertura</dt>
          <dd>{HEDGE_TYPE_LABEL[rel.hedge_type]}</dd>
          <dt>Fecha de designación</dt>
          <dd>{fmtDate(rel.designation_date)}</dd>
          <dt>{DOC_FIELD_LABEL.risk_management_objective}</dt>
          <dd>{doc.risk_management_objective}</dd>
          <dt>{DOC_FIELD_LABEL.hedged_risk}</dt>
          <dd>{doc.hedged_risk}</dd>
          <dt>Partida cubierta</dt>
          <dd>{describeItem(doc.hedged_item.item_kind, doc.hedged_item.item_terms)}</dd>
          <dt>Instrumento de cobertura</dt>
          <dd>
            {`Operación #${inst.trade_id} · ${productTitle(inst.product)} · ${inst.counterparty} · ${fmtPct(inst.fraction)} designado · ${fmtMoney(inst.notional, inst.currency)} · ${fmtDate(inst.start_date)} a ${fmtDate(inst.maturity_date)}`}
          </dd>
          <dt>Razón de cobertura</dt>
          <dd>{fmtNumber(doc.hedge_ratio, 4)}</dd>
          <dt>{DOC_FIELD_LABEL.effectiveness_method}</dt>
          <dd>{doc.effectiveness_method}</dd>
          <dt>{DOC_FIELD_LABEL.ineffectiveness_sources}</dt>
          <dd>{doc.ineffectiveness_sources}</dd>
          {rel.warnings.length > 0 && (
            <>
              <dt>Avisos de la designación</dt>
              <dd>
                <ul className="hedge-report__list">
                  {rel.warnings.map((w) => (
                    <li key={w.code}>{w.message}</li>
                  ))}
                </ul>
              </dd>
            </>
          )}
          {ded && (
            <>
              <dt>Desdesignación</dt>
              <dd>
                {[
                  fmtDate(ded.date),
                  ded.cause ? DEDESIGNATION_CAUSE_LABEL[ded.cause] : null,
                  ded.reason,
                ]
                  .filter((part) => part != null)
                  .join(' · ')}
              </dd>
            </>
          )}
        </dl>
      </Section>

      <Section title="Prueba prospectiva">
        <Prospective data={report.prospective} />
      </Section>

      <Section title="Periodos">
        <Periods report={report} />
      </Section>

      <Section title="Asientos por periodo">
        {report.entries_by_period.length === 0 ? (
          <p className="hedge-report__dim">Sin asientos</p>
        ) : (
          report.entries_by_period.map((p) => (
            <div key={p.period_id} className="hedge-report__period">
              <h3>Periodo al {fmtDate(p.as_of)}</h3>
              <JournalTable rows={p.entries} memo />
            </div>
          ))
        )}
      </Section>

      {report.reserve_releases.length > 0 && (
        <Section title="Liberaciones de reserva">
          {report.reserve_releases.map((r) => (
            <div key={r.id} className="hedge-report__period">
              <h3>Liberación al {fmtDate(r.as_of)}</h3>
              <p className="hedge-report__dim">
                {`${RELEASE_CAUSE_LABEL[r.cause]} · Snapshot ${r.snapshot} · Monto ${fmtMoney(r.amount, 'MXN')} · Reserva restante ${fmtMoney(r.reserve_after, 'MXN')}`}
              </p>
              <JournalTable rows={r.entries} memo />
            </div>
          ))}
        </Section>
      )}

      <Section title="Acumulado">
        {report.entries_total.length === 0 ? (
          <p className="hedge-report__dim">Sin asientos</p>
        ) : (
          <JournalTable rows={report.entries_total} memo={false} />
        )}
      </Section>

      <Section title="Jerarquía de valor razonable">
        <p>
          <strong>Nivel {hier.level}</strong>
        </p>
        <p>{hier.basis}</p>
        <Table>
          <thead>
            <tr>
              <th>Rol</th>
              <th>Snapshot</th>
              <th className="num">Fecha</th>
              <th>Procedencia</th>
            </tr>
          </thead>
          <tbody>
            {hier.snapshots.map((s, i) => (
              <tr key={`${s.role}-${s.snapshot}-${i}`}>
                <td>{s.role === 'designation' ? HEDGE_EVENT_LABEL.designation : HEDGE_EVENT_LABEL.period_close}</td>
                <td>{s.snapshot}</td>
                <td className="num">{fmtDate(s.as_of)}</td>
                <td>{qualityText(s.data_quality)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Section>

      <Section title="Reserva">
        <p>Saldo de la reserva de cobertura: {fmtMoney(reserve.balance, 'MXN')}</p>
        {Math.abs(reserve.released) >= 0.005 && <p>Reserva liberada: {fmtMoney(reserve.released, 'MXN')}</p>}
        {reserve.frozen && reserve.note && <p className="hedge-report__frozen">{reserve.note}</p>}
      </Section>

      <Section title="Supuestos de la metodología">
        <ul className="hedge-report__list">
          {HEDGE_DECLARATIONS.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      </Section>

      <p className="hedge-report__dim">Generado: {fmtDateTime(report.generated_at)}</p>
    </>
  );
}

export default function HedgeReportScreen() {
  const { id: idParam } = useParams();
  const id = idParam != null && /^\d+$/.test(idParam) ? Number(idParam) : null;
  const [report, setReport] = useState<HedgeReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id == null) return;
    let live = true;
    setReport(null);
    setError(null);
    hedgeReport(id).then(
      (r) => {
        if (live) setReport(r);
      },
      (e: unknown) => {
        if (live) setError(describe(e));
      },
    );
    return () => {
      live = false;
    };
  }, [id]);

  return (
    <article className="hedge-report">
      <div className="hedge-report__actions">
        <Link to={id != null ? `/coberturas/${id}` : '/coberturas'}>Volver</Link>
        <button type="button" className="hedge-report__btn" onClick={() => window.print()}>
          Imprimir
        </button>
      </div>
      <h1>Reporte de relación de cobertura{id != null ? ` #${id}` : ''}</h1>
      <AccountingNotice />
      {id == null && (
        <div className="hedge-report__banner" role="alert">
          Cobertura inválida
        </div>
      )}
      {error && (
        <div className="hedge-report__banner" role="alert">
          {error}
        </div>
      )}
      {id != null && !error && !report && <p className="hedge-report__dim">Cargando reporte…</p>}
      {report && <ReportBody report={report} />}
    </article>
  );
}
