import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { ScreenLoading } from './components/ScreenLoading';
import { Shell } from './components/Shell';

// Cada pantalla es su propio trozo: el de entrada solo lleva el menú y el enrutador.
const HedgeReportScreen = lazy(() => import('./screens/HedgeReportScreen'));
const HedgeScreen = lazy(() => import('./screens/HedgeScreen'));
const HedgesScreen = lazy(() => import('./screens/HedgesScreen'));
const MarketScreen = lazy(() => import('./screens/MarketScreen').then((m) => ({ default: m.MarketScreen })));
const MethodologyScreen = lazy(() =>
  import('./screens/MethodologyScreen').then((m) => ({ default: m.MethodologyScreen })),
);
const PortfolioScreen = lazy(() =>
  import('./screens/PortfolioScreen').then((m) => ({ default: m.PortfolioScreen })),
);
const RiskScreen = lazy(() => import('./screens/RiskScreen').then((m) => ({ default: m.RiskScreen })));
const TradeScreen = lazy(() => import('./screens/TradeScreen'));
const PricersScreen = lazy(() =>
  import('./screens/pricers/PricersScreen').then((m) => ({ default: m.PricersScreen })),
);
// --- corte 5 ---
const ConfirmationScreen = lazy(() => import('./screens/ops/ConfirmationScreen'));
const OpsScreen = lazy(() => import('./screens/ops/OpsScreen'));
// --- fin corte 5 ---
// corte 7
const ValidationScreen = lazy(() => import('./screens/ValidationScreen'));
// fin corte 7
// corte 9
const XvaScreen = lazy(() => import('./screens/XvaScreen'));
// fin corte 9

export default function App() {
  return (
    <Shell>
      <Suspense fallback={<ScreenLoading />}>
        <Routes>
          <Route path="/" element={<Navigate to="/mercado" replace />} />
          <Route path="/mercado" element={<MarketScreen />} />
          <Route path="/pricers" element={<Navigate to="/pricers/irs" replace />} />
          <Route path="/pricers/:product" element={<PricersScreen />} />
          <Route path="/portafolio" element={<PortfolioScreen />} />
          <Route path="/portafolio/:id" element={<TradeScreen />} />
          <Route path="/riesgo" element={<RiskScreen />} />
          <Route path="/coberturas" element={<HedgesScreen />} />
          <Route path="/coberturas/:id" element={<HedgeScreen />} />
          <Route path="/coberturas/:id/reporte" element={<HedgeReportScreen />} />
          <Route path="/metodologia" element={<MethodologyScreen />} />
          {/* corte 5 */}
          <Route path="/operaciones" element={<OpsScreen />} />
          <Route path="/portafolio/:id/confirmacion" element={<ConfirmationScreen />} />
          {/* corte 7 */}
          <Route path="/validacion" element={<ValidationScreen />} />
          {/* fin corte 7 */}
          {/* corte 9 */}
          <Route path="/xva" element={<XvaScreen />} />
          {/* fin corte 9 */}
        </Routes>
      </Suspense>
    </Shell>
  );
}
