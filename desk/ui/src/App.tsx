import { Navigate, Route, Routes } from 'react-router-dom';
import { Shell } from './components/Shell';
import HedgeReportScreen from './screens/HedgeReportScreen';
import HedgeScreen from './screens/HedgeScreen';
import HedgesScreen from './screens/HedgesScreen';
import { MarketScreen } from './screens/MarketScreen';
import { MethodologyScreen } from './screens/MethodologyScreen';
import { PortfolioScreen } from './screens/PortfolioScreen';
import { RiskScreen } from './screens/RiskScreen';
import TradeScreen from './screens/TradeScreen';
import { PricersScreen } from './screens/pricers/PricersScreen';
// --- corte 5 ---
import ConfirmationScreen from './screens/ops/ConfirmationScreen';
import OpsScreen from './screens/ops/OpsScreen';
// --- fin corte 5 ---
// corte 7
import ValidationScreen from './screens/ValidationScreen';
// fin corte 7

export default function App() {
  return (
    <Shell>
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
      </Routes>
    </Shell>
  );
}
