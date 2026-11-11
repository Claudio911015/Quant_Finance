# QF Desk — hoja de ruta de punta a punta

Escrita el 2026-11-10 por Fable tras revisar el proyecto contra fuentes públicas (modelo de eventos de FINOS CDM, ORE, Strata, FpML, Eclipse Tradista, notas de Banorte y CME sobre TIIE de Fondeo). Cada **corte** de este documento está pensado para ser una corrida de `/fableorchestrate`: Fable convierte el corte en `design.md`, Opus lo planea, Sonnet/Haiku implementan, Opus audita.

Lo marcado **[verificar]** viene de resúmenes de búsqueda o de mi conocimiento general, no de haber leído la fuente; se confirma en la fase de diseño del corte correspondiente.

## 1. Tesis

Un sistema tipo Murex completo es trabajo de equipos durante años. Lo alcanzable y vendible es **punta a punta para un nicho**: los derivados de cobertura de una tesorería corporativa mexicana (swaps TIIE de Fondeo y SOFR, forwards y opciones USDMXN, caps, cross currency swaps). Son pocos productos, con ciclo de vida sencillo, y el dolor del cliente es concreto: valuar sin depender del banco y sostener la contabilidad de coberturas ante su auditor.

El corte 1 (en curso) deja una calculadora con portafolio y riesgo. Lo que lo separa de un sistema no es más pricing: es que **la operación no tiene vida** (fecha, estados, fijaciones, pagos, asientos). Ese es el eje de la hoja de ruta.

## 2. Principios (valen para todos los cortes)

1. **La matemática vive en C++** y se expone por `qfpy`. Python orquesta, valida y persiste.
2. **Los hechos son eventos inmutables.** Nada de `UPDATE` sobre una operación: se añade un evento. El estado es el resultado de aplicar los eventos en orden.
3. **Toda cifra se puede explicar.** Cada valuación guarda con qué snapshot, qué curvas y qué fijaciones se calculó.
4. **Cada requisito es comprobable por un tercero** con un comando o una identidad numérica (paridades, sumas que cuadran, reprecio a cero).
5. **Lo que no se hace se declara** en la página de Metodología. Un límite declarado es vendible; uno escondido no.
6. **Un corte, una corrida.** Ningún corte depende de trabajo sin auditar del anterior.

## 3. Mapa de cortes

```
Corte 1  Workstation núcleo ........................ hecho y auditado
Corte 2  La operación con vida + mercado con historia ... hecho y auditado 2026-11-11 (docs/superpowers/qf-desk/corte2/)
Corte 3  Curvas MXN multi-curva + cross currency swap
Corte 4  Contabilidad de coberturas IFRS 9 ......... hecho y auditado en 3 rondas 2026-11-11 (corte4/); falta revisión de un contador
Corte 5  Operaciones: flujos, confirmaciones, conciliación (requiere 2)
Corte 6  Riesgo avanzado: P&L explicado, límites, VaR histórico, CVA (requiere 2)
Corte 7  Validación independiente y reporte de credibilidad
Corte 8  Plataforma: usuarios, aprobación, datos reales, despliegue
```

Orden recomendado: 2 → 4 → 3 → 5 → 6 → 7 → 8. El 4 va antes que el 3 porque es por lo que el cliente paga; el 3 mejora la exactitud y puede esperar. El 7 puede adelantarse si un prospecto pide evidencia.

---

## Corte 2 — La operación con vida y el mercado con historia

**Por qué.** Hoy una operación es un JSON de parámetros valuado siempre "como recién pactada". Sin fechas ni historia no hay ciclo de vida, ni P&L, ni contabilidad. Es reestructuración: conviene hacerla antes de que haya datos reales que migrar.

**Fuente.** Modelo de eventos de CDM: un `TradeState` con historia de fijaciones y de transferencias, y eventos compuestos de instrucciones primitivas (ejecución, fijación, transferencia, cambio de cantidad, cambio de términos, ejercicio) que apuntan al estado anterior. Se copia la forma, no el modelo completo.

