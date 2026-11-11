// Selector de archivo con textos en español: el control nativo ("Choose File / No file chosen") sigue el
// idioma del navegador y no se puede traducir, así que se oculta y se pinta uno propio (corte 5, auditoría).
import { useState } from 'react';
import type { ChangeEvent } from 'react';
import './FilePicker.css';

interface Props {
  label: string; // nombre accesible del input
  accept?: string;
  onFile: (file: File) => void;
}

export function FilePicker({ label, accept, onFile }: Props) {
  const [name, setName] = useState<string | null>(null);

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const input = e.target;
    const file = input.files?.[0];
    if (!file) return;
    setName(file.name);
    onFile(file);
    input.value = ''; // permite elegir el mismo archivo otra vez
  }

  return (
    <label className="ops-file">
      <input type="file" className="ops-file__input" aria-label={label} accept={accept} onChange={onChange} />
      <span className="ops-file__btn">Elegir archivo</span>
      <span className="ops-file__name">{name ?? 'Ningún archivo seleccionado'}</span>
    </label>
  );
}
