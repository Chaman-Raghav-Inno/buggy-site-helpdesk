"""Beacon Support's demo world: companies, people, tickets with their conversations, canned replies and help articles.

Every timestamp is placed relative to the day the session starts, so the site never goes stale and the SLA clocks
always read the same way: the desk clock is fixed at 12:00 Dubai time on that day (see NOW_LOCAL), and business-day
seeds ("two working days ago at 14:00") skip weekends and the desk's public holidays.

Every visitor gets a fresh copy (see server.Store), so scans never disturb each other.
"""

import datetime as dt
import hashlib

PASSWORD = "Beacon@2026"
SALT = b"beacon-demo-salt"

HOME_OFFSET = 4  # the desk's home time zone (Dubai, UTC+4); reports count days in it
NOW_LOCAL = dt.time(12, 0)  # the demo clock: noon in the desk's home time zone on the session's day
OPEN_AT, CLOSE_AT = dt.time(9, 0), dt.time(17, 30)

# business hours (minutes): first response, resolution
TARGETS = {
    "urgent": (60, 8 * 60),
    "high": (2 * 60, 16 * 60),
    "normal": (8 * 60, 40 * 60),
    "low": (16 * 60, 80 * 60),
}
PRIORITIES = ["urgent", "high", "normal", "low"]
CATEGORIES = ["billing", "technical", "account", "other"]
REOPEN_DAYS = 7
MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
FILE_TYPES = ("png", "jpg", "jpeg", "pdf", "txt", "log", "csv")
MAX_CC = 5
MAX_TAGS = 5
SUBJECT_MAX = 120
DESCRIPTION_MIN = 20
PAGE_SIZE = 5


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 20_000).hex()


DEMO_HASH = password_hash(PASSWORD, SALT)


