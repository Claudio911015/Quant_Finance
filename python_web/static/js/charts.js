// Tab switching
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
  });
});

const plotlyLayout = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(8,28,36,0.8)',
  font: { color: '#f6fcff', family: 'Inter, sans-serif', size: 12 },
  margin: { t: 30, r: 20, b: 50, l: 60 },
  xaxis: { gridcolor: 'rgba(27,59,69,0.8)', zerolinecolor: 'rgba(54,192,216,0.3)' },
  yaxis: { gridcolor: 'rgba(27,59,69,0.8)', zerolinecolor: 'rgba(54,192,216,0.3)' },
};

const plotlyConfig = { responsive: true, displayModeBar: false };

function getFormPayload() {
  const f = document.getElementById('bs-form');
  return {
    spot: Number(f.spot.value),
    strike: Number(f.strike.value),
    r: Number(f.r.value),
    q: Number(f.q.value),
    vol: Number(f.vol.value),
    t: Number(f.t.value),
    optionType: f.optionType.value,
    exerciseType: f.exerciseType.value,
    fdMethod: f.fdMethod.value
  };
}

async function fetchPayoff() {
  try {
    const res = await fetch('/api/payoff', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(getFormPayload())
    });
    if (!res.ok) return;
    const data = await res.json();
    renderPayoffChart(data);
  } catch (e) { /* silent */ }
}

function renderPayoffChart(data) {
  const spots = data.map(d => d.spot);
  const traces = [
    {
      x: spots, y: data.map(d => d.payoff),
      name: 'Payoff at Expiry',
      line: { color: '#36c0d8', width: 2 }
    },
    {
      x: spots, y: data.map(d => d.profit),
      name: 'Profit (incl. premium)',
      line: { color: '#64e2f0', width: 2, dash: 'dash' },
      fill: 'tozeroy',
      fillcolor: 'rgba(100,226,240,0.08)'
    },
    {
      x: [spots[0], spots[spots.length - 1]], y: [0, 0],
      name: 'Break-even',
      line: { color: 'rgba(255,107,107,0.5)', width: 1, dash: 'dot' },
      showlegend: false
    }
  ];

  const layout = {
    ...plotlyLayout,
    xaxis: { ...plotlyLayout.xaxis, title: 'Spot Price' },
    yaxis: { ...plotlyLayout.yaxis, title: 'P&L' },
    legend: { x: 0.02, y: 0.98, bgcolor: 'rgba(0,0,0,0)' }
  };

  Plotly.newPlot('chart-payoff', traces, layout, plotlyConfig);
}

async function fetchGreeksSurface() {
  const greek = document.getElementById('greek-select').value;
  const variable = document.getElementById('variable-select').value;
  const payload = { ...getFormPayload(), greek, variable };

  try {
    const res = await fetch('/api/greeks-surface', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) return;
    const data = await res.json();
    renderGreeksChart(data, greek, variable);
  } catch (e) { /* silent */ }
}

function renderGreeksChart(data, greek, variable) {
  const varLabels = { spot: 'Spot Price', vol: 'Volatility', maturity: 'Maturity (years)' };
  const traces = [{
    x: data.map(d => d.x),
    y: data.map(d => d.y),
    line: { color: '#36c0d8', width: 2 },
    name: greek.charAt(0).toUpperCase() + greek.slice(1)
  }];

  const layout = {
    ...plotlyLayout,
    xaxis: { ...plotlyLayout.xaxis, title: varLabels[variable] || variable },
    yaxis: { ...plotlyLayout.yaxis, title: greek.charAt(0).toUpperCase() + greek.slice(1) }
  };

  Plotly.newPlot('chart-greeks', traces, layout, plotlyConfig);
}

async function fetchConvergence() {
  try {
    const res = await fetch('/api/model-convergence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(getFormPayload())
    });
    if (!res.ok) return;
    const data = await res.json();
    renderConvergenceChart(data);
  } catch (e) { /* silent */ }
}

function renderConvergenceChart(data) {
  const traces = [
    {
      x: data.binomial.map(d => d.x), y: data.binomial.map(d => d.y),
      name: 'Binomial Tree (steps)',
      line: { color: '#36c0d8', width: 2 }
    },
    {
      x: data.montecarlo.map(d => d.x), y: data.montecarlo.map(d => d.y),
      name: 'Monte Carlo (paths)',
      line: { color: '#64e2f0', width: 2 }
    },
    {
      x: data.fd.map(d => d.x), y: data.fd.map(d => d.y),
      name: 'Finite Difference (grid)',
      line: { color: '#8cb9c4', width: 2 }
    },
    {
      x: [data.binomial[0].x, data.binomial[data.binomial.length - 1].x],
      y: [data.bs_reference, data.bs_reference],
      name: 'BS Analytical',
      line: { color: '#ff6b6b', width: 1.5, dash: 'dash' }
    }
  ];

  const layout = {
    ...plotlyLayout,
    xaxis: { ...plotlyLayout.xaxis, title: 'Parameter (steps / paths / grid points)' },
    yaxis: { ...plotlyLayout.yaxis, title: 'Price' },
    legend: { x: 0.02, y: 0.98, bgcolor: 'rgba(0,0,0,0)' }
  };

  Plotly.newPlot('chart-convergence', traces, layout, plotlyConfig);
}
