# Beacon Support: answer key (40 planted bugs)

Beacon Support is a demo customer-support helpdesk (a customer portal with tickets, conversations, ratings, company
tickets and a help centre, and an agent workspace with a queue, SLA timers, canned replies, tags, escalation, merging,
bulk actions and reports) with **functional bugs planted on purpose**, for checking what the AI QA Scanner finds.
Most bugs break a rule published on the site, so finding them takes the rules, some business-hours arithmetic, a
download, a second page or the other account.

This file is never served, and nothing the site serves (pages, scripts, CSS, images) names or hints at a bug.
Server-side code marks each one with a `BUG-nn` comment; `tests/test_beacon.py` keeps the server-side ones in place.
The rules every bug breaks are published on the site's **Service policy** page (`/help`).

## Run it

- **Locally**: `python -m beacon` (port 8089, or `PORT`), then open http://localhost:8089.
- **Railway**: New service → GitHub repo → this repository, then **Generate domain**. `railway.json` sets the start
  command and health check; no variables or volume needed.

Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
other's changes. Logging in as Ivy and then Sam in the same browser shares one world, so what Sam does shows up for
Ivy. A restart resets everything.

## Test data

Days are counted from the day the session starts ("day 0" is today, UTC). The desk clock is fixed at **12:00 Dubai
time (UTC+4) on day 0**, whatever the real time; everything new (tickets, replies) is stamped with it. "Working day
−n" means the n-th Monday–Friday before today, skipping the desk's holidays.

| What | Value |
|---|---|
| Accounts (password `Beacon@2026`, listed on the login page) | `ivy@beacon.test` Ivy Marsh, customer and company admin at Northwind Traders · `sam@beacon.test` Sam Okafor, support agent and team lead |
| Companies | Northwind Traders: Standard plan, Dubai (UTC+4), colleagues Tom Reyes and Mei Lin (`@northwind.test`) · Halcyon Foods: Premium plan, Singapore (UTC+8), Raj Patel and Ana Souza |
| Agents | Sam Okafor, Priya Nair, Leo Brandt (**away** until day +9) |
| Holidays | New Year's Day and **Founders' Day**, which is always the third weekday before today (listed on `/help`) |
| SLA targets (business hours) | Urgent 1h / 8h · High 2h / 16h · Normal 8h / 40h · Low 16h / 80h; business hours Mon–Fri 09:00–17:30 local |
| Ivy's tickets (12) | Open: #1013, #1016, #1018 (Waiting on you), #1022 (has an internal note, 4 tags), #1023 (no reply yet), #1026 (raised today) · Solved: #1004 (raised day −20, solved day −2), #1011, #1012 · Closed: #1001, #1002, #1006 |
| Colleagues' tickets | Tom: #1005 (closed), #1009 (solved day −4, not rated), #1014 (Low, agent Leo), #1024 (duplicate of #1022, no reply) · Mei: #1008 (solved on the last day of last month), #1015, #1017 (raised the working day before Founders' Day, answered the working day after), #1020 (only an internal note so far) |
| Halcyon Foods' tickets | #1003, #1007 (closed), #1010 (solved by Raj himself, no agent), #1019, #1021 (Urgent), #1025 (raised today) |
| Ratings | 8 ratings: 5★ ×2, 4★ ×2, 3★ ×2, 2★ ×1, 1★ ×1, so CSAT should be 50% |
| Help centre | 8 articles; "Setting up single sign-on" (id 2) mentions SAML in its text and has 12 Yes / 28 No votes |

Difficulty: **Medium** needs a flow or a comparison; **Hard** needs the published rules, a second page, a download,
a reload or the other account; **Expert** needs arithmetic across several numbers, business hours or a calendar edge.

## The bugs

