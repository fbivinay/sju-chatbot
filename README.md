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
     └─► Gemini (gemini-flash-latest)
              system prompt = built-in facts + retrieved chunks
              → generates the answer
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
- **AI:** Google Gemini `gemini-flash-latest` (free tier)
- **Knowledge base:** Supabase (Postgres) full-text search
- **Frontend:** single `static/index.html` — no framework
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

## Deploy to Vercel

1. Push this repo to GitHub.
2. In Vercel: **Add New → Project → Import** the repo. `vercel.json` builds
   `main.py` as a Python serverless function — no build command needed.
3. **Settings → Environment Variables:** add `GEMINI_API_KEY` (and
   `SUPABASE_URL` / `SUPABASE_KEY` for the knowledge base).
4. Redeploy so the env vars take effect. You get a URL like
   `sju-chatbot.vercel.app`.

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

**Refreshing content:** the scraper (`scrape_playwright.py`) is a laptop-only
tool kept out of the repo (gitignored, may hold keys). It pulls SJU's
`sitemap.xml`, renders each page with Playwright, chunks the text, clears the
table, and re-uploads. Re-run it whenever the site changes.

---

## Endpoints

| Method | Path      | Purpose                            |
|--------|-----------|------------------------------------|
| GET    | `/`       | Serves the website + chat widget   |
| POST   | `/chat`   | `{ question, history }` → `{ answer }` |
| GET    | `/health` | Status / config check              |

---

## Local run

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...   SUPABASE_URL=...   SUPABASE_KEY=...
uvicorn main:app --reload
# open http://localhost:8000
```
