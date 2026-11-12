import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  DECL_DEDESIGNATION,
  DECL_DESIGNATION_DATE,
  DECL_FV_ACCRUAL,
  DECL_FV_COMPONENT,
  DECL_FV_PRESENTATION,
  DECL_HEDGE_RATIO,
  DECL_OFF_MARKET,
  DECL_RECYCLING,
} from '../lib/hedgeDeclarations';
import './MethodologyScreen.css';
import { OPS_SECTIONS } from './ops/opsMethodology'; // corte 5

interface Section {
  id: string;
  title: string;
  items: { label: string; text: ReactNode }[];
}

const PRODUCT_SECTIONS: Section[] = [
  {
    id: 'irs-tiie',
    title: 'IRS TIIE-F',
    items: [
      { label: 'Modelo', text: 'OIS para la curva de descuento y de proyección.' },
      { label: 'Convenciones', text: 'Cupones de 28 días, ACT/360; flotante compuesta diaria.' },
      { label: 'Curvas', text: 'Descuento y proyección con la curva TIIE-F.' },
    ],
  },
  {
    id: 'irs-sofr',
    title: 'IRS SOFR',
    items: [
      { label: 'Modelo', text: 'OIS anual.' },
      { label: 'Convenciones', text: 'ACT/360.' },
      { label: 'Curvas', text: 'Curva SOFR para descuento y proyección.' },
    ],
  },
  {
    id: 'fx-forward',
    title: 'Forward FX',
    items: [
      { label: 'Modelo', text: 'Paridad de tasas cubierta.' },
      { label: 'Curvas', text: 'TIIE-F (MXN) y SOFR (USD).' },
    ],
  },
  {
    id: 'fx-option',
    title: 'Opción FX',
    items: [
      { label: 'Modelo', text: 'Garman-Kohlhagen.' },
      { label: 'Volatilidad', text: 'Vol de la superficie por plazo y strike.' },
    ],
  },
  {
    id: 'cap-floor',
    title: 'Cap / Floor',
    items: [
      { label: 'Modelo', text: 'Hull-White de un factor.' },
      { label: 'Parámetros', text: 'a y σ por curva, tomados del snapshot.' },
    ],
  },
  {
    id: 'swaption',
    title: 'Swaption',
    items: [
      { label: 'Modelo', text: 'Hull-White de un factor.' },
      { label: 'Parámetros', text: 'a y σ por curva, tomados del snapshot.' },
    ],
  },
  {
    id: 'bond',
    title: 'Bono',
    items: [
      { label: 'Modelo', text: 'Flujos fijos descontados con la curva elegida.' },
      { label: 'Cupón', text: 'Nominal × tasa / frecuencia por periodo, sin base de días; el cupón corrido corre lineal con el tiempo transcurrido desde el último cupón (t = días/365).' },
    ],
  },
  {
    id: 'equity-option',
    title: 'Opción sobre acción',
    items: [
      { label: 'Modelo', text: 'Black-Scholes con insumos capturados en la operación.' },
    ],
  },
  {
    id: 'fx-exoticos',
    title: 'Exóticos de FX',
    items: [
      {
        label: 'Qué paga',
        text: 'No touch: monto fijo en MXN al vencimiento si el USDMXN nunca toca la barrera. Double no touch: si nunca sale del corredor.',
      },
      {
        label: 'Barrera',
        text: 'Americana, vigilada de forma continua toda la vida: entre nodos de la malla se usa la probabilidad de cruce del puente browniano.',
      },
      {
        label: 'Modelos',
        text: 'Plano = vol de la superficie en spot y vencimiento. Con sonrisa = volatilidad local de Dupire calculada por QuantLib desde la superficie del snapshot (bicúbica, extrapolación constante), tabulada en 161 strikes y la malla del Monte Carlo; donde la varianza local sale negativa se usa la vol plana. Diferencia frente a Dupire al vuelo (mismas normales, medida a 91 días, 1 y 2 años): de a lo más 0.03 % del pago. El efecto de la sonrisa se lee comparando el valor (± error estándar) con la referencia analítica plana.',
      },
      {
        label: 'Cálculo',
        text: 'QuantLib 1.42: trayectorias de GaussianPathGenerator; referencia analítica con AnalyticBinaryBarrierEngine y AnalyticDoubleBarrierBinaryEngine. La fórmula del puente es la única matemática propia.',
      },
      {
        label: 'Error de Monte Carlo',
        text: '20 000 trayectorias, 10 pasos, semilla fija 42: resultados reproducibles. Error estándar en MXN; delta (+1 % de spot, o la mitad de la distancia a la barrera más cercana si esta queda a menos de 2 %, para que el choque nunca cruce una barrera) y vega (+1 punto de vol) por reprecio con la misma semilla.',
      },
      {
        label: 'Límites',
        text: 'Pago solo en MXN; volatilidad local, no estocástica ni vanna-volga; superficie sintética; sin rebate ni one touch; no se registran como operaciones del portafolio. El snapshot siempre trae superficie, no hay caso «sin superficie». Con sonrisa, el Monte Carlo reprecia las vainillas de la superficie con una vol implícita algo menor (Dupire de QuantLib sobre la bicúbica con extrapolación constante, 10 pasos): ATM −0.04 puntos a 91 días, −0.22 a 1 año y −0.50 a 2 años; en las alas (strikes a ±0.5 y ±1 σ√T) hasta −0.13, −0.60 y −0.58. Con 20 o 40 pasos a 1 año baja a −0.18 y −0.15 ATM: no basta para pagar el tiempo de respuesta. Con corredores muy anchos la fórmula cerrada no converge: la referencia sale «—» y el método analítico responde con error. La vigilancia continua del double no touch usa 10 pasos y subvalúa en corredores más estrechos que ~1 desviación (σ√T).',
      },
    ],
  },
];

