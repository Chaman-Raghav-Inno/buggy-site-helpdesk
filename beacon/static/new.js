(function () {
  'use strict';

  const F = window.Beacon;
  const { $, esc } = F;

  const ALLOWED = /\.(png|jpe?g|pdf|txt|log|csv)$/;
  const MAX_SIZE = 10 * 1024 * 1024;

  F.pages.new = async function () {
    const me = (await F.api('/api/me')).data;
    const user = me.user;
    $('#nt-plan').textContent = `Urgent is for a service that's down and is part of the Premium plan. ${user.company} is on the ${user.plan} plan.`;
    $('#nt-cc-hint').textContent = `Up to 5 colleagues with an @${user.domain} address.`;
    let files = [];

    $('#nt-files').addEventListener('change', () => {
      files = Array.from($('#nt-files').files).map((f) => ({ name: f.name, size: f.size }));
      $('#nt-file-list').innerHTML = files.map((f) => `<li>${esc(f.name)} <span class="muted small">${F.bytes(f.size)}</span></li>`).join('');
    });

    $('#nt-form').addEventListener('submit', async () => {
      const msg = $('#nt-msg');
      const subject = $('#nt-subject').value.trim();
      const description = $('#nt-description').value.trim();
      const cc = $('#nt-cc').value.split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);
      if (!subject) return F.say(msg, 'Enter a subject.', 'error');
      if (!$('#nt-category').value) return F.say(msg, 'Choose a category.', 'error');
      if (description.length < 20) return F.say(msg, 'Describe the problem in at least 20 characters.', 'error');
      const badEmail = cc.find((a) => !F.EMAIL.test(a));
      if (badEmail) return F.say(msg, `${badEmail} isn't a valid email address.`, 'error');
      const badType = files.find((f) => !ALLOWED.test(f.name));
      if (badType) return F.say(msg, `${badType.name}: only PNG, JPG, PDF, TXT, LOG or CSV files.`, 'error');
      const big = files.find((f) => f.size > MAX_SIZE);
      if (big) return F.say(msg, `${big.name} is larger than 10 MB.`, 'error');
      const r = await F.api('/api/tickets', {
        subject, category: $('#nt-category').value, priority: $('#nt-priority').value, description, cc, attachments: files,
      });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not create the ticket.', 'error');
      F.say(msg, '');
      const t = r.data.ticket;
      const replyBy = new Date(Date.parse(me.now) + r.data.target_minutes * 60000).toISOString().replace(/\.\d+Z$/, 'Z');
      $('#nt-done-text').textContent = `Ticket #${t.id} “${t.subject}” is with our team. With ${F.cap(t.priority)} priority, you'll hear from us by ${F.when(replyBy, t.offset)} (${F.tz(t.tz, t.offset)}).`;
      $('#nt-done-link').href = `/ticket?id=${t.id}`;
      $('#nt-done').hidden = false;
      $('#nt-done').scrollIntoView({ block: 'nearest' });
      $('#nt-form').reset();
      files = [];
      $('#nt-file-list').innerHTML = '';
    });
  };
})();
