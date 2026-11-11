import { useEffect, useMemo, useState } from 'react';
import { ApiError, getValidationReport } from '../api/client';
import type {
  KnownDifferenceKind,
  ValidationProduct,
  ValidationReport,
  ValidationVerdict
} from '../api/types';
import { fmtDate, fmtDateTime, fmtNumber } from '../lib/format';
import './ValidationScreen.css';

const VERDICT_LABEL: Record<ValidationVerdict, string> = {
  ok: 'Dentro de tolerancia',
  explained: 'Diferencia explicada',
  fail: 'Fuera de tolerancia'
};

const KIND_LABEL: Record<KnownDifferenceKind, string> = {
  convention: 'Convención',
  interpolation: 'Interpolación',
  defect: 'Defecto abierto'
};

const SOURCE_LABEL = { portfolio: 'Portafolio de ejemplo', battery: 'Batería' } as const;

const VERDICTS: ValidationVerdict[] = ['ok', 'explained', 'fail'];

const NOT_FOUND =
  'Aún no hay reporte de validación. Genera uno con desk/validation/make_report.sh.';

/** Diferencias y tolerancias: notación científica con 2 decimales; `0` → "0", `null` → "—". */
function fmtSci(v: number | null): string {
  if (v === null) return '—';
  return v === 0 ? '0' : v.toExponential(2);
}

/** PV y nocionales; `null` (sin referencia) → "—". */
function fmtPv(v: number | null): string {
  return v === null ? '—' : fmtNumber(v, 2);
}

/** Commits a 7 caracteres. */
function short(commit: string | null): string {
  return commit ? commit.slice(0, 7) : '—';
}

type Load =
  | { state: 'loading' }
  | { state: 'ready'; report: ValidationReport }
  | { state: 'missing' }
  | { state: 'error'; message: string };