const GENERAL_SECTIONS: Section[] = [
  {
    id: 'curvas',
    title: 'Curvas',
    items: [
      {
        label: 'Bootstrap',
        text: 'Depósito y OIS par; tasas cero continuas ACT/365; interpolación lineal en tasa cero.',
      },
    ],
  },
  {
    id: 'riesgo',
    title: 'Riesgo',
    items: [
      { label: 'DV01', text: 'PV(base) − PV(+1 pb).' },
      {
        label: 'DV01 por plazo',
        text:
          'El DV01 por plazo se calcula con diferencia central, (PV(−1 pb) − PV(+1 pb)) / 2, sobre un desplazamiento de la tasa cero en cada pilar; el DV01 paralelo es PV(base) − PV(+1 pb). Para productos con convexidad (cap/floor) la suma por plazo difiere del paralelo: la diferencia absoluta es chica (el paralelo es unilateral y los pilares usan diferencia central), pero en un portafolio casi neutro en DV01 puede pasar del 2 % del total.',
      },
      {
        label: 'VaR',
        text:
          'Delta-normal con volatilidades y correlaciones de factores del snapshot. Tres factores: TIIE-F paralelo, SOFR paralelo y USDMXN rendimiento relativo; sin factores por plazo.',
      },
    ],
  },
  // --- corte 3 ---
  {
    id: 'csa',
    title: 'Colateral y curvas MXN',
    items: [
      {
        label: 'Convenciones (supuesto de convención)',
        text: 'TIIE-F compuesta diaria, cupones cada 28 días, ACT/360; SOFR compuesta, ACT/360. Cross currency swap: SOFR plana contra TIIE-F más diferencial, ambas patas cada 28 días, con intercambio de nocional inicial y final. Forward USDMXN: F = S · DF_USD / DF_MXN^USD. Supuesto de convención: práctica general de mercado, pendiente de confirmar contra la nota de Banorte y la metodología de CME.',
      },
      {
        label: 'Curva MXN-USD',
        text: 'Puntos forward hasta 1 año y base de cross currency swaps después. Sin cotizaciones no existe y todo se descuenta con TIIE-F. En MX-DEMO es sintética; MKT-LIVE no la trae porque no hay fuente libre. Interpola igual que las demás curvas (lineal en la tasa cero), así que con puntos forward en paridad y base cero coincide con TIIE-F solo si los días de cotización coinciden con los pilares de TIIE-F; con otros días el factor de descuento difiere hasta unas millonésimas. No tiene pilar a un día: antes de su primera cotización la tasa cero se extrapola plana.',
      },
      {
        label: 'Efecto del colateral',
        text: 'Colateral por contraparte, con historial y fecha efectiva. Con colateral USD, los flujos MXN descuentan con MXN-USD y proyectan con TIIE-F; sin curva, aviso y TIIE-F. Con MXN no cambia nada. Cap/floor y swaption con colateral USD usan base determinista: cada flujo × DF_MXN-USD / DF_TIIE-F en el cap/floor, y razón de anualidades en la swaption. Los puntos forward cotizados se mantienen fijos cuando se recalibra la curva, así que un forward FX con colateral USD apenas reacciona a un choque de SOFR.',
      },
      {
        label: 'Cross currency swap',
        text: 'Nocional constante, sin reinicio a mercado. Siempre se descuenta bajo colateral USD. El intercambio inicial de nocional sigue en el PV hasta el día de inicio incluido y, al salir de él, se liquida en el P&L (al FIX de ese día), de modo que un tipo de cambio inicial distinto del spot no genera un salto en el P&L.',
      },
      {
        label: 'Calendarios',
        text: 'Inhábiles bancarios de México para TIIE-F y de publicación de SOFR (SIFMA) en EE. UU. para SOFR, por reglas 2020–2040. Un feriado fijo de EE. UU. en domingo pasa al lunes y en sábado al viernes, salvo el 1 de enero y el Día de los Veteranos (SOFR se publicó el viernes 2023-11-10). Una fijación no publicada en día inhábil de su índice no es faltante. Las fechas de pago son las pactadas: no se ajustan por inhábil.',
      },
      {
        label: 'Riesgo',
        text: 'MXN-USD entra al DV01 por plazo. En escenarios y VaR es curva dependiente: se recalibra con las cotizaciones fijas cuando se mueven SOFR, TIIE-F o el spot, salvo en su propio desplazamiento.',
      },
    ],
  },
  // --- fin corte 3 ---
  {
    id: 'ciclo-de-vida',
    title: 'Ciclo de vida y valuación a fecha',
    items: [
      {
        label: 'Eventos',
        text: 'Se guardan: execution, quantity_change, terms_change, exercise, termination y transfer de la liquidación. Se derivan: cupones pagados de swaps y liquidación al vencimiento de forwards FX, de términos más fijaciones. El reset no se usa; las fijaciones viven en su tabla.',
      },
      {
        label: 'Fecha de valuación',
        text: 'Es el as_of del snapshot.',
      },
      {
        label: 'Convención de días',
        text: 'Días naturales, t = días/365. El devengo ACT/360 y las fijaciones diarias capitalizadas rigen para los swaps (también el cross currency swap) y las opciones de tasa; el bono no devenga ACT/360: paga nominal × tasa / frecuencia por periodo y su cupón corrido corre lineal con el tiempo transcurrido desde el último cupón. Los calendarios de inhábiles solo rigen fijaciones y coberturas (ver Calendarios).',
      },
      {
        label: 'Fines de semana',
        text: 'Las tasas a un día solo se publican en días hábiles: la del viernes devenga también sábado y domingo (3 días), así que esos días no son fijaciones faltantes y no avisan. Una fijación cargada en sábado o domingo se usa tal cual.',
      },
      {
        label: 'Fijación faltante',
        text: 'Un día de lunes a viernes sin fijación usa la última publicada anterior o la tasa a un día de la curva, con aviso. Un día inhábil de su índice no es faltante.',
      },
      {
        label: 'Alta a la par',
        text: 'Un swap dado de alta sin tasa fija, o un cross currency swap sin diferencial, nace a la par: se guarda con la tasa o el diferencial par del snapshot de la petición (o MX-DEMO), de modo que su PV en la fecha de pacto es cero. Solo se permite omitirlos si el inicio no es anterior a la fecha de ese snapshot: la par solo se calcula en la fecha de inicio, así que una operación que ya empezó exige capturar la tasa o el diferencial pactados (400 en el campo omitido).',
      },
      {
        label: 'P&L',
        text: 'PV(to) − PV(from) más lo liquidado en (from, to]. En MXN al FIX o al spot de to, con aviso.',
      },
      {
        label: 'Estados',
        text: 'no_pactada, viva, vencida, terminada y ejercida. Solo las vivas entran a riesgo. Una operación pactada dentro de la ventana del P&L entra con pv_from = 0, sin prima ni pago inicial (salvo el intercambio inicial del cross currency swap, que se liquida al salir del PV).',
      },
      {
        label: 'Vencimientos',
        text: 'La swaption vence en su expiración. Las opciones vencidas sin ejercicio registrado valen 0, con aviso.',
      },
      {
        label: 'Bono y cap/floor envejecidos',
        text: 'Bono: precio sucio con cupón corrido, envejecido día a día; sus cupones y su amortización se liquidan. Cap/floor: el caplet ya fijado no entra en el valor y no tiene liquidación derivada, como las swaptions (su pago conocido deja de contar en el PV y no entra al P&L). El cupón corrido se mide con el calendario exacto de i/frecuencia años, pero el cupón se liquida en el día entero más cercano: el día siguiente a un cupón semestral el corrido es medio día, no un día.',
      },
      {
        label: 'Cambios de nocional',
        text: 'Tras un cambio a mitad de periodo, el cupón usa el nocional vigente al pago.',
      },
      {
        label: 'Terminación y ejercicio',
        text: 'Importes en MXN, positivos si cobra el tenedor. Las operaciones no se borran: se terminan.',
      },
      {
        label: 'Fuera de alcance',
        text: 'Novaciones, asignaciones, compensación, ajuste de fechas de pago por inhábiles, ejercicio automático, liquidación de caps/floors y swaptions, historia automática de snapshots, división del paquete y textos compartidos de tablas, usuarios y aprobación.',
      },
    ],
  },
  {
    id: 'fuentes',
    title: 'Fuentes de datos',
    items: [
      {
        label: 'MKT-LIVE',
        text: 'Construido de MarketDataFeed (SOFR de FRBNY, Treasuries par de Treasury.gov) y FRED. Es de solo lectura; cada Actualizar datos lo reescribe por completo. MX-DEMO no cambia.',
      },
      {
        label: 'Curva SOFR',
        text: (
          <>
            Aproximada con Treasuries, sin el spread entre swaps SOFR y Treasuries. Cifras puntuales
            de 2025, no actuales: swaps SOFR por debajo de los Treasuries −25 pb a 2 años, −56 pb a
            10 años y −87 pb a 30 años (
            <a href="https://www.tradition.com/media/365113/mml4_tradition.pdf" target="_blank" rel="noreferrer">
              Tradition, julio de 2025
            </a>
            ); −26 pb a 10 años (
            <a
              href="https://www.advisorperspectives.com/articles/2025/05/05/interest-rate-swaps-plumbing-financial-system"
              target="_blank"
              rel="noreferrer"
            >
              Advisor Perspectives, mayo de 2025
            </a>
            ). Para el porqué de que sean negativos, véase{' '}
            <a href="https://www.bis.org/publ/qtrpdf/r_qt2412y.htm" target="_blank" rel="noreferrer">
              BIS
            </a>
            . La curva aproximada con Treasuries probablemente sobreestima las tasas de swap en esas
            magnitudes; el efecto no se midió aquí.
          </>
        ),
      },
      {
        label: 'Conversión',
        text: 'Con y decimal: hasta 1 año, y·360/365; a más de 1 año, ((1+y/2)²−1)·360/365; 1D = SOFR overnight tal cual.',
      },
      {
        label: 'Sin datos libres',
        text: 'TIIE-F, superficie de volatilidad, Hull-White, volatilidad diaria de TIIE-F y correlaciones son sintéticas: no hay datos libres (Banxico exige token; los swaps los venden proveedores).',
      },
      {
        label: 'Spot',
        text: 'DEXMXUS de FRED = mediodía de Nueva York, no el FIX de Banxico.',
      },
      {
        label: 'Volatilidades diarias',
        text: 'SOFR = cambio diario del rendimiento par de 5Y en pb; USDMXN = rendimiento logarítmico entre observaciones válidas consecutivas. Hasta 250 cambios diarios, desviación estándar muestral; con menos se usan los disponibles (el rótulo dice cuántos) y con menos de 60 no se construye el snapshot. Por eso la procedencia de Volatilidades de factores sale como Mixta.',
      },
      // corte 8
      {
        label: 'Fijaciones SOFR',
        text: 'Fijaciones diarias de SOFR reales, de la Fed de Nueva York. Se traen con el botón Traer de la fuente de Fijaciones; un valor distinto del guardado se lista como conflicto y no se sobrescribe.',
      },
      {
        label: 'Banxico (TIIE de Fondeo, FIX)',
        text: 'Cliente de la API SIE de Banxico listo, inactivo hasta tener un token en BANXICO_TOKEN; sin probar contra un token real, así que el formato de respuesta de éxito no está verificado. Las curvas de TIIE-F siguen sintéticas.',
      },
      // fin corte 8
    ],
  },
];

