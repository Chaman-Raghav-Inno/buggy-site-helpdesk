(function () {
  'use strict';

  const F = window.Beacon;
  const { $, $$, esc } = F;

  const STATE = { met: 'Met', breached: 'Breached', running: 'Running', paused: 'Paused while waiting on the customer', none: 'No reply needed' };
  const first = (name) => String(name || '').split(' ')[0];

  F.pages.work = async function () {
    const id = Number(F.params.get('id'));
    let t;

    function fill(text) {
      return text
        .replaceAll('{{first_name}}', first(t.me.name))
        .replaceAll('{{ticket_id}}', `#${t.id}`)
        .replaceAll('{{agent_name}}', first(t.me.name));
    }

    function draw() {
      document.title = `#${t.id} ${t.subject} · Beacon Support`;
      $('#wk-number').textContent = `Ticket #${t.id}${t.merged_into ? ` · merged into #${t.merged_into}` : ''}`;
      $('#wk-subject').textContent = t.subject;
      $('#wk-pills').innerHTML = `${F.status(t.status, true)} ${F.prio(t.priority)}${t.escalated ? ' <span class="pill pill-tier">Tier 2</span>' : ''}`;
      $('#wk-who').textContent = `${t.requester} <${t.requester_email}> · ${t.company}, ${t.plan} plan${t.cc.length ? ` · copied: ${t.cc.join(', ')}` : ''}`;
      $('#wk-tz').textContent = `Times are in ${F.tz(t.tz, t.offset)}, the customer's time zone.`;
      $('#wk-thread').innerHTML = t.messages.map((m) => {
        const at = F.when(m.at, t.offset);
        if (m.kind === 'system') return `<li class="msg-system">${esc(m.body)} <span class="muted small">${at}</span></li>`;
        const files = m.attachments.length ? `<p class="small">Attached: ${m.attachments.map((f) => `${esc(f.name)} (${F.bytes(f.size)})`).join(', ')}</p>` : '';
        const tag = m.kind === 'note' ? ' <span class="pill pill-note">Internal note</span>' : '';
        return `<li class="msg-item${m.author.agent ? ' from-agent' : ''}${m.kind === 'note' ? ' note' : ''}"><p class="msg-head"><strong>${esc(m.author.name)}</strong>${tag} <span class="muted small">${at}</span></p>${F.paras(m.body)}${files}</li>`;
      }).join('');
      const statuses = [['open', 'Open'], ['pending', 'Waiting on customer'], ['solved', 'Solved']];
      if (t.status === 'new' || t.status === 'closed') statuses.unshift([t.status, F.statusName(t.status, true)]);
      $('#wk-status').innerHTML = statuses.map(([v, l]) => `<option value="${v}"${v === t.status ? ' selected' : ''}${v === 'new' || v === 'closed' ? ' disabled' : ''}>${l}</option>`).join('');
      $('#wk-priority').value = t.priority;
      $('#wk-assignee').innerHTML = '<option value="">Unassigned</option>' + t.agents.map((a) => `<option value="${a.id}"${a.id === t.assignee_id ? ' selected' : ''}>${esc(a.name)}${a.away ? ` (away until ${F.date(a.away_until)})` : ''}</option>`).join('');
      const s = t.sla;
      const facts = [
        ['First response target', F.dur(s.first_target)],
        ['First response time', `${F.dur(s.first_elapsed)} · ${STATE[s.first_state]}`],
        ['Resolution target', F.dur(s.res_target)],
        ['Resolution time', `${F.dur(s.res_elapsed)} · ${STATE[s.res_state]}`],
        ['Time waiting on the customer', F.dur(s.waiting)],
      ];
      if (s.first_state === 'running') facts.push(['First response due', F.when(s.first_due, t.offset)]);
      if (s.res_state === 'running') facts.push(['Resolution due', F.when(s.res_due, t.offset)]);
      $('#wk-sla').innerHTML = facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
      $('#wk-tags').innerHTML = t.tags.map((g) => `<li>${esc(g)} <button type="button" class="link" data-untag="${esc(g)}" aria-label="Remove ${esc(g)}">×</button></li>`).join('')
        || '<li class="muted">No tags</li>';
      const closed = t.status === 'closed';
      $$('#work button, #work input, #work select, #work textarea').forEach((el) => { el.disabled = closed; });
    }

    async function post(path, body, msgSel, success) {
      const r = await F.api(path, body);
      if (!r.ok) {
        F.say($(msgSel), r.data.error || 'Something went wrong.', 'error');
        return false;
      }
      t = r.data;
      draw();
      F.say($(msgSel), success, 'success');
      return true;
    }

    const r = await F.api(`/api/work/${id}`);
    if (!r.ok) {
      $('#loading').textContent = r.data.error || 'We couldn’t find that ticket.';
      return;
    }
    t = r.data;
    $('#wk-canned').innerHTML += t.canned.map((c) => `<option value="${c.id}">${esc(c.title)}</option>`).join('');
    draw();
    $('#loading').hidden = true;
    $('#work').hidden = false;

    const kind = () => $$('input[name="wk-kind"]').find((i) => i.checked).value;
    $$('input[name="wk-kind"]').forEach((i) => i.addEventListener('change', () => {
      $('#wk-after-field').hidden = kind() === 'note';
      $('#wk-send').textContent = kind() === 'note' ? 'Add note' : 'Send reply';
    }));
    $('#wk-canned').addEventListener('change', () => {
      const c = t.canned.find((x) => String(x.id) === $('#wk-canned').value);
      if (c) $('#wk-body').value = fill(c.body);
      $('#wk-canned').value = '';
    });
    $('#wk-compose').addEventListener('submit', async () => {
      const body = $('#wk-body').value.trim();
      if (!body) return F.say($('#wk-compose-msg'), 'Write a message.', 'error');
      const note = kind() === 'note';
      const ok = await post(`/api/work/${id}/reply`, { kind: kind(), body, status: $('#wk-after').value }, '#wk-compose-msg', note ? 'Note added.' : 'Reply sent.');
      if (ok) $('#wk-body').value = '';
    });
    $('#wk-props').addEventListener('submit', () => {
      const body = { priority: $('#wk-priority').value, assignee: $('#wk-assignee').value ? Number($('#wk-assignee').value) : null };
      if ($('#wk-status').value !== t.status) body.status = $('#wk-status').value;
      post(`/api/work/${id}/update`, body, '#wk-props-msg', 'Saved.');
    });
    $('#wk-tag-form').addEventListener('submit', async () => {
      const tag = $('#wk-tag').value.trim();
      if (!tag) return F.say($('#wk-tag-msg'), 'Type a tag.', 'error');
      if (await post(`/api/work/${id}/tags`, { tag }, '#wk-tag-msg', `Added ${tag}.`)) $('#wk-tag').value = '';
    });
    $('#wk-tags').addEventListener('click', (e) => {
      const b = e.target.closest('[data-untag]');
      if (b) post(`/api/work/${id}/tags`, { tag: b.dataset.untag, remove: true }, '#wk-tag-msg', `Removed ${b.dataset.untag}.`);
    });

    $('#wk-escalate').addEventListener('click', () => {
      $('#wk-esc-reason').value = '';
      $('#wk-esc-dialog').returnValue = '';
      $('#wk-esc-dialog').showModal();
    });
    $$('#wk-esc-dialog button').forEach((b) => b.addEventListener('click', () => $('#wk-esc-dialog').close(b.dataset.value)));
    $('#wk-esc-dialog').addEventListener('close', () => {
      if ($('#wk-esc-dialog').returnValue !== 'escalate') return;
      post(`/api/work/${id}/escalate`, { reason: $('#wk-esc-reason').value.trim() }, '#wk-more-msg', 'Escalated to Tier 2.');
    });

    let mergeTarget = null;
    $('#wk-merge-form').addEventListener('submit', () => {
      const n = Number($('#wk-merge').value.replace(/[#\s]/g, ''));
      if (!Number.isInteger(n) || n <= 0) return F.say($('#wk-more-msg'), 'Enter a ticket number.', 'error');
      mergeTarget = n;
      $('#wk-merge-text').textContent = `Ticket #${t.id} will be closed and its conversation moved into #${n}.`;
      $('#wk-merge-dialog').returnValue = '';
      $('#wk-merge-dialog').showModal();
    });
    $$('#wk-merge-dialog button').forEach((b) => b.addEventListener('click', () => $('#wk-merge-dialog').close(b.dataset.value)));
    $('#wk-merge-dialog').addEventListener('close', async () => {
      if ($('#wk-merge-dialog').returnValue !== 'merge' || !mergeTarget) return;
      if (await post(`/api/work/${id}/merge`, { target: mergeTarget }, '#wk-more-msg', `Merged into #${mergeTarget}.`)) $('#wk-merge').value = '';
    });
  };
})();
