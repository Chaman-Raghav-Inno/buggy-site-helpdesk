(function () {
  'use strict';

  const F = window.Beacon;
  const { $, esc } = F;

  F.pages.kb = async function () {
    let seq = 0;
    async function load() {
      const mine = ++seq;
      const q = $('#kb-q').value.trim();
      const r = await F.api('/api/kb?' + new URLSearchParams({ q }).toString());
      if (mine !== seq) return;
      if (!r.ok) return F.toast(r.data.error || 'Could not load the help centre.', 'error');
      const list = r.data.articles;
      $('#kb-count').textContent = q ? `${F.plural(list.length, 'article')} for “${q}”` : F.plural(list.length, 'article');
      $('#kb-list').innerHTML = list.map((a) => `<li><a href="/article?id=${a.id}">${esc(a.title)}</a> <span class="pill">${esc(a.category)}</span></li>`).join('')
        || '<li class="muted">No articles match. Try other words, or raise a ticket.</li>';
    }
    let timer;
    $('#kb-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(load, 250); });
    $('#kb-form').addEventListener('submit', () => { clearTimeout(timer); load(); });
    await load();
  };
})();