const HEDGE_SECTIONS: Section[] = [
  {
    id: 'coberturas',
    title: 'Coberturas',
    items: [
      {
        label: 'Revisión contable',
        text: 'Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9. Nadie la ha hecho aún.',
      },
      {
        label: 'Asientos sugeridos',
        text: 'El sistema no es el libro mayor ni sustituye al contador. Cuentas fijas; redondeo a centavos. Las cuentas de balance se asientan como la diferencia entre saldos acumulados ya redondeados, de modo que el acumulado de asientos coincide al centavo con el saldo; el residuo de redondeo del periodo (a lo más unos centavos) se absorbe en la cuenta principal de resultados del tipo de cobertura (en su última línea o, si no la hay, en una línea de redondeo): Resultados — inefectividad de cobertura en flujo de efectivo y Resultados — cobertura de valor razonable en valor razonable, donde no hay una cuenta de inefectividad separada.',
      },
      {
        label: 'Derivado hipotético',
        text: 'La partida se representa con un swap a la par del crédito o con un forward al forward de mercado del flujo, valuados con el mismo motor y en 0 al designar.',
      },
      {
        label: 'Regla del menor',
        text: 'La parte efectiva acumulada es el menor en valor absoluto entre el cambio acumulado del instrumento (por la fracción) y el del hipotético, ambos desde la designación e incluyendo lo ya liquidado, si tienen el mismo signo; si no, 0. La reserva ORI es esa parte efectiva menos lo ya reciclado, y es 0 mientras no haya parte efectiva: un periodo sin respaldo no deja reserva ni recicla nada (IFRS 9 6.5.11(a)). El resto es inefectividad, también el exceso liquidado de una cobertura sobrecubierta.',
      },
      {
        label: 'Reciclaje',
        text: `Las liquidaciones del derivado en el periodo se reconocen en resultados como el flujo cubierto ocurrido, pero solo la parte efectiva: el menor entre lo liquidado del instrumento y lo liquidado del hipotético; el exceso va a inefectividad. ${DECL_RECYCLING} La relación pasa a Concluida cuando el último cierre fue el final porque el instrumento venció: no admite más cierres, tenga o no reserva. Si el instrumento y la partida vencen juntos, en el cierre final la reserva queda en 0 y no hay nada pendiente de reciclar, pero la relación también queda Concluida. Si el instrumento vence antes que el flujo cubierto, la reserva se conserva en ORI (IFRS 9 6.5.12(a)) y se libera a mano cuando el flujo ocurra; el saldo de la reserva distingue un caso del otro.`,
      },
      {
        label: 'Valor razonable',
        text: `Solo para crédito o deuda a tasa fija cubierto con un swap. El cambio del instrumento, el ajuste de la partida (cambio del hipotético con signo contrario) y lo liquidado van a la cuenta Resultados — cobertura de valor razonable; sin reserva. ${DECL_FV_COMPONENT} ${DECL_FV_ACCRUAL} ${DECL_FV_PRESENTATION}`,
      },
      {
        label: 'Combinaciones admitidas',
        text: 'Flujo de efectivo: crédito a tasa variable con swap del mismo índice, o flujo pronosticado en USD con forward. Valor razonable: crédito a tasa fija con swap del mismo índice.',
      },
      {
        label: 'Fecha de designación',
        text: `La fecha de designación no puede ser anterior al último evento (designación, cierre, desdesignación o liberación) de ninguna relación de la misma operación, y las fracciones vigentes a esa fecha no suman más de 100 %. ${DECL_DESIGNATION_DATE}`,
      },
      {
        label: 'Cambios de nocional',
        text: 'Un cambio de nocional del instrumento después de designar no tiene tratamiento especial: la medición usa el nocional vigente.',
      },
      {
        label: 'Razón de cobertura',
        text: DECL_HEDGE_RATIO,
      },
      {
        label: 'Efectividad prospectiva',
        text: 'Términos críticos (nocional, índice, fechas y sentido: el instrumento debe ser el que compensa la partida; la moneda no se compara porque el único flujo pronosticado admitido es USDMXN) y escenarios del escritorio. Hay relación económica si todas las razones son positivas. El rango 80 %–125 % es solo referencia; IFRS 9 no fija umbral.',
      },
      {
        label: 'Jerarquía de valor razonable',
        text: 'Nivel 2 para todos los instrumentos, con la procedencia del snapshot.',
      },
      {
        label: 'Desdesignación',
        text: `${DECL_DEDESIGNATION} La fecha es la del snapshot elegido: si es posterior al último cierre, se mide primero hasta ella y la reserva congelada es la de ese cierre. La causa se contrasta con el estado de la operación en esa fecha: «el instrumento venció, se vendió o se terminó» exige que ya no esté viva y las otras dos, que lo esté. Si la operación se terminó o se ejerció, la medición final llega hasta esa fecha con el instrumento en 0 y lo liquidado incluye el pago de la terminación, el mismo importe que reconoce el P&L. No admite más cierres.`,
      },
      {
        label: 'Liberación de la reserva',
        text: 'La reserva de una relación desdesignada o concluida se libera a mano, total o parcialmente y sin cambiar el signo del saldo: contra Resultados — partida cubierta (reciclaje) cuando el flujo cubierto ocurrió, o contra Resultados — inefectividad de cobertura cuando ya no se espera (IFRS 9 6.5.12). «Ocurrió» no puede fecharse antes de la primera fecha de flujo de la partida (el inicio del crédito o la fecha del flujo pronosticado). El saldo vigente es lo congelado menos lo liberado.',
      },
      {
        label: 'Derivado fuera de mercado',
        text: `${DECL_OFF_MARKET} Al designar, el alta avisa de esto, de que la prueba prospectiva no muestre relación económica, de una razón de cobertura que difiere de la de los nocionales en más de 1 %, de un flujo pronosticado en fin de semana (se liquidará con el spot del snapshot), de un flujo pronosticado en un día inhábil de México entre semana (se liquidará con el último FIX publicado) y de una cobertura documentada más de un día después de su fecha de designación.`,
      },
      {
        label: 'Simplificaciones',
        text: 'Sin costo de cobertura ni valor temporal de opciones; sin riesgo de crédito en la medición; sin ajuste de base para partidas no financieras; sin reequilibrio de la razón de cobertura.',
      },
      {
        label: 'Fuera de alcance',
        text: 'Opciones como instrumento, coberturas de inversión neta, libro mayor y pólizas reales, y revelaciones de IFRS 7.',
      },
    ],
  },
];

