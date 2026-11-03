(function () {
  'use strict';

  const F = window.Beacon;
  const { $ } = F;

  F.pages.help = async function () {
    const r = await F.api('/api/policy');
    if (!r.ok) return;
    const year = r.data.today.slice(0, 4);
    const shown = r.data.holidays.filter((h) => h.name !== "New Year's Day" || h.date.slice(0, 4) === year);
    $('#hp-holidays').textContent = shown.map((h) => `${h.name} (${F.date(h.date)})`).join(' and ');
  };
})();
