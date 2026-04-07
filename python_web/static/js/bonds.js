function addRow() {
  const tbody = document.querySelector('#curve-table tbody');
  const tr = document.createElement('tr');
  tr.innerHTML = '<td><input type="number" step="any" class="curve-mat" value=""></td>' +
    '<td><input type="number" step="any" class="curve-rate" value=""></td>' +
    '<td><button type="button" class="btn-remove" onclick="removeRow(this)">×</button></td>';
  tbody.appendChild(tr);
}

function removeRow(btn) {
  const tbody = document.querySelector('#curve-table tbody');
  if (tbody.rows.length > 2) {
    btn.closest('tr').remove();
  }
}

function getCurveData() {
  const mats = [], rates = [];
  document.querySelectorAll('#curve-table tbody tr').forEach(tr => {
    const m = Number(tr.querySelector('.curve-mat').value);
    const r = Number(tr.querySelector('.curve-rate').value);
    if (!isNaN(m) && !isNaN(r) && m > 0) {
      mats.push(m);
      rates.push(r);
    }
  });
  return { maturities: mats, zeroRates: rates };
}

function setLoading(loading) {
  const btn = document.getElementById('bond-calc-btn');
  const text = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.spinner');
  btn.disabled = loading;
  text.textContent = loading ? 'Calculating...' : 'Calculate';
  spinner.hidden = !loading;
}

function showError(msg) {
  const banner = document.getElementById('error-banner');
  banner.textContent = msg;
  banner.hidden = false;
}

function hideError() {
  document.getElementById('error-banner').hidden = true;
}

async function calcBond() {
  hideError();
  setLoading(true);

  const f = document.getElementById('bond-form');
  const curve = getCurveData();

  if (curve.maturities.length < 2) {
    showError('Need at least 2 yield curve points');
    setLoading(false);
    return;
  }

  const payload = {
    faceValue: Number(f.faceValue.value),
    couponRate: Number(f.couponRate.value),
    periods: Number(f.periods.value),
    frequency: Number(f.frequency.value),
    maturities: curve.maturities,
    zeroRates: curve.zeroRates,
    interpMethod: f.interpMethod.value
  };

  try {
    const res = await fetch('/api/bond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Server error');

    document.getElementById('bond-price').textContent = data.price.toFixed(4);
    document.getElementById('bond-duration').textContent = data.duration.toFixed(4);
    document.getElementById('bond-convexity').textContent = data.convexity.toFixed(4);

    // Fetch and plot yield curve
    fetchYieldCurve(payload);
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
}

async function fetchYieldCurve(payload) {
  try {
    const res = await fetch('/api/yield-curve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) return;
    const data = await res.json();
    renderYieldCurve(data.points);
  } catch (e) { /* silent */ }
}

function renderYieldCurve(points) {
  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(8,28,36,0.8)',
    font: { color: '#f6fcff', family: 'Inter, sans-serif', size: 12 },
    margin: { t: 30, r: 60, b: 50, l: 60 },
    xaxis: { title: 'Maturity (years)', gridcolor: 'rgba(27,59,69,0.8)' },
    yaxis: { title: 'Rate / Factor', gridcolor: 'rgba(27,59,69,0.8)' },
    legend: { x: 0.02, y: 0.98, bgcolor: 'rgba(0,0,0,0)' }
  };

  const ts = points.map(p => p.t);
  const traces = [
    {
      x: ts, y: points.map(p => p.zeroRate),
      name: 'Zero Rate', line: { color: '#36c0d8', width: 2 }
    },
    {
      x: ts, y: points.map(p => p.forwardRate),
      name: 'Forward Rate', line: { color: '#64e2f0', width: 2, dash: 'dash' }
    },
    {
      x: ts, y: points.map(p => p.discountFactor),
      name: 'Discount Factor', line: { color: '#8cb9c4', width: 2 },
      yaxis: 'y2'
    }
  ];

  layout.yaxis2 = {
    title: 'Discount Factor',
    overlaying: 'y', side: 'right',
    gridcolor: 'rgba(27,59,69,0.4)'
  };

  Plotly.newPlot('chart-yield-curve', traces, layout, { responsive: true, displayModeBar: false });
}
