(function () {
  'use strict';

  const F = window.Beacon;
  const { $, esc } = F;

  F.pages.reports = async function () {
    const r = await F.api('/api/reports');
    if (!r.ok) return F.toast(r.data.error || 'Could not load the reports.', 'error');
    const d = r.data;
    $('#rp-period').textContent = `Tickets raised from ${F.date(d.period_start)} to ${F.date(d.today)} (Dubai time).`;
    $('#rp-count').textContent = d.tickets;
    $('#rp-first').textContent = F.dur(d.avg_first);
    $('#rp-breach').textContent = `${d.breach_rate.toFixed(1)}%`;
    $('#rp-breach-note').textContent = `${F.plural(d.breached, 'ticket')} missed a target`;
    const total = Object.values(d.ratings).reduce((s, n) => s + n, 0);
    $('#rp-csat').textContent = d.csat === null ? '–' : `${d.csat.toFixed(1)}%`;
    $('#rp-csat-note').textContent = F.plural(total, 'rating');
    const most = Math.max(1, ...d.per_day.map((x) => x.count));
    $('#rp-days').innerHTML = d.per_day.map((x) => `<li><span class="bar-label">${F.day(x.day)}</span><span class="bar"><span style="width:${(100 * x.count) / most}%"></span></span><span class="bar-num">${x.count}</span></li>`).join('');
    const top = Math.max(1, ...Object.values(d.ratings));
    $('#rp-ratings').innerHTML = ['5', '4', '3', '2', '1'].map((k) => `<li><span class="bar-label">${k} ${k === '1' ? 'star' : 'stars'}</span><span class="bar"><span style="width:${(100 * d.ratings[k]) / top}%"></span></span><span class="bar-num">${d.ratings[k]}</span></li>`).join('');
    $('#rp-rows').innerHTML = d.rows.map((x) => `<tr data-id="${x.id}"><td><a href="/work?id=${x.id}">#${x.id}</a></td><td class="subject">${esc(x.subject)}</td><td>${esc(x.company)}</td>
        <td>${F.prio(x.priority)}</td><td>${F.status(x.status, true)}</td><td>${F.day(x.day)}</td>
        <td class="num">${x.first === null ? '<span class="muted">No reply yet</span>' : F.dur(x.first)}</td>
        <td>${x.breached ? '<span class="sla sla-breached">Missed</span>' : ['solved', 'closed'].includes(x.status) ? '<span class="sla sla-met">Met</span>' : '<span class="sla sla-running">On track</span>'}</td><td>${x.rating ? F.plural(x.rating, 'star') : '–'}</td></tr>`).join('');
  };
})();
