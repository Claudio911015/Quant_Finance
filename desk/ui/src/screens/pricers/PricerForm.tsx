import type { ProductSpec } from './types';

export function PricerForm({ spec }: { spec: ProductSpec }) {
  return <h1>{spec.title}</h1>;
}