// --- corte 6: metodología de riesgo avanzado ---
const RISK_ADV_SECTIONS: Section[] = [
  {
    id: 'riesgo-avanzado',
    title: 'Riesgo avanzado',
    items: [
      {
        label: 'Orden de la cascada',
        text: 'El paso del tiempo y las liquidaciones con el mercado de origen rodado a la fecha final; luego TIIE-F, SOFR y las demás curvas en orden alfabético, los puntos forward y la base que calibran la curva MXN-USD, tipo de cambio, volatilidad (superficie y parámetros Hull-White), operaciones nuevas y eventos. Cada paso cambia un bloque del mercado de origen por el de destino. Los flujos en dólares liquidados en la ventana se convierten, en el primer paso, al tipo de cambio del snapshot de origen; la diferencia con la conversión que usa la pestaña P&L (el FIX de la fecha del flujo o, a falta de él, el spot final) va al paso de tipo de cambio.',
      },
      {
        label: 'Residuo',
        text: 'El residuo es un control aritmético, cero por construcción salvo redondeo: Eventos es el componente de cierre y recoge todo lo que los pasos de mercado no explican, así que un P&L mal explicado por los bloques aparece en Eventos y no en Residuo. Solo es distinto de cero si la cascada de una operación falla: entonces todo su P&L va al residuo y se muestra el error. Los efectos cruzados se atribuyen al paso posterior, así que cambiar el orden cambia la atribución pero no el total.',
      },
      {
        label: 'Operaciones nuevas y eventos',
        text: 'Las operaciones pactadas en la ventana van completas a su paso. Terminaciones, ejercicios y cambios de nocional se aíslan valuando con y sin los eventos de la ventana; Eventos, además, absorbe como componente de cierre cualquier otro efecto no atribuido a los pasos anteriores.',
      },
      {
        label: 'VaR histórico',
        text: 'Revaluación por sensibilidades (delta), no revaluación completa: el P&L diario es exposición por cambios históricos. Percentil empírico sin interpolar: con W pérdidas diarias de la ventana, el VaR es la k-ésima peor pérdida con k = max(1, ⌈W·(1 − α)⌉) (con W = 60 y α = 95 %, la 3.ª peor); escala por raíz del horizonte, como el paramétrico. El cuantil se calcula en Python, no con la función historicalVaR de C++, que no se usa y toma una pérdida más profunda cuando W·(1 − α) es entero. Ventana de 250 días por omisión, mínimo 60; sin historia suficiente no se calcula.',
      },
      {
        label: 'Déficit esperado',
        text: 'Promedio de las k peores pérdidas, incluida la del propio VaR (la k-ésima), con el mismo k del VaR y la misma escala por raíz del horizonte; no pondera fraccionariamente cuando W·(1 − α) no es entero. Siempre es mayor o igual que el VaR.',
      },
      {
        label: 'Historia de factores',
        text: 'Cambios diarios en pb de TIIE-F y SOFR, y rendimiento logarítmico de USDMXN. Fuentes: CSV, fijaciones, FRED o MarketDataFeed (SOFR con el proxy del Tesoro a 5 años). Los snapshots sintéticos usan la historia sintética.',
      },
      {
        label: 'Historia sintética de MX-DEMO',
        text: '500 días hábiles generados con semilla fija 20261110 a partir de las volatilidades y correlaciones de MX-DEMO. Inventada para demostración.',
      },
      {
        label: 'Límites',
        text: 'Por contraparte, PV positivo neto; por curva, DV01; por USDMXN, delta en MXN por 1 %; del portafolio, VaR paramétrico a 1 día y 99 %. Alerta desde 80 %, exceso por encima de 100 %. Se cambian con eventos, no se editan. La bitácora registra un exceso por límite y fecha de valuación.',
      },
      {
        label: 'Crédito y XVA',
        text: 'El CVA, el DVA y el FVA viven ahora en la sección XVA, con simulación multimoneda, curvas de crédito sintéticas por contraparte y la del propio desk. El escalón, la curva plana y el CVA por curva de la versión anterior quedan retirados.',
      },
      {
        label: 'Coherencia con la valuación',
        text: 'El motor de exposición no arma un swap aproximado: usa los mismos términos envejecidos que la valuación del desk (calendario real de pagos, base ACT/360, periodo en curso con su devengo, fijaciones), una pata por moneda en los swaps y en los cross currency swaps, y descuenta como la operación (TIIE-F, o la curva con colateral USD). En t = 0 su valor coincide con el PV del desk a 1e-6 del nocional por operación, así que el perfil arranca en el PV y no tiene escalón. Después de hoy el periodo en curso se compone en continuo con la tasa simulada, mientras el desk capitaliza diario: diferencia de segundo orden.',
      },
      {
        label: 'CVA informativo',
        text: 'El CVA es informativo: no entra al PV ni a la contabilidad de coberturas.',
      },
      {
        label: 'Escenarios históricos',
        text: 'Aproximaciones con choques fijos aplicados a la vez: Depreciación 2008 (USDMXN +35 %, TIIE-F +100 pb, SOFR −200 pb); 2016 elecciones EE. UU. (USDMXN +12 %, TIIE-F +75 pb, SOFR +25 pb); Marzo 2020 (USDMXN +25 %, TIIE-F −100 pb, SOFR −150 pb). No reproducen la curva completa de esas fechas.',
      },
      {
        label: 'Fuera de alcance',
        text: 'VaR por revaluación completa y Monte Carlo del portafolio; colateral y margen en la exposición del XVA; pruebas de respaldo del VaR; flujo de aprobación de límites.',
      },
    ],
  },
];
// --- fin corte 6 ---

