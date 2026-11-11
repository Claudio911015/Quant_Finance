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

## Segunda ronda

Re-auditoría independiente de `bf8f948` (backend) y `09f8a6b` (interfaz) contra C1–C8 y R1–R12. No se leyeron reportes de implementadores; no se tocó el repo ni se hicieron commits. Escenarios propios con el cliente de pruebas de Flask sobre bases temporales (scratchpad `reaudit.py`, `edge.py`, `term.py`, `seedui.py`) y, para la interfaz, backend en 127.0.0.1:5073 + Chrome headless propio (puerto 9335, perfil en scratchpad) a 1280 px. Todo apagado al final (5073 y 9335 libres; 5070, 9222 y Brave sin tocar).

### Suites

| Suite | Resultado |
|---|---|
| C++ `ctest --test-dir build` | 402/402 |
| `pytests` (qfpy) | 56 OK |
| `pytest desk/api/tests -q` | 2335 pasan |
| UI `npm test` | 266 pasan (18 archivos) |
| UI `npm run build` | compila (solo aviso de tamaño de chunk) |

### Escenarios propios (números)

Snapshots rodados desde MX-DEMO (2026-11-10) y movidos con `PUT`: S1 +35 d, TIIE-F +40 pb, spot 19.10; S2 +70 d, −10 pb; S3 +105 d, −60 pb; S4 +400 d (después del vencimiento). Fijaciones TIIE-F 7.05 %. Crédito variable 100 M a 364 d. El hipotético se verificó **por fuera**: el instrumento de la relación idéntica es exactamente el hipotético, así que su `inst_total`/`settled_period` sirve de referencia independiente para `hypo_total`/`hypo_settled_period` de las demás. 255 comprobaciones; solo 3 «fallos» esperados (la relación de signo opuesto no tiene línea de reciclaje porque `recycled = 0` por definición).

- **Idéntico (R2):** inefectividad 0.00000000 en S1–S4; `oci = inst_cum` (374 636.23; −365 102.62; −38 730.40; 0.00); `Δoci + reciclaje = Δinst_total`. Cierre final S4 `vencida`, Σ reciclaje 321 609.64 = `inst_total`.
- **Sobrecubierto 120 % (R3/C3):** `hypo_total` = total del idéntico en cada cierre; `effective_cum` = menor sobre totales; reciclaje = cupón del hipotético (no el del swap); Σ inefectividad 64 321.93 = 20 % del total; Σ reciclaje 321 609.64 (= lo del hipotético).
- **Subcubierto 80 %:** `|oci| = |inst_cum|`, inefectividad 0 en todos los cierres; reciclaje = cupón del instrumento; Σ 257 287.71.
- **Signo opuesto:** `oci = 0` en todos los cierres, Σ inefectividad −321 609.64, aviso `no_economic_relationship` al designar.
- **Fracción 0.5 sobre 200 M:** idéntico al de 100 M, cuadra.
- **R4:** cargos = abonos al centavo por periodo y acumulados; `identity_residual` ≤ 1e-6; `Δinst_cum + settled_period = F × pnl(/api/pnl?from&to)` ≤ 1e-6 en los 20 cierres (incluida F = 0.5).
- **Forward 1 M USD a 50 d (miércoles), F = 0.7 (R5):** S1 reserva 312 147.17; cierre final `vencida`: reserva 0, reciclaje 301 000.00 = 0.7 × 1 M × 0.43; `ORI` y `Derivado` acumulados netos **0.00** exactos; `Efectivo` = liquidación; cierre posterior 409 (P12).
- **Valor razonable (R6):** deuda fija 300 M con swap receptor idéntico: `Δinst_cum + item_adjustment = 0` en S1/S2/S3 (−2 199 427.27 / +2 199 427.27, etc.); la cuenta de cobertura neta 0 sin la línea de liquidación; acumulado de `Derivado` y `Partida cubierta` = saldo redondeado (C4).

### Veredictos C1–C8

