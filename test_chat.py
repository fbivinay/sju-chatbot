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
assert ask({M[0]: (200, sse("Hello ", "there", thought="planning..."))}) == ("Hello there", [M[0]])

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
reset()
for _ in range(5):
    ask({M[0]: (200, sse("ok"))})
assert ask({M[0]: (200, sse("A")), M[1]: (200, sse("B"))}) == ("B", [M[1]])
reset()
main._today[M[0]] = 20
assert ask({M[0]: (200, sse("A")), M[1]: (200, sse("B"))}) == ("B", [M[1]])
main._quota_day -= 1   # those 20 were yesterday's
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
# knowledge-base chunks; a notices question reads announcements; anything else reads nothing.
rows = [{"content": "stored MCA text", "source_url": MCA, "page_name": "mca"},
        {"content": "stored hostel text", "source_url": "https://www.sju.edu.in/hostel.php", "page_name": "hostel"}]
real_search = main.search_kb
main.search_kb = lambda q: rows
pages = {main.DATES_PAGE: "<p>MCA: last date 5 January 2027</p>", main.NEWS_PAGE: "<p>6 October: exam notice</p>"}
try:
    for question, expected in [("When is the last date to apply for MCA?", [main.DATES_PAGE]),
                               ("Any latest announcements?", [main.NEWS_PAGE]),
                               ("Tell me about the MCA syllabus", [])]:
        main._live_cache.clear()
        fetched, restore = serve(pages)
        try:
            context = asyncio.run(main.gather_context(question))
        finally:
            restore()
        assert fetched == expected, (question, fetched)
        assert "stored MCA text" in context and "stored hostel text" in context
        assert ("=== LIVE FROM THE OFFICIAL SJU WEBSITE" in context) == bool(expected)
    assert "last date 5 January 2027" not in context   # the syllabus question read nothing live

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
