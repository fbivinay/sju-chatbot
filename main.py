"""
SJU Chatbot - LIVE RETRIEVAL VERSION
Uses Gemini 2.5 Flash with Google Search grounding.
The AI searches the web LIVE for each question (biased to sju.edu.in),
reads the real rendered content, and answers from it - not preloaded text.

Free tier: ~1500 grounded searches/day. Uses your existing GEMINI_API_KEY.
No Supabase or crawler needed.
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

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are the official AI assistant for St Joseph's University (SJU), Bengaluru (website: sju.edu.in).
You help students by searching the web LIVE and answering from real, current information.

HOW TO ANSWER:
1. Use Google Search to find the answer. ALWAYS prioritise pages from sju.edu.in and admissions.sju.edu.in.
   Good searches include the site, e.g. "MSc Big Data Analytics fees site:sju.edu.in" or
   "St Joseph's University Bengaluru hostel fees".
2. Base your answer on what you find. Give specific details - fees, dates, names, eligibility, syllabus - when the search returns them.
3. If sju.edu.in doesn't have it but a reliable source (CollegeDunia, Shiksha, etc.) does, you may use that,
   but say clearly it's from a third-party source and they should confirm on the official site.
4. If you genuinely can't find something, say so honestly and point them to the right SJU page or to call 080-2227-4079.
   Never invent fees, dates, or names.
5. If the student says "yes", "tell me more", "go on" - continue the previous topic.
6. Be warm and friendly like a helpful senior SJU student. Use bullet points for lists. Keep answers under 250 words.

KEY SJU CONTACT INFO (always correct):
- Phone: 080-2227-4079 | Email: pro@sju.edu.in | WhatsApp: 9480811912
- Address: 36 Lalbagh Road, Bengaluru 560027
- Website: sju.edu.in | Admissions: admissions.sju.edu.in
- Founded 1882, Jesuit university, NAAC A++, India's first Public-Private University (RUSA 2.0)"""


class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Message]] = []


async def ask_gemini(contents, use_search=True):
    """Call Gemini. use_search=True enables live Google Search grounding."""
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 600, "temperature": 0.3},
    }
    if use_search:
        body["tools"] = [{"google_search": {}}]

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_KEY}",
            headers={"Content-Type": "application/json"},
            json=body,
        )
        return resp.json(), resp.status_code


def extract_answer(data):
    """Pull the text answer out of a Gemini response."""
    if "candidates" in data and data["candidates"]:
        cand = data["candidates"][0]
        if "content" in cand and "parts" in cand["content"]:
            parts = cand["content"]["parts"]
            texts = [p.get("text", "") for p in parts if "text" in p]
            answer = "".join(texts).strip()
            if answer:
                return answer
    return None


@app.post("/chat")
async def chat(req: ChatRequest):
    q = req.question.strip()
    if not q:
        return {"answer": "Please type a question!"}
    if not GEMINI_KEY:
        return {"answer": "Gemini API key not configured. Please add GEMINI_API_KEY in Railway variables."}

    # Build conversation
    contents = []
    if req.history:
        for m in req.history[-10:]:
            if m.role == "user":
                contents.append({"role": "user", "parts": [{"text": m.content}]})
            elif m.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": m.content}]})
    contents.append({"role": "user", "parts": [{"text": q}]})

    try:
        # First try WITH live Google Search grounding
        data, status = await ask_gemini(contents, use_search=True)
        answer = extract_answer(data)
        if answer:
            return {"answer": answer}

        # If grounding hit an error, log it and retry without search
        if "error" in data:
            err = data["error"].get("message", "")
            print(f"Grounded call error: {err}")
            if "quota" in err.lower() or "RESOURCE_EXHAUSTED" in str(err):
                return {"answer": (
                    "I've hit my search limit for now. Please try again in a little while.\n\n"
                    "Or contact SJU directly: 📞 080-2227-4079 | 🌐 sju.edu.in"
                )}

        # Fallback: answer without live search
        data2, _ = await ask_gemini(contents, use_search=False)
        answer2 = extract_answer(data2)
        if answer2:
            return {"answer": answer2}

        return {"answer": "Sorry, I couldn't find an answer right now. Please try rephrasing, or call SJU at 080-2227-4079."}

    except httpx.TimeoutException:
        return {"answer": "That search took too long. Please try again in a moment."}
    except Exception as e:
        print(f"Error: {e}")
        return {"answer": "Something went wrong. Please try again or call SJU at 080-2227-4079."}


@app.get("/health")
def health():
    return {
        "status": "running",
        "ai": MODEL,
        "live_search": True,
        "gemini_configured": bool(GEMINI_KEY),
    }


@app.get("/")
def root():
    return FileResponse("static/index.html")