export default function ValidationScreen() {
  const [load, setLoad] = useState<Load>({ state: 'loading' });

  useEffect(() => {
    let cancelled = false;
    getValidationReport()
      .then((report) => {
        if (!cancelled) setLoad({ state: 'ready', report });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) setLoad({ state: 'missing' });
        else setLoad({ state: 'error', message: e instanceof ApiError ? e.message : 'No se pudo conectar con el backend' });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="vld">
      <h1>Validación independiente</h1>
      {load.state === 'loading' && <p className="vld-dim">Cargando reporte de validación…</p>}
      {load.state === 'missing' && (
        <p className="vld-empty" role="status">
          {NOT_FOUND}
        </p>
      )}
      {load.state === 'error' && (
        <p className="vld-error" role="alert">
          {load.message}
        </p>
      )}
      {load.state === 'ready' && <ReportView report={load.report} />}
    </section>
  );
}

function ReportView({ report }: { report: ValidationReport }) {
  const [product, setProduct] = useState<'all' | ValidationProduct>('all');
  const [verdict, setVerdict] = useState<'all' | ValidationVerdict>('all');

  const productLabel = useMemo(() => {
    const labels: Record<string, string> = {};
    report.summary.forEach((s) => {
      labels[s.product] = s.label;
    });
    return labels;
  }, [report.summary]);

  const shown = useMemo(
    () =>
      report.cases.filter(
        (c) => (product === 'all' || c.product === product) && (verdict === 'all' || c.verdict === verdict)
      ),
    [report.cases, product, verdict]
  );

  const { reference, snapshot, totals, reproduce } = report;

  return (
    <>
      <p className="vld-dim vld-provenance">
        {`Generado el ${fmtDateTime(report.generated_at)} · QuantLib ${reference.version} (Python ${reference.python}, entorno ${reference.env}) · snapshot ${snapshot.id} al ${fmtDate(snapshot.as_of)} · commit ${short(report.desk_commit)}`}
      </p>

      {report.commit_matches === false && (
        <p className="vld-warning" role="status">
          {`El reporte se generó con el commit ${short(report.desk_commit)} y el código de valuación actual está en ${short(report.current_commit)}: regenera el reporte (ver «Cómo reproducir»).`}
        </p>
      )}
      {report.commit_matches === null && (
        <p className="vld-warning" role="status">
          No se pudo determinar el commit actual del código de valuación.
        </p>
      )}
      {report.desk_dirty === true && (
        <p className="vld-warning" role="status">
          El reporte se generó con cambios sin commit en el código de valuación.
        </p>
      )}

      <p className="vld-totals">
        <b>{totals.cases}</b> casos · <b>{totals.within}</b> dentro de tolerancia · <b>{totals.explained}</b> con
        diferencia explicada · <b className={totals.failed > 0 ? 'vld-totals__fail' : undefined}>{totals.failed}</b>{' '}
        fuera de tolerancia
      </p>

      <div className="vld-card">
        <h2 id="vld-h-summary">Resumen por producto</h2>
        <div className="vld-scroll">
          <table className="vld-table" aria-labelledby="vld-h-summary">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Método de referencia</th>
                <th className="num">Casos</th>
                <th className="num">Dentro</th>
                <th className="num">Explicadas</th>
                <th className="num">Fuera</th>
                <th className="num">Peor diferencia (rel. al nocional)</th>
                <th className="num">Tolerancia</th>
              </tr>
            </thead>
            <tbody>
              {report.summary.map((s) => (
                <tr key={s.product}>
                  <td>{s.label}</td>
                  <td className="vld-wrap">{s.method}</td>
                  <td className="num">{s.cases}</td>
                  <td className="num">{s.within}</td>
                  <td className="num">{s.explained}</td>
                  <td className={s.failed > 0 ? 'num vld-fail' : 'num'}>{s.failed}</td>
                  <td className="num">{fmtSci(s.worst_rel_diff)}</td>
                  <td className="num">{fmtSci(s.tolerance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="vld-card">
        <h2 id="vld-h-curves">Curvas</h2>
        <div className="vld-scroll">
          <table className="vld-table" aria-labelledby="vld-h-curves">
            <thead>
              <tr>
                <th>Curva</th>
                <th>Interpolación</th>
                <th className="num">Máx. diferencia en pilares</th>
                <th className="num">Máx. diferencia en fechas intermedias</th>
                <th className="num">Tolerancias</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {report.curves.map((c) => (
                <tr key={c.curve}>
                  <td>{c.curve}</td>
                  <td className="vld-wrap">{c.interpolation}</td>
                  <td className="num">{fmtSci(c.pillar_max_abs_diff)}</td>
                  <td className="num">{fmtSci(c.check_max_abs_diff)}</td>
                  <td className="num">{`pilares ${fmtSci(c.pillar_tolerance)} · intermedias ${fmtSci(c.check_tolerance)}`}</td>
                  <td className={c.ok ? 'vld-ok' : 'vld-fail'}>{c.ok ? 'Idénticas' : 'Difieren'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="vld-card">
        <h2 id="vld-h-cases">Casos</h2>
        <div className="vld-filters">
          <select
            className="vld-select"
            aria-label="Producto"
            value={product}
            onChange={(e) => setProduct(e.target.value as 'all' | ValidationProduct)}
          >
            <option value="all">Todos los productos</option>
            {report.summary.map((s) => (
              <option key={s.product} value={s.product}>
                {s.label}
              </option>
            ))}
          </select>
          <select
            className="vld-select"
            aria-label="Veredicto"
            value={verdict}
            onChange={(e) => setVerdict(e.target.value as 'all' | ValidationVerdict)}
          >
            <option value="all">Todos los veredictos</option>
            {VERDICTS.map((v) => (
              <option key={v} value={v}>
                {VERDICT_LABEL[v]}
              </option>
            ))}
          </select>
          <span className="vld-dim">{`Mostrando ${shown.length} de ${report.cases.length} casos`}</span>
        </div>
        <div className="vld-scroll">
          <table className="vld-table" aria-labelledby="vld-h-cases">
            <thead>
              <tr>
                <th>Caso</th>
                <th>Producto</th>
                <th>Descripción</th>
                <th>Moneda</th>
                <th className="num">Nocional</th>
                <th className="num">PV QF Desk</th>
                <th className="num">PV QuantLib</th>
                <th className="num">Diferencia</th>
                <th className="num">Dif. relativa</th>
                <th className="num">Tolerancia</th>
                <th>Veredicto</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>{productLabel[c.product] ?? c.product}</td>
                  <td className="vld-wrap">
                    {c.label}
                    {c.source === 'portfolio' && <span className="vld-tag">{SOURCE_LABEL.portfolio}</span>}
                  </td>
                  <td>{c.currency}</td>
                  <td className="num">{fmtPv(c.notional)}</td>
                  <td className="num">{fmtPv(c.pv_desk)}</td>
                  <td className="num">{fmtPv(c.pv_ref)}</td>
                  <td className="num">{fmtSci(c.abs_diff)}</td>
                  <td className="num">{fmtSci(c.rel_diff)}</td>
                  <td className="num">{fmtSci(c.tolerance)}</td>
                  <td className={`vld-verdict vld-verdict--${c.verdict}`} title={c.error ?? undefined}>
                    {VERDICT_LABEL[c.verdict]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="vld-card">
        <h2>Diferencias conocidas</h2>
        {report.known_differences.length === 0 ? (
          <p className="vld-dim">Ninguna: todos los casos están dentro de su tolerancia.</p>
        ) : (
          report.known_differences.map((k) => (
            <article className="vld-known" key={k.case_id}>
              <dl>
                <dt>Caso</dt>
                <dd>{`${k.case_id} · ${k.label}`}</dd>
                <dt>Producto</dt>
                <dd>{productLabel[k.product] ?? k.product}</dd>
                <dt>Tipo</dt>
                <dd>{KIND_LABEL[k.kind]}</dd>
                <dt>Convención</dt>
                <dd>{k.convention}</dd>
                <dt>Causa</dt>
                <dd>{k.cause}</dd>
                <dt>Magnitud</dt>
                <dd>{`esperada ${fmtSci(k.expected_rel_diff)} · observada ${fmtSci(k.observed_rel_diff)} · tolerancia ${fmtSci(k.tolerance)}`}</dd>
              </dl>
            </article>
          ))
        )}
      </div>

      <div className="vld-card">
        <h2>Cómo reproducir</h2>
        <pre className="vld-pre">{[reproduce.command, ...reproduce.steps.map((s, i) => `${i + 1}. ${s}`)].join('\n')}</pre>
        <p className="vld-dim">{`Python del backend: ${reproduce.backend_python}`}</p>
        <p className="vld-dim">{`Python de QuantLib: ${reproduce.quantlib_python}`}</p>
      </div>
    </>
  );
}
