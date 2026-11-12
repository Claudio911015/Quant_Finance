# Hallazgos de la documentación técnica

Discrepancias entre lo que el código **hace** y lo que declara la Metodología de la aplicación
(`desk/ui/src/screens/MethodologyScreen.tsx`, `desk/ui/src/screens/ops/opsMethodology.ts`) o el diseño del
corte correspondiente, encontradas al escribir los capítulos de `docs/tex/`. Un hallazgo **no se corrige ni
se maquilla**: el capítulo describe lo que el código hace y aquí queda anotado qué difiere, con archivo y
símbolo, para que se decida aparte (corregir el código o corregir la Metodología).

Archivo compartido entre redactores: releer antes de editar, añadir solo **al final**, commit inmediato.

## Formato de entrada

```
## HNN — <título corto>
Archivo: <ruta relativa al repo>
Símbolo: <función, clase o constante>
Qué hace el código: <comportamiento real, con convención de signo/base/unidad si aplica>
Qué declara la Metodología/el diseño: <texto o referencia al documento>
Impacto: <qué cambia para el usuario o el auditor>
Capítulo: <número y título del capítulo que lo describe>
```

`NN` es correlativo (H01, H02, …). Si dos redactores añaden a la vez, el segundo renumera la suya al releer.

## Entradas
