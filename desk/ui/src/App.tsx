import { Navigate, Route, Routes } from 'react-router-dom';
import { Shell } from './components/Shell';
import { MarketScreen } from './screens/MarketScreen';
import { MethodologyScreen } from './screens/MethodologyScreen';
import { PortfolioScreen } from './screens/PortfolioScreen';
import { RiskScreen } from './screens/RiskScreen';
import { PricersScreen } from './screens/pricers/PricersScreen';

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/mercado" replace />} />
        <Route path="/mercado" element={<MarketScreen />} />
        <Route path="/pricers" element={<Navigate to="/pricers/irs" replace />} />
        <Route path="/pricers/:product" element={<PricersScreen />} />
        <Route path="/portafolio" element={<PortfolioScreen />} />
        <Route path="/riesgo" element={<RiskScreen />} />
        <Route path="/metodologia" element={<MethodologyScreen />} />
      </Routes>
    </Shell>
  );
}
