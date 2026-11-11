import { NavLink, Navigate, useParams } from 'react-router-dom';
import type { ProductId } from '../../api/types';
import { PricerForm } from './PricerForm';
import { PRODUCT_SPECS } from './registry';
import './PricerForm.css';

export function PricersScreen() {
  const { product } = useParams();
  const spec = PRODUCT_SPECS[product as ProductId];
  if (!spec) return <Navigate to="/pricers/irs" replace />;
  return (
    <div className="pricers">
      <nav className="pricers__list" aria-label="Productos">
        <div className="pricer__caption">Productos</div>
        {Object.values(PRODUCT_SPECS).map((s) => (
          <NavLink key={s.product} to={`/pricers/${s.product}`} className="pricers__link">
            {s.title}
          </NavLink>
        ))}
      </nav>
      {/* key: al cambiar de producto el formulario arranca de cero */}
      <PricerForm key={spec.product} spec={spec} />
    </div>
  );
}