### Raising a ticket

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-01 | Urgent accepted on the Standard plan | As Ivy (Northwind, Standard plan), New ticket with priority Urgent | Refused: Urgent is part of the Premium plan | "Ticket created … With Urgent priority" | High | Medium | `server.py` `Store.create_ticket` |
| BUG-02 | Copies go to outside addresses | New ticket, Copy in `pat.lee@gmail.test` | Refused: only `@northwind.test` colleagues | Created, copied to pat.lee@gmail.test | High | Medium | `server.py` `Store.create_ticket` |
| BUG-03 | Upper-case file extensions refused | New ticket with the attachment `Screenshot.PNG` | Accepted ("whatever the case of the file name") | "Screenshot.PNG: only PNG, JPG, PDF, TXT, LOG or CSV files." (`screenshot.png` works) | Medium | Hard | `static/new.js` (`ALLOWED` has no `i` flag) |
| BUG-04 | More than 5 attachments accepted | New ticket with 7 small `.txt` files | Refused (up to 5 files) | Created with 7 attachments | Low | Medium | `server.py` `Store.create_ticket` |
| BUG-05 | Confirmation promises a reply outside business hours | New Normal ticket; compare the confirmation with the ticket page | Both say the next working day 11:30 (8 business hours from 12:00) | Confirmation: "by Tue 3 Nov, 20:00" (8 calendar hours); the ticket says "Wed 4 Nov, 11:30" | Medium | Hard | `static/new.js` (adds calendar hours to the clock) |

