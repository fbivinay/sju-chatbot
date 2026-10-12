# SJU Chatbot

AI chatbot for **St Joseph's University, Bengaluru** — answers questions about
programmes, admissions, fees, campus, and more. A FastAPI backend serves a
single-page website clone of sju.edu.in with an embedded chat widget, powered by
Google Gemini and grounded in real content scraped from the university site.

Live demo deploys to Vercel as a Python serverless function.

---

## How it works

```
User question
     │
     ▼
FastAPI  /chat  (main.py)
     │
     ├─► Supabase full-text search ── top 6 relevant chunks of real SJU content
     │        (match_sju_knowledge, Postgres plainto_tsquery + ts_rank)
     │
     ├─► Live sju.edu.in pages ── for questions about dates, deadlines or
     │        notices: the important-dates and announcements pages, read
     │        while the student waits (cached 15 min)
     │
     └─► Gemini — first free-tier model with quota left (8 in rotation)
              system prompt = live pages + stored chunks + built-in facts
              → answer streams back word by word
```

Three knowledge sources are combined, newest first:

1. **Live official pages** — what changes within a day: the important-dates
   page (deadlines, entrance tests, interviews per programme) and announcements,
   read from sju.edu.in at question time, so they are what the site says right
   now. Only `*.sju.edu.in` is read; if the site is slow or down the bot answers
   from the knowledge base instead (pages time out after 3 s).
2. **Supabase knowledge base** — ~960 text chunks from ~290 SJU pages,
   re-scraped every day, retrieved by **Postgres full-text search**
   (keyword/relevance ranking, no embeddings).
3. **Built-in knowledge** (`KNOWLEDGE` in `main.py`) — core facts (address,
   rankings, course list, contacts) hard-coded so the bot always answers common
   questions, even with no database.

Gemini is used **only to write the final answer**, from what it is given — it
doesn't browse. It is told never to guess specifics (fees, dates, names): if none
of the sources state them, it says so and points to the official page or phone.

---

## Tech stack

- **Backend:** FastAPI + Python (Vercel Python serverless)
- **AI:** Google Gemini free tier, rotating across 8 models (`MODELS` in `main.py`)
- **Knowledge base:** Supabase (Postgres) full-text search
- **Frontend:** plain HTML/JS, no framework — `static/embed.html` (chat UI),
  `static/widget.js` (one-tag embed loader), `static/index.html` (demo site)
- **Hosting:** Vercel

---

## Environment variables

| Variable          | Needed for            | Notes                                         |
|-------------------|-----------------------|-----------------------------------------------|
| `GEMINI_API_KEY`  | Chat answers          | Required. Get one free at ai.google.dev       |
| `SUPABASE_URL`    | Knowledge-base search | Optional — bot still runs on built-in facts   |
| `SUPABASE_KEY`    | Knowledge-base search | Publishable key (`sb_publishable_…`) — the public keys can only read |

If Supabase vars are missing, the bot falls back to built-in knowledge only.

---

## Model rotation and streaming

Each Gemini free-tier model has its own quota (a few requests per minute and
20–500 per day), so `main.py` rotates through eight of them. Together that is
about 60 requests a minute and 1,100+ a day before Gemma's large daily pool.

- **Order is fastest first.** The first six start answering in ~1–2 s; the
  last two need a higher thinking level and add ~8 s.
- **No waiting on full models.** The server counts each model's requests per
  minute, per day and tokens per minute, and only calls one with room left.
- **Fails over fast.** A 429 or 503 comes back in under a second and the next
  model is tried at once; a model that hasn't started answering within 6 s is
  abandoned. A 429 benches that model for a minute (per-minute limit) or until
  the daily reset, so later questions skip it entirely. Nothing reaches the
  student unless every model is unavailable at once.
- **Streams.** `POST /chat/stream` sends the answer as server-sent events, so
  the first words appear about a second after the model starts writing.

To change models or limits, edit the `MODELS` table — the numbers come from
AI Studio → Rate limits for the key's project. `GET /health` shows each
model's usage on the instance that answers (Vercel can run several, so AI
Studio stays the full picture). `python test_chat.py` checks the rotation and
the live page reading offline, without spending quota.

---

## Deploy to Vercel

1. Push this repo to GitHub.
2. In Vercel: **Add New → Project → Import** the repo. `vercel.json` builds
   `main.py` as a Python serverless function — no build command needed.
3. **Settings → Environment Variables:** add `GEMINI_API_KEY` (and
   `SUPABASE_URL` / `SUPABASE_KEY` for the knowledge base).
