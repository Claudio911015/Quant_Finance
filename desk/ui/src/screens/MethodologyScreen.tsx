import type { ReactNode } from 'react';
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
          'El DV01 por plazo se calcula con diferencia central, (PV(−1 pb) − PV(+1 pb)) / 2, sobre un desplazamiento de la tasa cero en cada pilar; el DV01 paralelo es PV(base) − PV(+1 pb). Para productos con convexidad (cap/floor) la suma por plazo puede diferir del paralelo en unas décimas de punto porcentual.',
      },
      {
        label: 'VaR',
        text:
          'Delta-normal con volatilidades y correlaciones de factores del snapshot. Tres factores: TIIE-F paralelo, SOFR paralelo y USDMXN rendimiento relativo; sin factores por plazo.',
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

const LIMITS: { label: string; text: string }[] = [
  {
    label: 'Datos',
    text: 'Mixtos en MKT-LIVE: curva SOFR aproximada, spot y volatilidades de SOFR y USDMXN de fuentes reales; el resto sintético. Ver Fuentes de datos.',
  },
  { label: 'Alcance', text: 'Sin XVA. Un solo usuario.' },
  {
    label: 'Fechas',
    text: 'Días naturales sin calendario de inhábiles; t = días/365; SOFR en periodos de 365 días.',
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
    text: 'No envejecen entre snapshots; los vencimientos se derivan del as_of.',
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
