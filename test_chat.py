"""Offline checks of the model rotation and live page reading - no network, no key, no quota.

    python test_chat.py
"""
import asyncio
import json
import os
import time

os.environ.setdefault("GEMINI_API_KEY", "test")
import httpx  # noqa: E402
import main   # noqa: E402

M = [m[0] for m in main.MODELS]
GEMMA = M.index("gemma-4-26b-a4b-it")
DAILY_429 = json.dumps({"error": {"details": [{"violations": [
    {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})


def sse(*texts, thought=None):
    parts = ([{"text": thought, "thought": True}] if thought else []) + [{"text": t} for t in texts]
    return "data: " + json.dumps({"candidates": [{"content": {"parts": parts}}]}) + "\n\n"


class Dropped(httpx.AsyncByteStream):
    """A stream that sends one chunk, then loses the connection."""
    async def __aiter__(self):
        yield sse("Half an ").encode()
        raise httpx.ReadError("connection reset")


def reset():
    for model in M:
        main._recent[model], main._today[model], main._skip_until[model] = [], 0, 0.0


def skipped_for(model):
    return main._skip_until[model] - time.time()


def ask(responses, sent=None):
    """responses: model -> (status, body) or an exception. Returns (answer, models called)."""
    called = []

    def handler(request):
        model = request.url.path.split("/models/")[1].split(":")[0]
        called.append(model)
        if sent is not None:
            sent.append(json.loads(request.content))
        r = responses.get(model, (503, "{}"))
        if isinstance(r, Exception):
            raise r
        status, body = r
        return httpx.Response(status, stream=body) if isinstance(body, httpx.AsyncByteStream) \
            else httpx.Response(status, text=body)

    async def collect():
        body = {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]}
        return "".join([t async for t in main.gemini_stream(body)])

    real = httpx.AsyncClient
    httpx.AsyncClient = lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    try:
        return asyncio.run(collect()), called
    finally:
        httpx.AsyncClient = real


# A healthy first model answers; its thinking never reaches the student.
reset()
sent = []
assert ask({M[0]: (200, sse("Hello ", "there", thought="planning..."))}, sent) == ("Hello there", [M[0]])
assert sent[0]["tools"] == [{"google_search": {}}]   # Gemini may search for what the content lacks
# A searched answer counts toward the daily cap; at the cap, search isn't offered.
GROUNDED = "data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]},
                                                  "groundingMetadata": {"webSearchQueries": ["q"]}}]}) + "\n\n"