4. Redeploy so the env vars take effect. You get a URL like
   `sju-chatbot.vercel.app`.

---

## Embedding the chatbot in the university website

The university does **not** host the bot. It stays on Vercel; their site loads
it with one tag placed just before `</body>` on any page (PHP, WordPress,
plain HTML — it makes no difference):

```html
<script src="https://sju-chatbot.vercel.app/static/widget.js" defer></script>
```

That is the whole integration. `widget.js` adds a floating button and opens
`static/embed.html` in an iframe, so:

- **No CSS or JavaScript conflicts.** The chat UI renders in its own document,
  isolated from the university's stylesheets, jQuery version, and page scripts.
- **No API keys on their server.** `GEMINI_API_KEY` stays in Vercel; the browser
  only ever talks to this app.
- **Updates need no action from them.** Fixes ship on redeploy — the tag stays.
- **Nothing to install.** No npm, no build step, no server changes.

To put the widget on every page at once, add the tag to the site's shared
footer include (e.g. `footer.php`) rather than to each page.

**Only SJU's sites can embed it.** The chat UI is served with
`Content-Security-Policy: frame-ancestors 'self' https://sju.edu.in https://*.sju.edu.in`
(`FRAME_ANCESTORS` in `main.py`), so any other website that adds the tag gets an
empty frame, and the API sends no CORS headers, so other sites' pages can't call
it from a browser either. If the university hosts the widget on another domain,
add it to `FRAME_ANCESTORS`. (Scripts outside a browser can still reach the API —
the Gemini rate limits and model rotation are the backstop there.)

`static/embed.html` is the chat UI itself, and `static/index.html` (the demo
site clone) loads it through the very same `widget.js` — one copy of the chat
code, so the demo can never drift from what the university runs.

---

## Knowledge base (Supabase)

The `sju_knowledge` table holds the scraped content:

| column       | type        |
|--------------|-------------|
| `id`         | bigint (PK) |
| `content`    | text        |
| `source_url` | text        |
| `page_name`  | text        |
| `created_at` | timestamptz |

**One-time setup:** run `supabase_setup.sql` in the Supabase SQL Editor. It
creates the full-text index, the `match_sju_knowledge(query, match_count)`
function that `main.py` calls, the read-only rules for public keys, the
no-duplicates index and the staging table + swap function the refresh uses.

**Daily refresh:** `.github/workflows/refresh-knowledge.yml` runs
`scrape_playwright.py` every day at 03:00 IST on GitHub Actions (free for public
repos; also runnable by hand from the Actions tab). The scraper pulls SJU's
`sitemap.xml`, renders each page with Playwright and chunks the text, then:

- loads the chunks into `sju_knowledge_staging`, never into the live table;
- calls `swap_sju_knowledge()`, which replaces the live table with the staged
  chunks **in one transaction** — the bot sees the old set or the new one, never
  a half-loaded or doubled table;
- keeps one copy of each text (a unique index on `md5(content)` makes duplicates
  impossible whatever writes to the table);
- refuses a scrape that comes back far smaller than what's live (less than 60%),
  so a site outage or redesign can't wipe the knowledge base — the run fails,
  yesterday's data stays live, and GitHub emails the repo owner.

It needs one repository secret, `SUPABASE_SECRET_KEY`: a Supabase **secret**
key (`sb_secret_…`, Supabase → Project Settings → API Keys → Secret keys), since
the publishable key can only read. Never commit it. GitHub pauses scheduled
workflows in a repo with no commits for 60 days — re-enable it from the Actions
tab if that happens.

---

## Endpoints

| Method | Path      | Purpose                            |
|--------|-----------|------------------------------------|
| GET    | `/`                  | Demo site clone, loads the widget       |
| GET    | `/static/widget.js`  | Embed loader for the university site    |
| GET    | `/static/embed.html` | The chat UI itself (runs in the iframe) |
| POST   | `/chat/stream`       | `{ question, history }` → answer as server-sent events (used by the widget) |
| POST   | `/chat`              | `{ question, history }` → `{ answer }` in one reply |
| GET    | `/health`            | Status / config check                   |

---

## Local run

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...   SUPABASE_URL=...   SUPABASE_KEY=...
uvicorn main:app --reload
# open http://localhost:8000

python test_chat.py   # offline checks: model rotation, live page reading, embedding lock
node test_widget.js   # offline check: which programme the option cards point at
```
