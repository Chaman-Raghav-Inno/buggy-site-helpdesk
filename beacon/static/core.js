(function () {
  'use strict';

  const F = (window.Beacon = window.Beacon || {});
  F.pages = F.pages || {};
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  F.$ = $;
  F.$$ = $$;
  F.esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ENTITIES[c]);
  F.params = new URLSearchParams(location.search);
  F.role = document.body.dataset.role || '';
  F.EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  document.addEventListener('submit', (e) => {
    if (!e.target.matches('[data-native]')) e.preventDefault();
  }, true);

  F.api = async function (path, body) {
    const opts = body === undefined
      ? { credentials: 'same-origin' }
      : { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    let res;
    try {
      res = await fetch(path, opts);
    } catch (e) {
      return { ok: false, status: 0, data: { error: 'You appear to be offline. Try again.' } };
    }
    if (res.status === 401 && !path.startsWith('/api/login')) {
      location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search);
    }
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      data = {};
    }
    return { ok: res.ok, status: res.status, data };
  };

  let toastTimer;
  F.toast = function (text, kind) {
    const el = $('#toast');
    el.textContent = text;
    el.className = 'toast' + (kind ? ' toast-' + kind : '');
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
  };
  F.say = function (el, text, kind) {
    el.textContent = text || '';
    el.classList.toggle('error', kind === 'error');
    el.classList.toggle('success', kind === 'success');
  };
  F.plural = (n, word, many) => `${n} ${n === 1 ? word : many || word + 's'}`;
  const DAY_FMT = { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' };
  F.day = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', DAY_FMT);
  F.date = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  // Moments are stored in UTC; each company has a fixed offset from UTC.
  const shift = (iso, offset) => new Date(Date.parse(iso) + offset * 3600000);
  F.when = (iso, offset) => {
    const d = shift(iso, offset);
    return `${d.toLocaleDateString('en-GB', DAY_FMT)}, ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })}`;
  };
  F.tz = (name, offset) => `${name} time (UTC${offset >= 0 ? '+' : '−'}${Math.abs(offset)})`;
  F.dur = (mins) => {
    const m = Math.max(0, Math.round(mins));
    const h = Math.floor(m / 60);
    return h ? `${h}h ${String(m % 60).padStart(2, '0')}m` : `${m}m`;
  };
  F.bytes = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
  const CUSTOMER = { new: 'Open', open: 'Open', pending: 'Waiting on you', solved: 'Solved', closed: 'Closed' };
  const AGENT = { new: 'New', open: 'Open', pending: 'Waiting on customer', solved: 'Solved', closed: 'Closed' };
  F.status = (s, agent) => `<span class="pill pill-${F.esc(s)}">${F.esc((agent ? AGENT : CUSTOMER)[s] || s)}</span>`;
  F.statusName = (s, agent) => (agent ? AGENT : CUSTOMER)[s] || s;
  F.cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : '');
  F.prio = (p) => `<span class="prio prio-${F.esc(p)}">${F.esc(F.cap(p))}</span>`;
  F.paras = (text) => F.esc(text).split(/\n{2,}/).map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');

  function setupChrome() {
    const page = document.body.dataset.page;
    $$('.nav a').forEach((a) => { if (a.dataset.nav === page) a.setAttribute('aria-current', 'page'); });
    const logout = $('#logout');
    if (logout) {
      logout.addEventListener('click', async () => {
        await F.api('/api/logout', {});
        location.href = '/';
      });
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    setupChrome();
    const run = F.pages[document.body.dataset.page];
    if (!run) return;
    document.body.classList.add('is-loading');
    try {
      await run();
    } finally {
      document.body.classList.remove('is-loading');
    }
  });
})();
