(function () {
  'use strict';

  const F = window.Beacon;
  const { $, $$, esc } = F;

  F.pages.tickets = async function () {
    let tab = 'open';
    let page = 1;
    let seq = 0;

    async function load() {
      const mine = ++seq;
      const q = new URLSearchParams({ tab, q: $('#tk-q').value.trim(), sort: $('#tk-sort').value, page });
      const r = await F.api('/api/tickets?' + q.toString());
      if (mine !== seq) return;
      if (!r.ok) return F.toast(r.data.error || 'Could not load your tickets.', 'error');
      const d = r.data;
      $$('[data-count]').forEach((el) => { el.textContent = `(${d.counts[el.dataset.count]})`; });
      $$('#tk-tabs [role="tab"]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
      $('#tk-count').textContent = F.plural(d.count, 'ticket');
      $('#tk-rows').innerHTML = d.tickets.map((t) => `<tr data-id="${t.id}"><td><a href="/ticket?id=${t.id}">#${t.id}</a></td>
          <td class="subject"><a href="/ticket?id=${t.id}">${esc(t.subject)}</a><br><span class="muted small">${esc(F.cap(t.category))}</span></td>
          <td>${F.status(t.status)}</td><td>${F.prio(t.priority)}</td><td>${F.when(t.updated, t.offset)}</td></tr>`).join('')
        || '<tr><td colspan="5" class="muted">No tickets here.</td></tr>';
      $('#tk-page').textContent = `Page ${d.page} of ${d.pages}`;
      $('#tk-prev').disabled = d.page <= 1;
      $('#tk-next').disabled = d.page >= d.pages;
    }

    $$('#tk-tabs [role="tab"]').forEach((b) => b.addEventListener('click', () => { tab = b.dataset.tab; page = 1; load(); }));
    let timer;
    $('#tk-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 250); });
    $('#tk-filters').addEventListener('submit', () => { clearTimeout(timer); page = 1; load(); });
    $('#tk-sort').addEventListener('change', () => { page = 1; load(); });
    $('#tk-prev').addEventListener('click', () => { page -= 1; load(); });
    $('#tk-next').addEventListener('click', () => { page += 1; load(); });
    await load();
  };
})();