**Decisiones de arquitectura.**
- Tablas: `counterparties`; `trades` (identidad y términos económicos, fecha de pacto, de inicio y de vencimiento fijas); `trade_events` (solo inserción: tipo, fecha de evento, datos, evento previo, marca de tiempo); `fixings` (índice, fecha, valor); `snapshots` uno por fecha de valuación.
- Tipos de evento: `execution`, `reset`, `transfer`, `quantity_change`, `terms_change`, `exercise`, `termination`. Estado de la operación (`viva`, `vencida`, `terminada`, `ejercida`) derivado de sus eventos.
- La valuación recibe una **fecha de valuación**: descuenta solo flujos futuros y, para el periodo en curso de un OIS, compone las fijaciones ya publicadas y proyecta el resto. Eso se implementa en C++ (extensión de `OisSwap`), no en Python.
- Selector global pasa de "snapshot" a "fecha de valuación".

**Requisitos (borrador).**
- R1 Una operación creada tiene fecha de pacto, inicio y vencimiento, y un evento `execution`. `trade_events` rechaza `UPDATE` y `DELETE` (lo impide un disparador de SQLite, con test).
- R2 Reproducir los eventos de una operación desde cero da el mismo estado que el guardado (test de replay sobre todas las operaciones).
- R3 Envejecimiento: un swap pactado a la par en D0, valuado en D0+28 días con fijaciones iguales a los forwards de D0 y la curva de D0 desplazada en el tiempo, vale lo mismo que su valor proyectado en D0 (tolerancia 1e-6 × nocional).
- R4 Identidad de P&L: para toda operación y todo par de fechas, `PV(D1) − PV(D0) + flujos liquidados entre D0 y D1` es igual al P&L reportado.
- R5 Una terminación anticipada genera un evento, un flujo de liquidación y deja la operación fuera de valuación y riesgo desde esa fecha.
- R6 Fijaciones: carga manual y por CSV; un swap cuyo periodo en curso carece de una fijación ya debida se valúa con aviso, no con error.
- R7 Interfaz: ficha de operación con línea de tiempo de eventos y calendario de flujos (pasados liquidados, futuros proyectados); el blotter filtra por estado.
- R8 Migración: las operaciones del corte 1 se convierten sin perder ninguna y su PV al `as_of` original no cambia (1e-8 relativo).

**Fuera de alcance.** Novaciones, asignaciones, compensación, calendarios de días inhábiles (se declaran; calendario mexicano entra en el corte 3).

**Tamaño estimado.** 18 a 22 tareas. Riesgo principal: la valuación de swaps envejecidos; va primero y sola.

---

## Corte 3 — Curvas MXN como las arma el mercado

**Por qué.** El corte 1 descuenta y proyecta MXN con una sola curva. El mercado construye el descuento MXN con cross currency swaps SOFR contra TIIE de Fondeo, separado de la proyección **[verificar en la nota de Banorte y la metodología MXN de CME]**. Para un cliente con contrato de colateral en USD la diferencia aparece en la valuación, y un auditor la va a preguntar.

**Decisiones de arquitectura.**
- Tarea cero del diseño (Fable): leer las dos fuentes y fijar convenciones exactas (base de días, rezagos, calendario, fórmula de TIIE a plazo). Sin eso no se planea.
- C++: bootstrap conjunto proyección + descuento; instrumento `XccySwap` (nocional constante primero); calendario de días inhábiles de México y de EE. UU.
- El snapshot gana la curva de base y la moneda de colateral por contraparte.

**Requisitos (borrador).**
- R1 Todo instrumento de calibración reprecia a cero (1e-8 × nocional), incluidos los cross currency swaps.
- R2 Los forwards USDMXN implícitos en las curvas coinciden con los puntos forward cotizados (tolerancia a definir en diseño).
- R3 Cambiar la moneda de colateral de una contraparte cambia el PV de sus swaps MXN en el sentido esperado; con base cero el resultado coincide con el corte 1.
- R4 DV01 por plazo incluye la curva de base y la suma por plazo cuadra con el paralelo (2 %).
- R5 `XccySwap` como producto en pricer, portafolio y riesgo.

**Tamaño estimado.** 12 a 16 tareas, casi todas `sonnet` y en serie (C++).

---

## Corte 4 — Contabilidad de coberturas IFRS 9