| C | Veredicto | Evidencia |
|---|---|---|
| C1 | CORREGIDO | Reproducción de D-1: relación 50 % designada en MX-DEMO, cierre S1, desdesignada en S2; designar 100 % con MX-DEMO → **409 `snapshot`**; con S1 → 409; con S2 (= fecha de desdesignación) → 201; 10 % más en S3 → 409 (fracción). Otra operación: 60 % en MX-DEMO, luego 60 % en S1 → 409 y 40 % en S1 → 201. Ver observación sobre retroactividad absoluta. |
| C2 | CORREGIDO (con hueco) | Reproducción de D-2: cierre S1 (oci 374 636.23), desdesignar con S2 → cierre implícito al 2027-01-19 y `frozen_oci` = −38 730.40 (el de S2, no el de S1). Cuerpo antiguo `{date}` → 400; sin `cause` → 400 `cause`; `cause` desconocida → 400; con el snapshot de la designación → 201 sin cierre. **Hueco:** si la operación se terminó, no se puede medir hasta la terminación (defecto N-2). |
| C3 | CORREGIDO (según su texto) | Fórmulas verificadas por fuera en 20 cierres (arriba). Identidad `F×ΔPV + liquidado = Δoci + reciclaje + inefectividad` se cumple. Pero la propia regla de reciclaje de C3 produce una reserva sin respaldo cuando `effective_cum = 0` (defecto N-1). |
| C4 | CORREGIDO | Forward con F = 0.7: acumulados `ORI` y `Derivado` 0.00 exactos tras el cierre final (D-3 ya no se reproduce). Swap tres cierres y valor razonable: acumulado de cada cuenta de balance = saldo redondeado al centavo. Tras liberar toda la reserva, `ORI` acumulado 0.00. |
| C5 | CORREGIDO | Desdesignada con −38 730.40: liberar con fecha anterior al último evento 409; signo contrario 409; 101 % 409; en relación activa 409; parcial 40 % (`flow_occurred`) 201 → saldo −23 238.24, asiento `ORI` abono 15 492.16 / reciclaje cargo; liberación anterior a la previa 409; total (`flow_no_longer_expected`) 201 → saldo 0, asiento contra inefectividad; con saldo 0 → 409. Reporte: `reserve_releases`, `reserve.released`, `entries_total`; CSV cuadra e incluye filas con `period_id` vacío. Detalle y reporte en la interfaz lo muestran. |
| C6 | CORREGIDO | Avisos devueltos y guardados (aparecen en `GET /api/hedges/<id>`): `no_economic_relationship` (swap receptor), `instrument_off_market` (swap a 9 % fija), `forecast_date_weekend` (2027-01-16, sábado). Término `side` «Sentido» en créditos: receptor vs `pays_floating` → `mismatch` (D-4 resuelto). |
| C7 | CORREGIDO | `hedgeDeclarations.ts` es fuente única usada por Metodología y por el reporte: reciclaje con el hipotético como proxy, componente de tasa de referencia (6.3.7) sin amortizar, presentación del cupón en la cuenta de cobertura, causa obligatoria (6.5.6), derivado fuera de mercado. Se quitó «designación de componentes de riesgo» de fuera de alcance. |
| C8 | CORREGIDO | Headless 1280 px sin desborde en `/coberturas`, `/1`, `/2`, `/3`, `/4`, `/3/reporte`, `/metodologia`; banda D10 en todas. Desdesignar con snapshot + causa + motivo (sin `<input type="date">`, D-6 resuelto); «Liberar reserva» solo en desdesignadas con saldo (monto tecleado en magnitud y firmado con el saldo); avisos en el alta y en el detalle; «Sentido» en términos críticos; fechas ISO (ninguna `dd/mm/aaaa` en pantalla); «Generado: 2026-11-11 16:35 UTC»; `break-inside: avoid` en el resumen de efectividad; errores de formulario se limpian al activar otro (`if (!p.active) setErrors({})`). Menor: el selector de snapshot de «Liberar reserva» arranca en el snapshot global (MX-DEMO), que el backend rechaza por anterior al último evento. |

### R1–R12 con la nueva medición

R1–R12 siguen cumpliéndose (R2–R6 con los números de arriba; R7 términos críticos ahora con `side`; R8 con desdesignación por snapshot; R9 con liberaciones; R10/R11 vistos en headless y en Metodología; R12 suites verdes). Sin regresiones en las suites.

### Defectos nuevos

