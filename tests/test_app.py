import os
import sys
import types
import unittest
from unittest.mock import MagicMock

# Ensure python_web imports a controlled qfpy module for deterministic tests
fake_qfpy = types.SimpleNamespace()

class FDMethod:
    Explicit = 0
    Implicit = 1
    CrankNicolson = 2

class OptionType:
    Call = 0
    Put = 1

class ExerciseType:
    European = 0
    American = 1

class InterpolationMethod:
    Linear = 0
    CubicSpline = 1
    LogLinear = 2

fake_qfpy.__file__ = '<fake-qfpy>'
fake_qfpy.OptionParams = MagicMock(return_value=MagicMock())
fake_qfpy.OptionType = OptionType
fake_qfpy.ExerciseType = ExerciseType
fake_qfpy.FDMethod = FDMethod
fake_qfpy.InterpolationMethod = InterpolationMethod
fake_qfpy.black_scholes = MagicMock(return_value={
    'price': 10.45,
    'delta': 0.63,
    'gamma': 0.018,
    'vega': 0.37,
    'theta': -0.02,
    'rho': 0.53,
})
fake_qfpy.binomial_tree_price = MagicMock(return_value=10.44)
fake_qfpy.montecarlo_price = MagicMock(return_value=10.43)
fake_qfpy.finite_difference_price = MagicMock(return_value=10.42)
fake_qfpy.implied_volatility = MagicMock(return_value=0.2)

# Mock HestonParams
fake_qfpy.HestonParams = MagicMock(return_value=MagicMock())
fake_qfpy.heston_price = MagicMock(return_value=10.50)
fake_qfpy.heston_montecarlo = MagicMock(return_value=10.48)

# Mock Bond
mock_bond_instance = MagicMock()
mock_bond_instance.price = MagicMock(return_value=950.0)
mock_bond_instance.duration = MagicMock(return_value=7.5)
mock_bond_instance.convexity = MagicMock(return_value=65.0)
fake_qfpy.Bond = MagicMock(return_value=mock_bond_instance)

# Mock YieldCurve
mock_curve_instance = MagicMock()
mock_curve_instance.zero_rate = MagicMock(return_value=0.045)
mock_curve_instance.discount_factor = MagicMock(return_value=0.956)
mock_curve_instance.forward_rate = MagicMock(return_value=0.048)
fake_qfpy.YieldCurve = MagicMock(return_value=mock_curve_instance)

sys.modules['qfpy'] = fake_qfpy