**Por qué.** Es la función por la que una tesorería paga, y ninguno de los proyectos abiertos revisados la cubre. Requiere el corte 2 (fechas e historia).

**Decisiones de arquitectura.**
- Entidad `hedge_relationships`: instrumento (una operación o una fracción), partida cubierta (crédito a tasa variable, compra o venta pronosticada en USD) con sus términos, tipo (flujo de efectivo o valor razonable), razón de cobertura, fecha de designación, documentación.
- La partida cubierta se representa con un **derivado hipotético** construido con sus términos críticos y valuado con el mismo motor.
- Efectividad prospectiva (coincidencia de términos críticos y análisis de escenarios) y medición retrospectiva de inefectividad por periodo.
- Los asientos son **sugeridos**: el sistema no es el libro mayor.

**Requisitos (borrador).**
- R1 Con un hipotético idéntico al instrumento, la inefectividad es cero y todo el cambio de valor razonable va a otro resultado integral.
- R2 Cobertura de flujo de efectivo: el monto acumulado en otro resultado integral es el menor, en valor absoluto, entre el cambio acumulado del instrumento y el del hipotético; el exceso va a resultados (test con un caso sobrecubierto y uno subcubierto).
- R3 Todo juego de asientos sugeridos cuadra: cargos igual a abonos, por periodo y acumulado.
- R4 Reciclaje: al ocurrir el flujo cubierto, la parte correspondiente sale de otro resultado integral a resultados.
- R5 Desdesignar una relación genera un evento y congela su saldo acumulado.
- R6 Reporte por relación: documentación de designación, prueba de efectividad, asientos del periodo y nivel de jerarquía de valor razonable, exportable.

**Advertencia.** Un contador con experiencia en IFRS 9 debe revisar el diseño antes de implementarlo y el resultado antes de venderlo. Esa revisión es un requisito del corte, no un opcional.

**Tamaño estimado.** 16 a 20 tareas.

---

## Corte 5 — Operaciones

**Por qué.** Cierra el "back": lo que se paga, lo que se confirma y lo que se concilia.

**Requisitos (borrador).**
- R1 Calendario de flujos por cobrar y pagar por fecha, contraparte y moneda, con exportación.
- R2 Confirmación por operación en documento imprimible con todos sus términos.
- R3 Exportar e importar FpML para swap OIS, forward y opción FX: exportar e importar de nuevo da la misma operación (ida y vuelta).
- R4 **Conciliación con el banco**: cargar el archivo de valuaciones del banco y obtener, por operación, la diferencia y su descomposición (curva, fecha, términos). Es la función con mejor demostración comercial.
- R5 Marcar un flujo como liquidado genera su evento `transfer`.

**Tamaño estimado.** 12 a 15 tareas; varias `haiku` (plantillas, exportaciones).

---

## Corte 6 — Riesgo avanzado

**Requisitos (borrador).**
- R1 P&L explicado entre dos fechas: paso del tiempo, tasas por curva, tipo de cambio, volatilidad, operaciones nuevas y residuo. La suma de componentes iguala el P&L total; el residuo es menor al 2 % en el portafolio de ejemplo.
- R2 Límites por contraparte y por factor, con uso, alerta y bitácora de excesos.
- R3 VaR histórico con la historia del corte 2, junto al paramétrico; con rendimientos normales simulados ambos convergen (test estadístico con tolerancia).
- R4 CVA y perfil de exposición en la interfaz, usando el módulo `qf::xva` que ya existe.
- R5 Biblioteca de escenarios guardados (por ejemplo, depreciaciones históricas del peso).

**Tamaño estimado.** 14 a 18 tareas.

---

## Corte 7 — Validación independiente

**Por qué.** "Mi número contra el de una referencia conocida" es lo que convierte una demo en algo creíble.

**Decisión.** Referencia principal: QuantLib en Python (misma decisión que en QuantSuite). ORE como segunda referencia solo si un prospecto la pide: su valor está en XVA y exposición.

