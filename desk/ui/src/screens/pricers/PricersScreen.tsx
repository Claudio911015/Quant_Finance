import { Navigate, useParams } from 'react-router-dom';
import type { ProductId } from '../../api/types';
import { PricerForm } from './PricerForm';
import { PRODUCT_SPECS } from './registry';

export function PricersScreen() {
  const { product } = useParams();
  const spec = PRODUCT_SPECS[product as ProductId];
  if (!spec) return <Navigate to="/pricers/irs" replace />;
  return <PricerForm spec={spec} />;
}
