/* Interest Rate Swaps UI */

let currentMode = 'regular';

function setMode(mode) {
  currentMode = mode;
  document.getElementById('section-regular').style.display   = mode === 'regular'   ? '' : 'none';
  document.getElementById('section-scheduled').style.display = mode === 'scheduled' ? '' : 'none';
  document.getElementById('sw-results').style.display = 'none';
  hideSwError();
}

function showSwError(msg) {
  const banner = document.getElementById('sw-error-banner');
  banner.textContent = msg;
  banner.hidden = false;
}

function hideSwError() {
  document.getElementById('sw-error-banner').hidden = true;
}

function setLoading(btn, loading) {
  const text    = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.spinner');
  if (!text || !spinner) return;
  btn.disabled = loading;
  spinner.hidden = !loading;
  if (loading) text.textContent = 'Calculating...';
  else         text.textContent = btn === document.querySelector('#section-scheduled button[onclick="priceScheduled()"]')
    ? 'Price Scheduled Swap' : 'Price Swap';
}

// ── Yield curve helpers ──────────────────────────────────────────────────────

function getCurve(suffix) {
  const tableId = 'curve-table' + (suffix || '');
  const rateClass = '.curve-rate' + (suffix || '');
  const tenorCells = document.querySelectorAll('#' + tableId + ' tbody tr td:first-child');
  const rateCells  = document.querySelectorAll(rateClass);
  const tenors = Array.from(tenorCells).map(td => parseFloat(td.textContent));
  const rates  = Array.from(rateCells).map(inp => parseFloat(inp.value) / 100);
  return { curve_tenors: tenors, curve_rates: rates };
}

// ── Formatting ───────────────────────────────────────────────────────────────

function formatCurrency(val) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: 0, maximumFractionDigits: 0
  }).format(val);
}

// ── Results rendering ────────────────────────────────────────────────────────

function showResults(data) {
  document.getElementById('res-npv').textContent  =
    data.npv !== undefined ? formatCurrency(data.npv) : '—';
  document.getElementById('res-par').textContent  =
    data.par_rate !== undefined ? data.par_rate.toFixed(4) + '%' : '—';
  document.getElementById('res-dv01').textContent =
    data.dv01 !== undefined ? formatCurrency(data.dv01) : '—';

  const schedule = data.schedule || [];
  const tbody = document.getElementById('res-schedule-body');
  tbody.innerHTML = schedule.map(p =>
    `<tr>
       <td>${p.pay_time.toFixed(4)}</td>
       <td>${p.accrual_frac !== undefined ? p.accrual_frac.toFixed(4) : '—'}</td>
       <td>${formatCurrency(p.notional)}</td>
     </tr>`
  ).join('');

  // Cash flow bar chart
  const cfs = data.cash_flows || schedule.map(p => ({ t: p.pay_time, cf: 0 }));
  const colors = cfs.map(d => d.cf >= 0 ? '#36c0d8' : '#ff6b6b');

  Plotly.react('cashflow-chart', [{
    type: 'bar',
    x: cfs.map(d => d.t),
    y: cfs.map(d => d.cf),
    marker: { color: colors },
    name: 'Net Cash Flow',
    hovertemplate: 'T=%{x:.2f}Y<br>CF=%{y:,.0f}<extra></extra>'
  }], {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor:  'rgba(8,28,36,0.8)',
    font: { color: '#f6fcff', family: 'Inter, sans-serif', size: 12 },
    margin: { t: 30, r: 40, b: 50, l: 70 },
    xaxis: { title: 'Time (years)', gridcolor: 'rgba(27,59,69,0.8)' },
    yaxis: { title: 'Net Cash Flow (USD)', gridcolor: 'rgba(27,59,69,0.8)' },
    bargap: 0.3
  }, { responsive: true, displayModeBar: false });

  document.getElementById('sw-results').style.display = '';
}

// ── Regular mode ─────────────────────────────────────────────────────────────

