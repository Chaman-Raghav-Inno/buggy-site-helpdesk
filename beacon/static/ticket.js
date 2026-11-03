(function () {
  'use strict';

  const F = window.Beacon;
  const { $, $$, esc } = F;

  const STAMP = { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' };

  F.pages.ticket = async function () {
    const id = Number(F.params.get('id'));
    let t;

    function draw() {
      document.title = `#${t.id} ${t.subject} · Beacon Support`;
      $('#tc-number').textContent = `Ticket #${t.id}`;
      $('#tc-subject').textContent = t.subject;
      $('#tc-pills').innerHTML = `${F.status(t.status)} ${F.prio(t.priority)}`;
      $('#tc-tz').textContent = `Times are in ${F.tz(t.tz, t.offset)}.`;
      $('#tc-thread').innerHTML = t.messages.map((m) => {
        const at = new Date(m.at).toLocaleString('en-GB', STAMP);
        if (m.kind === 'system') return `<li class="msg-system">${esc(m.body)} <span class="muted small">${at}</span></li>`;
        const files = m.attachments.length ? `<p class="small">Attached: ${m.attachments.map((f) => `${esc(f.name)} (${F.bytes(f.size)})`).join(', ')}</p>` : '';
        return `<li class="msg-item${m.author.agent ? ' from-agent' : ''}"><p class="msg-head"><strong>${esc(m.author.name)}</strong>${m.author.agent ? ' <span class="pill">Beacon Support</span>' : ''} <span class="muted small">${at}</span></p>${F.paras(m.body)}${files}</li>`;
      }).join('');
      const replyBy = $('#tc-replyby');
      replyBy.hidden = !t.reply_by;
      if (t.reply_by) replyBy.textContent = `We aim to send you a first reply by ${F.when(t.reply_by, t.offset)}.`;
      const facts = [
        ['Raised by', esc(t.requester)],
        ['Company', esc(t.company)],
        ['Category', esc(F.cap(t.category))],
        ['Created', F.when(t.created, t.offset)],
        ['Last updated', F.when(t.updated, t.offset)],
      ];
      if (t.cc.length) facts.push(['Copied in', t.cc.map(esc).join(', ')]);
      if (t.assignee) facts.push(['Agent', esc(t.assignee)]);
      $('#tc-facts').innerHTML = facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
      $('#tc-reply-form').hidden = !t.can_reply;
      $('#tc-close').hidden = !t.can_close;
      $('#tc-reopen').hidden = !t.can_reopen;
      $('#tc-transcript').href = `/api/tickets/${t.id}/transcript.txt`;
      $('#tc-rate-form').hidden = !t.can_rate;
      $('#tc-rated').textContent = t.rating ? `This ticket was rated ${F.plural(t.rating, 'star')}.` : 'Rate the help you got on this ticket.';
    }

    async function act(path, body, success) {
      const r = await F.api(path, body);
      if (!r.ok) return F.say($('#tc-msg'), r.data.error || 'Something went wrong.', 'error');
      t = r.data;
      draw();
      F.say($('#tc-msg'), success, 'success');
      return true;
    }

    const r = await F.api(`/api/tickets/${id}`);
    t = r.data;
    draw();
    $('#loading').hidden = true;
    $('#ticket').hidden = false;

    $('#tc-reply-form').addEventListener('submit', async () => {
      const body = $('#tc-reply').value.trim();
      if (!body) return F.say($('#tc-msg'), 'Write your reply.', 'error');
      if (await act(`/api/tickets/${id}/reply`, { body }, 'Reply sent.')) $('#tc-reply').value = '';
    });
    $('#tc-close').addEventListener('click', () => act(`/api/tickets/${id}/close`, {}, 'Marked as solved. Thanks for letting us know.'));
    $('#tc-reopen').addEventListener('click', () => act(`/api/tickets/${id}/reopen`, {}, 'Ticket reopened.'));
    $('#tc-rate-form').addEventListener('submit', async () => {
      const picked = $$('input[name="tc-score"]').find((i) => i.checked);
      const msg = $('#tc-rate-msg');
      if (!picked) return F.say(msg, 'Choose 1 to 5 stars.', 'error');
      const res = await F.api(`/api/tickets/${id}/rate`, { score: Number(picked.value) });
      if (!res.ok) return F.say(msg, res.data.error || 'Could not save your rating.', 'error');
      t = res.data;
      draw();
      F.say(msg, 'Thanks for your rating.', 'success');
    });
  };
})();