**Requisitos (borrador).**
- R1 Arnés que valúa el portafolio de ejemplo en QF Desk y en la referencia, con las mismas curvas y convenciones, y reporta diferencia por operación.
- R2 Tolerancias declaradas por producto; toda diferencia mayor queda explicada o es un defecto abierto.
- R3 Página de Validación en la interfaz, generada del último reporte, con fecha y versión.

**Tamaño estimado.** 8 a 10 tareas.

---

## Corte 8 — Plataforma y datos reales

- Usuarios, roles y aprobación de dos personas para altas y terminaciones (el modelo de eventos ya guarda quién y cuándo).
- Empresas separadas (un cliente no ve datos de otro).
- Datos reales: fijaciones de TIIE de Fondeo y tipo de cambio FIX desde la API de Banxico, SOFR desde la Fed de Nueva York **[verificar acceso y condiciones de uso]**; cotizaciones de curva importadas del archivo del proveedor de precios del cliente (en México, PiP o Valmer **[verificar formatos]**) o pegadas desde Bloomberg.
- Despliegue con contenedores, respaldos, licencia y términos de uso.

No se dimensiona hasta tener un primer cliente piloto: sus requisitos mandan.

---

## 4. Deuda del corte 1 a saldar al inicio del corte 2

- En valuación, el `pv` de las filas FX va en USD mientras `/api/price` lo da en MXN; unificar.
- El paquete de la interfaz supera 500 kB (tablas y gráficas completas); cargar por pantalla.
- Textos de las tablas en español definidos por pantalla; compartir uno.
- Los desplazamientos de riesgo son sobre tasa cero, no sobre cotización; documentarlo o cambiarlo.
- Lo que señale la auditoría del corte 1.

## 5. Cómo repartir cada corte con `/fableorchestrate`

Lecciones de la corrida del corte 1, para aplicarlas desde el diseño:

1. **Contratos primero.** La primera tarea fija rutas, formas de datos e interfaces internas; así backend y frontend avanzan en paralelo sin leerse.
2. **C++ en serie, lo demás en paralelo.** Las tareas que comparten `build/` van una tras otra; las pantallas van juntas.
3. **Anotar en el Contexto lo que cada tarea decide.** Tras cada tarea, Fable añade al plan las firmas y nombres reales; ahorra redescubrimiento a las siguientes.
4. **Una tarea de integración al final** que pruebe la interfaz contra el backend real: las pantallas se construyen contra simulados.
5. **Los implementadores encuentran huecos del diseño** (pasó con el swap sin tasa fija). Fable responde en el diseño, no en el código.
6. **Costo.** Cada agente gasta entre 70 y 160 mil tokens; un corte de 20 tareas ronda 2 a 3 millones más las auditorías.

Para lanzar un corte: `/fableorchestrate corte N de docs/superpowers/qf-desk/roadmap.md`.

## 6. Carril comercial (no es código, pero decide el orden)

- Tres conversaciones con tesoreros o contralores antes del corte 4: confirmar que la contabilidad de coberturas es el dolor y cómo lo resuelven hoy.
- Un contador revisor para el corte 4.
- Aviso legal de valuación (la herramienta apoya, no sustituye, la valuación oficial) antes de cualquier piloto.

## 7. Fuentes

- FINOS Common Domain Model: https://github.com/finos/common-domain-model · modelo de eventos: https://cdm.finos.org/docs/event-model
- Open Source Risk Engine: https://www.lseg.com/en/post-trade/solutions/advise/open-source-risk-engine
- OpenGamma Strata: https://strata.opengamma.io/introduction/
- FpML: https://www.fpml.org/spec/fpml-5-6-5-rec-1/html/confirmation/fpml-5-6-intro-6.html
- Eclipse Tradista: https://github.com/eclipse-tradista/tradista
- Banorte, valuación de swaps de TIIE: https://www.banorte.com/dam/jcr:46935817-9fa9-46ff-bdb4-5514b03f396a/03.%20Valuaci%C3%B3n%20de%20Swaps%20de%20TIIE%20Legacy.pdf
- CME, metodología MXN: https://www.cmegroup.com/articles/files/2024/mxn-methodology-and-examples.pdf
- Contabilidad de coberturas (fichas de proveedores): https://iongroup.com/blog/treasury/ifrs-9-hedge-accounting-from-policy-to-execution/
