import type { ProductId } from '../../api/types';

export type FieldKind = 'number' | 'int' | 'percent' | 'select' | 'text';

export interface FieldSpec {
  name: string;
  label: string;
  kind: FieldKind;
  default: string | number | null;
  options?: { value: string; label: string }[];
  optional?: boolean;
  help?: string;
}

export interface ProductSpec {
  product: ProductId;
  title: string;
  fields: FieldSpec[];
  chart: 'cashflows' | 'payoff' | 'none';
}
