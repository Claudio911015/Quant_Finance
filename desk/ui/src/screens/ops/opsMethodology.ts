// Secciones de Metodología sobre operaciones (corte 5).
export const OPS_SECTIONS: {
  id: string;
  title: string;
  items: { label: string; text: string }[];
}[] = [
  {
    id: 'operaciones',
    title: 'Operaciones',
    items: [
      {
        label: 'Calendario de flujos',
        text: 'Une los flujos ya liquidados, derivados de los términos y de las fijaciones, con los proyectados de los swaps y bonos vivos, usando el mismo instrumento que la valuación. El signo positivo indica que la empresa cobra; los montos en USD se convierten a MXN con el fixing en los liquidados y con el spot del snapshot en los proyectados. Los forwards y las opciones no proyectan flujo.',
      },
      {
        label: 'Liquidación confirmada',
        text: 'Registra el pago real como evento de tipo transfer (settlement_confirmed), una vez por flujo. No cambia la valuación ni el P&L: el flujo derivado es el que cuenta, y la diferencia entre ambos se reporta aparte.',
      },
      {
        label: 'Confirmación',
        text: 'Documento informativo con los términos pactados y las convenciones de la operación. No sustituye la confirmación ISDA ni el contrato marco, y no lleva firma.',
      },
      {
        label: 'FpML',
        text: 'Exporta e importa swaps OIS, forwards y opciones USD/MXN en FpML 5.12 (vista de confirmación), con el subconjunto de elementos necesario para ida y vuelta. No se valida contra el esquema XSD oficial, no se aceptan DTD ni entidades, y los nombres de índice ISDA (MXN-TIIE-ON-OIS Compound, USD-SOFR-OIS Compound) están por verificar contra las definiciones vigentes. No incluye prima de opciones ni ajustes de días hábiles.',
      },
      {
        label: 'Conciliación',
        text: 'Compara el PV propio contra el del banco, con la convención de signo de la empresa y el USD al spot del snapshot. Queda conciliada si la diferencia es menor o igual a 0.01 % del nocional (configurable); es explicable si la atribuyen la fecha (±1 día hábil), un desplazamiento paralelo de la curva de hasta ±10 pb o un movimiento de spot de hasta ±1 %; en otro caso se marca para revisar, con bandera de términos si ni ±25 pb ni ±2 % la explican.',
      },
      {
        label: 'Descomposición indicativa',
        text: 'La descomposición es una ayuda de diagnóstico, no una prueba: indica qué movimiento explicaría la diferencia, no que lo haya causado. Mueve un solo factor a la vez, en paralelo sobre la tasa cero, y no usa calendario de días inhábiles.',
      },
      {
        label: 'Fuera de alcance',
        text: 'No incluye validación XSD, otros productos en FpML, mensajería (SWIFT, MarkitWire), instrucciones de liquidación y cuentas, neteo de pagos, conciliación de colateral ni confirmación con firma.',
      },
    ],
  },
];
