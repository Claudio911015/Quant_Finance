/** Fallback de `Suspense` mientras se descarga el trozo de una pantalla. */
export function ScreenLoading() {
  return (
    <p role="status" aria-live="polite">
      Cargando…
    </p>
  );
}