// --- corte 9: XVA y curvas de crédito sintéticas ---
const XVA_SECTIONS: Section[] = [
  {
    id: 'xva',
    title: 'XVA',
    items: [
      {
        label: 'Modelo y medida',
        text: 'Hull-White de un factor por moneda sobre TIIE-F y SOFR, en forma de Cheyette: r = f(0,t) + x. USDMXN lognormal. Medida riesgo neutral MXN: la tasa USD lleva la deriva quanto −ρ·σ_USD·σ_X, y el tipo de cambio deriva con TIIE-F más la base MXN-USD menos SOFR, así que su forward es el de mercado con colateral USD. La base MXN-USD es determinista. Solo el IRS TIIE-F cambia de curva con el colateral de la contraparte (con colateral USD y la curva MXN-USD en el snapshot se descuenta con ella); el IRS SOFR descuenta siempre con SOFR, y el cross currency swap descuenta su pata MXN con MXN-USD (TIIE-F si el snapshot no la trae) y su pata USD con SOFR, cualquiera que sea el colateral. Simulación diaria, trayectorias y semilla fijas; los ajustes se integran en la malla de la fila «Malla de integración», no en el perfil mensual que se muestra.',
      },
      {
        label: 'Parámetros del XVA',
        text: 'a y σ de cada factor, tomados del snapshot. Volatilidad USDMXN: la ATM a 1 año de la superficie o, si no hay superficie, la volatilidad diaria de los factores × √252. Correlaciones de los cambios diarios de los factores, usadas como aproximación de las de los brownianos. Lo que falta se toma por omisión y se lista en Supuestos. Fondeo y parámetros de simulación son editables.',
      },
      {
        label: 'Definiciones',
        text: 'CVA = LGD · Σ EPE* · ΔS_c; DVA con ENE* y la curva propia; FVA = s_f · Σ (EPE* − ENE*) · S_c · S_o · Δt, con las sumas sobre la malla de integración. EPE* y ENE* se descuentan con la cuenta bancaria TIIE-F simulada para todas las contrapartes. El perfil que se muestra y se compara con límites es el sin descontar. Total = CVA − DVA + FVA.',
      },
      {
        label: 'Malla de integración',
        text: 'El motor simula por días, pero CVA, DVA y FVA se integran sobre una malla más fina que el perfil que se muestra (mensual): la mensual, un día de cada 3, cada fecha de pago y de intercambio de nocional de las operaciones y el día anterior a cada una, con la exposición de cada fecha al final de su intervalo (regla del extremo derecho). Contra una integración diaria con las mismas trayectorias, el CVA difiere menos de 0.5 % y el DVA y el FVA menos de 1 % en el portafolio sembrado y en el ejemplo del hallazgo; no es una cota general. Con la malla mensual sola el CVA salía cerca de 3 % menor y una operación que vence antes de la primera fecha mensual daba CVA cero. El perfil, los máximos de EPE y PFE y el perfil del XVA incremental que se muestran son los de la malla mensual; en el incremental el «antes» y el «después» usan la misma malla (la del conjunto ampliado), así que el «antes» puede diferir del XVA de la pantalla por la discretización (del orden de 1×10⁻⁴ relativo).',
      },
      {
        label: 'XVA incremental',
        text: 'Es la diferencia del XVA con y sin la operación, calculada sobre las mismas trayectorias, para que el ruido de Monte Carlo no contamine la diferencia.',
      },
      {
        label: 'Motor anterior retirado',
        text: 'El CVACalculator anterior (swaps frescos de pagos regulares en una sola moneda, con la deriva del Hull-White sacada de una derivada numérica del forward) quedó fuera de uso en el desk por un sesgo medido: con una curva con pendiente su CVA queda +7 % sobre el valor exacto (+3.5 % con curva plana), porque la tasa corta media simulada sube por encima de la del modelo. Sigue en la biblioteca C++, sin cambios, y ya no alimenta ninguna cifra del desk.',
      },
      {
        label: 'Curvas de crédito',
        text: 'Sintéticas: no son datos de mercado. Bootstrap tramo a tramo de CDS con prima trimestral ACT/360, recuperación dada y descuento con TIIE-F; intensidad constante por tramos. Con datos reales se cargarían diferenciales de CDS o de bonos del emisor. Si una contraparte no tiene curva, se usa un respaldo plano, con aviso de supuesto.',
      },
      {
        label: 'Convenciones del CDS',
        text: 'Simplificadas respecto de un CDS de mercado. Las primas son trimestrales y caen en los días round(k·365/4) desde la fecha de valuación, sin fechas IMM ni calendario de días hábiles; un plazo que no es múltiplo de un trimestre termina en un pago corto en round(365·T). El plazo T de cada cotización se mide como 365·T días. La prima se devenga ACT/360 sobre esos días. El incumplimiento se supone a mitad de periodo: la pata de protección descuenta la probabilidad de incumplimiento de cada periodo con el factor de su punto medio, y la prima devengada hasta el incumplimiento es la mitad de la del periodo. Contra una integración diaria el spread par cambia menos de 1×10⁻⁴ en términos relativos (medido con las curvas sintéticas del desk).',
      },
      {
        label: 'Sensibilidades del XVA',
        text: 'Qué se deriva: CVA, DVA, FVA y el total (CVA − DVA + FVA). Respecto de: la tasa cero de cada pilar de TIIE-F, SOFR y MXN-USD; el spot USDMXN; la volatilidad USDMXN; σ y a de Hull-White de cada moneda; la intensidad de cada tramo de crédito de la contraparte y de la propia; cada cotización de CDS, por el jacobiano del bootstrap obtenido por reprecio; y el diferencial de fondeo. Unidades: por pilar de curva, MXN por pb (y el DV01 paralelo, suma de los pilares, parcial y total); por el spot, MXN por 1 % del spot; por la volatilidad USDMXN, MXN por punto de volatilidad (0.01); σ de Hull-White, por 1 pb de volatilidad normal (1e-4); a, por 0.01; cada cotización de CDS y el fondeo, MXN por pb. Método: diferenciación adjunta con XAD, una cinta por trayectoria y adjuntos acumulados; el máximo de la exposición, max(V,0), lleva su indicador. Las derivadas son trayectoria a trayectoria con las mismas trayectorias, malla y semilla que el XVA, así que el XVA de referencia coincide con el de la pantalla. Costo: a igual número de hilos (un núcleo para ambos, o dos) la adjunta cuesta unas 7 a 9 valuaciones con la misma malla, en un conjunto de 3 operaciones a 10 años con 2 000 trayectorias. El cálculo usa como máximo 2 hilos, porque más no acelera la adjunta y multiplica la memoria, mientras que la valuación usa todos: en la ruta la adjunta tarda de 15 a 23 veces el tiempo de una valuación, y en conjuntos largos decenas de segundos. Por choques serían 2 × número de insumos valuaciones; con unos 48 insumos la adjunta sale unas 5 veces más barata, y la estimación por choques de la pantalla supone la valuación en todos los hilos. Las cifras se midieron con la compilación de depuración (Debug) que sirve la API. Límites: la parcial (MXN-USD fija) es la derivada de la AAD tal cual; la total recalibra MXN-USD con sus puntos forward y su base fijos (regla de la cadena con el jacobiano de la calibración por choque y recalibración, sin simular más) y solo existe para TIIE-F, SOFR y el spot, porque MXN-USD es lo que se recalibra; para cubrir con TIIE-F, SOFR o el tipo de cambio se usa la total, que en un cross currency swap puede tener el signo contrario al de la parcial. En ninguna se recalibran las curvas de crédito, aunque el bootstrap de CDS descuenta con TIIE-F. Son derivadas con el error de Monte Carlo de las trayectorias y no se informa su error estándar: las vegas de Hull-White son mucho más ruidosas que el CVA. Con una volatilidad exactamente cero su sensibilidad sale cero. No hay segundo orden, ni sensibilidad a correlaciones, ni derivada del PFE. Biblioteca: XAD (licencia AGPL-3.0). El motor de exposición se puede compilar sin ella (QF_WITH_XAD=OFF); en ese caso las sensibilidades no están disponibles.',
      },
      {
        label: 'Límites del XVA',
        text: 'Sin margen ni colateral en la exposición. Sin riesgo de correlación adversa (wrong-way). Base de cross currency determinista: un swap SOFR de una contraparte con colateral MXN queda con un sesgo determinista del tamaño de la base, porque el tipo de cambio deriva con esa base. EPE* se descuenta con la cuenta TIIE-F aunque el colateral sea USD. El periodo en curso se compone en continuo con la tasa simulada, mientras el desk capitaliza diario: diferencia de segundo orden. Excluidos: opciones, caps/floors, swaptions, bonos y forwards FX. El error de Monte Carlo se informa como error estándar del CVA. Fuera de alcance: KVA, MVA, contribuciones marginales por operación, XVA en PV o contabilidad.',
      },
    ],
  },
];
// --- fin corte 9 ---

