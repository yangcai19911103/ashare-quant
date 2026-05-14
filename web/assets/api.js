// ashare-quant 前端 API 客户端
// 统一封装 fetch，处理 base URL、错误、loading 状态。

(function () {
  const DEFAULT_BASE = (function () {
    // 1) 如果挂在 FastAPI 静态站点下 (/web/*)，同源用空 baseURL
    // 2) 否则猜测后端在 localhost:8000
    if (window.location.pathname.startsWith('/web')) return '';
    if (window.location.port && window.location.port !== '8000') {
      return 'http://' + window.location.hostname + ':8000';
    }
    return '';
  })();

  const BASE = window.AQ_API_BASE || DEFAULT_BASE;

  async function request(path, opts = {}) {
    const url = BASE + path;
    const init = {
      method: opts.method || 'GET',
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    };
    if (opts.body !== undefined) init.body = JSON.stringify(opts.body);
    if (opts.params) {
      const qs = new URLSearchParams(opts.params).toString();
      if (qs) {
        return fetch(url + (url.includes('?') ? '&' : '?') + qs, init).then(handleResp);
      }
    }
    return fetch(url, init).then(handleResp);
  }

  async function handleResp(r) {
    if (!r.ok) {
      let detail = r.statusText;
      try { const j = await r.json(); detail = j.detail || JSON.stringify(j); } catch (_) {}
      const err = new Error(`HTTP ${r.status}: ${detail}`);
      err.status = r.status;
      throw err;
    }
    const ct = r.headers.get('content-type') || '';
    return ct.includes('application/json') ? r.json() : r.text();
  }

  const API = {
    base: BASE,

    // ========== Overview ==========
    overview: () => request('/api/overview/'),

    // ========== Data ==========
    data: {
      sources:   ()       => request('/api/data/sources'),
      warehouse: ()       => request('/api/data/warehouse'),
      init:      (body)   => request('/api/data/init', { method: 'POST', body }),
      job:       (id)     => request('/api/data/jobs/' + id),
      jobs:      ()       => request('/api/data/jobs'),
      calendar:  (params) => request('/api/data/calendar', { params }),
      universe:  (body)   => request('/api/data/universe', { method: 'POST', body }),
      query:     (sql)    => request('/api/data/query', { method: 'POST', body: { sql } }),
    },

    // ========== Factors ==========
    factors: {
      list:     ()         => request('/api/factors/'),
      registry: ()         => request('/api/factors/registry'),
      compute:  (body)     => request('/api/factors/compute', { method: 'POST', body }),
    },

    // ========== Strategies ==========
    strategies: {
      list: (category)    => request('/api/strategies/', { params: category ? { category } : {} }),
      get:  (name)        => request('/api/strategies/' + encodeURIComponent(name)),
    },

    // ========== Backtest ==========
    backtest: {
      run:     (body)  => request('/api/backtest/run', { method: 'POST', body }),
      status:  (id)    => request('/api/backtest/status/' + id),
      result:  (id)    => request('/api/backtest/result/' + id),
      runs:    ()      => request('/api/backtest/runs'),
    },

    // ========== Risk ==========
    risk: {
      getConfig:   ()        => request('/api/risk/config'),
      saveConfig:  (body)    => request('/api/risk/config', { method: 'POST', body }),
      alerts:      ()        => request('/api/risk/alerts'),
      resolve:     (id)      => request('/api/risk/alerts/' + id + '/resolve', { method: 'POST' }),
      channels:    ()        => request('/api/risk/channels'),
      testChannel: (n)       => request('/api/risk/channels/' + encodeURIComponent(n) + '/test', { method: 'POST' }),
      drawdown:    ()        => request('/api/risk/drawdown'),
      attribution: ()        => request('/api/risk/attribution'),
      halt:        ()        => request('/api/risk/halt', { method: 'POST' }),
    },

    // ========== Portfolio ==========
    portfolio: {
      optimize: (body)    => request('/api/portfolio/optimize', { method: 'POST', body }),
    },

    // ========== Paper ==========
    paper: {
      start:        (body)  => request('/api/paper/start', { method: 'POST', body }),
      stop:         ()      => request('/api/paper/stop', { method: 'POST' }),
      account:      ()      => request('/api/paper/account'),
      positions:    ()      => request('/api/paper/positions'),
      orders:       ()      => request('/api/paper/orders'),
      fills:        ()      => request('/api/paper/fills'),
      nav:          ()      => request('/api/paper/nav'),
      order:        (body)  => request('/api/paper/order', { method: 'POST', body }),
      closePos:     (sym)   => request('/api/paper/positions/' + encodeURIComponent(sym) + '/close', { method: 'POST' }),
    },

    // ========== Live ==========
    live: {
      status:       ()      => request('/api/live/status'),
      connect:      (body)  => request('/api/live/qmt/connect', { method: 'POST', body }),
      disconnect:   ()      => request('/api/live/qmt/disconnect', { method: 'POST' }),
      account:      ()      => request('/api/live/account'),
      deployments:  ()      => request('/api/live/deployments'),
      deploy:       (st, ac)=> request('/api/live/deployments/' + encodeURIComponent(st) + '/' + ac, { method: 'POST' }),
      order:        (body)  => request('/api/live/order', { method: 'POST', body }),
      approvals:    ()      => request('/api/live/approvals'),
      approve:      (id)    => request('/api/live/approvals/' + id + '/approve', { method: 'POST' }),
      reject:       (id)    => request('/api/live/approvals/' + id + '/reject', { method: 'POST' }),
      estimate:     (body)  => request('/api/live/estimate', { method: 'POST', body }),
    },

    // ========== Monitor ==========
    monitor: {
      snapshot:  ()         => request('/api/monitor/snapshot'),
      system:    ()         => request('/api/monitor/system'),
      tickStream: (onTick) => {
        const url = BASE + '/api/monitor/ticks/stream';
        const es = new EventSource(url);
        es.onmessage = (e) => {
          try { onTick(JSON.parse(e.data)); } catch (_) {}
        };
        return es;
      },
    },

    // ========== Reports ==========
    reports: {
      list:    (params)     => request('/api/reports/', { params }),
      get:     (id)         => request('/api/reports/' + id),
      compare: (ids)        => request('/api/reports/compare', { params: { ids: ids.join(',') } }),
    },
  };

  window.API = API;
})();
