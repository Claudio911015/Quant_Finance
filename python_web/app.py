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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quant Finance Dashboard</title>
    <style>
      :root {
        --bg: #081c24;
        --card: #123139;
        --card2: #1b3b45;
        --accent: #36c0d8;
        --accent-2: #64e2f0;
        --text: #f6fcff;
        --muted: #8cb9c4;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: linear-gradient(145deg, #02121a, #0e2e3c);
        color: var(--text);
      }
      .container {
        max-width: 980px;
        margin: 24px auto;
        padding: 1rem;
      }
      header {
        text-align: center;
        margin-bottom: 1rem;
      }
      header h1 { margin: .2rem 0; font-size: 2.1rem; }
      header p { color: var(--muted); }
      .panel {
        background: var(--card);
        border: 1px solid rgba(98, 175, 190, 0.2);
        border-radius: 14px;
        padding: 18px;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 12px;
      }
      .field {
        display: flex;
        flex-direction: column;
        margin-bottom: 8px;
      }
      .field label {
        font-size: 0.9rem;
        color: var(--muted);
        margin-bottom: 4px;
      }
      .field input {
        border: 1px solid rgba(150, 207, 219, 0.35);
        border-radius: 8px;
        background: var(--card2);
        color: var(--text);
        padding: 8px 10px;
      }
      button {
        display: inline-flex;
        background: linear-gradient(120deg, var(--accent), var(--accent-2));
        border: 0;
        border-radius: 10px;
        color: #082d33;
        font-weight: 700;
        padding: 11px 20px;
        cursor: pointer;
        transition: transform .15s ease, filter .15s ease;
        margin-top: 0.6rem;
      }
      button:hover { transform: translateY(-2px); filter: brightness(1.08); }
      .resultado {
        margin-top: 18px;
        padding: 16px;
        white-space: pre-wrap;
        background: #021a26;
        border-radius: 10px;
        border: 1px dashed rgba(54, 192, 216, 0.35);
        min-height: 12.5rem;
        overflow-x: auto;
        color: #d3eff6;
      }
      .foot {
        text-align: center;
        color: var(--muted);
        margin-top: 14px;
        font-size: 0.87rem;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <header>
        <h1>Quant Finance Dashboard</h1>
        <p>Interfaz web para probar precios de opciones con modelos C++</p>
      </header>
      <div class="panel">
        <form id="bs-form">
          <div class="grid">
            <div class="field"><label>Spot</label><input type="number" step="any" name="spot" value="100"></div>
            <div class="field"><label>Strike</label><input type="number" step="any" name="strike" value="100"></div>
            <div class="field"><label>Rate</label><input type="number" step="any" name="r" value="0.05"></div>
            <div class="field"><label>Dividend</label><input type="number" step="any" name="q" value="0.0"></div>
            <div class="field"><label>Volatility</label><input type="number" step="any" name="vol" value="0.2"></div>
            <div class="field"><label>Maturity</label><input type="number" step="any" name="t" value="1.0"></div>
          </div>
          <button type="button" onclick="price()">Calcular precio</button>
        </form>
        <div class="resultado" id="result">
          <div class="result-grid">
            <div>
              <h3>Precios por modelo</h3>
              <table id="prices-table" class="result-table">
                <thead><tr><th>Modelo</th><th>Precio</th></tr></thead>
                <tbody></tbody>
              </table>
            </div>
            <div>
              <h3>Griegas (Black-Scholes)</h3>
              <table id="greeks-table" class="result-table">
                <thead><tr><th>Griega</th><th>Valor</th></tr></thead>
                <tbody></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
      <div class="foot">Los valores se calculan en C++ a través de qfpy; actualiza la página para volver a cargar.</div>
    </div>
    <script>
      async function price(){
        const f = document.getElementById('bs-form');
        const payload = {
          spot: Number(f.spot.value),
          strike: Number(f.strike.value),
          r: Number(f.r.value),
          q: Number(f.q.value),
          vol: Number(f.vol.value),
          t: Number(f.t.value)
        };
        const resultEl = document.getElementById('result');
        resultEl.innerText = 'Calculando...';
        try {
          const response = await fetch('/api/price', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload)
          });
          if (!response.ok) throw new Error('Error del servidor: ' + response.status);
          const data = await response.json();
          resultEl.innerText = JSON.stringify(data, null, 2);
        } catch(e) {
          resultEl.innerText = 'Error: ' + e.message;
        }
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