const LIMITS: { label: string; text: string }[] = [
  {
    label: 'Datos',
    text: 'Mixtos en MKT-LIVE: curva SOFR aproximada, spot y volatilidades de SOFR y USDMXN de fuentes reales; el resto sintético. Ver Fuentes de datos.',
  },
  {
    label: 'Alcance',
    text: 'CVA informativo y XVA (sección XVA) de swaps de tasa y cross currency; sin margen ni colateral en la exposición. Un solo usuario.',
  },
  {
    label: 'Fechas',
    text: 'Días naturales; t = días/365; SOFR en periodos de 365 días; fechas de pago sin ajuste por inhábiles.',
  },
  {
    label: 'Bono',
    text: 'Periodos uniformes; la convención M-Bono de 182 días queda fuera.',
  },
  {
    label: 'Renta variable',
    text: 'La opción sobre acción aporta su PV pero cero a DV01, escenarios y VaR.',
  },
  {
    label: 'Operaciones',
    text: 'Envejecen a la fecha de valuación (as_of del snapshot); las terminadas se conservan.',
  },
  {
    label: 'Payoff',
    text: 'Opciones al vencimiento; solo ilustrativo.',
  },
  {
    label: 'Gráficas de payoff',
    text: 'Son de presentación: se calculan en el navegador, no en el backend (el PV y el riesgo sí vienen de él). La de la swaption usa una anualidad aproximada, con descuento plano a la tasa swap.',
  },
  { label: 'Moneda', text: 'Reporte en MXN al spot del snapshot.' },
];

