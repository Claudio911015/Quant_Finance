# Auditoría independiente — QF Desk corte 4 (coberturas IFRS 9)

Rama `feat/qf-desk`, commits `c2c3529..a64d761` (14 commits). Contrastado contra `design.md` (D1–D10, R1–R12, P1–P15). No se leyó `plan.md` ni los reportes de los implementadores. No se modificó el repo ni se hicieron commits (los `graphify-out/*` que aparecen modificados en `git status` ya lo estaban antes de esta auditoría: mtime 07:22).

## Suites (corridas por el auditor)

| Suite | Resultado |
|---|---|
| C++ `ctest --test-dir build` | 402/402 pasan |
| `pytests` (bindings qfpy) | 56 pasan (OK) |
| `pytest desk/api/tests -q` | 2292 pasan |
| UI `npm test` | 229 pasan (18 archivos) |
| UI `npm run build` | compila (solo aviso de tamaño de chunk) |

## Método

Backend real en `127.0.0.1:5073` con base temporal nueva (`scratchpad/audit.db`), sembrada con MX-DEMO (as_of 2026-11-10). Snapshots propios rodados y movidos con `PUT /api/market/snapshots`: A1 (+20 d, TIIE-F +50 pb, spot 19.10), A2 (+45 d, +20 pb, 18.90), A3 (+75 d, −30 pb, 19.40), A4 (+90 d). Fijaciones TIIE-F 7.05 % diarias. Siete relaciones por HTTP: swap idéntico 100 M, sobrecubierto 120 M, subcubierto 80 M, de signo opuesto (receiver), fracción 0.5, forward USD 1 M a 60 d al forward de mercado, y valor razonable de deuda fija (receiver). Tres cierres cada una; para cada cierre se recalculó por fuera ORI (regla del menor), inefectividad, cuadratura de asientos en `Decimal`, identidad y P&L contra `GET /api/pnl?from&to` × F. Interfaz: Chrome headless propio (puerto 9334, perfil en scratchpad) a 1280 px sobre la UI servida por el backend 5073, más las capturas de `shots/`. Todo se apagó al final (5073 y 9334 libres).

## Veredictos

