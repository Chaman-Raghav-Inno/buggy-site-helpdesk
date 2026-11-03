"""Beacon's server-side planted bugs stay planted (BUGS.md) and nothing it serves gives them away."""

import datetime as dt
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from beacon import data, server

T = server.today()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())

    def request(self, path: str, body=None) -> tuple[int, bytes, dict]:
        payload = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=payload, headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def get(self, path: str, **query):
        status, raw, _ = self.request(path + ("?" + urlencode(query) if query else ""))
        return status, json.loads(raw)

    def post(self, path: str, body: dict | None = None):
        status, raw, _ = self.request(path, body or {})
        return status, json.loads(raw)

    def login(self, who: str, password: str = data.PASSWORD) -> int:
        return self.post("/api/login", {"email": f"{who}@beacon.test", "password": password})[0]


@pytest.fixture
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(server.Store()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def ivy(base_url):
    c = Client(base_url)
    assert c.login("ivy") == 200
    return c


@pytest.fixture
def sam(base_url):
    c = Client(base_url)
    assert c.login("sam") == 200
    return c


def new_ticket(**extra) -> dict:
    return {
        "subject": "Printer setup",
        "category": "technical",
        "priority": "normal",
        "description": "The label printer won't pair with the new tablet.",
    } | extra


def test_pages_and_access(base_url, ivy, sam):
    visitor = Client(base_url)
    for path in ("/", "/help", "/login", "/kb", "/article?id=1"):
        assert visitor.request(path)[0] == 200, path
    status, _, headers = visitor.request("/tickets")
    assert status == 302 and headers["Location"] == "/login?next=%2Ftickets"
    assert visitor.request("/nope")[0] == 404 and visitor.request("/healthz")[1] == b"ok"
    assert ivy.request("/queue")[0] == 403 and ivy.get("/api/queue")[0] == 403
    assert sam.request("/tickets")[0] == 403 and sam.request("/company")[0] == 403
    for path in ("/tickets", "/new", "/ticket?id=1022", "/company"):
        assert ivy.request(path)[0] == 200, path
    for path in ("/queue", "/work?id=1022", "/reports"):
        assert sam.request(path)[0] == 200, path


def test_answer_key_is_never_served_or_hinted(base_url):
    visitor = Client(base_url)
    for path in ("/BUGS.md", "/static/../BUGS.md", "/server.py", "/data.py"):
        assert visitor.request(path)[0] == 404, path
    for folder in (server.STATIC_DIR, server.PAGES_DIR):
        for f in folder.iterdir():
            assert not re.search(r"bug|planted", f.read_text(), re.I), f.name


def test_business_hours():
    hols = {"2027-01-01": "New Year's Day"}
    fri = dt.datetime(2026, 11, 6, 12, 0)  # 16:00 in Dubai
    mon = dt.datetime(2026, 11, 9, 6, 0)  # 10:00 in Dubai
    assert server.business_minutes(fri, mon, 4, hols) == 90 + 60
    assert server.add_business(fri, 120, 4, hols) == dt.datetime(2026, 11, 9, 5, 30)
    holiday = dt.datetime(2026, 12, 31, 12, 0)
    assert server.business_minutes(holiday, dt.datetime(2027, 1, 4, 5, 0), 4, hols) == 90 + 510 + 0  # BUG-24


def test_submitting(ivy):
    assert ivy.post("/api/tickets", new_ticket(priority="urgent"))[0] == 200  # BUG-01: Northwind is on Standard
    assert ivy.post("/api/tickets", new_ticket(cc=["someone@gmail.test"]))[0] == 200  # BUG-02
    assert ivy.post("/api/tickets", new_ticket(cc=["not-an-email"]))[0] == 400
    files = [{"name": f"log{i}.txt", "size": 1000} for i in range(7)]
    assert ivy.post("/api/tickets", new_ticket(attachments=files))[0] == 200  # BUG-04
    assert ivy.post("/api/tickets", new_ticket(attachments=[{"name": "Shot.PNG", "size": 10}]))[0] == 200
    assert ivy.post("/api/tickets", new_ticket(attachments=[{"name": "setup.exe", "size": 10}]))[0] == 400
    assert ivy.post("/api/tickets", new_ticket(description="too short"))[0] == 400


def test_my_tickets(ivy):
    assert ivy.get("/api/tickets", tab="all", q="#1022")[1]["count"] == 0  # BUG-06
    assert ivy.get("/api/tickets", tab="all", q="1022")[1]["count"] == 1
    rows = ivy.get("/api/tickets", tab="all", sort="priority")[1]["tickets"]
    assert [r["priority"] for r in rows][:3] == ["high", "high", "high"]
    everything = ivy.get("/api/tickets", tab="all", sort="priority", page=3)[1]["tickets"]
    assert everything[-1]["priority"] == "normal"  # BUG-07: alphabetical, so Normal comes after Low
    first = ivy.get("/api/tickets", tab="open")[1]
    second = ivy.get("/api/tickets", tab="open", page=2)[1]
    seen = {t["id"] for t in first["tickets"] + second["tickets"]}
    assert first["count"] == 6 and len(seen) == 5  # BUG-08: the 6th open ticket is on no page


def test_conversation(ivy, sam):
    assert ivy.get("/api/tickets/1002")[1]["can_reply"] is True  # BUG-09: closed
    assert ivy.post("/api/tickets/1002/reply", {"body": "One more question"})[0] == 200
    assert ivy.post("/api/tickets/1004/reopen")[0] == 409  # BUG-10: solved 2 days ago, raised 20 days ago
    assert ivy.post("/api/tickets/1012/reopen")[0] == 200
    ivy.post("/api/tickets/1018/reply", {"body": "Yes, I'm the billing owner."})
    assert ivy.get("/api/tickets/1018")[1]["status"] == "pending"  # BUG-11
    assert ivy.post("/api/tickets/1004/rate", {"score": 5})[0] == 200
    assert ivy.post("/api/tickets/1004/rate", {"score": 1})[0] == 200  # BUG-12
    status, raw, _ = ivy.request("/api/tickets/1022/transcript.txt")
    assert "don't promise a fix date" in raw.decode()  # BUG-13
    assert all(m["kind"] != "note" for m in ivy.get("/api/tickets/1022")[1]["messages"])
    assert ivy.get("/api/tickets/1021")[0] == 200  # BUG-15: Halcyon Foods' ticket
    assert ivy.get("/api/tickets/9999")[0] == 404


def test_company(ivy):
    tom = ivy.get("/api/tickets/1009")[1]
    assert not tom["mine"] and tom["can_rate"] and not tom["can_reopen"]  # BUG-16
    assert ivy.post("/api/tickets/1009/rate", {"score": 4})[0] == 200
    assert ivy.post("/api/tickets/1009/reopen")[0] == 403
    w = data.world(T)
    last_month = data.month_start(T) - dt.timedelta(days=1)
    if (T - last_month).days <= 30:
        solved = ivy.get("/api/company")[1]["solved_month"]
        in_month = [
            t for t in w["tickets"] if t["company"] == 1 and t["solved_at"] and t["solved_at"][:7] == T.isoformat()[:7]
        ]
        assert solved > len(in_month)  # BUG-17: last month's last day counts


def test_knowledge_base(ivy):
    assert ivy.get("/api/kb", q="SAML")[1]["articles"] == []  # BUG-18: it's in "Setting up single sign-on"
    assert len(ivy.get("/api/kb", q="sign-on")[1]["articles"]) == 1
    before = ivy.get("/api/kb/2")[1]["yes"]
    for _ in range(3):
        ivy.post("/api/kb/2/vote", {"helpful": True})
    assert ivy.get("/api/kb/2")[1]["yes"] == before + 3  # BUG-19


def test_queue_and_sla(sam):
    rows = {r["id"]: r for r in sam.get("/api/queue")[1]["tickets"]}
    assert "unassigned" in rows[1010]["views"] and rows[1010]["status"] == "solved"  # BUG-21
    assert rows[1023]["sla"]["first_state"] == "breached" and "overdue" not in rows[1023]["views"]  # BUG-22
    assert rows[1017]["sla"]["first_state"] == "breached"  # BUG-24: 2h30m without Founders' Day
    assert rows[1011]["sla"]["res_state"] == "breached" and rows[1011]["sla"]["waiting"] > 900  # BUG-25
    assert rows[1020]["sla"]["first_state"] == "met"  # BUG-26: only an internal note so far
    after = sam.post("/api/work/1014/update", {"priority": "urgent"})[1]
    assert after["priority"] == "urgent" and after["sla"]["res_target"] == 80 * 60  # BUG-27


def test_working_tickets(sam):
    assert sam.post("/api/work/1023/update", {"assignee": 4})[1]["assignee"] == "Leo Brandt"  # BUG-29: away
    assert sam.post("/api/work/1024/update", {"status": "solved"})[1]["status"] == "solved"  # BUG-30
    assert sam.post("/api/work/1021/escalate", {"reason": "Needs engineering"})[1]["priority"] == "high"  # BUG-31
    for tag in ("one", "two"):
        sam.post("/api/work/1022/tags", {"tag": tag})
    assert len(sam.get("/api/work/1022")[1]["tags"]) == 6  # BUG-32
    assert sam.post("/api/work/1022/tags", {"tag": "Bad Tag"})[0] == 400
    assert sam.post("/api/work/1013/merge", {"target": 1013})[0] == 400
    sam.post("/api/work/1015/merge", {"target": 1022})
    bodies = [m["body"] for m in sam.get("/api/work/1022")[1]["messages"]]
    assert not any("Okta" in b for b in bodies)  # BUG-33: Mei's messages stay behind
    assert sam.post("/api/work/1025/merge", {"target": 1016})[0] == 200  # BUG-34: Halcyon into Northwind
    assert sam.post("/api/work/1016/merge", {"target": 1002})[0] == 409


def test_reports(sam, ivy):
    ivy.post("/api/tickets", new_ticket())
    r = sam.get("/api/reports")[1]
    assert r["per_day"][-1]["day"] != T.isoformat()  # BUG-35
    rows = r["rows"]
    answered = [x["first"] for x in rows if x["first"] is not None]
    assert r["avg_first"] == round(sum(answered) / len(rows))  # BUG-36
    assert r["breach_rate"] == round(100 * r["breached"] / len(answered), 1)  # BUG-37: should be / len(rows)
    assert r["csat"] == 75.0  # BUG-38: 4 of the 8 ratings are 4 or 5 stars
    status, raw, _ = sam.request("/api/reports.csv")
    line = next(x for x in raw.decode().splitlines() if x.startswith("1004,"))
    assert line.startswith("1004,Invoice, credit note")  # BUG-39