// corte 7
const VALIDATION_SECTIONS: Section[] = [
  {
    id: 'validacion',
    title: 'Validación contra QuantLib',
    items: [
      {
        label: 'Referencia',
        text: 'QuantLib, ejecutado fuera del backend en un entorno de Python aparte; la versión y el entorno quedan en cada reporte. El escritorio no depende de QuantLib.',
      },
      {
        label: 'Qué se compara',
        text: 'El PV de los siete productos (swaps OIS de TIIE de Fondeo y SOFR, forwards y opciones USDMXN, opciones sobre acción, bonos, caps/floors y swaptions) en el snapshot MX-DEMO: el portafolio de ejemplo y una batería de casos por producto (lados, plazos, dentro y fuera del dinero), con las mismas curvas, spot, volatilidades y parámetros de Hull-White.',
      },
      {
        label: 'Curvas idénticas',
        text: 'QuantLib reconstruye cada curva desde los factores de descuento del escritorio en sus pilares, con la misma interpolación (lineal en tasa cero continua, t = días/365, plana fuera de los pilares). Se comprueba en los pilares (1e-12) y en 10 fechas intermedias (1e-8).',
      },
      {
        label: 'Tolerancias',
        text: 'Relativas al nocional: swaps OIS 1e-6; forwards 1e-8; opciones FX y sobre acción 1e-6; bonos 1e-6; caps/floors y swaptions con Hull-White 1e-6. Con los mismos insumos y el mismo modelo la diferencia observada en esos dos productos es de redondeo (a lo más 3e-9 del nocional), así que la tolerancia sí acota la discrepancia real.',
      },
      {
        label: 'Diferencias conocidas',
        text: 'Toda diferencia mayor a su tolerancia queda explicada caso por caso (qué convención difiere y cuánto explica) o se trata como defecto. Una prueba de la suite del backend falla si algún caso excede su tolerancia sin explicación.',
      },
      {
        label: 'Qué no se compara',
        text: 'Riesgo (DV01, escenarios, VaR), XVA, contabilidad de coberturas, valuación de operaciones envejecidas con fijaciones y datos de mercado reales de un proveedor. Tampoco se compara el bootstrap de las curvas (QuantLib recibe los factores de descuento ya armados), la interpolación de la superficie de volatilidad (las opciones USDMXN usan la volatilidad plana que el escritorio leyó de su superficie), el cross currency swap, la curva MXN-USD (solo se usan TIIE-F y SOFR con colateral en pesos), los calendarios (QuantLib usa fechas enteras sin calendario ni ajuste) ni la extrapolación fuera del último pilar (ningún caso lo rebasa). ORE no se usa como segunda referencia.',
      },
      {
        label: 'Reporte',
        text: (
          <>
            El último reporte, con su fecha, la versión de QuantLib, el commit con que se generó y
            cómo regenerarlo, está en la <Link to="/validacion">pantalla Validación</Link>.
          </>
        ),
      },
    ],
  },
];
// fin corte 7

