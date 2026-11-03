# buggy-site-helpdesk: Beacon Support

Beacon Support is a demo customer-support helpdesk (a customer portal for raising and following tickets, company
tickets for admins, a help centre, and an agent workspace with a queue, SLA timers in business hours, canned replies,
tags, escalation, merging, bulk actions and reports) with **40 functional bugs planted on purpose**, to measure how
many the AI QA Scanner finds. It is the tenth benchmark site, after
[buggy-site](https://github.com/Chaman-Raghav-Inno/buggy-site) (Lumen Goods),
[buggy-site-taskline](https://github.com/Chaman-Raghav-Inno/buggy-site-taskline) (Taskline),
[buggy-site-driftwood](https://github.com/Chaman-Raghav-Inno/buggy-site-driftwood) (Driftwood Stays),
[buggy-site-fernhill](https://github.com/Chaman-Raghav-Inno/buggy-site-fernhill) (Fernhill Academy),
[buggy-site-kestrel](https://github.com/Chaman-Raghav-Inno/buggy-site-kestrel) (Kestrel Works),
[buggy-site-copperleaf](https://github.com/Chaman-Raghav-Inno/buggy-site-copperleaf) (Copperleaf Bank),
[buggy-site-meadowbrook](https://github.com/Chaman-Raghav-Inno/buggy-site-meadowbrook) (Meadowbrook Clinic),
[buggy-site-forkline](https://github.com/Chaman-Raghav-Inno/buggy-site-forkline) (Forkline) and
[buggy-site-marquee](https://github.com/Chaman-Raghav-Inno/buggy-site-marquee) (Marquee). Its bugs break helpdesk
rules: SLA targets, business hours, holidays and pauses, who may set Urgent, attachment and copy rules, the reopen
window, ratings, internal notes, merging and escalation, and report formulas.

It is not a real helpdesk: no real customers or support, and it says so on every page.

[BUGS.md](BUGS.md) is the answer key: for each bug, the steps to reproduce, what should happen, what happens, its
severity, how hard it is to notice and where it is in the code. The site never serves that file, and nothing it
serves names or hints at a bug. The rules each bug breaks are published on the site (`/help`).

## Run it

```sh
python -m beacon          # http://localhost:8089 (PORT changes the port)
```

Standard library only (Python 3.11+); no install step.

- Accounts (password `Beacon@2026`, shown on the login page): `ivy@beacon.test` (Ivy Marsh, a customer and company
  admin at Northwind Traders), `sam@beacon.test` (Sam Okafor, support agent and team lead).
- Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
  other's changes. Both accounts share that copy within one browser. A restart or redeploy resets everything.
- SLA clocks are deterministic: the desk clock is fixed at 12:00 Dubai time on the day the session starts, and seeded
  tickets are placed on working days relative to it.

## Deploy on Railway

New service → GitHub repo → this repository, then **Generate domain** under Networking. `railway.json` sets the
start command and health check (`/healthz`); no variables or volume are needed. Avoid redeploying while a scan runs.

## Development

```sh
pip install ruff pytest
ruff check . && ruff format --check .
pytest -q
```

`tests/test_beacon.py` keeps the server-side bugs in place and checks that nothing served gives a bug away.
Server-side code marks each bug with a `BUG-nn` comment; the served files must not.
