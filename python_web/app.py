from flask import Flask, render_template_string, request, jsonify
import os, sys

# Ensure qfpy built extension is importable:
build_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'build'))
build_src = os.path.join(build_root, 'src')
for p in (build_src, build_root):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import qfpy
except ModuleNotFoundError:
    raise ModuleNotFoundError('qfpy module not found. Run cmake --build build --target qfpy first.')

app = Flask(__name__)

HTML = '''
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Quant Finance Browser</title>
    <style>
      body {font-family: Arial, sans-serif; margin: 40px;}
      label {display:block; margin-top:8px;}
      input {width:120px;}
      button {margin-top:12px;}
      pre {background:#f6f6f6; padding:12px;}
    </style>
  </head>
  <body>
    <h1>Quant Finance Quick UI</h1>
    <form id="bs-form">
      <label>Spot <input type="number" step="any" name="spot" value="100"></label>
      <label>Strike <input type="number" step="any" name="strike" value="100"></label>
      <label>Rate <input type="number" step="any" name="r" value="0.05"></label>
      <label>Dividend <input type="number" step="any" name="q" value="0.0"></label>
      <label>Volatility <input type="number" step="any" name="vol" value="0.2"></label>
      <label>Maturity <input type="number" step="any" name="t" value="1.0"></label>
      <button type="button" onclick="price()">Compute</button>
    </form>
    <pre id="result"></pre>
    <script>
      function price(){
        const f = document.getElementById('bs-form');
        const data = {spot: Number(f.spot.value), strike: Number(f.strike.value), r: Number(f.r.value), q: Number(f.q.value), vol: Number(f.vol.value), t: Number(f.t.value)};
        fetch('/api/price', {
          method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)
        }).then(r=>r.json()).then(d=>document.getElementById('result').innerText = JSON.stringify(d,null,2));
      }
    </script>
  </body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/price', methods=['POST'])
def api_price():
    data = request.json
    p = qfpy.OptionParams()
    p.spot = data.get('spot', 100.0)
    p.strike = data.get('strike', 100.0)
    p.riskFreeRate = data.get('r', 0.05)
    p.dividendYield = data.get('q', 0.0)
    p.volatility = data.get('vol', 0.2)
    p.maturity = data.get('t', 1.0)
    p.type = qfpy.OptionType.Call
    p.exercise = qfpy.ExerciseType.European

    bs = qfpy.black_scholes(p)
    bt = qfpy.binomial_tree_price(p, 1000)
    mc = qfpy.montecarlo_price(p, 200000, seed=123)
    fd = qfpy.finite_difference_price(p, nS=200, nT=200, method=qfpy.FDMethod.CrankNicolson)

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