### My tickets

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-06 | Search by "#number" finds nothing | My tickets, All tab, search `#1022` | Ticket #1022 | "0 tickets" (`1022` finds it) | Low | Medium | `server.py` `Store.my_tickets` |
| BUG-07 | Priority sort is alphabetical | All tab, Sort by Priority, page through | High, Normal, Low | High…, Low, Low, Normal… (Low before Normal) | Low | Medium | `server.py` `Store.my_tickets` |
| BUG-08 | Pages after the first skip a ticket | Open tab ("6 tickets"), Next | The 6th ticket (#1013) on page 2 | Page 2 is empty; #1013 is never listed (on the All tab, pages 2 and 3 each skip one) | High | Hard | `server.py` `Store.my_tickets` |

### Ticket conversation

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-09 | Closed tickets take replies | Open #1002 (Closed) | No reply box: raise a new ticket | Reply box shown; "Reply sent." | Medium | Medium | `server.py` `Store.ticket_view` / `Store.reply` |
| BUG-10 | Reopen window counted from the day it was raised | #1004 (solved 2 days ago, raised 20 days ago): Reopen | Reopened (within 7 days of being solved) | "This ticket was solved more than 7 days ago" | High | Hard | `server.py` `Store.reopen` |
| BUG-11 | Replying doesn't take a ticket off "Waiting on you" | #1018 (Waiting on you): send a reply | Status back to Open, resolution clock restarts | Still "Waiting on you" (agents see it paused) | High | Hard | `server.py` `Store.reply` |
| BUG-12 | A ticket can be rated twice | #1004: rate 5 stars, then 1 star | Second rating refused (rate once) | "Thanks for your rating." both times; both count in CSAT | Medium | Medium | `server.py` `Store.rate` |
| BUG-13 | Downloaded conversation includes internal notes | #1022: Download conversation | Only the public messages | The file has Sam's note "Standard plan: don't promise a fix date … up for renewal next month" | Critical | Hard | `server.py` `Store.transcript` |
| BUG-14 | Thread times are in UTC, labelled Dubai time | #1022: compare Created with the first message's time | Both 09:20 (Dubai time, as the page says) | Created 09:20; first message 05:20 (4 hours early on every message) | Low | Expert | `static/ticket.js` (`STAMP` uses UTC) |
| BUG-15 | Another company's ticket opens by its number | As Ivy, open `/ticket?id=1021` (numbers skip from #1002 to #1004 in her list) | "We couldn't find that ticket" | Halcyon Foods' "Payment terminal integration returns 502", with its conversation | Critical | Hard | `server.py` `Store.customer_ticket` |

### Company tickets

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-16 | Admins can rate colleagues' tickets | Company tickets → #1009 (raised by Tom): rate it | No rating form (only the requester rates) | Rating form shown; "Thanks for your rating." (Reopen is correctly hidden) | Medium | Hard | `server.py` `Store.ticket_view` / `Store.rate` |
| BUG-17 | "Solved this month" counts the last 30 days | Company tickets: Solved this month; compare with each ticket's solve date | Tickets solved since the 1st | Also counts tickets solved last month (e.g. #1008 on the last day of last month) | Low | Expert | `server.py` `Store.company_tickets` |

### Help centre

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-18 | Search ignores article text | Help centre, search `SAML` | "Setting up single sign-on" (its text mentions SAML) | "0 articles" | Medium | Medium | `server.py` `Store.kb` |
| BUG-19 | Votes can be repeated | "Setting up single sign-on": click Yes three times | One vote per person | Yes goes 12 → 15 | Low | Medium | `server.py` `Store.vote` |
| BUG-20 | Helpful score uses the No votes | "Setting up single sign-on": 12 yes, 28 no | 30% found this helpful | "70% found this helpful" | Low | Hard | `static/article.js` (`share` divides `a.no`) |

### Agent queue

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-21 | Unassigned view includes solved tickets | As Sam, Queue → Unassigned | #1023–#1026 only (unsolved) | Also #1010 (Solved) | Medium | Medium | `server.py` `Store.queue` |
| BUG-22 | Overdue misses unanswered tickets past their first-response target | Queue: #1023 (High, raised 15:00 on working day −1, no reply) shows First response "Breached"; open Overdue | #1023 in Overdue (with any other unanswered ticket past its first-response target) | #1023 missing: Overdue lists only resolution breaches (e.g. #1015, #1019, #1021) | High | Hard | `server.py` `Store.queue` |
| BUG-23 | "Select all" bulk-changes tickets outside the view | Unassigned view (5 rows), tick Select all ("5 selected"), Assign to me, Apply | 5 tickets assigned | "Updated 20 tickets." – every ticket in the queue, solved ones and other agents' included, is now Sam's | Critical | Hard | `static/queue.js` (select-all adds `data.tickets`) |

### SLA timers

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-24 | Public holidays count as business hours | #1017 (raised 16:00 the working day before Founders' Day, answered 10:00 the working day after): SLA panel | First response 2h 30m · Met | "11h 00m · Breached" (Founders' Day's 8h 30m counted) | High | Expert | `server.py` `is_business_day` |
| BUG-25 | Waiting time isn't paused | #1011 (High, 16h target): SLA panel | Resolution 5h 30m · Met (27h 30m minus 22h waiting on the customer) | "27h 30m · Breached" next to "Time waiting on the customer 22h 00m" | High | Hard | `server.py` `Store.sla` |
| BUG-26 | An internal note counts as the first response | #1020 (only Priya's internal note, no public reply): SLA panel / queue | First response still running, now Breached (8h target) | "30m · Met" | High | Hard | `server.py` `Store.sla` |
| BUG-27 | Changing priority keeps the old targets | #1014 (Low): set Priority to Urgent, Save | Targets 1h / 8h | Still 16h / 80h: "Resolution target 80h 00m" | High | Hard | `server.py` `Store.sla` / `Store.update` |

### Working a ticket

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-28 | `{{first_name}}` fills in the agent's name | #1022 (Ivy's): Canned reply "Thanks, we're on it" | "Hi Ivy," | "Hi Sam," | Medium | Medium | `static/work.js` (`fill`) |
| BUG-29 | Away agents can be given tickets | #1023: Agent "Leo Brandt (away until …)", Save | Refused | "Saved." | Medium | Medium | `server.py` `Store.update` |
| BUG-30 | A ticket can be solved without any public reply | #1024 (no reply yet): Status Solved, Save | Refused: the customer needs a public reply first | "Saved."; status Solved | High | Hard | `server.py` `Store.set_status` |
| BUG-31 | Escalating an Urgent ticket lowers it to High | #1021 (Urgent): Escalate to Tier 2 with a reason | Stays Urgent, gets `tier-2` | Priority High (and a 16h target) | High | Hard | `server.py` `Store.escalate` |
| BUG-32 | More than 5 tags allowed | #1022 (4 tags): add `renewal` and `eng-4471` | The 6th refused | 6 tags | Low | Medium | `server.py` `Store.tags` |
| BUG-33 | Merging loses the duplicate's messages | #1024: merge into #1022 | #1022 gains Tom's message | Only a line "Ticket #1024 … was merged into this ticket"; Tom's message is gone from view | High | Hard | `server.py` `Store.merge` |
| BUG-34 | Tickets from different companies can be merged | #1025 (Halcyon Foods): merge into #1016 (Northwind); then as Ivy open #1016 | Refused | Merged; Ivy reads "Ticket #1025 (Recipe cards cut off when printed) from Ana Souza, Halcyon Foods, was merged into this ticket" | Critical | Medium | `server.py` `Store.merge` |

