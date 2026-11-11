import { Command } from 'cmdk';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { PRODUCT_SPECS } from '../screens/pricers/registry';
import './CommandPalette.css';

interface Props {
  open: boolean;
  onOpenChange(open: boolean): void;
  screens: { to: string; label: string }[];
}

export function CommandPalette({ open, onOpenChange, screens }: Props) {
  const navigate = useNavigate();

  // Ctrl+K (o Cmd+K) alterna la paleta desde cualquier pantalla.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onOpenChange]);

  const go = (to: string) => {
    onOpenChange(false);
    navigate(to);
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Paleta de comandos"
      overlayClassName="palette-overlay"
      contentClassName="palette"
    >
      <Command.Input className="palette__input" placeholder="Ir a una pantalla o a un pricer…" />
      <Command.List className="palette__list">
        <Command.Empty className="palette__empty">Sin resultados</Command.Empty>
        <Command.Group heading="Pantallas">
          {screens.map((s) => (
            <Command.Item key={s.to} value={s.label} className="palette__item" onSelect={() => go(s.to)}>
              <span>{s.label}</span>
              <span className="palette__hint">{s.to}</span>
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Pricers">
          {Object.values(PRODUCT_SPECS).map((spec) => (
            <Command.Item
              key={spec.product}
              value={`Pricer ${spec.title}`}
              keywords={[spec.product]}
              className="palette__item"
              onSelect={() => go(`/pricers/${spec.product}`)}
            >
              <span>{spec.title}</span>
              <span className="palette__hint">{spec.product}</span>
            </Command.Item>
          ))}
        </Command.Group>
      </Command.List>
      <div className="palette__footer" aria-hidden="true">
        <span>↑↓ navegar</span>
        <span>Enter abrir</span>
        <span>Esc cerrar</span>
      </div>
    </Command.Dialog>
  );
}