main._searches[:] = [int(time.time() // 86400), main.SEARCH_DAY_MAX - 1]
reset()
ask({M[0]: (200, GROUNDED)})
assert main._searches[1] == main.SEARCH_DAY_MAX
sent = []
reset()
ask({M[0]: (200, sse("ok"))}, sent)
assert "tools" not in sent[0]
main._searches[:] = [0, 0]

# Daily quota used up: benched until the next reset, the next model answers.
reset()
answer, called = ask({M[0]: (429, DAILY_429), M[1]: (200, sse("ok"))})
now = time.time()
next_reset = (int((now - main.DAY_START) // 86400) + 1) * 86400 + main.DAY_START
assert (answer, called) == ("ok", M[:2]) and abs(skipped_for(M[0]) - (next_reset - now)) < 5

# Per-minute 429 benches for 60s, an overloaded 503 for 20s, a timeout for 20s.
reset()
answer, called = ask({M[0]: (429, "{}"), M[1]: (503, "{}"), M[2]: httpx.ReadTimeout("slow"),
                      M[3]: (200, sse("ok"))})
assert (answer, called) == ("ok", M[:4])
assert 55 < skipped_for(M[0]) <= 60 and 15 < skipped_for(M[1]) <= 20 and 15 < skipped_for(M[2]) <= 20
# ...and the next question goes straight to a model that can answer.
assert ask({M[3]: (200, sse("fast"))}) == ("fast", [M[3]])

# A 400 benches a model only when another model answers the same question:
# a request every model rejects must not take the whole bot down.
reset()
assert ask({M[0]: (400, "{}"), M[1]: (200, sse("ok"))}) == ("ok", M[:2]) and skipped_for(M[0]) > 500
reset()
answer, called = ask({m: (400, "{}") for m in M})
assert (answer, called) == (main.BUSY_MSG, M) and all(skipped_for(m) <= 0 for m in M)

# Our own counts keep a model out before Google has to say no: RPM, RPD, then a new day.
RPM, RPD = main.MODELS[0][1:3]
reset()
main._recent[M[0]] = [(time.time(), 10)] * (RPM - 1)
ask({M[0]: (200, sse("ok"))})
assert ask({M[0]: (200, sse("A")), M[1]: (200, sse("B"))}) == ("B", [M[1]])
reset()
main._today[M[0]] = RPD
assert ask({M[0]: (200, sse("A")), M[1]: (200, sse("B"))}) == ("B", [M[1]])
main._quota_day -= 1   # those were yesterday's
assert ask({M[0]: (200, sse("A"))}) == ("A", [M[0]])

# Gemma's 16K tokens-per-minute: a full minute's budget skips it.
reset()
for model in M[:GEMMA]:
    main._skip_until[model] = time.time() + 100
main._recent[M[GEMMA]] = [(time.time(), 15_990)]
assert ask({M[GEMMA]: (200, sse("A")), M[GEMMA + 1]: (200, sse("B"))}) == ("B", [M[GEMMA + 1]])

# A stream that breaks midway - dropped connection or a 503 "high demand" error chunk -
# hands the half answer to the next model, which carries on from there: one answer, no retyping.
MID_503 = sse("Half an ") + "data: " + json.dumps({"error": {"code": 503}}) + "\n\n"
for broken, bench in ((Dropped(), 20), (MID_503, 300)):
    reset()
    sent = []
    answer, called = ask({M[0]: (200, broken), M[1]: (200, sse("answer."))}, sent)
    assert (answer, called) == ("Half an answer.", M[:2]), answer
    assert sent[1]["contents"][-2:] == [{"role": "model", "parts": [{"text": "Half an "}]},
                                        {"role": "user", "parts": [{"text": main.CONTINUE}]}]
    assert bench - 5 < skipped_for(M[0]) <= bench

# A half-finished word is held back, so the next model continues from a clean break.
reset()
sent = []
answer, _ = ask({M[0]: (200, sse("Half an ans") + "data: " + json.dumps({"error": {"code": 503}}) + "\n\n"),
                 M[1]: (200, sse("answer."))}, sent)
assert answer == "Half an answer." and sent[1]["contents"][-2]["parts"][0]["text"] == "Half an "

# An error after the model said it was done changes nothing.
reset()
DONE_THEN_503 = ("data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": "All of it."}]},
                                                         "finishReason": "STOP"}]}) + "\n\n"
                 + "data: " + json.dumps({"error": {"code": 503}}) + "\n\n")
assert ask({M[0]: (200, DONE_THEN_503)}) == ("All of it.", [M[0]])

# No model finishes: the half answer stays, marked as cut short.
reset()
answer, called = ask({M[0]: (200, Dropped())})
assert called == M and answer.startswith("Half an ") and answer.endswith("cut short - please ask again.)")

print("rotation OK")


# ── Live pages from sju.edu.in ───────────────────────────────────────────────
def serve(pages):
    """Route the live reader at fake pages: url -> html, or (status, html, final_url)."""
    fetched = []

    def handler(request):
        url = str(request.url)
        fetched.append(url)
        page = pages.get(url, (404, "", url))
        status, body, final = page if isinstance(page, tuple) else (200, page, url)
        if final != url:   # a redirect
            return httpx.Response(302, headers={"location": final})
        return httpx.Response(status, text=body, headers={"content-type": "text/html; charset=utf-8"})

    real = httpx.AsyncClient
    httpx.AsyncClient = lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    return fetched, lambda: setattr(httpx, "AsyncClient", real)


MCA = "https://www.sju.edu.in/mca.php"
PAGE = ("<html><head><script>var x=1</script></head><body><header>Home Admissions Menu</header>"
        "<nav>BCA MCA BBA menu</nav><h1>Master of Computer Applications</h1>"
        "<p>Applications open till 31 May 2026. Fees: Karnataka &#8377;1,50,000</p>"
        "<footer>Contact us</footer></body></html>")

# Menus, header, footer and scripts never reach the prompt.
assert main.page_text(PAGE) == ("Master of Computer Applications Applications open till 31 May 2026. "
                                "Fees: Karnataka ₹1,50,000")

# A long page keeps its opening (headings) plus the passages that match the question...
long_text = "Important Dates header row " + " ".join(f"Programme{i} closes {i} June." for i in range(400))
picked = main.relevant(long_text + " MCA last date to apply is 5 January 2027.", ["mca"])
assert picked.startswith("Important Dates header row") and "MCA last date" in picked and len(picked) < 4000
# ...and with nothing matching, the top of the page, where the newest notices are.
assert main.relevant(long_text, ["zzz"]).startswith("Important Dates header row")