from python_web import app

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.client.testing = True
        # Reset mocks before each test
        fake_qfpy.OptionParams.reset_mock()
        fake_qfpy.black_scholes.reset_mock()
        fake_qfpy.binomial_tree_price.reset_mock()
        fake_qfpy.montecarlo_price.reset_mock()
        fake_qfpy.finite_difference_price.reset_mock()

    def _default_payload(self, **overrides):
        payload = {
            'spot': 100.0, 'strike': 100.0, 'r': 0.05,
            'q': 0.0, 'vol': 0.2, 't': 1.0
        }
        payload.update(overrides)
        return payload

    # --- Options pricing tests ---

    def test_index_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Quant Finance Dashboard', response.get_data(as_text=True))

    def test_api_price_returns_expected_keys(self):
        response = self.client.post('/api/price', json=self._default_payload())
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIsInstance(data, dict)

        for key in ['black_scholes', 'binomial', 'montecarlo', 'finite_difference',
                    'delta', 'gamma', 'vega', 'theta', 'rho']:
            self.assertIn(key, data)

        self.assertAlmostEqual(data['black_scholes'], 10.45)
        self.assertAlmostEqual(data['binomial'], 10.44)
        self.assertAlmostEqual(data['montecarlo'], 10.43)
        self.assertAlmostEqual(data['finite_difference'], 10.42)

    def test_api_price_put_option(self):
        response = self.client.post('/api/price',
                                    json=self._default_payload(optionType='Put'))
        self.assertEqual(response.status_code, 200)
        params = fake_qfpy.OptionParams.return_value
        self.assertEqual(params.type, OptionType.Put)

    def test_api_price_american(self):
        response = self.client.post('/api/price',
                                    json=self._default_payload(exerciseType='American'))
        self.assertEqual(response.status_code, 200)
        params = fake_qfpy.OptionParams.return_value
        self.assertEqual(params.exercise, ExerciseType.American)

    def test_api_price_fd_explicit(self):
        response = self.client.post('/api/price',
                                    json=self._default_payload(fdMethod='Explicit'))
        self.assertEqual(response.status_code, 200)
        _, kwargs = fake_qfpy.finite_difference_price.call_args
        self.assertEqual(kwargs['method'], FDMethod.Explicit)

    def test_api_price_invalid_input(self):
        response = self.client.post('/api/price',
                                    json=self._default_payload(spot=-10))
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('error', data)

    def test_api_price_missing_fields(self):
        response = self.client.post('/api/price', json={})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('black_scholes', data)

    # --- Chart endpoint tests ---

    def test_api_payoff(self):
        response = self.client.post('/api/payoff', json=self._default_payload())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 101)
        self.assertIn('spot', data[0])
        self.assertIn('payoff', data[0])
        self.assertIn('profit', data[0])

    def test_api_greeks_surface(self):
        payload = self._default_payload(greek='delta', variable='spot')
        response = self.client.post('/api/greeks-surface', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn('x', data[0])
        self.assertIn('y', data[0])

    def test_api_model_convergence(self):
        response = self.client.post('/api/model-convergence', json=self._default_payload())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        for key in ['binomial', 'montecarlo', 'fd', 'bs_reference']:
            self.assertIn(key, data)
        self.assertIsInstance(data['binomial'], list)
        self.assertIsInstance(data['bs_reference'], float)

    # --- Bonds and yield curve tests ---

    def test_bonds_page(self):
        response = self.client.get('/bonds')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Fixed Income', response.get_data(as_text=True))

    def test_api_bond_pricing(self):
        payload = {
            'faceValue': 1000, 'couponRate': 0.05, 'periods': 10, 'frequency': 2,
            'maturities': [0.5, 1, 2, 5, 10], 'zeroRates': [0.04, 0.042, 0.045, 0.048, 0.05],
            'interpMethod': 'CubicSpline'
        }
        response = self.client.post('/api/bond', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        for key in ['price', 'duration', 'convexity']:
            self.assertIn(key, data)
        self.assertAlmostEqual(data['price'], 950.0)

    def test_api_bond_insufficient_points(self):
        payload = {
            'faceValue': 1000, 'couponRate': 0.05, 'periods': 10,
            'maturities': [1], 'zeroRates': [0.04]
        }
        response = self.client.post('/api/bond', json=payload)
        self.assertEqual(response.status_code, 400)

    def test_api_yield_curve(self):
        payload = {
            'maturities': [0.5, 1, 2, 5, 10], 'zeroRates': [0.04, 0.042, 0.045, 0.048, 0.05],
            'interpMethod': 'CubicSpline'
        }
        response = self.client.post('/api/yield-curve', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('points', data)
        self.assertIsInstance(data['points'], list)
        self.assertGreater(len(data['points']), 0)
        point = data['points'][0]
        for key in ['t', 'zeroRate', 'discountFactor', 'forwardRate']:
            self.assertIn(key, point)

    # --- Heston tests ---

    def test_api_price_heston(self):
        payload = self._default_payload(v0=0.04, kappa=2.0, theta=0.04, sigma=0.3, rho=-0.7)
        response = self.client.post('/api/price-heston', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('heston_analytical', data)
        self.assertIn('heston_mc', data)
        self.assertAlmostEqual(data['heston_analytical'], 10.50)

    # --- Implied volatility tests ---

    def test_api_implied_vol(self):
        payload = self._default_payload(marketPrice=10.45)
        response = self.client.post('/api/implied-vol', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('impliedVol', data)
        self.assertAlmostEqual(data['impliedVol'], 0.2)


if __name__ == '__main__':
    unittest.main()
