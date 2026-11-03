(function () {
  'use strict';

  const F = window.Beacon;
  const { $, $$, esc } = F;

  F.pages.article = async function () {
    const id = Number(F.params.get('id'));
    function draw(a) {
      document.title = `${a.title} · Beacon Support`;
      $('#ar-category').textContent = a.category;
      $('#ar-title').textContent = a.title;
      $('#ar-body').innerHTML = a.body.map((p) => `<p>${esc(p)}</p>`).join('');
      const total = a.yes + a.no;
      const share = total ? Math.round((100 * a.no) / total) : 0;
      $('#ar-score').textContent = total
        ? `${F.plural(a.yes, 'person', 'people')} said yes and ${a.no} said no: ${share}% found this helpful.`
        : 'No votes yet.';
    }
    const r = await F.api(`/api/kb/${id}`);
    if (!r.ok) {
      $('#loading').textContent = r.data.error || 'We couldn’t find that article.';
      return;
    }
    draw(r.data);
    $('#loading').hidden = true;
    $('#article').hidden = false;
    $$('[data-vote]').forEach((b) => b.addEventListener('click', async () => {
      const v = await F.api(`/api/kb/${id}/vote`, { helpful: b.dataset.vote === 'yes' });
      if (!v.ok) return F.say($('#ar-msg'), v.data.error || 'Could not save your vote.', 'error');
      draw(v.data);
      F.say($('#ar-msg'), 'Thanks for your feedback.', 'success');
    }));
  };
})();
