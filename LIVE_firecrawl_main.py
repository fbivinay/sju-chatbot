"""
SJU Chatbot - LIVE RETRIEVAL via Firecrawl + Gemini
For each question: Firecrawl searches SJU's site LIVE (renders JavaScript),
returns the real page content, and Gemini answers from it.

Uses your EXISTING keys: FIRECRAWL_API_KEY + GEMINI_API_KEY. No card needed.
Firecrawl free tier ~1000 credits/month (~200 questions). Gemini free 1500/day.
"""
import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "")
FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY", "")
MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are the official AI assistant for St Joseph's University (SJU), Bengaluru.
You answer students using the LIVE website content provided to you below (freshly fetched from sju.edu.in for this question).

RULES:
1. Answer using the website content provided below. Give specific details - fees, dates, names, eligibility, syllabus - when they appear in the content.
2. If the content has the answer, state it clearly and confidently.
3. If the provided content does NOT contain the answer, say honestly: "I couldn't find that specific detail on the SJU website right now. Please check sju.edu.in or call 080-2227-4079." Never invent fees, dates, or names.
4. If the student says "yes", "tell me more", "go on" - continue the previous topic.
5. Be warm and friendly like a helpful senior SJU student. Use bullet points for lists. Keep answers under 250 words.

KEY SJU CONTACT INFO (always correct):
- Phone: 080-2227-4079 | Email: pro@sju.edu.in | WhatsApp: 9480811912
- Address: 36 Lalbagh Road, Bengaluru 560027
- Website: sju.edu.in | Admissions: admissions.sju.edu.in
- Founded 1882, Jesuit university, NAAC A++, India's first Public-Private University (RUSA 2.0)

=== LIVE WEBSITE CONTENT FOR THIS QUESTION ===
{context}
=============================================="""


async def firecrawl_search(query: str) -> str:
    """Search SJU's site live via Firecrawl, return real page content."""
    if not FIRECRAWL_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(
                "https://api.firecrawl.dev/v2/search",
                headers={
                    "Authorization": f"Bearer {FIRECRAWL_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": f"{query} St Joseph's University Bengaluru sju.edu.in",
                    "limit": 3,
                    "scrapeOptions": {
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                    },
                },
            )
            data = resp.json()

        # Firecrawl response can be {data: {web: [...]}} or {data: [...]}
        results = []
        d = data.get("data", data)
        if isinstance(d, dict):
            results = d.get("web", []) or d.get("results", [])
        elif isinstance(d, list):
            results = d

        if not results:
            return ""

        chunks = []
        for r in results[:3]:
            if not isinstance(r, dict):
                continue
            title = r.get("title", "") or r.get("metadata", {}).get("title", "")
            url   = r.get("url", "") or r.get("metadata", {}).get("sourceURL", "")
            text  = r.get("markdown", "") or r.get("content", "") or r.get("description", "")
            if text:
                # keep it reasonable so the prompt isn't huge
                text = text.strip()[:2500]
                chunks.append(f"[Source: {title or url}]\n{text}")

        return "\n\n---\n\n".join(chunks)

    except Exception as e:
        print(f"Firecrawl search error: {e}")
        return ""


async def ask_gemini(contents, system):
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 600, "temperature": 0.3},
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_KEY}",
            headers={"Content-Type": "application/json"},
            json=body,
        )
        return resp.json()


def extract_answer(data):
    if "candidates" in data and data["candidates"]:
        cand = data["candidates"][0]
        if "content" in cand and "parts" in cand["content"]:
            parts = cand["content"]["parts"]
            answer = "".join(p.get("text", "") for p in parts if "text" in p).strip()
            if answer:
                return answer
    return None


class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Message]] = []


@app.post("/chat")
async def chat(req: ChatRequest):
    q = req.question.strip()
    if not q:
        return {"answer": "Please type a question!"}
    if not GEMINI_KEY:
        return {"answer": "Gemini API key not configured. Please add GEMINI_API_KEY in Railway."}

    # Step 1: live-fetch real content from SJU site via Firecrawl
    context = await firecrawl_search(q)
    if not context:
        context = "(No live content could be fetched for this question. Answer from the contact info and general knowledge, and point the student to sju.edu.in.)"

    system = SYSTEM_PROMPT.format(context=context)

    # Step 2: build conversation
    contents = []
    if req.history:
        for m in req.history[-10:]:
            if m.role == "user":
                contents.append({"role": "user", "parts": [{"text": m.content}]})
            elif m.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": m.content}]})
    contents.append({"role": "user", "parts": [{"text": q}]})

    # Step 3: Gemini answers from the live content
    try:
        data = await ask_gemini(contents, system)
        answer = extract_answer(data)
        if answer:
            return {"answer": answer}
        if "error" in data:
            err = data["error"].get("message", "")
            print(f"Gemini error: {err}")
            if "quota" in err.lower() or "RESOURCE_EXHAUSTED" in str(err):
                return {"answer": "I'm getting a lot of questions right now. Please try again in a moment.\n\n📞 080-2227-4079 | 🌐 sju.edu.in"}
        return {"answer": "Sorry, I couldn't form an answer. Please try rephrasing, or call SJU at 080-2227-4079."}
    except httpx.TimeoutException:
        return {"answer": "That took too long. Please try again in a moment."}
    except Exception as e:
        print(f"Error: {e}")
        return {"answer": "Something went wrong. Please try again or call SJU at 080-2227-4079."}


@app.get("/health")
def health():
    return {
        "status": "running",
        "ai": MODEL,
        "live_retrieval": "firecrawl",
        "gemini_configured": bool(GEMINI_KEY),
        "firecrawl_configured": bool(FIRECRAWL_KEY),
    }


@app.get("/")
def root():
    return FileResponse("static/index.html")
