"""Beacon Support: a demo customer-support helpdesk with planted functional bugs, for checking what the AI QA Scanner
finds.

The bugs are listed in BUGS.md (the answer key), which is never served. Comments marking a planted bug (BUG-nn)
only appear in server-side code; the pages and scripts the scanner reads carry none.

Each visitor (cookie) gets a private copy of the demo world, kept in memory, so parallel scans never see each
other's changes. Logging in as the customer or the agent in the same browser shares that world.
"""

import datetime as dt
import hmac
import html
import json
import os
import re
import secrets
import threading
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from . import data

HERE = Path(__file__).resolve().parent
PAGES_DIR = HERE / "pages"
STATIC_DIR = HERE / "static"
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    ),
}
MAX_BODY = 1024 * 1024
MAX_SESSIONS = 1500
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
TAG = re.compile(r"[a-z0-9-]{1,24}")
OPEN = ("new", "open", "pending")
DONE = ("solved", "closed")
AGENT_STATUSES = ("open", "pending", "solved")

# path -> (page, title, who may open it)
PAGES = {
    "/": ("landing", "Welcome", None),
    "/login": ("login", "Log in", None),
    "/help": ("help", "Service policy", None),
    "/kb": ("kb", "Help centre", None),
    "/article": ("article", "Article", None),
    "/tickets": ("tickets", "My tickets", "customer"),
    "/new": ("new", "New ticket", "customer"),
    "/ticket": ("ticket", "Ticket", "customer"),
    "/company": ("company", "Company tickets", "customer"),
    "/queue": ("queue", "Queue", "agent"),
    "/work": ("work", "Ticket", "agent"),
    "/reports": ("reports", "Reports", "agent"),
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _text(body: dict, key: str, limit: int = 200) -> str:
    value = body.get(key, "")
    return value.strip()[:limit] if isinstance(value, str) else ""


def _int(value, message: str) -> int:
    try:
        return int(str(value).strip().lstrip("#"))
    except (TypeError, ValueError):
        raise ApiError(400, message) from None


# business hours


def is_business_day(day: dt.date, holidays: dict) -> bool:
    return day.weekday() < 5  # BUG-24: the desk's public holidays are not skipped


def business_minutes(start: dt.datetime, end: dt.datetime, offset: int, holidays: dict) -> int:
    """Minutes of business hours (Mon-Fri 09:00-17:30 local) between two UTC moments."""
    if end <= start:
        return 0
    s, e = start + dt.timedelta(hours=offset), end + dt.timedelta(hours=offset)
    total, day = 0.0, s.date()
    while day <= e.date():
        if is_business_day(day, holidays):
            lo = max(s, dt.datetime.combine(day, data.OPEN_AT))
            hi = min(e, dt.datetime.combine(day, data.CLOSE_AT))
            if hi > lo:
                total += (hi - lo).total_seconds()
        day += dt.timedelta(days=1)
    return int(total // 60)


def add_business(start: dt.datetime, minutes: int, offset: int, holidays: dict) -> dt.datetime:
    """The UTC moment when `minutes` of business hours have passed after start."""
    local = start + dt.timedelta(hours=offset)
    left = minutes
    day = local.date()
    while True:
        if is_business_day(day, holidays):
            lo = max(local, dt.datetime.combine(day, data.OPEN_AT))
            hi = dt.datetime.combine(day, data.CLOSE_AT)
            if hi > lo:
                span = (hi - lo).total_seconds() / 60
                if span >= left:
                    return lo + dt.timedelta(minutes=left) - dt.timedelta(hours=offset)
                left -= span
        day += dt.timedelta(days=1)


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: OrderedDict[str, dict] = OrderedDict()

    def session(self, sid: str | None) -> tuple[str, dict]:
        if sid and sid in self.sessions:
            self.sessions.move_to_end(sid)
            return sid, self.sessions[sid]
        sid = secrets.token_urlsafe(24)
        self.sessions[sid] = {"world": None, "user": None}
        while len(self.sessions) > MAX_SESSIONS:
            self.sessions.popitem(last=False)
        return sid, self.sessions[sid]

    @staticmethod
    def world(sess: dict) -> dict:
        if sess["world"] is None:
            sess["world"] = data.world(today())
        return sess["world"]

    def user(self, sess: dict) -> dict | None:
        if sess["user"] is None:
            return None
        return self.person(self.world(sess), sess["user"])

    @staticmethod
    def person(w: dict, pid) -> dict | None:
        return next((p for p in w["people"] if p["id"] == pid), None)

    @staticmethod
    def company(w: dict, cid) -> dict:
        return next(c for c in w["companies"] if c["id"] == cid)

    def signed_in(self, sess: dict, role: str = "customer") -> tuple[dict, dict]:
        user = self.user(sess)
        if not user:
            raise ApiError(401, "Please log in.")
        if user["role"] != role:
            raise ApiError(403, "That is for " + ("customers." if role == "customer" else "the support team."))
        return self.world(sess), user

    def me(self, sess: dict) -> dict:
        w = self.world(sess)
        user = self.user(sess)
        out = {"today": w["today"], "now": w["now"], "home_offset": data.HOME_OFFSET}
        if not user:
            return out | {"user": None}
        info = {k: user[k] for k in ("id", "name", "email", "role")}
        if user["role"] == "customer":
            c = self.company(w, user["company"])
            info |= {"admin": user["admin"], "company": c["name"], "plan": c["plan"], "domain": c["domain"]}
            info |= {"tz": c["tz"], "offset": c["offset"]}
        return out | {"user": info}

    def login(self, sess: dict, body: dict) -> dict:
        w = self.world(sess)
        email = _text(body, "email").lower()
        u = next((p for p in w["people"] if p["email"] == email and p.get("hash")), None)
        password = body.get("password")
        if not (u and isinstance(password, str)) or not hmac.compare_digest(
            u["hash"], data.password_hash(password, bytes.fromhex(u["salt"]))
        ):
            raise ApiError(401, "Incorrect email or password.")
        sess["user"] = u["id"]
        return self.me(sess)

    def policy(self, sess: dict) -> dict:
        w = self.world(sess)
        return {
            "holidays": [{"date": k, "name": v} for k, v in w["holidays"].items()],
            "targets": {p: {"first": f, "resolve": r} for p, (f, r) in data.TARGETS.items()},
            "companies": [{k: c[k] for k in ("name", "plan", "tz", "offset")} for c in w["companies"]],
            "today": w["today"],
        }

    # tickets: shared helpers

    @staticmethod
    def find(w: dict, tid: int) -> dict:
        t = next((t for t in w["tickets"] if t["id"] == tid), None)
        if not t:
            raise ApiError(404, "We couldn't find that ticket.")
        return t

    def is_agent(self, w: dict, pid) -> bool:
        p = self.person(w, pid)
        return bool(p and p["role"] == "agent")

    @staticmethod
    def pauses(t: dict, end: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
        out, log = [], t["status_log"]
        for i, (when, status) in enumerate(log):
            if status != "pending":
                continue
            stop = data.parse(log[i + 1][0]) if i + 1 < len(log) else end
            out.append((data.parse(when), min(stop, end)))
        return out

    def sla(self, w: dict, t: dict) -> dict:
        off = w["offsets"][t["company"]]
        hols = w["holidays"]
        now = data.parse(w["now"])
        created = data.parse(t["created"])
        first_target, res_target = data.TARGETS[t["sla_priority"]]  # BUG-27: targets of the priority it was opened with
        replies = [
            m
            for m in t["messages"]
            if self.is_agent(w, m["author"]) and m["kind"] in ("public", "note")  # BUG-26: internal notes count
        ]
        first_at = min((data.parse(m["at"]) for m in replies), default=None)
        done = t["status"] in DONE
        first_elapsed = business_minutes(created, first_at or now, off, hols)
        if first_at:
            first_state = "met" if first_elapsed <= first_target else "breached"
        elif done:
            first_state = "none"
        else:
            first_state = "breached" if first_elapsed > first_target else "running"
        end = data.parse(t["solved_at"]) if done and t["solved_at"] else now
        waiting = sum(business_minutes(a, b, off, hols) for a, b in self.pauses(t, end))
        res_elapsed = business_minutes(created, end, off, hols)  # BUG-25: time waiting on the customer isn't taken off
        if done:
            res_state = "met" if res_elapsed <= res_target else "breached"
        elif res_elapsed > res_target:
            res_state = "breached"
        else:
            res_state = "paused" if t["status"] == "pending" else "running"
        return {
            "first_target": first_target,
            "first_elapsed": first_elapsed,
            "first_state": first_state,
            "first_at": data.iso(first_at) if first_at else None,
            "first_due": data.iso(add_business(created, first_target, off, hols)),
            "res_target": res_target,
            "res_elapsed": res_elapsed,
            "res_state": res_state,
            "waiting": waiting,
            "res_due": data.iso(add_business(created, res_target, off, hols)),
        }

    def touch(self, w: dict, t: dict, status: str | None = None) -> None:
        t["updated"] = w["now"]
        if status and status != t["status"]:
            t["status"] = status
            t["status_log"].append([w["now"], status])
            if status == "solved":
                t["solved_at"] = w["now"]
            elif status in OPEN:
                t["solved_at"] = None
            if status == "closed":
                t["closed_at"] = w["now"]

    def message(self, w: dict, t: dict, author, kind: str, body: str, attachments=None) -> dict:
        m = {"id": w["next_id"], "author": author, "kind": kind, "body": body, "at": w["now"]}
        if attachments:
            m["attachments"] = attachments
        w["next_id"] += 1
        t["messages"].append(m)
        return m

    def author(self, w: dict, pid) -> dict:
        p = self.person(w, pid)
        if not p:
            return {"name": "Beacon Support", "agent": True}
        return {"name": p["name"], "agent": p["role"] == "agent"}

    def row(self, w: dict, t: dict) -> dict:
        requester = self.person(w, t["requester"])
        c = self.company(w, t["company"])
        assignee = self.person(w, t["assignee"]) if t["assignee"] else None
        out = {k: t[k] for k in ("id", "subject", "category", "priority", "status", "created", "updated", "tags")}
        return out | {
            "requester": requester["name"],
            "company": c["name"],
            "offset": c["offset"],
            "tz": c["tz"],
            "assignee": assignee["name"] if assignee else None,
            "assignee_id": t["assignee"],
        }

    # customer

    def my_tickets(self, sess: dict, query: dict) -> dict:
        w, user = self.signed_in(sess)
        arg = {k: (query.get(k) or [""])[0] for k in query}
        mine = [t for t in w["tickets"] if t["requester"] == user["id"]]
        tabs = {
            "open": lambda t: t["status"] in OPEN,
            "solved": lambda t: t["status"] == "solved",
            "closed": lambda t: t["status"] == "closed",
            "all": lambda t: True,
        }
        tab = arg.get("tab") if arg.get("tab") in tabs else "open"
        counts = {k: sum(1 for t in mine if f(t)) for k, f in tabs.items()}
        rows = [t for t in mine if tabs[tab](t)]
        q = arg.get("q", "").strip().lower()
        if q:
            rows = [t for t in rows if q in t["subject"].lower() or q == str(t["id"])]  # BUG-06: "#1022" never matches
        sort = arg.get("sort") or "updated"
        if sort == "priority":
            rows.sort(key=lambda t: (t["priority"], -t["id"]))  # BUG-07: sorts the names alphabetically
        elif sort == "newest":
            rows.sort(key=lambda t: (t["created"], t["id"]), reverse=True)
        else:
            rows.sort(key=lambda t: (t["updated"], t["id"]), reverse=True)
        try:
            page = max(1, int(arg.get("page") or 1))
        except ValueError:
            raise ApiError(400, "Bad page.") from None
        pages = max(1, -(-len(rows) // data.PAGE_SIZE))
        start = (page - 1) * data.PAGE_SIZE + (1 if page > 1 else 0)  # BUG-08: page 2 onwards starts one row late
        return {
            "tickets": [self.row(w, t) for t in rows[start : start + data.PAGE_SIZE]],
            "count": len(rows),
            "counts": counts,
            "tab": tab,
            "page": page,
            "pages": pages,
        }

    def company_tickets(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        if not user["admin"]:
            raise ApiError(403, "Only company admins can see every ticket of the company.")
        rows = [t for t in w["tickets"] if t["company"] == user["company"]]
        now = data.parse(w["now"])
        solved_recent = sum(
            1 for t in rows if t["solved_at"] and now - data.parse(t["solved_at"]) <= dt.timedelta(days=30)
        )  # BUG-17: "this month" is taken as the last 30 days, not the calendar month
        c = self.company(w, user["company"])
        return {
            "company": c["name"],
            "open": sum(1 for t in rows if t["status"] in ("new", "open")),
            "waiting": sum(1 for t in rows if t["status"] == "pending"),
            "solved_month": solved_recent,
            "tickets": [self.row(w, t) for t in sorted(rows, key=lambda t: (t["updated"], t["id"]), reverse=True)],
        }

    def customer_ticket(self, sess: dict, tid: int) -> tuple[dict, dict, dict]:
        w, user = self.signed_in(sess)
        t = self.find(w, tid)
        # BUG-15: nothing checks that the ticket belongs to the customer (or, for admins, to their company)
        return w, user, t

    def ticket_view(self, sess: dict, tid: int) -> dict:
        w, user, t = self.customer_ticket(sess, tid)
        mine = t["requester"] == user["id"]
        s = self.sla(w, t)
        public_reply = any(self.is_agent(w, m["author"]) and m["kind"] == "public" for m in t["messages"])
        messages = [
            {k: m[k] for k in ("id", "kind", "body", "at")}
            | {"author": self.author(w, m["author"]), "attachments": m.get("attachments", [])}
            for m in t["messages"]
            if m["kind"] != "note"
        ]
        cc = self.person(w, t["requester"])
        return self.row(w, t) | {
            "requester_email": cc["email"],
            "cc": t["cc"],
            "attachments": t["attachments"],
            "messages": messages,
            "reply_by": None if public_reply or t["status"] in DONE else s["first_due"],
            "solved_at": t["solved_at"],
            "rating": t["rating"],
            "mine": mine,
            "can_reply": t["status"] != "solved",  # BUG-09: closed tickets still take replies
            "can_close": mine and t["status"] in OPEN,
            "can_reopen": mine and t["status"] == "solved",
            "can_rate": t["status"] in DONE and (mine or user["admin"]),  # BUG-16: admins may rate colleagues' tickets
        }

    def transcript(self, sess: dict, tid: int) -> tuple[bytes, str, str]:
        w, _, t = self.customer_ticket(sess, tid)
        off = w["offsets"][t["company"]]

        def stamp(iso):
            return (data.parse(iso) + dt.timedelta(hours=off)).strftime("%a %d %b %Y %H:%M")

        lines = [f"Ticket #{t['id']}: {t['subject']}", f"Status: {t['status']}", ""]
        for m in t["messages"]:  # BUG-13: internal notes go into the download too
            who = self.author(w, m["author"])["name"]
            lines += [f"[{stamp(m['at'])}] {who}:", m["body"], ""]
        return "\n".join(lines).encode(), "text/plain; charset=utf-8", f"ticket-{t['id']}.txt"

    def create_ticket(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess)
        c = self.company(w, user["company"])
        subject = _text(body, "subject", 500)
        if not subject or len(subject) > data.SUBJECT_MAX:
            raise ApiError(400, f"Enter a subject of up to {data.SUBJECT_MAX} characters.")
        category = body.get("category")
        if category not in data.CATEGORIES:
            raise ApiError(400, "Choose a category.")
        priority = body.get("priority")
        if priority not in data.PRIORITIES:
            raise ApiError(400, "Choose a priority.")
        # BUG-01: Urgent is accepted on the Standard plan
        description = _text(body, "description", 5000)
        if len(description) < data.DESCRIPTION_MIN:
            raise ApiError(400, f"Describe the problem in at least {data.DESCRIPTION_MIN} characters.")
        cc = body.get("cc") or []
        if not isinstance(cc, list) or len(cc) > data.MAX_CC:
            raise ApiError(400, f"You can copy in up to {data.MAX_CC} colleagues.")
        cc = [str(x).strip().lower() for x in cc]
        for address in cc:
            if not EMAIL.fullmatch(address):
                raise ApiError(400, f"{address} isn't a valid email address.")
            # BUG-02: addresses outside the company's own domain are accepted
        files = body.get("attachments") or []
        if not isinstance(files, list):
            raise ApiError(400, "Bad attachments.")
        attachments = []
        for f in files:  # BUG-04: more than five files are accepted
            name = str((f or {}).get("name", ""))[:120]
            size = (f or {}).get("size")
            if not name or "." not in name or name.rsplit(".", 1)[1].lower() not in data.FILE_TYPES:
                raise ApiError(400, f"{name or 'That file'}: only PNG, JPG, PDF, TXT, LOG or CSV files.")
            if not isinstance(size, int) or size <= 0 or size > data.MAX_FILE_BYTES:
                raise ApiError(400, f"{name} is larger than 10 MB.")
            attachments.append({"name": name, "size": size})
        t = {
            "id": w["next_ticket"], "requester": user["id"], "company": c["id"], "subject": subject,
            "category": category, "priority": priority, "sla_priority": priority, "status": "new", "assignee": None,
            "tags": [], "cc": cc, "attachments": attachments, "created": w["now"], "updated": w["now"],
            "solved_at": None, "closed_at": None, "rating": None, "escalated": False, "merged_into": None,
            "messages": [], "status_log": [[w["now"], "new"]],
        }  # fmt: skip
        w["next_ticket"] += 1
        self.message(w, t, user["id"], "public", description, attachments)
        w["tickets"].append(t)
        return {"ticket": self.row(w, t), "target_minutes": data.TARGETS[priority][0]}

    def reply(self, sess: dict, tid: int, body: dict) -> dict:
        w, user, t = self.customer_ticket(sess, tid)
        text = _text(body, "body", 5000)
        if not text:
            raise ApiError(400, "Write your reply.")
        if t["status"] == "solved":
            raise ApiError(409, "This ticket is solved. Reopen it to reply.")
        self.message(w, t, user["id"], "public", text)
        self.touch(w, t)  # BUG-11: a reply while "Waiting on you" leaves the ticket waiting, so its clock stays paused
        return self.ticket_view(sess, tid)

    def reopen(self, sess: dict, tid: int) -> dict:
        w, user, t = self.customer_ticket(sess, tid)
        if t["requester"] != user["id"]:
            raise ApiError(403, "Only the person who raised this ticket can reopen it.")
        if t["status"] != "solved":
            raise ApiError(409, "Only solved tickets can be reopened.")
        age = data.parse(w["now"]) - data.parse(t["created"])  # BUG-10: counted from the day it was raised
        if age > dt.timedelta(days=data.REOPEN_DAYS):
            raise ApiError(409, "This ticket was solved more than 7 days ago. Please open a new ticket.")
        self.touch(w, t, "open")
        return self.ticket_view(sess, tid)

    def close(self, sess: dict, tid: int) -> dict:
        w, user, t = self.customer_ticket(sess, tid)
        if t["requester"] != user["id"]:
            raise ApiError(403, "Only the person who raised this ticket can mark it as solved.")
        if t["status"] not in OPEN:
            raise ApiError(409, "This ticket is already solved.")
        self.message(w, t, None, "system", f"{user['name']} marked this ticket as solved.")
        self.touch(w, t, "solved")
        return self.ticket_view(sess, tid)

    def rate(self, sess: dict, tid: int, body: dict) -> dict:
        w, user, t = self.customer_ticket(sess, tid)
        if t["status"] not in DONE:
            raise ApiError(409, "You can rate a ticket once it's solved.")
        if t["requester"] != user["id"] and not user["admin"]:  # BUG-16 (see ticket_view)
            raise ApiError(403, "Only the person who raised this ticket can rate it.")
        score = body.get("score")
        if isinstance(score, bool) or score not in (1, 2, 3, 4, 5):
            raise ApiError(400, "Choose 1 to 5 stars.")
        # BUG-12: a ticket that already has a rating can be rated again (and both count)
        t["rating"] = score
        w["ratings"].append({"ticket": t["id"], "score": score})
        return self.ticket_view(sess, tid)

    # knowledge base

    def kb(self, sess: dict, q: str) -> dict:
        w = self.world(sess)
        q = q.strip().lower()
        rows = w["articles"]
        if q:
            rows = [a for a in rows if q in a["title"].lower()]  # BUG-18: the article text isn't searched
        return {"articles": [{k: a[k] for k in ("id", "title", "category", "yes", "no")} for a in rows]}

    def article(self, sess: dict, aid: int) -> dict:
        w = self.world(sess)
        a = next((a for a in w["articles"] if a["id"] == aid), None)
        if not a:
            raise ApiError(404, "We couldn't find that article.")
        return a

    def vote(self, sess: dict, aid: int, body: dict) -> dict:
        a = self.article(sess, aid)
        # BUG-19: nothing stops the same visitor voting again and again
        a["yes" if body.get("helpful") is True else "no"] += 1
        return a

    # agents

    def queue(self, sess: dict) -> dict:
        w, user = self.signed_in(sess, "agent")
        rows = []
        for t in w["tickets"]:
            if t["status"] == "closed":
                continue
            s = self.sla(w, t)
            open_ = t["status"] in OPEN
            views = ["open"] if open_ else []
            if t["assignee"] is None:  # BUG-21: solved tickets nobody owns land in Unassigned too
                views.append("unassigned")
            if open_ and t["assignee"] == user["id"]:
                views.append("mine")
            if open_ and s["res_state"] == "breached":  # BUG-22: a missed first-response target isn't overdue
                views.append("overdue")
            if open_ and t["priority"] in ("urgent", "high"):
                views.append("priority")
            rows.append(self.row(w, t) | {"sla": s, "views": views})
        rows.sort(key=lambda r: r["id"])
        counts = {
            v: sum(1 for r in rows if v in r["views"]) for v in ("open", "unassigned", "mine", "overdue", "priority")
        }
        return {"tickets": rows, "counts": counts, "now": w["now"], "home_offset": data.HOME_OFFSET}

    def work(self, sess: dict, tid: int) -> dict:
        w, user = self.signed_in(sess, "agent")
        t = self.find(w, tid)
        requester = self.person(w, t["requester"])
        c = self.company(w, t["company"])
        messages = [
            {k: m[k] for k in ("id", "kind", "body", "at")}
            | {"author": self.author(w, m["author"]), "attachments": m.get("attachments", [])}
            for m in t["messages"]
        ]
        agents = [
            {"id": p["id"], "name": p["name"], "away": p["away"], "away_until": p.get("away_until")}
            for p in w["people"]
            if p["role"] == "agent"
        ]
        return self.row(w, t) | {
            "requester_email": requester["email"],
            "plan": c["plan"],
            "cc": t["cc"],
            "attachments": t["attachments"],
            "messages": messages,
            "sla": self.sla(w, t),
            "agents": agents,
            "canned": w["canned"],
            "escalated": t["escalated"],
            "merged_into": t["merged_into"],
            "me": {"id": user["id"], "name": user["name"]},
            "now": w["now"],
        }

    def set_status(self, w: dict, t: dict, status: str) -> None:
        if status not in AGENT_STATUSES:
            raise ApiError(400, "Choose Open, Waiting on customer or Solved.")
        if t["status"] == "closed":
            raise ApiError(409, f"Ticket #{t['id']} is closed.")
        # BUG-30: a ticket can be solved before the customer has had any public reply
        self.touch(w, t, status)

    def agent_reply(self, sess: dict, tid: int, body: dict) -> dict:
        w, user = self.signed_in(sess, "agent")
        t = self.find(w, tid)
        if t["status"] == "closed":
            raise ApiError(409, "This ticket is closed.")
        text = _text(body, "body", 5000)
        if not text:
            raise ApiError(400, "Write a message.")
        kind = "note" if body.get("kind") == "note" else "public"
        self.message(w, t, user["id"], kind, text)
        if kind == "public":
            if t["assignee"] is None:
                t["assignee"] = user["id"]
            self.set_status(w, t, body.get("status") if body.get("status") in AGENT_STATUSES else "pending")
        else:
            t["updated"] = w["now"]
        return self.work(sess, tid)

    def update(self, sess: dict, tid: int, body: dict) -> dict:
        w, _ = self.signed_in(sess, "agent")
        t = self.find(w, tid)
        if t["status"] == "closed":
            raise ApiError(409, "This ticket is closed.")
        if "assignee" in body:
            aid = body.get("assignee")
            if aid is not None:
                if not self.is_agent(w, aid):
                    raise ApiError(400, "Choose an agent.")
                # BUG-29: agents who are away can still be given tickets
            t["assignee"] = aid
        if body.get("priority"):
            if body["priority"] not in data.PRIORITIES:
                raise ApiError(400, "Choose a priority.")
            t["priority"] = body["priority"]  # BUG-27 (see sla): the SLA targets keep the old priority
        if body.get("status") and body["status"] != t["status"]:
            self.set_status(w, t, body["status"])
        t["updated"] = w["now"]
        return self.work(sess, tid)

    def tags(self, sess: dict, tid: int, body: dict) -> dict:
        w, _ = self.signed_in(sess, "agent")
        t = self.find(w, tid)
        tag = _text(body, "tag", 40)
        if body.get("remove"):
            if tag in t["tags"]:
                t["tags"].remove(tag)
            return self.work(sess, tid)
        if not TAG.fullmatch(tag):
            raise ApiError(400, "Tags use lowercase letters, numbers and hyphens (up to 24).")
        if tag in t["tags"]:
            raise ApiError(409, f"The ticket already has the tag {tag}.")
        t["tags"].append(tag)  # BUG-32: the limit of 5 tags isn't applied
        return self.work(sess, tid)

    def escalate(self, sess: dict, tid: int, body: dict) -> dict:
        w, user = self.signed_in(sess, "agent")
        t = self.find(w, tid)
        if t["status"] not in OPEN:
            raise ApiError(409, "Only open tickets can be escalated.")
        if t["escalated"]:
            raise ApiError(409, "This ticket is already with Tier 2.")
        reason = _text(body, "reason", 500)
        if not reason:
            raise ApiError(400, "Say why you're escalating.")
        t["escalated"] = True
        if "tier-2" not in t["tags"]:
            t["tags"].append("tier-2")
        t["priority"] = "high"  # BUG-31: an Urgent ticket is lowered to High instead of staying Urgent
        self.message(w, t, user["id"], "note", f"Escalated to Tier 2: {reason}")
        t["updated"] = w["now"]
        return self.work(sess, tid)

    def merge(self, sess: dict, tid: int, body: dict) -> dict:
        w, user = self.signed_in(sess, "agent")
        source = self.find(w, tid)
        target_id = _int(body.get("target"), "Enter the number of the ticket to merge into.")
        target = next((t for t in w["tickets"] if t["id"] == target_id), None)
        if not target:
            raise ApiError(404, f"There's no ticket #{target_id}.")
        if target is source:
            raise ApiError(400, "A ticket can't be merged into itself.")
        if source["status"] == "closed" or target["status"] == "closed":
            raise ApiError(409, "Closed tickets can't be merged.")
        # BUG-34: tickets from different companies can be merged
        requester = self.person(w, source["requester"])
        company = self.company(w, source["company"])
        # BUG-33: the source ticket's messages are not copied into the target
        self.message(
            w,
            target,
            None,
            "system",
            f"Ticket #{source['id']} ({source['subject']}) from {requester['name']}, {company['name']}, "
            "was merged into this ticket.",
        )
        target["updated"] = w["now"]
        self.message(w, source, user["id"], "note", f"Merged into #{target['id']}.")
        source["merged_into"] = target["id"]
        self.touch(w, source, "closed")
        return self.work(sess, tid)

    def bulk(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess, "agent")
        ids = body.get("ids")
        if not isinstance(ids, list) or not ids:
            raise ApiError(400, "Select at least one ticket.")
        action, value = body.get("action"), body.get("value")
        targets = [self.find(w, _int(i, "Bad ticket.")) for i in ids]
        targets = [t for t in targets if t["status"] != "closed"]
        for t in targets:
            if action == "assign_me":
                t["assignee"] = user["id"]
                t["updated"] = w["now"]
            elif action == "status":
                self.set_status(w, t, value)
            elif action == "tag":
                tag = str(value or "").strip()
                if not TAG.fullmatch(tag):
                    raise ApiError(400, "Tags use lowercase letters, numbers and hyphens (up to 24).")
                if tag not in t["tags"]:
                    t["tags"].append(tag)
            else:
                raise ApiError(400, "Choose an action.")
        return self.queue(sess) | {"updated": len(targets)}

    # reports

    def report_rows(self, w: dict) -> list[dict]:
        first_day = (dt.date.fromisoformat(w["today"]) - dt.timedelta(days=29)).isoformat()
        rows = []
        for t in w["tickets"]:
            local_day = (data.parse(t["created"]) + dt.timedelta(hours=data.HOME_OFFSET)).date().isoformat()
            if local_day < first_day or t["merged_into"]:
                continue
            s = self.sla(w, t)
            rows.append(
                {
                    "id": t["id"],
                    "subject": t["subject"],
                    "company": self.company(w, t["company"])["name"],
                    "priority": t["priority"],
                    "status": t["status"],
                    "day": local_day,
                    "first": s["first_elapsed"] if s["first_at"] else None,
                    "breached": "breached" in (s["first_state"], s["res_state"]),
                    "rating": t["rating"],
                }
            )
        return rows

    def reports(self, sess: dict) -> dict:
        w, _ = self.signed_in(sess, "agent")
        rows = self.report_rows(w)
        now = dt.date.fromisoformat(w["today"])
        days = [(now - dt.timedelta(days=k)).isoformat() for k in range(7, 0, -1)]  # BUG-35: today is left out
        per_day = [{"day": d, "count": sum(1 for r in rows if r["day"] == d)} for d in days]
        answered = [r["first"] for r in rows if r["first"] is not None]
        avg_first = sum(answered) / len(rows) if rows else 0  # BUG-36: divides by every ticket, answered or not
        breached = sum(1 for r in rows if r["breached"])
        answered_count = len(answered)
        breach_rate = 100 * breached / answered_count if answered_count else 0  # BUG-37: out of answered tickets only
        scores = [r["score"] for r in w["ratings"]]
        happy = sum(1 for s in scores if s >= 3)  # BUG-38: 3-star ratings count as satisfied
        return {
            "period_start": (now - dt.timedelta(days=29)).isoformat(),
            "today": w["today"],
            "tickets": len(rows),
            "per_day": per_day,
            "avg_first": round(avg_first),
            "breached": breached,
            "breach_rate": round(breach_rate, 1),
            "csat": round(100 * happy / len(scores), 1) if scores else None,
            "ratings": {str(k): scores.count(k) for k in (5, 4, 3, 2, 1)},
            "rows": rows,
        }

    def reports_csv(self, sess: dict) -> tuple[bytes, str, str]:
        w, _ = self.signed_in(sess, "agent")
        lines = ["Ticket,Subject,Company,Priority,Status,Created,First response (minutes),SLA breached,Rating"]
        for r in self.report_rows(w):
            first = "" if r["first"] is None else r["first"]
            lines.append(
                f"{r['id']},{r['subject']},{r['company']},{r['priority']},{r['status']},{r['day']},{first},"
                f"{'yes' if r['breached'] else 'no'},{r['rating'] or ''}"
            )  # BUG-39: subjects with commas aren't quoted, so their columns shift
        return ("\n".join(lines) + "\n").encode(), "text/csv; charset=utf-8", "beacon-tickets.csv"


def render(path: str, store: Store, sess: dict, status_page: str | None = None) -> bytes:
    name, title, _ = PAGES[path] if not status_page else (status_page, "Page not found", None)
    if status_page == "403":
        title = "Not for this account"
    user = store.user(sess)
    help_links = [("/kb", "kb", "Help centre"), ("/help", "help", "Service policy")]
    if not user:
        links = [("/", "landing", "Welcome")] + help_links
        account = '<a href="/login" id="login-link">Log in</a>'
    else:
        if user["role"] == "customer":
            links = [("/tickets", "tickets", "My tickets"), ("/new", "new", "New ticket")]
            if user.get("admin"):
                links.append(("/company", "company", "Company tickets"))
        else:
            links = [("/queue", "queue", "Queue"), ("/reports", "reports", "Reports")]
        links += help_links
        account = f'<span class="who">{html.escape(user["name"].split()[0])}</span>'
        account += '<button type="button" id="logout" class="link">Log out</button>'
    nav = "".join(f'<a href="{h}" data-nav="{k}">{t}</a>' for h, k, t in links)
    script = f'<script src="/static/{name}.js" defer></script>' if (STATIC_DIR / f"{name}.js").exists() else ""
    out = (PAGES_DIR / "_layout.html").read_text()
    values = {
        "title": html.escape(title),
        "page": name,
        "role": user["role"] if user else "",
        "nav": nav,
        "account": account,
        "content": (PAGES_DIR / f"{name}.html").read_text(),
        "scripts": script,
    }
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out.encode()


def make_handler(store: Store | None = None):
    store = store or Store()
    static = {f.name: f for f in STATIC_DIR.iterdir() if f.is_file() and f.suffix in STATIC_TYPES}

    class Handler(BaseHTTPRequestHandler):
        server_version = "beacon"

        def log_message(self, fmt, *args):
            pass

        def _session(self) -> tuple[str, dict, bool]:
            sid = None
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                sid = cookie["be_sid"].value if "be_sid" in cookie else None
            except CookieError:
                pass
            new_sid, sess = store.session(sid)
            return new_sid, sess, new_sid != sid

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            if self._new_sid:
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie", f"be_sid={self._sid}; Path=/; HttpOnly; SameSite=Lax{secure}")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Bad request.") from None
            if length > MAX_BODY:
                raise ApiError(413, "Request too large.")
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                raise ApiError(400, "Send JSON.") from None
            if not isinstance(payload, dict):
                raise ApiError(400, "Send a JSON object.")
            return payload

        def do_HEAD(self):
            self._handle("GET")

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method: str):
            self._sid, self._new_sid = None, False
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            query = parse_qs(url.query)
            try:
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                if path == "/robots.txt":
                    return self._send(200, b"User-agent: *\nAllow: /\n", "text/plain")
                if path.startswith("/static/") and path[8:] in static:
                    f = static[path[8:]]
                    return self._send(200, f.read_bytes(), STATIC_TYPES[f.suffix])
                with store.lock:
                    self._sid, sess, self._new_sid = self._session()
                    if path.startswith("/api/"):
                        body = self._body() if method == "POST" else {}
                        result = self._api(sess, method, path, body, query)
                        if isinstance(result, tuple):
                            raw, ctype, filename = result
                            extra = {"Content-Disposition": f'attachment; filename="{filename}"'}
                            return self._send(200, raw, ctype, extra)
                        return self._json(200, result)
                    if method != "GET":
                        return self._send(405, b"Method not allowed", "text/plain", {"Allow": "GET, HEAD"})
                    if path not in PAGES:
                        return self._send(404, render("/", store, sess, "404"), "text/html; charset=utf-8")
                    role = PAGES[path][2]
                    user = store.user(sess)
                    if role and not user:
                        location = "/login?next=" + quote(self.path, safe="")
                        return self._send(302, b"", "text/plain", {"Location": location})
                    if role and (user["role"] != role or (path == "/company" and not user.get("admin"))):
                        return self._send(403, render("/", store, sess, "403"), "text/html; charset=utf-8")
                    return self._send(200, render(path, store, sess), "text/html; charset=utf-8")
            except ApiError as err:
                return self._json(err.status, {"ok": False, "error": str(err)})
            except Exception:
                return self._json(500, {"ok": False, "error": "Internal Server Error"})

        def _api(self, sess: dict, method: str, path: str, body: dict, query: dict):
            q = lambda k: (query.get(k) or [""])[0]  # noqa: E731
            if method == "GET":
                gets = {
                    "/api/me": lambda: store.me(sess),
                    "/api/policy": lambda: store.policy(sess),
                    "/api/tickets": lambda: store.my_tickets(sess, query),
                    "/api/company": lambda: store.company_tickets(sess),
                    "/api/kb": lambda: store.kb(sess, q("q")),
                    "/api/queue": lambda: store.queue(sess),
                    "/api/reports": lambda: store.reports(sess),
                    "/api/reports.csv": lambda: store.reports_csv(sess),
                }
                if path in gets:
                    return gets[path]()
                routes = (
                    (r"/api/tickets/(\d+)", lambda i: store.ticket_view(sess, int(i))),
                    (r"/api/tickets/(\d+)/transcript\.txt", lambda i: store.transcript(sess, int(i))),
                    (r"/api/kb/(\d+)", lambda i: store.article(sess, int(i))),
                    (r"/api/work/(\d+)", lambda i: store.work(sess, int(i))),
                )
            else:
                posts = {
                    "/api/login": lambda: store.login(sess, body),
                    "/api/logout": lambda: sess.update(user=None) or {"ok": True},
                    "/api/tickets": lambda: store.create_ticket(sess, body),
                    "/api/work/bulk": lambda: store.bulk(sess, body),
                }
                if path in posts:
                    return posts[path]()
                routes = (
                    (r"/api/tickets/(\d+)/reply", lambda i: store.reply(sess, int(i), body)),
                    (r"/api/tickets/(\d+)/reopen", lambda i: store.reopen(sess, int(i))),
                    (r"/api/tickets/(\d+)/close", lambda i: store.close(sess, int(i))),
                    (r"/api/tickets/(\d+)/rate", lambda i: store.rate(sess, int(i), body)),
                    (r"/api/kb/(\d+)/vote", lambda i: store.vote(sess, int(i), body)),
                    (r"/api/work/(\d+)/reply", lambda i: store.agent_reply(sess, int(i), body)),
                    (r"/api/work/(\d+)/update", lambda i: store.update(sess, int(i), body)),
                    (r"/api/work/(\d+)/tags", lambda i: store.tags(sess, int(i), body)),
                    (r"/api/work/(\d+)/escalate", lambda i: store.escalate(sess, int(i), body)),
                    (r"/api/work/(\d+)/merge", lambda i: store.merge(sess, int(i), body)),
                )
            for pattern, run in routes:
                m = re.fullmatch(pattern, path)
                if m:
                    return run(m.group(1))
            raise ApiError(404, "Not found.")

    return Handler


def serve(env: dict[str, str] | None = None) -> None:
    env = dict(os.environ if env is None else env)
    port = int(env.get("PORT", "8089"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler())
    print(f"Beacon Support listening on :{port}", flush=True)
    httpd.serve_forever()
