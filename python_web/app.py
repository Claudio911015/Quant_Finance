from flask import Flask, render_template, request, jsonify
import os, sys

# Ensure qfpy built extension is importable:
build_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'build'))
build_src = os.path.join(build_root, 'src')
for p in (build_src, build_root):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import qfpy
    print(f"qfpy loaded from: {qfpy.__file__}")
except ModuleNotFoundError:
    raise ModuleNotFoundError('qfpy module not found. Run cmake --build build --target qfpy first.')

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/price', methods=['POST'])
def api_price():
    data = request.json or {}

    try:
        p = qfpy.OptionParams()
        p.spot = float(data.get('spot', 100.0))
        p.strike = float(data.get('strike', 100.0))
        p.riskFreeRate = float(data.get('r', 0.05))
        p.dividendYield = float(data.get('q', 0.0))
        p.volatility = float(data.get('vol', 0.2))
        p.maturity = float(data.get('t', 1.0))

        if p.spot <= 0 or p.strike <= 0 or p.volatility <= 0 or p.maturity <= 0:
            return jsonify({'error': 'spot, strike, volatility and maturity must be positive'}), 400

        option_type = data.get('optionType', 'Call')
        p.type = qfpy.OptionType.Put if option_type == 'Put' else qfpy.OptionType.Call

        exercise_type = data.get('exerciseType', 'European')
        p.exercise = qfpy.ExerciseType.American if exercise_type == 'American' else qfpy.ExerciseType.European

        fd_method_map = {
            'Explicit': qfpy.FDMethod.Explicit,
            'Implicit': qfpy.FDMethod.Implicit,
            'CrankNicolson': qfpy.FDMethod.CrankNicolson,
        }
        fd_method = fd_method_map.get(data.get('fdMethod', 'CrankNicolson'), qfpy.FDMethod.CrankNicolson)

        bs = qfpy.black_scholes(p)
        bt = qfpy.binomial_tree_price(p, 1000)
        mc = qfpy.montecarlo_price(p, 200000, seed=123)
        fd = qfpy.finite_difference_price(p, nS=500, nT=1000, method=fd_method)

        if not (fd and fd == fd):  # check nan
            fd = 0.0

        return jsonify({
            'black_scholes': bs['price'],
            'delta': bs['delta'],
            'gamma': bs['gamma'],
            'vega': bs['vega'],
            'theta': bs['theta'],
            'rho': bs['rho'],
            'binomial': bt,
            'montecarlo': mc,
            'finite_difference': fd
        })
    except (ValueError, TypeError) as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/payoff', methods=['POST'])
def api_payoff():
    data = request.json or {}
    spot = float(data.get('spot', 100.0))
    strike = float(data.get('strike', 100.0))
    option_type = data.get('optionType', 'Call')

    # Calculate premium using BS
    p = qfpy.OptionParams()
    p.spot = spot
    p.strike = strike
    p.riskFreeRate = float(data.get('r', 0.05))
    p.dividendYield = float(data.get('q', 0.0))
    p.volatility = float(data.get('vol', 0.2))
    p.maturity = float(data.get('t', 1.0))
    p.type = qfpy.OptionType.Put if option_type == 'Put' else qfpy.OptionType.Call
    p.exercise = qfpy.ExerciseType.European
    premium = qfpy.black_scholes(p)['price']

    lo, hi = 0.5 * strike, 1.5 * strike
    n = 100
    results = []
    for i in range(n + 1):
        s = lo + (hi - lo) * i / n
        if option_type == 'Put':
            payoff = max(strike - s, 0)
        else:
            payoff = max(s - strike, 0)
        results.append({'spot': round(s, 4), 'payoff': round(payoff, 6), 'profit': round(payoff - premium, 6)})
    return jsonify(results)