| # | Severidad | Defecto |
|---|---|---|
| N-1 | media | **Reciclaje sin reserva que lo respalde (regla de C3).** El reciclaje del periodo es el menor de lo liquidado por instrumento e hipotético aunque `effective_cum = 0`. Probado (`edge.py`): swap pagador de 728 d cubriendo crédito de 364 d, S1 con curva corta +50 pb y larga −150 pb: `inst_total` −2 315 375.77, `hypo_total` +487 353.49 → `effective_cum` 0, pero `recycled` 24 739.20 y **`oci` −24 739.20**: se crea una pérdida diferida en ORI que nunca fue porción efectiva, y el reciclaje lleva a «partida cubierta» una ganancia que no salió de la reserva. Bajo 6.5.11(a) la reserva debería ser 0 y todo el resultado del instrumento ir a inefectividad. Corrección natural: limitar el reciclaje a lo que la reserva tiene (mismo signo y no más que `effective_cum − Σ reciclaje previo`). Con hipotético idéntico, sobre o subcubierto sobre los mismos términos no se manifiesta. |
| N-2 | media | **Terminación del instrumento no medible (hueco de C2).** Con la operación terminada (evento `termination` 2027-01-19, monto 250 000), desdesignar con el snapshot de esa fecha → 409 «ya no está viva» y cerrar periodo → 409. Solo se puede desdesignar con el snapshot del último cierre: el cambio del derivado desde ese cierre, el último cupón y el pago de terminación (que `/api/pnl` sí reconoce: `settled` 274 739.20) nunca entran a los asientos de la cobertura, y la reserva se congela al último cierre. Es exactamente D-2 para la causa más común, `instrument_ended`. El docstring lo declara como «hueco resuelto de forma conservadora», pero no Metodología ni la pantalla. |
| N-3 | baja | Periodos guardados antes de `bf8f948` carecen de `inst_total`, `effective_cum`, `hypo_settled_period`…: cerrar un periodo nuevo sobre ellos da **500** (probado sobre copia de `it.db`, relación 5 con D2). No hay base real con coberturas (`desk/data/desk.db` no existe), así que solo afecta bases de prueba; no hay migración ni 409 legible. |
| N-4 | baja | El selector de snapshot de «Liberar reserva» (y de desdesignar) arranca en el snapshot global de la barra, normalmente anterior al último evento → 409 al primer intento. |

### Observaciones contables que siguen abiertas (no declaradas en Metodología ni en el reporte)

1. **Cierre final con partida que sobrevive al instrumento (6.5.12(a), 6.5.6).** Cuando el instrumento vence antes que el flujo cubierto, el cierre final recicla toda la reserva a «Resultados — partida cubierta (reciclaje)» (lo fija la prueba `test_the_final_close_zeroes_the_reserve_even_when_the_hypothetical_outlives_the_instrument`). La norma deja la reserva en ORI hasta que el flujo cubierto afecte resultados; ya existe el mecanismo (desdesignar `instrument_ended` + liberar con `flow_occurred`). Metodología dice «en el cierre final la reserva queda en 0», pero no lo presenta como desviación.
2. **Reserva sin respaldo (N-1)**: el contador objetaría un saldo de ORI distinto del menor de los acumulados.
3. **Terminación anticipada (N-2)**: el pago de terminación y la porción efectiva hasta la terminación no se asientan.
4. **Retroactividad absoluta (6.4.1(b)).** C1 solo ordena eventos de la misma operación: una relación nueva se puede designar hoy con cualquier snapshot pasado (no se compara contra `created_at`). Metodología afirma «La designación no es retroactiva», lo que sobreestima el control.
5. **Ajuste de la partida en valor razonable incluye devengo (6.5.8(b)).** El ajuste es `−Δ` del PV del swap hipotético (flujos futuros, no precio limpio): entre fechas de cupón incorpora el devengo del diferencial fija-variable y lo revierte al pagarse. Un contador mediría el componente de tasa con valor limpio. Con hipotético idéntico el neto es 0, por eso no lo detectan las pruebas.
6. **Causas sin verificar.** `cause = instrument_ended` se acepta con la operación viva y `flow_occurred` se acepta antes de la fecha del flujo cubierto; son elecciones del usuario sin contraste con los datos que el sistema sí tiene.
7. Siguen declaradas y aceptables: sin ajuste de base para partidas no financieras, sin costo de cobertura (puntos forward), reciclaje en la fecha del hipotético, cupón de valor razonable en la cuenta de cobertura, ajuste sin amortizar.
