import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { ApiError, addFixing, importFixingsCsv, listFixings } from '../api/client';
import type { Fixing, FixingIndex } from '../api/types';
import { fmtDate, fmtNumber, fmtRate } from '../lib/format';
import './FixingsPanel.css';

const INDICES: FixingIndex[] = ['TIIE-F', 'SOFR', 'USDMXN'];

// TIIE-F y SOFR son tasas (decimal en la API, % en pantalla); USDMXN es un tipo de cambio (MXN por USD).
const isRate = (index: FixingIndex) => index !== 'USDMXN';
const fmtValue = (f: Fixing) => (isRate(f.index) ? fmtRate(f.value) : fmtNumber(f.value, 4));

// Las tasas se capturan en % y viajan en decimal; el redondeo evita 0.07010000000000001.
const pctToDec = (pct: number) => Number((pct / 100).toFixed(8));

interface Message {
  ok: boolean;
  text: string;
}

function describeError(e: unknown): string {
  return e instanceof ApiError ? e.message : 'No se pudo conectar con el backend';
}

export default function FixingsPanel() {
  const [filter, setFilter] = useState<{ index: '' | FixingIndex; from: string; to: string }>({
    index: '',
    from: '',
    to: '',
  });
  const [rows, setRows] = useState<Fixing[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [form, setForm] = useState<{ index: FixingIndex; date: string; value: string }>({
    index: 'TIIE-F',
    date: '',
    value: '',
  });
  const [adding, setAdding] = useState(false);
  const [addMsg, setAddMsg] = useState<Message | null>(null);

  const [csv, setCsv] = useState('');
  const [importing, setImporting] = useState(false);
  const [csvMsg, setCsvMsg] = useState<Message | null>(null);

  // Cada carga toma un número; solo la última escribe estado (una respuesta lenta de un
  // filtro anterior no debe pisar la del filtro vigente).
  const latest = useRef(0);

  const load = useCallback(async () => {
    const n = ++latest.current;
    setLoading(true);
    try {
      const data = await listFixings({
        index: filter.index || undefined,
        from: filter.from || undefined,
        to: filter.to || undefined,
      });
      if (n !== latest.current) return;
      setRows(data);
      setListError(null);
    } catch (e) {
      if (n !== latest.current) return;
      setRows([]);
      setListError(describeError(e));
    } finally {
      if (n === latest.current) setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function submitAdd(e: FormEvent) {
    e.preventDefault();
    setAddMsg(null);
    const raw = form.value.trim();
    const num = Number(raw);
    if (!form.date || raw === '' || !Number.isFinite(num)) {
      setAddMsg({ ok: false, text: 'Captura la fecha y el valor' });
      return;
    }
    setAdding(true);
    try {
      const res = await addFixing({
        index: form.index,
        date: form.date,
        value: isRate(form.index) ? pctToDec(num) : num,
      });
      setAddMsg({ ok: true, text: res.created ? 'Fijación guardada' : 'Ya existía' });
      void load();
    } catch (err) {
      setAddMsg({ ok: false, text: describeError(err) });
    } finally {
      setAdding(false);
    }
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const input = e.target;
    const file = input.files?.[0];
    if (!file) return;
    try {
      setCsv(await file.text());
      setCsvMsg(null);
    } catch {
      setCsvMsg({ ok: false, text: 'No se pudo leer el archivo' });
    }
    input.value = '';
  }

  async function submitCsv(e: FormEvent) {
    e.preventDefault();
    setCsvMsg(null);
    setImporting(true);
    try {
      const res = await importFixingsCsv(csv);
      setCsvMsg({ ok: true, text: `Insertadas: ${res.inserted} · Sin cambio: ${res.unchanged}` });
      void load();
    } catch (err) {
      setCsvMsg({ ok: false, text: describeError(err) });
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="fixings" data-testid="fixings-panel">
      <div className="fixings__filters" role="group" aria-label="Filtro de fijaciones">
        <label className="fixings__field">
          Índice
          <select
            className="fixings__input"
            value={filter.index}
            onChange={(e) => setFilter({ ...filter, index: e.target.value as '' | FixingIndex })}
          >
            <option value="">Todos</option>
            {INDICES.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </label>
        <label className="fixings__field">
          Desde
          <input
            type="date"
            className="fixings__input"
            value={filter.from}
            onChange={(e) => setFilter({ ...filter, from: e.target.value })}
          />
        </label>
        <label className="fixings__field">
          Hasta
          <input
            type="date"
            className="fixings__input"
            value={filter.to}
            onChange={(e) => setFilter({ ...filter, to: e.target.value })}
          />
        </label>
      </div>

      {listError && (
        <p role="alert" className="fixings__error">
          {listError}
        </p>
      )}

      <div className="fixings__scroll">
        <table className="fixings__table" aria-label="Fijaciones">
          <thead>
            <tr>
              <th scope="col">Índice</th>
              <th scope="col" className="num">
                Fecha
              </th>
              <th scope="col" className="num">
                Valor
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={`${f.index}|${f.date}`}>
                <td>{f.index}</td>
                <td className="num">{fmtDate(f.date)}</td>
                <td className="num">{fmtValue(f)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && !listError && rows.length === 0 && <p className="fixings__meta">Sin fijaciones</p>}
        {loading && <p className="fixings__meta">Cargando fijaciones…</p>}
      </div>

      <div className="fixings__forms">
        <form className="fixings__form" onSubmit={(e) => void submitAdd(e)} aria-label="Alta de fijación">
          <h3>Alta de fijación</h3>
          <label className="fixings__field">
            Índice
            <select
              className="fixings__input"
              value={form.index}
              onChange={(e) => setForm({ ...form, index: e.target.value as FixingIndex })}
            >
              {INDICES.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
          </label>
          <label className="fixings__field">
            Fecha
            <input
              type="date"
              className="fixings__input"
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
            />
          </label>
          <label className="fixings__field">
            {isRate(form.index) ? 'Valor (%)' : 'Valor (MXN)'}
            <input
              type="number"
              step="any"
              className="fixings__input num"
              value={form.value}
              onChange={(e) => setForm({ ...form, value: e.target.value })}
            />
          </label>
          <button type="submit" className="fixings__btn" disabled={adding}>
            Guardar
          </button>
          {addMsg && (
            <p role={addMsg.ok ? 'status' : 'alert'} className={addMsg.ok ? 'fixings__ok' : 'fixings__error'}>
              {addMsg.text}
            </p>
          )}
        </form>

        <form className="fixings__form" onSubmit={(e) => void submitCsv(e)} aria-label="Importar CSV">
          <h3>Importar CSV</h3>
          <label className="fixings__field">
            Archivo
            <input type="file" accept=".csv" onChange={(e) => void onFile(e)} />
          </label>
          <label className="fixings__field fixings__field--col">
            CSV
            <textarea
              className="fixings__input fixings__csv"
              rows={6}
              spellCheck={false}
              placeholder={'index,date,value\nTIIE-F,2026-11-10,0.0701'}
              value={csv}
              onChange={(e) => setCsv(e.target.value)}
            />
          </label>
          <button type="submit" className="fixings__btn" disabled={importing || csv.trim() === ''}>
            Importar
          </button>
          {csvMsg && (
            <p role={csvMsg.ok ? 'status' : 'alert'} className={csvMsg.ok ? 'fixings__ok' : 'fixings__error'}>
              {csvMsg.text}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