def dates_page(programmes_per_cycle):
    """The important-dates page as SJU builds it: CYCLE tabs, then one table per cycle,
    a header row of column names, rows of names and dates - and stale commented-out cells."""
    head = "".join(f"<th>{h}</th>" for h in ("Sl. No.", "Programme Name", "Last Date to Apply",
                                               "SJU Entrance Test (SJUET) Date", "Date of Interview"))
    tables = []
    for cycle, programmes in enumerate(programmes_per_cycle, 1):
        rows = "".join(f"<tr><td>{n}</td><td>{p}</td><td>{n % 28 + 1} January 2026</td>"
                       f"<td>{n % 27 + 2} January 2026</td><td>—</td><!-- <td>{n} May 2025</td> --></tr>"
                       for n, p in enumerate(programmes, 1))
        tables.append(f"<table><tr>{head}</tr>{rows}</table>")
    return ("<h1>Important Dates</h1><ul><li>CYCLE 1</li><li>CYCLE 2</li><li>CYCLE 3</li></ul>"
            + "".join(tables))


filler = [f"Master of Science (M.Sc.) in Subject {i}" for i in range(60)]
DATES_TABLE = dates_page([filler[:20] + ["Master of Computer Applications (MCA)"] + filler[20:],
                          filler[:40] + ["Master of Computer Applications (MCA)"] + filler[40:],
                          ["Master of Science (M.Sc.) in Computer Science"] + filler + ["Master of Computer Applications (MCA)"]])

# Each table row becomes one line naming its cycle and columns; commented-out cells are dropped.
rows_text = main.page_text(DATES_TABLE)
assert ("Cycle 1: Programme Name: Master of Computer Applications (MCA); Last Date to Apply: 22 January 2026; "
        "SJU Entrance Test (SJUET) Date: 23 January 2026.") in rows_text, rows_text[:400]
assert "May 2025" not in rows_text

# Pages are read once, then served from the cache; failures are retried only after a pause.
main._live_cache.clear()
fetched, restore = serve({MCA: PAGE})
try:
    assert asyncio.run(main.read_live([MCA, "https://www.sju.edu.in/gone.php"])) == {MCA: main.page_text(PAGE)}
    asyncio.run(main.read_live([MCA, "https://www.sju.edu.in/gone.php"]))
    assert fetched == [MCA, "https://www.sju.edu.in/gone.php"]   # second call: nothing re-fetched
finally:
    restore()

# A redirect off SJU's own site is not read.
main._live_cache.clear()
fetched, restore = serve({MCA: (302, "", "https://evil.example/page"), "https://evil.example/page": "<p>spam</p>"})
try:
    assert asyncio.run(main.read_live([MCA])) == {}
finally:
    restore()

# Choosing pages: a deadline question reads the important-dates page live, next to the
# knowledge-base chunks; a notices question gets the notice list; anything else reads nothing.
rows = [{"content": "stored MCA text", "source_url": MCA, "page_name": "mca"},
        {"content": "stored hostel text", "source_url": "https://www.sju.edu.in/hostel.php", "page_name": "hostel"}]
real_search = main.search_kb
main.search_kb = lambda q: rows
def card(href, title):
    return f'<div class="event-content"><a href="{href}"><p>date</p><h5>{title}</h5></a></div>'
NEWS = (card("https://sjudata.s3.ap-south-1.amazonaws.com/Notice+%E2%80%93+Hall+Ticket(End+Sem).pdf",
             "22 October 2026 : Notice - Hall Ticket (End Semester October 2026)")
        + card("announcement-detail.php?slug=special-holiday", "17 October 2026 : Notice - Special Holiday")
        + card("https://sjudata.s3.ap-south-1.amazonaws.com/a/Rank+Holders.pdf", "17 August 2026 : Provisional Rank Holders List"))
