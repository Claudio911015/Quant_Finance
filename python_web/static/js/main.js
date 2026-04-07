function validate(form) {
  let valid = true;
  form.querySelectorAll('.field').forEach(f => {
    f.classList.remove('field--error');
    const msg = f.querySelector('.error-msg');
    if (msg) msg.textContent = '';
  });

  const checks = [
    { name: 'spot', label: 'Spot', test: v => v > 0, msg: 'Must be > 0' },
    { name: 'strike', label: 'Strike', test: v => v > 0, msg: 'Must be > 0' },
    { name: 'vol', label: 'Volatility', test: v => v > 0 && v <= 5, msg: 'Must be in (0, 5]' },
    { name: 't', label: 'Maturity', test: v => v > 0 && v <= 30, msg: 'Must be in (0, 30]' },
  ];

  checks.forEach(({ name, test, msg }) => {
    const input = form.elements[name];
    const val = Number(input.value);
    if (isNaN(val) || !test(val)) {
      const field = input.closest('.field');
      field.classList.add('field--error');
      const errSpan = field.querySelector('.error-msg');
      if (errSpan) errSpan.textContent = msg;
      valid = false;
    }
  });

  return valid;
}

function setLoading(loading) {
  const btn = document.getElementById('calc-btn');
  const text = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.spinner');
  btn.disabled = loading;
  btn.setAttribute('aria-busy', loading);
  text.textContent = loading ? 'Calculating...' : 'Calculate';
  spinner.hidden = !loading;
}

function showError(message) {
  const banner = document.getElementById('error-banner');
  banner.textContent = message;
  banner.hidden = false;
}

function hideError() {
  document.getElementById('error-banner').hidden = true;
}

function row(tab, name, value, cssClass) {
  const tr = document.createElement('tr');
  const tdn = document.createElement('td');
  tdn.innerText = name;
  const tdv = document.createElement('td');
  tdv.innerText = value;
  if (cssClass) tdv.className = cssClass;
  tr.appendChild(tdn);
  tr.appendChild(tdv);
  tab.appendChild(tr);
}

async function price() {
  const f = document.getElementById('bs-form');

  if (!validate(f)) return;

  hideError();
  setLoading(true);

  const exerciseType = f.exerciseType.value;
  const isAmerican = exerciseType === 'American';

  const payload = {
    spot: Number(f.spot.value),
    strike: Number(f.strike.value),
    r: Number(f.r.value),
    q: Number(f.q.value),
    vol: Number(f.vol.value),
    t: Number(f.t.value),
    optionType: f.optionType.value,
    exerciseType: exerciseType,
    fdMethod: f.fdMethod.value
  };

  const pricesTable = document.querySelector('#prices-table tbody');
  const greeksTable = document.querySelector('#greeks-table tbody');

  pricesTable.innerHTML = '';
  greeksTable.innerHTML = '';

  try {
    const response = await fetch('/api/price', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Server error: ' + response.status);
    }

    if (isAmerican) {
      row(pricesTable, 'Black-Scholes', 'N/A (European only)', 'na-cell');
    } else {
      row(pricesTable, 'Black-Scholes', data.black_scholes.toFixed(6));
    }
    row(pricesTable, 'Binomial', data.binomial.toFixed(6));
    row(pricesTable, 'Monte Carlo', data.montecarlo.toFixed(6));
    row(pricesTable, 'Finite Difference', data.finite_difference.toFixed(6));

    if (isAmerican) {
      row(greeksTable, 'Delta', 'N/A', 'na-cell');
      row(greeksTable, 'Gamma', 'N/A', 'na-cell');
      row(greeksTable, 'Vega', 'N/A', 'na-cell');
      row(greeksTable, 'Theta', 'N/A', 'na-cell');
      row(greeksTable, 'Rho', 'N/A', 'na-cell');
    } else {
      row(greeksTable, 'Delta', data.delta.toFixed(6));
      row(greeksTable, 'Gamma', data.gamma.toFixed(6));
      row(greeksTable, 'Vega', data.vega.toFixed(6));
      row(greeksTable, 'Theta', data.theta.toFixed(6));
      row(greeksTable, 'Rho', data.rho.toFixed(6));
    }

    // Heston pricing if enabled
    const includeHeston = document.getElementById('include-heston');
    if (includeHeston && includeHeston.checked) {
      fetchHeston(payload);
    }

    // Auto-fetch payoff chart after successful calculation
    if (typeof fetchPayoff === 'function') fetchPayoff();

  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
}

async function fetchHeston(basePayload) {
  const hestonPayload = {
    ...basePayload,
    v0: Number(document.getElementById('heston-v0').value),
    kappa: Number(document.getElementById('heston-kappa').value),
    theta: Number(document.getElementById('heston-theta').value),
    sigma: Number(document.getElementById('heston-sigma').value),
    rho: Number(document.getElementById('heston-rho').value)
  };

  try {
    const res = await fetch('/api/price-heston', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(hestonPayload)
    });
    if (!res.ok) return;
    const data = await res.json();

    const pricesTable = document.querySelector('#prices-table tbody');
    row(pricesTable, 'Heston (Analytical)', data.heston_analytical.toFixed(6));
    row(pricesTable, 'Heston (Monte Carlo)', data.heston_mc.toFixed(6));
  } catch (e) { /* silent */ }
}

async function calcImpliedVol() {
  const f = document.getElementById('bs-form');
  const payload = {
    spot: Number(f.spot.value),
    strike: Number(f.strike.value),
    r: Number(f.r.value),
    q: Number(f.q.value),
    t: Number(f.t.value),
    optionType: f.optionType.value,
    marketPrice: Number(document.getElementById('iv-market-price').value)
  };

  const resultEl = document.getElementById('iv-result');
  resultEl.textContent = '...';

  try {
    const res = await fetch('/api/implied-vol', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Error');
    resultEl.textContent = (data.impliedVol * 100).toFixed(2) + '%';
  } catch (e) {
    resultEl.textContent = 'Error';
  }
}