@app.route('/api/greeks-surface', methods=['POST'])
def api_greeks_surface():
    data = request.json or {}
    greek = data.get('greek', 'delta')
    variable = data.get('variable', 'spot')

    base_spot = float(data.get('spot', 100.0))
    base_strike = float(data.get('strike', 100.0))
    base_r = float(data.get('r', 0.05))
    base_q = float(data.get('q', 0.0))
    base_vol = float(data.get('vol', 0.2))
    base_t = float(data.get('t', 1.0))
    option_type = data.get('optionType', 'Call')

    ranges = {
        'spot': (0.5 * base_strike, 1.5 * base_strike, 60),
        'vol': (0.01, min(base_vol * 4, 2.0), 60),
        'maturity': (0.01, min(base_t * 3, 10.0), 60),
    }

    lo, hi, n = ranges.get(variable, (0.5 * base_strike, 1.5 * base_strike, 60))
    results = []
    for i in range(n + 1):
        x = lo + (hi - lo) * i / n
        p = qfpy.OptionParams()
        p.spot = x if variable == 'spot' else base_spot
        p.strike = base_strike
        p.riskFreeRate = base_r
        p.dividendYield = base_q
        p.volatility = x if variable == 'vol' else base_vol
        p.maturity = x if variable == 'maturity' else base_t
        p.type = qfpy.OptionType.Put if option_type == 'Put' else qfpy.OptionType.Call
        p.exercise = qfpy.ExerciseType.European

        bs = qfpy.black_scholes(p)
        y = bs.get(greek, 0)
        results.append({'x': round(x, 6), 'y': round(y, 8)})

    return jsonify(results)


@app.route('/api/model-convergence', methods=['POST'])
def api_model_convergence():
    data = request.json or {}

    p = qfpy.OptionParams()
    p.spot = float(data.get('spot', 100.0))
    p.strike = float(data.get('strike', 100.0))
    p.riskFreeRate = float(data.get('r', 0.05))
    p.dividendYield = float(data.get('q', 0.0))
    p.volatility = float(data.get('vol', 0.2))
    p.maturity = float(data.get('t', 1.0))
    option_type = data.get('optionType', 'Call')
    p.type = qfpy.OptionType.Put if option_type == 'Put' else qfpy.OptionType.Call
    p.exercise = qfpy.ExerciseType.European

    fd_method_map = {
        'Explicit': qfpy.FDMethod.Explicit,
        'Implicit': qfpy.FDMethod.Implicit,
        'CrankNicolson': qfpy.FDMethod.CrankNicolson,
    }
    fd_method = fd_method_map.get(data.get('fdMethod', 'CrankNicolson'), qfpy.FDMethod.CrankNicolson)

    bs_ref = qfpy.black_scholes(p)['price']

    binomial = []
    for steps in range(10, 510, 25):
        price = qfpy.binomial_tree_price(p, steps)
        binomial.append({'x': steps, 'y': round(price, 8)})

    montecarlo = []
    for paths in range(1000, 200001, 10000):
        price = qfpy.montecarlo_price(p, paths, seed=123)
        montecarlo.append({'x': paths, 'y': round(price, 8)})

    fd = []
    for grid in range(20, 520, 25):
        price = qfpy.finite_difference_price(p, nS=grid, nT=grid * 2, method=fd_method)
        if price and price == price:  # check nan
            fd.append({'x': grid, 'y': round(price, 8)})

    return jsonify({
        'binomial': binomial,
        'montecarlo': montecarlo,
        'fd': fd,
        'bs_reference': round(bs_ref, 8)
    })


@app.route('/bonds')
def bonds():
    return render_template('bonds.html')


@app.route('/swaps')
def swaps():
    return render_template('swaps.html', active='swaps')