### Reports

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-35 | Tickets per day leaves out today | Reports: Tickets per day | The last 7 days including today (#1025, #1026 raised today) | Ends yesterday; today missing | Medium | Hard | `server.py` `Store.reports` |
| BUG-36 | Average first response counts unanswered tickets as zero | Reports: Average first response vs the table's First response column | Mean of the answered tickets (about 3h 25m on a Tuesday) | Lower (about 2h 46m on a Tuesday): divided by all 26 tickets | Medium | Expert | `server.py` `Store.reports` |
| BUG-37 | SLA breach rate uses the wrong base | Reports: SLA breach rate vs "N tickets missed a target" and the ticket count | Missed ÷ all tickets (13 ÷ 26 = 50.0% on a Tuesday) | Missed ÷ answered tickets (13 ÷ 21 = 61.9%) | Medium | Expert | `server.py` `Store.reports` |
| BUG-38 | CSAT counts 3-star ratings as satisfied | Reports: CSAT vs the Ratings breakdown | 4 of 8 ratings are 4–5 stars: 50.0% | "75.0%" | Medium | Hard | `server.py` `Store.reports` |
| BUG-39 | CSV doesn't quote subjects with commas | Reports: Download CSV, row for #1004 | "Invoice, credit note and VAT number mismatch" in one column | Splits into two columns; every column after it shifts | Low | Hard | `server.py` `Store.reports_csv` |

### Errors

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-40 | An unknown ticket hangs on "Loading…" | As Ivy, open `/ticket?id=9999` | "We couldn't find that ticket" | "Loading…" forever and a JavaScript error | Low | Medium | `static/ticket.js` (no check on the response) |

## What is not a planted bug

- Console errors that come with a bug or a page: 401 on wrong passwords, 404 and the JavaScript error on an unknown
  ticket (BUG-40), 409 when a reopen or rating is refused, 403 on agent pages as Ivy and customer pages as Sam,
  404 on unknown pages.
- Bugs that combine: the SLA bugs (BUG-24 to BUG-27) also change the queue's Breached labels, the Overdue view and
  the report's breach rate; BUG-12 and BUG-16 add ratings that change CSAT; BUG-23 can make later "Mine" checks
  look different; BUG-11 keeps a ticket "Paused" in the queue.
- Exact SLA minutes for tickets that are still open depend on the weekday (the clock is 12:00 Dubai time on day 0,
  and weekends don't count); the tickets named in the steps were placed so the bug shows on any day.
- BUG-17 can't show on the 31st of a month (last month's last day is then more than 30 days ago).
- Around New Year's Day, Founders' Day and the working days in the steps shift; the bugs still show.
- The demo clock doesn't move: replies and new tickets all carry 12:00 on day 0.
- Each visitor has a private world: changes in one browser session do not show in another.
- "Demo helpdesk for QA testing" in the footer and the demo accounts on the login page.

By area: raising a ticket 5, my tickets 3, ticket conversation 7, company tickets 2, help centre 3, agent queue 3,
SLA timers 4, working a ticket 7, reports 5, errors 1.
By difficulty: Medium 15, Hard 20, Expert 5. By severity: Critical 4, High 13, Medium 13, Low 10.