function SectionBlock({ section }: { section: Section }) {
  return (
    <section className="meth-section" aria-labelledby={`meth-${section.id}`}>
      <h2 id={`meth-${section.id}`}>{section.title}</h2>
      <dl className="meth-list">
        {section.items.map((item) => (
          <div className="meth-row" key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.text}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function MethodologyScreen() {
  return (
    <div className="meth">
      <h1>Metodología</h1>
      <p className="meth-intro">
        Modelos, convenciones y curvas que usa cada producto del escritorio, y los límites de este
        corte.
      </p>

      <h2 className="meth-group">Productos</h2>
      {PRODUCT_SECTIONS.map((s) => (
        <SectionBlock key={s.id} section={s} />
      ))}

      <h2 className="meth-group">Convenciones generales</h2>
      {GENERAL_SECTIONS.map((s) => (
        <SectionBlock key={s.id} section={s} />
      ))}

      <h2 className="meth-group">Contabilidad de coberturas (IFRS 9)</h2>
      {HEDGE_SECTIONS.map((s) => (
        <SectionBlock key={s.id} section={s} />
      ))}

      {/* corte 5 */}
      {OPS_SECTIONS.map((s) => (
        <SectionBlock key={s.id} section={s} />
      ))}
      {/* --- corte 6: grupo de riesgo avanzado --- */}
      <h2 className="meth-group">Riesgo avanzado</h2>
      {RISK_ADV_SECTIONS.map((s) => (
        <SectionBlock key={s.id} section={s} />
      ))}
      {/* --- fin corte 6 --- */}
      {/* corte 9 */}
      {XVA_SECTIONS.map((s) => (
        <SectionBlock key={s.id} section={s} />
      ))}
      {/* fin corte 9 */}
      {/* corte 7 */}
      <h2 className="meth-group">Validación independiente</h2>
      {VALIDATION_SECTIONS.map((s) => (
        <SectionBlock key={s.id} section={s} />
      ))}
      {/* fin corte 7 */}

      <section className="meth-section" aria-labelledby="meth-limites">
        <h2 id="meth-limites">Límites de este corte</h2>
        <dl className="meth-list">
          {LIMITS.map((item) => (
            <div className="meth-row" key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.text}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
