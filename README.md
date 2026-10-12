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
     │        (match_sju_knowledge, Postgres websearch_to_tsquery + ts_rank)
     │
     └─► Gemini — first free-tier model with quota left (8 in rotation)
              system prompt = built-in facts + retrieved chunks
              → answer streams back word by word
```

Two knowledge sources are combined:

1. **Built-in knowledge** (`KNOWLEDGE` in `main.py`) — core facts (address,
   rankings, course list, contacts) hard-coded so the bot always answers common
   questions, even with no database.
2. **Supabase knowledge base** — ~940 text chunks scraped from ~290 real SJU
   pages, retrieved by **Postgres full-text search** (keyword/relevance ranking,
   no embeddings).

Gemini is used **only to write the final answer**. Retrieval is plain SQL
full-text search, so there are no embedding API calls and no vector database.

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
| `SUPABASE_KEY`    | Knowledge-base search | Publishable/anon key is enough (read + write) |

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
Studio stays the full picture). `python test_rotation.py` checks the rotation
logic offline, without spending quota.

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

**Before going live**, restrict who may frame the app by returning
`Content-Security-Policy: frame-ancestors https://*.sju.edu.in` from
`main.py`; otherwise any site can embed the widget and spend the Gemini quota.

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
creates the GIN full-text index and the `match_sju_knowledge(query, match_count)`
function that `main.py` calls.

**Refreshing content:** the scraper (`scrape_playwright.py`) runs on a laptop,
reading `SUPABASE_URL` / `SUPABASE_KEY` from the environment. It pulls SJU's
`sitemap.xml`, renders each page with Playwright, chunks the text, clears the
table, and re-uploads (caching progress in the gitignored
`scraped_chunks.json`). Re-run it whenever the site changes.

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

python test_rotation.py   # offline check of the model rotation
```
