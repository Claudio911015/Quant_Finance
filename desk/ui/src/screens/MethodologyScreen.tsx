import './MethodologyScreen.css';

interface Section {
  id: string;
  title: string;
  items: { label: string; text: string }[];
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
        label: 'VaR',
        text:
          'Delta-normal con volatilidades y correlaciones de factores del snapshot. Tres factores: TIIE-F paralelo, SOFR paralelo y USDMXN rendimiento relativo; sin factores por plazo.',
      },
    ],
  },
];

const LIMITS: { label: string; text: string }[] = [
  { label: 'Datos', text: 'Sintéticos.' },
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
