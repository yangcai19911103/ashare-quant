// ashare-quant Web UI - 共享 JS
// 仅用于演示交互，所有数据均为前端 mock。

// =============================== 侧边栏注入 ===============================
const NAV_ITEMS = [
  { section: '主菜单' },
  { href: 'index.html', label: '总览', icon: 'home' },
  { section: '研究' },
  { href: 'data.html', label: '数据管理', icon: 'database' },
  { href: 'factors.html', label: '因子探索', icon: 'flask' },
  { href: 'strategies.html', label: '策略库', icon: 'layers' },
  { href: 'backtest.html', label: '策略回测', icon: 'play' },
  { href: 'portfolio.html', label: '组合优化', icon: 'pie' },
  { href: 'risk.html', label: '风控配置', icon: 'shield' },
  { section: '交易' },
  { href: 'paper.html', label: '模拟盘', icon: 'flask' },
  { href: 'live.html', label: '实盘交易', icon: 'zap' },
  { href: 'monitor.html', label: '监控大屏', icon: 'monitor' },
  { href: 'reports.html', label: '历史报告', icon: 'file' },
];

const ICONS = {
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12L12 3l9 9"/><path d="M5 10v10h14V10"/></svg>',
  database: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 11v6c0 1.7 4 3 9 3s9-1.3 9-3v-6"/></svg>',
  flask: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 3h6M10 3v6L4 19a2 2 0 002 2h12a2 2 0 002-2L14 9V3"/></svg>',
  layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 22 8 12 14 2 8 12 2"/><polyline points="2 14 12 20 22 14"/><polyline points="2 20 12 26 22 20" transform="translate(0,-6)"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="6 4 20 12 6 20 6 4" fill="currentColor"/></svg>',
  pie: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15A9 9 0 119 3v9z"/><path d="M21 12A9 9 0 0012 3v9z"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l8 4v6c0 5-3.5 9.5-8 10-4.5-.5-8-5-8-10V6z"/></svg>',
  zap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 4 14 12 14 11 22 20 10 12 10 13 2"/></svg>',
  monitor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
};

function renderSidebar(active) {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;
  let html = `
    <div class="sidebar-logo">
      <span class="dot"></span>
      ashare-quant
    </div>
  `;
  for (const it of NAV_ITEMS) {
    if (it.section) {
      html += `<div class="sidebar-section">${it.section}</div>`;
    } else {
      const cls = it.href === active ? 'active' : '';
      html += `<a class="${cls}" href="${it.href}">${ICONS[it.icon] || ''}<span>${it.label}</span></a>`;
    }
  }
  sidebar.innerHTML = html;
}

// =============================== 顶栏 ===============================
function renderTopbar(crumb) {
  const tb = document.querySelector('.topbar');
  if (!tb) return;
  tb.innerHTML = `
    <div class="breadcrumb">${crumb || ''}</div>
    <div class="status">
      <span class="pill"><span class="led"></span>数据已就绪</span>
      <span class="pill"><span class="led"></span>引擎正常</span>
      <span class="pill"><span class="led warn"></span>QMT 未连接</span>
      <span class="muted mono" id="clock"></span>
    </div>
  `;
  const clock = document.getElementById('clock');
  const tick = () => {
    const d = new Date();
    clock.textContent = d.toLocaleString('zh-CN', { hour12: false });
  };
  tick(); setInterval(tick, 1000);
}

// =============================== Toast ===============================
function toast(msg, type = 'info') {
  let c = document.querySelector('.toast-container');
  if (!c) {
    c = document.createElement('div');
    c.className = 'toast-container';
    document.body.appendChild(c);
  }
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

// =============================== 工具 ===============================
function fmt(n, d = 2) {
  if (n === null || n === undefined || isNaN(n)) return '-';
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function pct(n, d = 2) {
  if (n === null || n === undefined || isNaN(n)) return '-';
  return (n * 100).toFixed(d) + '%';
}
function rand(min, max) { return min + Math.random() * (max - min); }
function randn() { let u = 1 - Math.random(), v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

function genPriceSeries(n, s0 = 100, mu = 0.0005, sigma = 0.015, seed = 1) {
  let s = s0; const arr = [];
  for (let i = 0; i < n; i++) { s *= Math.exp(mu + sigma * randn()); arr.push(s); }
  return arr;
}
function genDates(n, end = new Date()) {
  const arr = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(end); d.setDate(d.getDate() - i);
    arr.push(d.toISOString().slice(0, 10));
  }
  return arr;
}

// =============================== Chart 默认配置 ===============================
const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
    tooltip: { backgroundColor: '#0b1220', borderColor: '#1f2a44', borderWidth: 1, titleColor: '#e2e8f0', bodyColor: '#e2e8f0' },
  },
  scales: {
    x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(31,42,68,0.6)' } },
    y: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(31,42,68,0.6)' } },
  },
};

window.AQ = { renderSidebar, renderTopbar, toast, fmt, pct, rand, randn, genPriceSeries, genDates, CHART_DEFAULTS };
