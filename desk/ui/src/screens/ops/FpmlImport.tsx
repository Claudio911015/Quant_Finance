// Importación de una operación desde un documento FpML, desde Portafolio.
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { importFpml } from '../../api/opsClient';
import type { FpmlImportResponse } from '../../api/opsTypes';
import { FilePicker } from './FilePicker';
import './TradeOps.css';

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

export function FpmlImport() {
  const [open, setOpen] = useState(false);
  const [xml, setXml] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FpmlImportResponse | null>(null);

  async function onFile(file: File) {
    try {
      setXml(await readFile(file));
      setError(null);
    } catch {
      setError('No se pudo leer el archivo.');
    }
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await importFpml(xml));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'No se pudo importar el FpML.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ops-fpml-host">
      <button
        type="button"
        className="ops-trade__btn"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        Importar FpML
      </button>
      {open && (
        <div className="ops-fpml" data-testid="fpml-import">
          <FilePicker label="Archivo FpML" accept=".xml,.fpml,application/xml" onFile={(f) => void onFile(f)} />
          <textarea
            aria-label="XML FpML"
            value={xml}
            onChange={(e) => setXml(e.target.value)}
            placeholder="Pega aquí el documento FpML"
          />
          <div className="ops-fpml__actions">
            <button type="button" className="ops-trade__btn" onClick={submit} disabled={busy || xml.trim() === ''}>
              Importar
            </button>
            <button type="button" className="ops-trade__btn" onClick={() => setOpen(false)}>
              Cerrar
            </button>
          </div>
          {error && <p role="alert">{error}</p>}
          {result && (
            <div role="status">
              <p>Operación importada</p>
              <Link to={`/portafolio/${result.trade.id}`}>Ver operación</Link>
              {result.warnings.length > 0 && (
                <ul className="ops-fpml__warnings">
                  {result.warnings.map((w, i) => (
                    <li key={`${w.code}-${i}`}>{w.message}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
