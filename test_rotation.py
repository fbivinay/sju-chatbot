"""Offline check of the Gemini model rotation - no network, no API key, no quota.

    python test_rotation.py
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


def ask(responses):
    """responses: model -> (status, body) or an exception. Returns (answer, models called)."""
    called = []

    def handler(request):
        model = request.url.path.split("/models/")[1].split(":")[0]
        called.append(model)
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

# A stream that breaks midway keeps the partial answer and says so.
reset()
answer, called = ask({M[0]: (200, Dropped())})
assert called == [M[0]] and answer.startswith("Half an ") and "connection dropped" in answer

print("rotation OK")