pages = {main.DATES_PAGE: "<p>MCA: last date 5 January 2027</p>", main.NEWS_PAGE: NEWS}
try:
    for question, expected in [("When is the last date to apply for MCA?", [main.DATES_PAGE]),
                               ("Any latest announcements?", []),
                               ("Tell me about the MCA syllabus", [])]:
        main._live_cache.clear()
        fetched, restore = serve(pages)
        try:
            context = asyncio.run(main.gather_context(question))
        finally:
            restore()
        assert sorted(fetched) == sorted(expected + [main.HOME_PAGE, main.NEWS_PAGE]), (question, fetched)
        assert "stored MCA text" in context and "stored hostel text" in context
        assert ("=== LIVE FROM THE OFFICIAL SJU WEBSITE" in context) == bool(expected)
    assert "last date 5 January 2027" not in context   # the syllabus question read nothing live
    assert "SJU ANNOUNCEMENTS" not in context            # and no notice names its words

    # Notices: a title naming the question's words is listed first with its own link, even
    # without "notice" in the question; "(", ")" are escaped so the Markdown link holds.
    main._live_cache.clear()
    fetched, restore = serve(pages)
    try:
        hall = asyncio.run(main.gather_context("When will I get my hall ticket?"))
        latest = asyncio.run(main.gather_context("Any latest announcements?"))
    finally:
        restore()
    notes = hall.split("=== SJU ANNOUNCEMENTS")[1].splitlines()
    assert notes[1] == ("- 22 October 2026 : Notice - Hall Ticket (End Semester October 2026) "
                        "(https://sjudata.s3.ap-south-1.amazonaws.com/Notice+%E2%80%93+Hall+Ticket%28End+Sem%29.pdf)"), notes
    assert "(passed)" not in notes[1]
    assert "https://www.sju.edu.in/announcement-detail.php?slug=special-holiday" in latest
    assert all(main._url_key(u) in main.known_urls(hall) for _, u in main.notices(NEWS)[:1])

    # The deadline question gets the named programme's row from every cycle - picking by
    # its "last date to apply" once sent Gemini the column headings instead.
    main._live_cache.clear()
    fetched, restore = serve({main.DATES_PAGE: DATES_TABLE})
    try:
        mca = asyncio.run(main.gather_context("When is the last date to apply for MCA?"))
        msc_cs = asyncio.run(main.gather_context("Last date for MSc Computer Science application?"))
    finally:
        restore()
    assert all(f"Cycle {c}: Programme Name: Master of Computer Applications (MCA);" in mca for c in (1, 2, 3)), mca[:600]
    assert "Programme Name: Master of Science (M.Sc.) in Computer Science;" in msc_cs, msc_cs[:600]
    # "Who is the registrar" reads the officials pages; a word in the homepage menu reads
    # the page it links to; event links and off-site links are never followed.
    MGMT = main.OFFICIALS_PAGES[0]
    OMBUD = "https://www.sju.edu.in/about/ombudsperson.php"
    home = ('<a href="/about/ombudsperson.php">Ombud Person</a><a href="events-detail.php?slug=ombudsperson-talk">'
            'Ombudsperson talk</a><a href="https://evil.example/ombudsperson">x</a>')
    main._live_cache.clear()
    fetched, restore = serve({MGMT: "<p>Dr Syed Wajeed Registrar Member Secretary</p>", main.HOME_PAGE: home,
                              OMBUD: "<p>Ombudsperson: Dr A</p>"})
    try:
        reg = asyncio.run(main.gather_context("Who is the registrar?"))
        ombud = asyncio.run(main.gather_context("Who is the ombudsperson"))
    finally:
        restore()
    assert "Dr Syed Wajeed Registrar" in reg, reg[:400]
    assert "Ombudsperson: Dr A" in ombud and OMBUD in fetched
    assert not any("evil" in u or "detail" in u for u in fetched), fetched
finally:
    main.search_kb = real_search

print("live pages OK")


# ── Embedding: only SJU's sites may frame the chat UI or use the API from a browser ──
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app)
page = client.get("/static/embed.html")
assert page.status_code == 200
assert page.headers["content-security-policy"] == "frame-ancestors 'self' https://sju.edu.in https://*.sju.edu.in"
preflight = client.options("/chat/stream", headers={"Origin": "https://evil.example",
                                                    "Access-Control-Request-Method": "POST",
                                                    "Access-Control-Request-Headers": "content-type"})
assert "access-control-allow-origin" not in preflight.headers

print("embedding OK")