def iso(moment: dt.datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(stamp: str) -> dt.datetime:
    return dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")


def holidays(today: dt.date) -> dict[str, str]:
    """The desk's public holidays near the session: New Year's Day and Founders' Day (three weekdays back)."""
    out = {dt.date(y, 1, 1).isoformat(): "New Year's Day" for y in (today.year - 1, today.year, today.year + 1)}
    d, seen = today, 0
    while seen < 3:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in out:
            seen += 1
    out[d.isoformat()] = "Founders' Day"
    return dict(sorted(out.items()))


def business_days_back(today: dt.date, hols: dict[str, str], count: int = 12) -> list[dt.date]:
    out, d = [], today
    while len(out) < count:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in hols:
            out.append(d)
    return out


def month_start(day: dt.date, back: int = 0) -> dt.date:
    y, m = divmod(day.year * 12 + day.month - 1 - back, 12)
    return dt.date(y, m + 1, 1)


COMPANIES = [
    {"id": 1, "name": "Northwind Traders", "domain": "northwind.test", "plan": "Standard", "tz": "Dubai", "offset": 4},
    {"id": 2, "name": "Halcyon Foods", "domain": "halcyon.test", "plan": "Premium", "tz": "Singapore", "offset": 8},
]

CANNED = [
    {"id": 1, "title": "Thanks, we're on it",
     "body": "Hi {{first_name}},\n\nThanks for getting in touch about ticket {{ticket_id}}. I'm looking into it now and "
             "will update you here as soon as I know more.\n\nBest,\n{{agent_name}}"},
    {"id": 2, "title": "Need more details",
     "body": "Hi {{first_name}},\n\nCould you send a screenshot and the time it happened? Reply on ticket "
             "{{ticket_id}} and we'll pick it up straight away.\n\nThanks,\n{{agent_name}}"},
    {"id": 3, "title": "Fixed, please confirm",
     "body": "Hi {{first_name}},\n\nWe've rolled out a fix for ticket {{ticket_id}}. Could you check on your side "
             "and let us know?\n\nBest,\n{{agent_name}}"},
]  # fmt: skip

ARTICLES = [
    {"id": 1, "title": "Resetting your password", "category": "Account", "yes": 41, "no": 3,
     "body": ["Use Forgot password on the sign-in page and we'll email you a link that works for 30 minutes.",
              "If the email doesn't arrive within five minutes, check your spam folder and ask your IT team to "
              "allow messages from beacon.test."]},
    {"id": 2, "title": "Setting up single sign-on", "category": "Account", "yes": 12, "no": 28,
     "body": ["Single sign-on lets your team log in with your identity provider. We support SAML 2.0 with Okta, "
              "Azure AD and Google Workspace.",
              "Ask your company admin to upload your provider's metadata file under Settings, then test with one "
              "account before switching everyone over."]},
    {"id": 3, "title": "Webhook retries and back-off", "category": "Technical", "yes": 17, "no": 4,
     "body": ["When your endpoint doesn't answer with a 2xx status, we retry after 1, 5 and 30 minutes, then "
              "hourly for a day.",
              "Answer quickly (within 10 seconds) and do the work in the background to avoid duplicate deliveries."]},
    {"id": 4, "title": "Exporting data to CSV", "category": "Technical", "yes": 9, "no": 6,
     "body": ["Exports cover up to 12 months at a time. Larger exports are emailed to you as a download link.",
              "Spreadsheet apps may show long numbers in scientific notation: format the column as text."]},
    {"id": 5, "title": "Understanding your invoice", "category": "Billing", "yes": 22, "no": 5,
     "body": ["Invoices are issued on the 1st of each month and list each user seat, add-ons and VAT.",
              "Your VAT number appears under the billing address. Changes apply from the next invoice."]},
    {"id": 6, "title": "Adding and removing user seats", "category": "Billing", "yes": 15, "no": 2,
     "body": ["Company admins can add seats at any time; you pay pro rata for the rest of the month.",
              "Removed seats stay active until the end of the billing month."]},
    {"id": 7, "title": "API rate limits by plan", "category": "Technical", "yes": 8, "no": 8,
     "body": ["Standard plans allow 600 requests a minute, Premium plans 3,000.",
              "Responses carry X-RateLimit-Remaining so you can slow down before you hit the limit."]},
    {"id": 8, "title": "Two-factor authentication", "category": "Account", "yes": 30, "no": 6,
     "body": ["Turn on two-factor authentication under Profile. Authenticator apps and security keys both work.",
              "Changed phones? Use one of your backup codes, then set up the new phone."]},
]  # fmt: skip


def world(today: dt.date) -> dict:
    """A fresh copy of everything one visitor can see and change."""
    hols = holidays(today)
    bdays = business_days_back(today, hols)

    def at(day: dt.date, hhmm: str, offset: int) -> str:
        h, m = map(int, hhmm.split(":"))
        return iso(dt.datetime.combine(day, dt.time(h, m)) - dt.timedelta(hours=offset))

    def b(n: int, hhmm: str, offset: int = 4) -> str:
        """n working days ago (weekends and holidays skipped), at a local time."""
        return at(bdays[n - 1], hhmm, offset)

    def d(n: int, hhmm: str, offset: int = 4) -> str:
        """n calendar days ago, at a local time."""
        return at(today - dt.timedelta(days=n), hhmm, offset)

    last_month_end = month_start(today) - dt.timedelta(days=1)

    def lm(n: int, hhmm: str) -> str:
        return at(last_month_end - dt.timedelta(days=n), hhmm, 4)

    people = [
        {"id": 1, "name": "Ivy Marsh", "email": "ivy@beacon.test", "role": "customer", "company": 1, "admin": True,
         "salt": SALT.hex(), "hash": DEMO_HASH},
        {"id": 2, "name": "Sam Okafor", "email": "sam@beacon.test", "role": "agent", "lead": True, "away": False,
         "salt": SALT.hex(), "hash": DEMO_HASH},
        {"id": 3, "name": "Priya Nair", "email": "priya@beacon.test", "role": "agent", "lead": False, "away": False},
        {"id": 4, "name": "Leo Brandt", "email": "leo@beacon.test", "role": "agent", "lead": False, "away": True,
         "away_until": (today + dt.timedelta(days=9)).isoformat()},
        {"id": 5, "name": "Tom Reyes", "email": "tom@northwind.test", "role": "customer", "company": 1,
         "admin": False},
        {"id": 6, "name": "Mei Lin", "email": "mei@northwind.test", "role": "customer", "company": 1, "admin": False},
        {"id": 7, "name": "Raj Patel", "email": "raj@halcyon.test", "role": "customer", "company": 2, "admin": True},
        {"id": 8, "name": "Ana Souza", "email": "ana@halcyon.test", "role": "customer", "company": 2, "admin": False},
    ]  # fmt: skip
    company_of = {p["id"]: p.get("company") for p in people}
    offset_of = {c["id"]: c["offset"] for c in COMPANIES}
    tickets: list[dict] = []
    mid = [5000]

    def ticket(tid, requester, subject, category, priority, created, body, events=(), **extra):
        """events: ("public"|"note", when, author, text, new_status) or ("status", when, None, None, status)."""
        t = {
            "id": tid, "requester": requester, "company": company_of[requester], "subject": subject,
            "category": category, "priority": priority, "sla_priority": priority, "status": "new",
            "assignee": None, "tags": [], "cc": [], "attachments": [], "created": created, "updated": created,
            "solved_at": None, "closed_at": None, "rating": None, "escalated": False, "merged_into": None,
            "messages": [], "status_log": [[created, "new"]],
        }  # fmt: skip
        mid[0] += 1
        t["messages"].append({"id": mid[0], "author": requester, "kind": "public", "body": body, "at": created})
        for kind, when, author, text, status in events:
            if kind in ("public", "note"):
                mid[0] += 1
                t["messages"].append({"id": mid[0], "author": author, "kind": kind, "body": text, "at": when})
                t["updated"] = when
            if status and status != t["status"]:
                t["status"] = status
                t["status_log"].append([when, status])
                t["updated"] = when
                if status == "solved":
                    t["solved_at"] = when
                if status == "closed":
                    t["closed_at"] = when
        t.update(extra)
        tickets.append(t)
        return t

    hf = 8
    ticket(
        1001,
        1,
        "Password reset email never arrives",
        "account",
        "low",
        d(29, "14:20"),
        "I asked for a password reset three times this morning and nothing has arrived.",
        [
            (
                "public",
                d(28, "09:30"),
                3,
                "Sorry about that. Could you check your spam folder for mail from beacon.test?",
                "pending",
            ),
            ("public", d(28, "10:00"), 1, "Found it in spam, thanks. All sorted.", "open"),
            ("status", d(28, "10:10"), None, None, "solved"),
            ("status", d(21, "10:10"), None, None, "closed"),
        ],
        assignee=3,
        rating=5,
    )
    ticket(
        1002,
        1,
        "CSV export times out for large date ranges",
        "technical",
        "high",
        d(26, "09:40"),
        "Exporting a full year of orders to CSV spins for a minute and then shows 'Request timed out'.",
        [
            (
                "public",
                d(26, "10:15"),
                2,
                "Thanks Ivy. Large exports are being moved to email delivery; I'll keep you posted.",
                "open",
            ),
            ("public", d(15, "16:00"), 2, "Year-long exports now arrive by email as a download link.", "solved"),
            ("status", d(8, "16:00"), None, None, "closed"),
        ],
        assignee=2,
        rating=4,
    )
    ticket(
        1003,
        7,
        "Loyalty points not syncing to the POS",
        "technical",
        "high",
        d(23, "10:00", hf),
        "Points earned online haven't appeared in our tills since Monday.",
        [
            ("public", d(23, "10:30", hf), 2, "We're on it, Raj. The sync job had stalled; restarting it now.", "open"),
            ("public", d(18, "15:00", hf), 2, "The backlog has been processed. Points are in sync again.", "solved"),
            ("status", d(11, "15:00", hf), None, None, "closed"),
        ],
        assignee=2,
        rating=1,
    )
    ticket(
        1004,
        1,
        "Invoice, credit note and VAT number mismatch",
        "billing",
        "normal",
        d(20, "10:05"),
        "Our October invoice and the credit note you sent show two different VAT numbers.",
        [
            ("public", d(20, "11:30"), 3, "Could you send us the invoice number so we can check it?", "pending"),
            ("public", d(19, "09:10"), 1, "It's INV-20931. The credit note is CN-1188.", "open"),
            ("public", d(2, "15:30"), 3, "We've reissued both documents with your correct VAT number.", "solved"),
        ],
        assignee=3,
    )
    ticket(
        1005,
        5,
        "Change the invoice email address",
        "billing",
        "low",
        d(27, "11:00"),
        "Please send our invoices to accounts@northwind.test from now on.",
        [
            ("public", d(25, "09:40"), 3, "Done: invoices now go to accounts@northwind.test.", "solved"),
            ("status", d(18, "09:40"), None, None, "closed"),
        ],
        assignee=3,
        rating=5,
    )
    ticket(
        1006,
        1,
        "Two-factor codes rejected after phone change",
        "account",
        "high",
        d(13, "09:15"),
        "I moved to a new phone and every code from the authenticator app is rejected.",
        [
            (
                "public",
                d(13, "09:50"),
                2,
                "I've reset two-factor on your account. You can set it up again at your next login.",
                "open",
            ),
            ("status", d(9, "11:00"), None, None, "solved"),
            ("status", d(2, "11:00"), None, None, "closed"),
        ],
        assignee=2,
        rating=3,
    )
    ticket(
        1007,
        8,
        "Allergen labels print in the wrong language",
        "technical",
        "normal",
        d(17, "10:00", hf),
        "Labels from the Orchard Road kitchen print in Portuguese instead of English.",
        [
            (
                "public",
                d(17, "13:00", hf),
                3,
                "The kitchen's locale was set to pt-BR. I've switched it to en-SG.",
                "solved",
            ),
            ("status", d(10, "13:00", hf), None, None, "closed"),
        ],
        assignee=3,
        rating=2,
    )
    solved = lm(0, "16:00")
    address = [("public", lm(1, "15:00"), 3, "Updated: your new address shows on the next invoice.", None),
               ("status", solved, None, None, "solved")]  # fmt: skip
    if (today - last_month_end).days > REOPEN_DAYS:
        address.append(("status", iso(parse(solved) + dt.timedelta(days=REOPEN_DAYS)), None, None, "closed"))
    ticket(
        1008,
        6,
        "Change our company address",
        "billing",
        "low",
        lm(2, "10:00"),
        "We've moved: our new address is 14 Harbour Lane, Dubai Marina.",
        address,
        assignee=3,
        rating=4,
    )
    ticket(
        1009,
        5,
        "Add our PO number to invoices",
        "billing",
        "low",
        d(6, "10:00"),
        "Could invoices show our purchase order number PO-77310?",
        [("public", d(4, "12:00"), 3, "Done: PO-77310 appears on every invoice from now on.", "solved")],
        assignee=3,
    )
    ticket(
        1010,
        7,
        "Copy of last year's annual invoice",
        "billing",
        "low",
        d(6, "09:00", hf),
        "Where can I download last year's annual invoice?",
        [("public", d(5, "10:00", hf), 7, "Found it under Billing > History. Closing this.", "solved")],
    )
    ticket(
        1011,
        1,
        "Refund for a duplicate charge",
        "billing",
        "high",
        b(6, "09:00"),
        "We were charged twice for November. Please refund the duplicate.",
        [
            (
                "public",
                b(6, "10:00"),
                2,
                "Sorry about that. Could you send the last four digits of the card charged?",
                "pending",
            ),
            ("public", b(4, "15:00"), 1, "It's the card ending 4417.", "open"),
            (
                "public",
                b(3, "11:00"),
                2,
                "The duplicate charge has been refunded. It takes 3–5 days to show.",
                "solved",
            ),
        ],
        assignee=2,
        rating=3,
    )
    ticket(
        1012,
        1,
        "Monthly report PDF is missing our logo",
        "other",
        "low",
        d(3, "10:00"),
        "Since this month the PDF reports have a blank space where our logo should be.",
        [
            ("public", d(3, "13:00"), 3, "Could you tell us which report and send a screenshot?", "pending"),
            ("public", d(2, "09:00"), 1, "The Monthly Sales report. Screenshot attached.", "open"),
            ("public", d(1, "16:00"), 3, "Fixed: the logo was too large for the new layout. It's back now.", "solved"),
        ],
        assignee=3,
        attachments=[{"name": "report-logo.png", "size": 184_320}],
    )
    ticket(
        1013,
        1,
        "Custom domain certificate stuck on pending",
        "technical",
        "normal",
        b(4, "13:00"),
        "help.northwind.test has shown 'Certificate pending' for two days.",
        [
            (
                "public",
                b(4, "13:30"),
                2,
                "We can see the DNS record. Issuing the certificate can take up to 48 hours.",
                "open",
            )
        ],
        assignee=2,
        tags=["domains", "ssl"],
    )
    ticket(
        1014,
        5,
        "Can we get SSO for contractors?",
        "account",
        "low",
        b(5, "10:00"),
        "Our contractors use a different identity provider. Can they use SSO too?",
        [("public", b(5, "11:00"), 4, "Good question. I'm checking with the product team.", "open")],
        assignee=4,
    )
    ticket(
        1015,
        6,
        "SSO login loops back to the sign-in page",
        "technical",
        "normal",
        b(5, "10:00"),
        "After signing in with Okta I land back on the sign-in page.",
        [
            ("public", b(5, "10:30"), 2, "Could you send the time of a failed attempt?", "pending"),
            ("public", b(4, "09:00"), 6, "Yesterday at 16:42, and again this morning at 08:55.", "open"),
        ],
        assignee=2,
        tags=["sso"],
    )
    ticket(
        1016,
        1,
        "Bulk import skips rows with accents",
        "technical",
        "normal",
        b(3, "14:00"),
        "Importing customers.csv skips every row whose name has an accent, like José or Zoë.",
        [
            ("public", b(3, "15:00"), 3, "Thanks Ivy, I can reproduce it. Passing it to engineering.", "open"),
            ("public", b(2, "09:30"), 1, "Any news? We have another import due on Friday.", None),
        ],
        assignee=3,
        attachments=[{"name": "customers.csv", "size": 52_118}],
    )
    ticket(
        1017,
        6,
        "Scheduled exports arrive a day late",
        "technical",
        "normal",
        b(3, "16:00"),
        "Our daily export, scheduled for 06:00, arrives the next day.",
        [
            (
                "public",
                b(2, "10:00"),
                3,
                "The schedule was saved in UTC. I've moved it to Dubai time; tomorrow's should be on time.",
                "open",
            )
        ],
        assignee=3,
    )
    ticket(
        1018,
        1,
        "Can't add a new user seat",
        "account",
        "normal",
        b(2, "11:00"),
        "Add seat is greyed out on our Team page, so I can't add our new hire.",
        [
            (
                "public",
                b(2, "11:40"),
                2,
                "Are you signed in as the billing owner? Only billing owners can add seats on Standard plans.",
                "pending",
            )
        ],
        assignee=2,
    )
    ticket(
        1019,
        8,
        "Menu sync stuck at 80%",
        "technical",
        "high",
        b(2, "09:30", hf),
        "The menu sync for our Tanjong Pagar site has been stuck at 80% since this morning.",
        [("public", b(2, "10:00", hf), 3, "Could you send the sync log from Settings > Diagnostics?", "pending")],
        assignee=3,
    )
    ticket(
        1020,
        6,
        "Dashboard charts are blank in Safari",
        "technical",
        "normal",
        b(2, "14:00"),
        "All charts on the dashboard are empty in Safari. Chrome is fine.",
        [("note", b(2, "14:30"), 3, "Reproduced on Safari 17. Waiting on the frontend team before replying.", "open")],
        assignee=3,
    )
    ticket(
        1021,
        7,
        "Payment terminal integration returns 502",
        "technical",
        "urgent",
        b(2, "15:00", hf),
        "Card payments at all three stores fail with a 502 from your terminal API.",
        [("public", b(2, "15:20", hf), 2, "We're treating this as an incident. Updates every hour.", "open")],
        assignee=2,
        tags=["payments", "incident"],
    )
    ticket(
        1022,
        1,
        "Webhook retries flood our endpoint",
        "technical",
        "high",
        b(1, "09:20"),
        "Since yesterday your webhooks retry the same event dozens of times a minute.",
        [
            (
                "note",
                b(1, "09:45"),
                2,
                "Standard plan: don't promise a fix date. Linked to engineering issue ENG-4471; "
                "Northwind is up for renewal next month, handle with care.",
                None,
            ),
            ("public", b(1, "10:00"), 2, "Thanks Ivy, we're looking at the retry queue now.", "open"),
        ],
        assignee=2,
        tags=["webhooks", "api", "retries", "integration"],
    )
    ticket(
        1023,
        1,
        "API rate limit lower than our plan says",
        "technical",
        "high",
        b(1, "15:00"),
        "We're getting 429 errors at about 300 requests a minute, but our plan allows 600.",
    )
    ticket(
        1024,
        5,
        "Webhooks hammering our server",
        "technical",
        "normal",
        b(1, "11:00"),
        "Same problem Ivy reported: your webhooks keep retrying events we already acknowledged.",
    )
    ticket(
        1025,
        8,
        "Recipe cards cut off when printed",
        "other",
        "normal",
        d(0, "08:10", hf),
        "Recipe cards print with the last ingredient cut off at the bottom of the page.",
    )
    ticket(1026, 1, "Update our billing contact", "billing", "low", d(0, "09:30"),
           "Please change our billing contact to Tom Reyes (tom@northwind.test).")  # fmt: skip

    return {
        "today": today.isoformat(),
        "now": iso(dt.datetime.combine(today, NOW_LOCAL) - dt.timedelta(hours=HOME_OFFSET)),
        "holidays": hols,
        "companies": [dict(c) for c in COMPANIES],
        "offsets": offset_of,
        "people": people,
        "tickets": tickets,
        "ratings": [{"ticket": t["id"], "score": t["rating"]} for t in tickets if t["rating"]],
        "canned": [dict(c) for c in CANNED],
        "articles": [a | {"body": list(a["body"])} for a in ARTICLES],
        "next_ticket": 1027,
        "next_id": 9000,
    }
