import os
import sys
import types
import unittest
from unittest.mock import MagicMock

# Ensure python_web imports a controlled qfpy module for deterministic tests
fake_qfpy = types.SimpleNamespace()

class FDMethod:
    CrankNicolson = 2

class OptionType:
    Call = 0

class ExerciseType:
    European = 0

fake_qfpy.__file__ = '<fake-qfpy>'
fake_qfpy.OptionParams = MagicMock(return_value=MagicMock())
fake_qfpy.OptionType = OptionType
fake_qfpy.ExerciseType = ExerciseType
fake_qfpy.FDMethod = FDMethod
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

sys.modules['qfpy'] = fake_qfpy

from python_web import app

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.client.testing = True

    def test_index_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Quant Finance Dashboard', response.get_data(as_text=True))

    def test_api_price_returns_expected_keys(self):
        payload = {
            'spot': 100.0,
            'strike': 100.0,
            'r': 0.05,
            'q': 0.0,
            'vol': 0.2,
            't': 1.0
        }
        response = self.client.post('/api/price', json=payload)
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


if __name__ == '__main__':
    unittest.main()