@app.route('/api/bond', methods=['POST'])
def api_bond():
    data = request.json or {}
    try:
        maturities = [float(x) for x in data.get('maturities', [])]
        zero_rates = [float(x) for x in data.get('zeroRates', [])]

        if len(maturities) < 2 or len(maturities) != len(zero_rates):
            return jsonify({'error': 'Need at least 2 matching maturity/rate pairs'}), 400

        interp_map = {
            'Linear': qfpy.InterpolationMethod.Linear,
            'CubicSpline': qfpy.InterpolationMethod.CubicSpline,
            'LogLinear': qfpy.InterpolationMethod.LogLinear,
        }
        interp = interp_map.get(data.get('interpMethod', 'CubicSpline'), qfpy.InterpolationMethod.CubicSpline)

        curve = qfpy.YieldCurve(maturities, zero_rates, interp)
        bond = qfpy.Bond(
            float(data.get('faceValue', 1000)),
            float(data.get('couponRate', 0.05)),
            int(data.get('periods', 10)),
            float(data.get('frequency', 2))
        )

        return jsonify({
            'price': bond.price(curve),
            'duration': bond.duration(curve),
            'convexity': bond.convexity(curve)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/swap', methods=['POST'])
def api_swap():
    """Price an IRS or ScheduledSwap.

    Request JSON (mode='regular'):
    {
        "mode": "regular",
        "notional": 1000000,
        "fixed_rate": 0.04,
        "maturity": 5.0,
        "frequency": 1.0,
        "swap_type": "payer",
        "curve_tenors": [1, 2, 3, 4, 5],
        "curve_rates":  [0.04, 0.04, 0.04, 0.04, 0.04]
    }

    Request JSON (mode='scheduled'):
    {
        "mode": "scheduled",
        "fixed_rate": 0.04,
        "schedule": [
            {"pay_time": 0.25, "accrual_frac": 0.25, "notional": 1000000},
            ...
        ],
        "curve_tenors": [1, 2, 3, 4, 5],
        "curve_rates":  [0.04, 0.04, 0.04, 0.04, 0.04]
    }
    """
    data = request.get_json(force=True)
    mode = data.get('mode', 'regular')

    tenors = data.get('curve_tenors', [1, 2, 3, 5, 10])
    rates  = data.get('curve_rates',  [0.04] * len(tenors))

    try:
        curve = qfpy.YieldCurve(tenors, rates, qfpy.InterpolationMethod.Linear)
        env   = qfpy.MarketEnvironment(curve)

        if mode == 'regular':
            notional   = float(data['notional'])
            fixed_rate = float(data['fixed_rate'])
            maturity   = float(data['maturity'])
            frequency  = float(data.get('frequency', 1.0))
            st = qfpy.SwapType.Payer if data.get('swap_type', 'payer') == 'payer' \
                 else qfpy.SwapType.Receiver

            sw  = qfpy.InterestRateSwap(notional, fixed_rate, maturity, frequency, st)
            npv = sw.npv(env)

            # par rate
            par = qfpy.InterestRateSwap.par_rate(maturity, frequency, env)

            # DV01: bump fixed rate by 1bp and recompute
            sw_bump = qfpy.InterestRateSwap(notional, fixed_rate + 1e-4, maturity, frequency, st)
            dv01 = abs(sw_bump.npv(env) - npv)

            # generate schedule for display
            dt = 1.0 / frequency
            n  = int(round(maturity * frequency))
            schedule = [{'pay_time': round((i + 1) * dt, 6),
                         'accrual_frac': round(dt, 6),
                         'notional': notional} for i in range(n)]

            return jsonify({
                'npv': round(npv, 2),
                'par_rate': round(par * 100, 4),
                'dv01': round(dv01, 2),
                'schedule': schedule,
            })

        elif mode == 'scheduled':
            fixed_rate = float(data['fixed_rate'])
            raw_sched  = data['schedule']
            specs = [qfpy.PeriodSpec(p['pay_time'], p['accrual_frac'], p['notional'])
                     for p in raw_sched]

            fixed_leg = qfpy.ScheduledLeg(fixed_rate, True, specs)
            float_leg = qfpy.ScheduledLeg(0.0, False, specs)

            ssw = qfpy.ScheduledSwap(fixed_leg, float_leg)
            npv = ssw.npv(env)
            cfs = ssw.cash_flows(env)

            return jsonify({
                'npv': round(npv, 2),
                'cash_flows': [{'t': round(t, 4), 'cf': round(cf, 2)} for t, cf in cfs],
            })

        else:
            return jsonify({'error': f'Unknown mode: {mode}'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/yield-curve', methods=['POST'])
def api_yield_curve():
    data = request.json or {}
    try:
        maturities = [float(x) for x in data.get('maturities', [])]
        zero_rates = [float(x) for x in data.get('zeroRates', [])]

        if len(maturities) < 2 or len(maturities) != len(zero_rates):
            return jsonify({'error': 'Need at least 2 matching maturity/rate pairs'}), 400

        interp_map = {
            'Linear': qfpy.InterpolationMethod.Linear,
            'CubicSpline': qfpy.InterpolationMethod.CubicSpline,
            'LogLinear': qfpy.InterpolationMethod.LogLinear,
        }
        interp = interp_map.get(data.get('interpMethod', 'CubicSpline'), qfpy.InterpolationMethod.CubicSpline)

        curve = qfpy.YieldCurve(maturities, zero_rates, interp)

        lo, hi = min(maturities), max(maturities)
        n = 100
        points = []
        for i in range(n + 1):
            t = lo + (hi - lo) * i / n
            if t <= 0:
                t = 0.001
            zr = curve.zero_rate(t)
            df = curve.discount_factor(t)
            # Forward rate: use a small interval around t
            t2 = min(t + 0.25, hi)
            if t2 <= t:
                t2 = t + 0.01
            fr = curve.forward_rate(t, t2)
            points.append({
                't': round(t, 6),
                'zeroRate': round(zr, 8),
                'discountFactor': round(df, 8),
                'forwardRate': round(fr, 8)
            })

        return jsonify({'points': points})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/price-heston', methods=['POST'])
def api_price_heston():
    data = request.json or {}
    try:
        p = qfpy.OptionParams()
        p.spot = float(data.get('spot', 100.0))
        p.strike = float(data.get('strike', 100.0))
        p.riskFreeRate = float(data.get('r', 0.05))
        p.dividendYield = float(data.get('q', 0.0))
        p.volatility = float(data.get('vol', 0.2))
        p.maturity = float(data.get('t', 1.0))
        option_type = data.get('optionType', 'Call')
        p.type = qfpy.OptionType.Put if option_type == 'Put' else qfpy.OptionType.Call
        p.exercise = qfpy.ExerciseType.European

        h = qfpy.HestonParams()
        h.v0 = float(data.get('v0', 0.04))
        h.kappa = float(data.get('kappa', 2.0))
        h.theta = float(data.get('theta', 0.04))
        h.sigma = float(data.get('sigma', 0.3))
        h.rho = float(data.get('rho', -0.7))

        analytical = qfpy.heston_price(p, h)
        mc = qfpy.heston_montecarlo(p, h, nPaths=50000, nSteps=252, seed=123)

        return jsonify({
            'heston_analytical': analytical,
            'heston_mc': mc
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/implied-vol', methods=['POST'])
def api_implied_vol():
    data = request.json or {}
    try:
        p = qfpy.OptionParams()
        p.spot = float(data.get('spot', 100.0))
        p.strike = float(data.get('strike', 100.0))
        p.riskFreeRate = float(data.get('r', 0.05))
        p.dividendYield = float(data.get('q', 0.0))
        p.volatility = 0.5  # initial guess
        p.maturity = float(data.get('t', 1.0))
        option_type = data.get('optionType', 'Call')
        p.type = qfpy.OptionType.Put if option_type == 'Put' else qfpy.OptionType.Call
        p.exercise = qfpy.ExerciseType.European

        market_price = float(data.get('marketPrice', 10.0))
        iv = qfpy.implied_volatility(p, market_price)

        return jsonify({'impliedVol': iv})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, port=5001)
