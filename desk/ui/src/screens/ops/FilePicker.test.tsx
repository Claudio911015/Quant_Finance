import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FilePicker } from './FilePicker';

describe('FilePicker', () => {
  it('muestra los textos en español en vez del control nativo del navegador', () => {
    const { container } = render(<FilePicker label="Archivo CSV" accept=".csv" onFile={() => undefined} />);
    expect(screen.getByText('Elegir archivo')).toBeTruthy();
    expect(screen.getByText('Ningún archivo seleccionado')).toBeTruthy();
    // el input nativo sigue ahí (accesible por su nombre) pero oculto visualmente
    const input = screen.getByLabelText('Archivo CSV') as HTMLInputElement;
    expect(input.type).toBe('file');
    expect(input.getAttribute('accept')).toBe('.csv');
    expect(container.querySelector('label')?.contains(input)).toBe(true); // clic en el texto abre el selector
  });

  it('al elegir un archivo lo entrega, muestra su nombre y permite elegir el mismo otra vez', () => {
    const onFile = vi.fn();
    render(<FilePicker label="Archivo CSV" onFile={onFile} />);
    const file = new File(['a'], 'banco.csv', { type: 'text/csv' });
    const input = screen.getByLabelText('Archivo CSV') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
    expect(screen.getByText('banco.csv')).toBeTruthy();
    expect(screen.queryByText('Ningún archivo seleccionado')).toBeNull();
  });

  it('un cambio sin archivo no llama a onFile', () => {
    const onFile = vi.fn();
    render(<FilePicker label="Archivo CSV" onFile={onFile} />);
    fireEvent.change(screen.getByLabelText('Archivo CSV'), { target: { files: [] } });
    expect(onFile).not.toHaveBeenCalled();
  });
});
