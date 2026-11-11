import type { ReactNode } from 'react';
import {
  DECL_DEDESIGNATION,
  DECL_DESIGNATION_DATE,
  DECL_FV_ACCRUAL,
  DECL_FV_COMPONENT,
  DECL_FV_PRESENTATION,
  DECL_OFF_MARKET,
  DECL_RECYCLING,
} from '../lib/hedgeDeclarations';
import './MethodologyScreen.css';

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
    title: 'Forward USDMXN',
    items: [
      { label: 'Modelo', text: 'Paridad de tasas cubierta.' },
      { label: 'Curvas', text: 'TIIE-F (MXN) y SOFR (USD).' },
    ],
  },
  {
    id: 'fx-option',
    title: 'Opción USDMXN',
    items: [
      { label: 'Modelo', text: 'Garman-Kohlhagen.' },
      { label: 'Volatilidad', text: 'Vol de la superficie por plazo y strike.' },
    ],
  },
  {
    id: 'cap-floor',
    title: 'Cap / floor',
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
    ],
  },
  {
    id: 'equity-option',
    title: 'Opción de renta variable',
    items: [
      { label: 'Modelo', text: 'Black-Scholes con insumos capturados en la operación.' },
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
        text: 'Inhábiles bancarios de México para TIIE-F y de publicación de SOFR (SIFMA) en EE. UU. para SOFR, por reglas 2020–2040. Una fijación no publicada en día inhábil de su índice no es faltante. Las fechas de pago son las pactadas: no se ajustan por inhábil.',
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
        text: 'Días naturales, t = días/365, devengo ACT/360, fijaciones diarias capitalizadas. Los calendarios de inhábiles solo rigen fijaciones y coberturas (ver Calendarios).',
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
        text: 'Un swap dado de alta sin tasa fija nace a la par: se guarda con la tasa par del snapshot de la petición (o MX-DEMO), de modo que su PV en la fecha de pacto es cero.',
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
        text: 'El sistema no es el libro mayor ni sustituye al contador. Cuentas fijas; redondeo a centavos. Las cuentas de balance se asientan como la diferencia entre saldos acumulados ya redondeados, de modo que el acumulado de asientos coincide al centavo con el saldo; el residuo del periodo va a resultados por inefectividad.',
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
        text: `Las liquidaciones del derivado en el periodo se reconocen en resultados como el flujo cubierto ocurrido, pero solo la parte efectiva: el menor entre lo liquidado del instrumento y lo liquidado del hipotético; el exceso va a inefectividad. ${DECL_RECYCLING} En el cierre final la reserva queda en 0 si el instrumento y la partida vencen juntos. Si el instrumento vence antes que el flujo cubierto, la reserva se conserva en ORI (IFRS 9 6.5.12(a)) y la relación pasa a Concluida: no admite más cierres, y la reserva se libera a mano cuando el flujo ocurra.`,
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
        label: 'Efectividad prospectiva',
        text: 'Términos críticos (nocional, índice o moneda, fechas y sentido: el swap debe ser el que compensa la partida) y escenarios del escritorio. Hay relación económica si todas las razones son positivas. El rango 80 %–125 % es solo referencia; IFRS 9 no fija umbral.',
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
        text: `${DECL_OFF_MARKET} Al designar, el alta avisa de esto, de que la prueba prospectiva no muestre relación económica, de un flujo pronosticado en fin de semana (se liquidará con el spot del snapshot) y de una cobertura documentada más de un día después de su fecha de designación.`,
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

const LIMITS: { label: string; text: string }[] = [
  {
    label: 'Datos',
    text: 'Mixtos en MKT-LIVE: curva SOFR aproximada, spot y volatilidades de SOFR y USDMXN de fuentes reales; el resto sintético. Ver Fuentes de datos.',
  },
  { label: 'Alcance', text: 'Sin XVA. Un solo usuario.' },
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
    text: 'equity_option aporta su PV pero cero a DV01, escenarios y VaR.',
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
