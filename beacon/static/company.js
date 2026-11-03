(function () {
  'use strict';

  const F = window.Beacon;
  const { $, esc } = F;

  F.pages.company = async function () {
    const r = await F.api('/api/company');
    if (!r.ok) return F.toast(r.data.error || 'Could not load the company tickets.', 'error');
    const d = r.data;
    $('#co-title').textContent = `${d.company} tickets`;
    $('#co-open').textContent = d.open;
    $('#co-waiting').textContent = d.waiting;
    $('#co-solved').textContent = d.solved_month;
    $('#co-rows').innerHTML = d.tickets.map((t) => `<tr data-id="${t.id}"><td><a href="/ticket?id=${t.id}">#${t.id}</a></td>
        <td class="subject"><a href="/ticket?id=${t.id}">${esc(t.subject)}</a></td><td>${esc(t.requester)}</td>
        <td>${F.status(t.status)}</td><td>${F.prio(t.priority)}</td><td>${F.when(t.updated, t.offset)}</td></tr>`).join('');
  };
})();