# ── Caching: Vercel gives every deployed file the same timestamp ─────────────────
# A same-size edit ("Admissions Open 2026" -> "Admissions" + padding) must still reach
# a browser that cached the old file.
import tempfile  # noqa: E402
from fastapi import FastAPI  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "embed.html")
    cached = TestClient(FastAPI())
    cached.app.mount("/s", main.SJUStaticFiles(directory=d))
    with open(path, "w") as f:
        f.write("Admissions Open 2026")
    os.utime(path, (1540000000, 1540000000))
    old = cached.get("/s/embed.html")
    assert "last-modified" not in old.headers
    with open(path, "w") as f:
        f.write("Admissions          ")   # same size
    os.utime(path, (1540000000, 1540000000))   # same frozen timestamp
    new = cached.get("/s/embed.html", headers={"If-None-Match": old.headers["etag"],
                                               "If-Modified-Since": "Sat, 20 Oct 2018 01:46:40 GMT"})
    assert new.status_code == 200 and new.text.startswith("Admissions "), new.status_code
    # ...while an unchanged file still gets a cheap 304
    assert cached.get("/s/embed.html", headers={"If-None-Match": new.headers["etag"]}).status_code == 304

print("caching OK")


# ── Answer guards ───────────────────────────────────────────────────────────────
from datetime import date  # noqa: E402

# Past dates are tagged before the model sees them ("Cycle 3: 31 May 2026" was "upcoming" in October).
today = date(2026, 10, 22)
assert main.mark_passed("Cycle 3: Last Date to Apply: 31 May 2026.", today) == "Cycle 3: Last Date to Apply: 31 May 2026 (passed)."
assert main.mark_passed("Apply by 5th January 2027, interview 22 Oct 2026", today) == "Apply by 5th January 2027, interview 22 Oct 2026"
assert main.mark_passed("21 October 2026 and 31 February 2026", today) == "21 October 2026 (passed) and 31 February 2026"

# Links the model makes up are dropped; links in the prompt (in any spelling) stay.
allowed = main.known_urls("see sju.edu.in/faq.php and https://www.sju.edu.in/programmes/msc-in-big-data-analytics")
keep = "[FAQ](https://www.sju.edu.in/faq) "
assert main.drop_unknown_links(keep, allowed) == keep
assert main.drop_unknown_links("[MSc BDA](http://sju.edu.in/programmes/msc-in-big-data-analytics/) ", allowed).endswith("analytics/) ")
assert main.drop_unknown_links("[Report format](https://www.sju.edu.in/pg-project-report-format.pdf). ", allowed) == "[Report format]. "
# A link cut off before its ")" is dropped, even when its start looks allowed (fails closed).
assert main.drop_unknown_links("[x](https://www.sju.edu.in/faq", allowed) == "[x]"
assert main.drop_unknown_links("[x](https://evil.example/a[cite:", allowed) == "[x]"

# Google's "[cite: 1]" markers are removed, even when split across streamed pieces.
async def fake_stream(body):
    for piece in ["Cycle 1: 15 January 2026 [cite: ", "1] and [cite: 2, 3]", " closed. "]:
        yield piece
real_stream, main.gemini_stream = main.gemini_stream, fake_stream
real_ctx, main.gather_context = main.gather_context, lambda q: asyncio.sleep(0, "")
async def collect():
    return "".join([t async for t in main.answer_stream(main.ChatRequest(question="mca"))])
try:
    got = asyncio.run(collect())
finally:
    main.gemini_stream, main.gather_context = real_stream, real_ctx
assert got == "Cycle 1: 15 January 2026 and closed. ", got

# The prompt opens with the same text for every question (billed at 10% when repeated);
# the date and per-question content come last.
assert main.SYSTEM_PROMPT.index("=== SJU KNOWLEDGE BASE ===") < main.SYSTEM_PROMPT.index("{today}") \
    < main.SYSTEM_PROMPT.index("{extra}")

# The AI gets the same programme list - and counts - as the chat's UG/PG buttons.
assert "Undergraduate - 40 programmes:" in main.KNOWLEDGE and "PhD - 13 programmes:" in main.KNOWLEDGE

print("answer guards OK")


# ── Rate limit + locked health ──────────────────────────────────────────────────
main._rl.clear(); main._rl_day.clear()
rl = TestClient(main.app)
hdr = {"X-Real-IP": "203.0.113.9"}
ok = sum(rl.post("/chat", json={"question": ""}, headers=hdr).status_code == 200 for _ in range(main.RATE_MAX))
assert ok == main.RATE_MAX, ok                                   # first RATE_MAX allowed
assert rl.post("/chat", json={"question": ""}, headers=hdr).status_code == 429   # then blocked
assert rl.post("/chat/stream", json={"question": ""}, headers=hdr).status_code == 429   # shared across endpoints
assert rl.post("/chat", json={"question": ""}, headers={"X-Real-IP": "198.51.100.2"}).status_code == 200  # other IP fine