async function priceRegular() {
  hideSwError();
  const btn = document.querySelector('#section-regular button[onclick="priceRegular()"]');
  setLoading(btn, true);

  const curve = getCurve('');
  if (curve.curve_tenors.length < 2) {
    showSwError('Need at least 2 yield curve points.');
    setLoading(btn, false);
    return;
  }

  const body = {
    mode:       'regular',
    notional:   parseFloat(document.getElementById('sw-notional').value),
    fixed_rate: parseFloat(document.getElementById('sw-fixed-rate').value) / 100,
    maturity:   parseFloat(document.getElementById('sw-maturity').value),
    frequency:  parseFloat(document.getElementById('sw-frequency').value),
    swap_type:  document.getElementById('sw-type').value,
    ...curve
  };

  try {
    const resp = await fetch('/api/swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      showSwError(data.error || 'Server error');
      return;
    }
    showResults(data);
  } catch (e) {
    showSwError('Request failed: ' + e.message);
  } finally {
    setLoading(btn, false);
  }
}

// ── Scheduled mode ────────────────────────────────────────────────────────────

function generateSchedule() {
  const notional = parseFloat(document.getElementById('sched-notional').value);
  const firstPay = parseFloat(document.getElementById('sched-first-pay').value);
  const freq     = parseFloat(document.getElementById('sched-freq').value);
  const maturity = parseFloat(document.getElementById('sched-maturity').value);
  const dt       = 1.0 / freq;

  const times = [firstPay];
  let t = firstPay + dt;
  while (t <= maturity + 1e-9) {
    times.push(parseFloat(t.toFixed(6)));
    t += dt;
  }

  const tbody = document.getElementById('sched-body');
  let prev = 0;
  tbody.innerHTML = times.map(pt => {
    const tau = parseFloat((pt - prev).toFixed(6));
    prev = pt;
    return `<tr>
      <td><input type="number" class="sched-pay-time"  value="${pt}"        step="0.25"></td>
      <td><input type="number" class="sched-accr-frac" value="${tau}"       step="0.01"></td>
      <td><input type="number" class="sched-notional"  value="${notional}"  step="100000"></td>
    </tr>`;
  }).join('');
}

function addScheduleRow() {
  const tbody = document.getElementById('sched-body');
  const rows  = tbody.querySelectorAll('tr');
  const lastT = rows.length
    ? parseFloat(rows[rows.length - 1].querySelector('.sched-pay-time').value)
    : 0;
  const row = document.createElement('tr');
  row.innerHTML = `
    <td><input type="number" class="sched-pay-time"  value="${(lastT + 1).toFixed(2)}" step="0.25"></td>
    <td><input type="number" class="sched-accr-frac" value="1.0"     step="0.01"></td>
    <td><input type="number" class="sched-notional"  value="1000000" step="100000"></td>`;
  tbody.appendChild(row);
}

async function priceScheduled() {
  hideSwError();
  const btn = document.querySelector('#section-scheduled button[onclick="priceScheduled()"]');
  setLoading(btn, true);

  const rows = document.querySelectorAll('#sched-body tr');
  if (!rows.length) {
    showSwError('Generate or add schedule rows first.');
    setLoading(btn, false);
    return;
  }

  const fixedRate = parseFloat(document.getElementById('sched-fixed-rate').value) / 100;
  const schedule  = Array.from(rows).map(r => ({
    pay_time:     parseFloat(r.querySelector('.sched-pay-time').value),
    accrual_frac: parseFloat(r.querySelector('.sched-accr-frac').value),
    notional:     parseFloat(r.querySelector('.sched-notional').value),
  }));

  const curve = getCurve('-s');
  if (curve.curve_tenors.length < 2) {
    showSwError('Need at least 2 yield curve points.');
    setLoading(btn, false);
    return;
  }

  const body = {
    mode:       'scheduled',
    fixed_rate: fixedRate,
    schedule,
    ...curve
  };

  try {
    const resp = await fetch('/api/swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      showSwError(data.error || 'Server error');
      return;
    }
    // Attach schedule for table display if backend doesn't echo it back
    if (!data.schedule) data.schedule = schedule;
    showResults(data);
  } catch (e) {
    showSwError('Request failed: ' + e.message);
  } finally {
    setLoading(btn, false);
  }
}