| R | Veredicto | Evidencia |
|---|---|---|
| R1 | CUMPLE | Alta 201 con evento `designation`. 400: `fair_value`+`floating_loan`, `cash_flow`+`fixed_loan` (campo `hedge_type`), fracción 0 y 1.5, `hedge_ratio` 0, fecha `2026-13-01`, falta de un texto de documentación, `fx_forward` para crédito (`item_kind`). 404 operación inexistente. 409 suma de fracciones >100 %, 409 operación `vencida` a la fecha de designación. UPDATE/DELETE sobre `hedge_events`, `hedge_periods` y `hedge_relationships` abortan por disparador (probado con sqlite3 sobre copia). Ver defecto D-1 sobre designación retroactiva. |
| R2 | CUMPLE | Swap idéntico: inefectividad 0.0000 y `Δoci = Δinst_cum` exactos en A1/A2/A3 (487 199.89; −281 252.84; −393 497.98). Forward al forward de mercado: inefectividad 0 en los tres cierres, incluido el final. |
| R3 | CUMPLE | Sobrecubierto 120 %: `oci = hypo_cum` (487 199.89 / 205 947.05 / −187 550.93) y el exceso a inefectividad (97 439.98; −56 250.57; −78 699.60). Subcubierto 80 %: `oci = inst_cum` e inefectividad 0. Signos opuestos: `oci = 0` en todos los cierres, todo a inefectividad. Recalculado por fuera: coincide al 1e-6. |
| R4 | CUMPLE | Cargos = abonos al centavo en los 21 cierres y en el acumulado de cada relación; CSV: Dr = Cr en las cuatro relaciones exportadas. `identity_residual` = 0. `Δinst_cum + settled_period − F × pnl(/api/pnl)` ≤ 3e-11 MXN en todos los cierres (incluida F = 0.5). |
| R5 | CUMPLE | Cierres A2/A3 del swap: `Efectivo` cargo 24 739.20 contra `Resultados — partida cubierta (reciclaje)` abono 24 739.20. Forward: cierre final `vencida`, PV 0, `oci = 0`, Σ(inefectividad + reciclaje) = 703 229.45 = liquidación total. (Nota: la liquidación usó el spot del snapshot por `fx_fallback`, porque el vencimiento cayó en sábado; el aviso viaja en `warnings`.) |
| R6 | CUMPLE | Deuda fija con swap idéntico: `Δinst_cum + item_adjustment = 0` en cada cierre (−487 199.89 + 487 199.89, etc.); la cuenta `Resultados — cobertura de valor razonable` neta 0 sin la línea de liquidación; registra cambio del derivado y ajuste de la partida. |
| R7 | CUMPLE | Idéntico: razones 1.0 en los escenarios que mueven el hipotético, `null` en los que no (P6), relación económica sí. Vencimiento distinto (+56 d): `maturity_date` `mismatch` con ambos valores, resto `match`; razones 0.86/0.86/1.26. Sobrecubierto: `notional` `mismatch`, razones 1.2. Signo opuesto: razones −1, relación económica `false`. Forward: nocional, moneda, vencimiento y sentido (P11). |
| R8 | CUMPLE | Desdesignar → 201, evento `dedesignation` con `frozen_oci` = saldo; cierre posterior 409; segunda desdesignación 409; fecha anterior al último cierre 409. Cierre con snapshot anterior o igual al último cierre 409. Operación terminada → 409 «desdesigna la relación». Cierre tras el final del forward → 409 `snapshot` (P12). |
| R9 | CUMPLE | `GET /report` trae documentación (objetivo, riesgo, partida, instrumento, razón, método, fuentes), prueba prospectiva (snapshot de designación), periodos, asientos por periodo y totales, reserva (con nota de congelada), jerarquía `level: 2` con `data_quality` por snapshot y el aviso. CSV `period_id,as_of,snapshot,account,debit,credit,memo` cuadra. |
| R10 | CUMPLE | Headless 1280 px: `/coberturas`, `/coberturas/1`, `/5`, `/7`, `/1/reporte`, `/metodologia` sin desborde horizontal (scrollWidth = clientWidth; ningún contenedor interno con scroll horizontal). Banda D10 presente en todas las pantallas de coberturas. Detalle con «Cerrar periodo», «Desdesignar», «Exportar asientos (CSV)», «Vista imprimible»; reporte con «Imprimir» y «Nivel 2». Ficha de operación: «Designada como cobertura #1 · Flujo de efectivo · 100% · Activa». Alta y errores por campo vistos en capturas 10–14 y respaldados por pruebas de vitest. Sin textos en inglés detectados. |
| R11 | CUMPLE | Metodología: hipotético, regla del menor, reciclaje por liquidaciones, asientos sugeridos, las cuatro simplificaciones y revisión pendiente, más combinaciones, cambios de nocional, desdesignación y fuera de alcance. |
| R12 | CUMPLE | Las cuatro suites verdes (arriba). |

## Lo construido que ningún R pidió

- Filtro `GET /api/hedges?trade_id=` (lo usa la ficha de operación; razonable).
- `DEFAULT_SCENARIOS` en `risk/scenarios.py` y `shock` hecho público (P6 aceptado). Duplica la lista de `RiskScreen.tsx`: dos fuentes de verdad.
- Disparadores en `hedge_relationships` (P15 aceptado).
- `docs/superpowers/qf-desk/corte4/plan.md` y `design.md` en el repo.
- Ruta propia `/coberturas/:id/reporte` para la vista imprimible (D8 la pide; la forma es una elección).

## Defectos fuera de los R