# A spoofed client x-forwarded-for does NOT change the key or reset the block.
assert rl.post("/chat", json={"question": ""},
               headers={"X-Real-IP": "203.0.113.9", "X-Forwarded-For": "1.2.3.4"}).status_code == 429

# LRU stays bounded and keeps the active abuser (most-recently-used), evicting idle IPs.
main._rl.clear(); main._rl_day.clear()
saved_cap = main.RATE_MAX_IPS
main.RATE_MAX_IPS = 100
try:
    for _ in range(main.RATE_MAX + 1):                           # drive 203.0.113.9 to the limit
        rl.post("/chat", json={"question": ""}, headers=hdr)
    for i in range(300):                                         # flood distinct IPs...
        rl.post("/chat", json={"question": ""}, headers={"X-Real-IP": f"10.0.{i // 256}.{i % 256}"})
        if i % 20 == 0:                                          # ...while the abuser keeps hitting
            rl.post("/chat", json={"question": ""}, headers=hdr)
    assert len(main._rl) <= main.RATE_MAX_IPS                    # hard cap holds
    assert "203.0.113.9" in main._rl                             # active abuser kept, not evicted
    assert rl.post("/chat", json={"question": ""}, headers=hdr).status_code == 429   # still blocked
finally:
    main.RATE_MAX_IPS = saved_cap
    main._rl.clear(); main._rl_day.clear()

# IPv6 addresses in the same /64 share one bucket, including compressed and IPv4-mapped forms.
def ip_of(raw):
    return main.client_ip(type("R", (), {"headers": {"x-real-ip": raw}, "client": None})())
assert ip_of("2001:db8:1:2:aaaa::1") == ip_of("2001:db8:1:2:bbbb::9") == "2001:db8:1:2::/64"
assert ip_of("2001:db8::1") == ip_of("2001:db8:0:0:ffff::9") == "2001:db8::/64"   # "::" compression
assert ip_of("not-an-ip") == "invalid" and ip_of("") == "unknown"
# IPv4-mapped IPv6 keys on the embedded host (not one shared ::/64 bucket).
assert ip_of("::ffff:1.2.3.4") == ip_of("1.2.3.4") == "1.2.3.4"
assert ip_of("::ffff:1.2.3.4") != ip_of("::ffff:5.6.7.8")   # distinct clients don't collide
assert ip_of("2002:0102:0304::1") == "1.2.3.4"              # 6to4 embeds the IPv4

# /health hides per-model quota unless the token matches
main.HEALTH_TOKEN = ""
assert "models" not in rl.get("/health").json()                 # no token set: minimal
main.HEALTH_TOKEN = "s3cret"
assert "models" not in rl.get("/health").json()                 # token set, none given: minimal
assert "models" not in rl.get("/health?token=wrong").json()
assert "models" in rl.get("/health?token=s3cret").json()        # correct token: full
main.HEALTH_TOKEN = ""

# Rule 9 tells the model the content is data, not commands
assert "untrusted REFERENCE DATA" in main.SYSTEM_PROMPT

# When Supabase is present, the shared counter is authoritative across instances.
class _FakeSB:
    def __init__(self, allowed): self.allowed, self.calls = allowed, []
    def rpc(self, name, params):
        self.calls.append((name, params))
        return type("E", (), {"execute": lambda self_: type("R", (), {"data": self.allowed})()})()
g = {"X-Real-IP": "203.0.113.200"}
main._rl.clear(); main._rl_day.clear()
main.sb = _FakeSB(True)
assert rl.post("/chat", json={"question": ""}, headers=g).status_code == 200      # DB says allow
main.sb = _FakeSB(False)
assert rl.post("/chat", json={"question": ""}, headers=g).status_code == 429      # DB says block
assert main.sb.calls[0] == ("sju_rate_check", {"p_ip": "203.0.113.200"})   # no caller-set limits
# DB unreachable -> fall back to the in-memory limit, never crash.
class _BrokenSB:
    def rpc(self, *a, **k): raise RuntimeError("db down")
main.sb = _BrokenSB()
main._rl.clear(); main._rl_day.clear()
assert rl.post("/chat", json={"question": ""}, headers=g).status_code == 200      # memory allows
main.sb = None

print("hardening OK")
