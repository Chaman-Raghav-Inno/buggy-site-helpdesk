(function () {
  'use strict';

  const F = window.Beacon;
  const { $, $$, esc } = F;

  F.sla = function (s, which) {
    const state = which === 'first' ? s.first_state : s.res_state;
    const left = which === 'first' ? s.first_target - s.first_elapsed : s.res_target - s.res_elapsed;
    if (state === 'met') return '<span class="sla sla-met">Met</span>';
    if (state === 'breached') return '<span class="sla sla-breached">Breached</span>';
    if (state === 'paused') return '<span class="sla sla-paused">Paused</span>';
    if (state === 'none') return '<span class="muted">–</span>';
    return `<span class="sla sla-running">${F.dur(left)} left</span>`;
  };

  F.pages.queue = async function () {
    let data;
    let view = 'open';
    const selected = new Set();

    function draw() {
      $('#qu-clock').textContent = `Desk clock: ${F.when(data.now, data.home_offset)} (Dubai)`;
      $$('[data-count]').forEach((el) => { el.textContent = `(${data.counts[el.dataset.count]})`; });
      $$('#qu-tabs [role="tab"]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.view === view)));
      const rows = data.tickets.filter((t) => t.views.includes(view));
      $('#qu-rows').innerHTML = rows.map((t) => `<tr data-id="${t.id}">
          <td><input type="checkbox" data-pick="${t.id}" aria-label="Select #${t.id}"${selected.has(t.id) ? ' checked' : ''}></td>
          <td><a href="/work?id=${t.id}">#${t.id}</a></td>
          <td class="subject"><a href="/work?id=${t.id}">${esc(t.subject)}</a><br><span class="muted small">${esc(t.requester)} · ${esc(t.company)}</span></td>
          <td>${F.prio(t.priority)}</td><td>${F.status(t.status, true)}</td><td>${t.assignee ? esc(t.assignee) : '<span class="muted">Unassigned</span>'}</td>
          <td>${F.sla(t.sla, 'first')}</td><td>${F.sla(t.sla, 'res')}</td></tr>`).join('')
        || '<tr><td colspan="8" class="muted">Nothing in this view.</td></tr>';
      $('#qu-all').checked = false;
      count();
    }

    function count() {
      $('#qu-selected').textContent = `${$$('#qu-rows input[data-pick]:checked').length} selected`;
    }

    $$('#qu-tabs [role="tab"]').forEach((b) => b.addEventListener('click', () => {
      view = b.dataset.view;
      selected.clear();
      draw();
    }));
    $('#qu-rows').addEventListener('change', (e) => {
      const box = e.target.closest('[data-pick]');
      if (!box) return;
      const tid = Number(box.dataset.pick);
      if (box.checked) selected.add(tid); else selected.delete(tid);
      count();
    });
    $('#qu-all').addEventListener('change', () => {
      const on = $('#qu-all').checked;
      selected.clear();
      if (on) data.tickets.forEach((t) => selected.add(t.id));
      $$('#qu-rows input[data-pick]').forEach((b) => { b.checked = on; });
      count();
    });
    $('#qu-action').addEventListener('change', () => { $('#qu-tag-field').hidden = $('#qu-action').value !== 'tag'; });
    $('#qu-bulk').addEventListener('submit', async () => {
      const msg = $('#qu-msg');
      if (!selected.size) return F.say(msg, 'Tick at least one ticket.', 'error');
      const [action, value] = $('#qu-action').value.split(':');
      const body = { ids: Array.from(selected), action, value: action === 'tag' ? $('#qu-tag').value.trim() : value };
      const r = await F.api('/api/work/bulk', body);
      if (!r.ok) return F.say(msg, r.data.error || 'Could not update the tickets.', 'error');
      data = r.data;
      selected.clear();
      draw();
      F.say(msg, `Updated ${F.plural(r.data.updated, 'ticket')}.`, 'success');
    });

    const r = await F.api('/api/queue');
    if (!r.ok) return F.toast(r.data.error || 'Could not load the queue.', 'error');
    data = r.data;
    draw();
  };
})();