| # | Severidad | Defecto |
|---|---|---|
| D-1 | media | **Designación retroactiva y solapada.** La fecha de designación es el `as_of` de cualquier snapshot, incluidos los pasados, y el control de fracción solo suma relaciones *activas hoy*. Probado: se desdesigna la relación 5 (50 % de la operación 12) con fecha 2027-01-29 y se designa otra vez el 100 % de la misma operación con MX-DEMO (2026-11-10). Entre el 2026-11-10 y el 2027-01-29 la operación queda designada al 150 %. IFRS 9 6.4.1(b) exige documentar al inicio y no admite designación retroactiva. |
| D-2 | media | **La desdesignación no mide hasta su fecha.** `frozen_oci` es el saldo del último cierre aunque la fecha de desdesignación sea posterior (probado: cierre al 2027-01-24, desdesignación al 2027-01-29). El cambio del derivado y de la reserva entre esas fechas no se asienta, y ninguna pantalla lo advierte. |
| D-3 | baja | Deriva por redondeo en cuentas de balance: tras el cierre final del forward la reserva vale 0 en cifras, pero el acumulado de asientos deja `ORI` +0.01 y `Derivado` −0.01. Cada cierre redondea su delta por separado; el residuo solo se absorbe en resultados *dentro* del periodo. |
| D-4 | baja | Términos críticos de crédito sin sentido (paga o recibe fija): un swap del lado equivocado sale «coincide» en los cuatro términos (lo delata solo la razón −1) y la designación se acepta. |
| D-5 | baja | Se admite una fecha de flujo pronosticado en fin de semana; la liquidación del forward cae a `fx_fallback` (spot del snapshot) sin advertencia al designar. |
| D-6 | baja | El campo fecha de «Desdesignar» se muestra con el formato del navegador (`12/15/2026` en locale en-US). |

## Observaciones contables (IFRS 9)

1. **Regla del menor sobre PV «limpio» (6.5.11(a)).** La norma compara las ganancias o pérdidas acumuladas *desde el inicio*. Aquí se comparan PV sin lo ya liquidado: equivale a la norma solo si las liquidaciones del instrumento y del hipotético coinciden. En coberturas sobre o subcubiertas, o con diferencias de base, el saldo de ORI difiere del de 6.5.11. Metodología no lo declara.
2. **Reciclaje = liquidación completa del instrumento.** En el caso sobrecubierto (130 % en la captura 05) se lleva a «Resultados — partida cubierta (reciclaje)» todo el cupón del swap, incluida la parte que excede la partida. Ese exceso se compensa con inefectividad negativa: el total cuadra, pero la línea de reciclaje sobrestima el flujo cubierto y la de inefectividad lo encubre. Un contador reclasificaría solo la porción del flujo cubierto.
3. **Momento del reciclaje (6.5.11(d)(ii)).** Se recicla al liquidarse el derivado, no cuando la partida afecta resultados (devengo de intereses o venta del inventario comprado en USD). Para `forecast_fx` sobre partida no financiera aplica además el ajuste de base obligatorio (6.5.11(d)(i)). Este último está declarado («sin ajuste de base»); el momento no.
4. **Reserva congelada sin mecanismo de reciclaje (6.5.12).** Tras desdesignar, la reserva queda congelada para siempre. No hay forma de reciclarla cuando ocurre el flujo ni de llevarla a resultados de inmediato si el flujo ya no se espera (6.5.12(b)). Metodología dice «se recicla cuando ocurra el flujo cubierto», pero el sistema no lo hace ni lo dice.
5. **Desdesignación voluntaria (6.5.6).** IFRS 9 prohíbe discontinuar voluntariamente una relación que sigue cumpliendo el objetivo de gestión de riesgo. El sistema acepta cualquier motivo de texto libre y no lo advierte.
6. **Valor razonable (6.5.8 / 6.5.10).** El ajuste de la partida se mide con un swap hipotético a tasa par de designación, no con el cupón contractual de la deuda (no se captura). Es aceptable como componente de riesgo de referencia, pero Metodología excluye la «designación de componentes de riesgo» y no explica la contradicción. Tampoco se amortiza el ajuste acumulado de la partida (6.5.10), y no se declara.
7. **Presentación de la liquidación en valor razonable.** El cupón neto del swap se lleva a «Resultados — cobertura de valor razonable» en vez de a gasto por intereses. Es una elección de presentación que el contador querría ver declarada.
8. **Componente forward del forward.** El hipotético al forward de mercado designa el forward completo, puntos forward incluidos, sin elección de 6.5.16. Está declarado («sin costo de cobertura»); es correcto como simplificación.
9. **Designación sin relación económica.** Se acepta una relación cuya prueba prospectiva da «relación económica: no» (6.4.1(c)(i)). La prueba es informativa y no bloquea la designación. Debería al menos advertirse en el alta.
