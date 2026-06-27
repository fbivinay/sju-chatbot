"""
SJU Chatbot - Production Server (Firecrawl + Supabase + Gemini)
Relies on REAL crawled website data from Supabase.
No hardcoded fees - everything comes from the actual SJU website.
"""
import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")

try:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    print("Supabase connected!" if sb else "Supabase not configured")
except Exception as e:
    sb = None
    print(f"Supabase error: {e}")

SYSTEM_PROMPT = """You are the official AI assistant for St Joseph's University (SJU), Bengaluru.
You help students with questions about the university in a warm, friendly way.

You have been given REAL content from the SJU website below as context.
Answer the student's question using that content.

RULES:
1. Answer directly and specifically using the website content provided below.
2. If the exact information is in the content, give it clearly (including any fees, dates, names, numbers).
3. If the specific information is NOT in the content provided, say honestly:
   "I couldn't find that specific detail on the SJU website. You can check sju.edu.in or call 080-2227-4079 for confirmation."
4. NEVER make up fees, dates, or numbers that aren't in the content. It's better to admit you don't know than to give wrong information.
5. If the student says "yes", "tell me more", "go on" — continue the previous topic.
6. Be warm and friendly like a helpful senior SJU student.
7. Use bullet points for lists. Keep answers under 250 words.

REAL CONTENT FROM SJU WEBSITE:
==============================
{context}
==============================

Basic SJU contact info (always available):
- Phone: 080-2227-4079 | Email: pro@sju.edu.in | Website: sju.edu.in
- Address: 36 Lalbagh Road, Bengaluru 560027 | WhatsApp: 9480811912
- Admissions: admissions.sju.edu.in"""


def search_knowledge(question: str) -> str:
    """Search Supabase for the most relevant real website content"""
    if not sb:
        return "No website content available. Database not connected."

    try:
        stop_words = {"what","when","where","how","is","are","the","a","an","at","in",
                      "of","for","to","do","does","tell","me","about","i","can","will",
                      "which","who","many","much","sju","college","university","joseph",
                      "st","please","give","yes","no","more","explain","ok","sure","hi","hello"}
        words = [w.lower().strip("?.,!:;") for w in question.split()
                 if w.lower() not in stop_words and len(w) > 2]

        all_results = []

        # Try searching with combined keywords first
        if words:
            term = " ".join(words[:5])
            r = sb.table("sju_knowledge").select("content, page_name, source_url") \
                .ilike("content", f"%{term}%").limit(6).execute()
            if r.data:
                all_results.extend(r.data)

        # Try each keyword individually if needed
        if len(all_results) < 3 and words:
            for word in words[:5]:
                r = sb.table("sju_knowledge").select("content, page_name, source_url") \
                    .ilike("content", f"%{word}%").limit(3).execute()
                if r.data:
                    all_results.extend(r.data)

        if all_results:
            seen = set()
            chunks = []
            for row in all_results:
                key = row["content"][:100]
                if key not in seen:
                    seen.add(key)
                    page = row.get("page_name", "SJU page")
                    chunks.append(f"[From: {page}]\n{row['content']}")
            return "\n\n---\n\n".join(chunks[:6])

        return "No specific matching content found on the website for this question."

    except Exception as e:
        print(f"Search error: {e}")
        return "Could not search website content."


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
        return {"answer": "Gemini API key not configured in Railway variables."}

    # Get real website content relevant to the question
    context = search_knowledge(q)
    system = SYSTEM_PROMPT.format(context=context)

    # Build conversation for Gemini
    contents = []
    if req.history:
        for msg in req.history[-12:]:
            if msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})
    contents.append({"role": "user", "parts": [{"text": q}]})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": contents,
                    "generationConfig": {"maxOutputTokens": 500, "temperature": 0.2},
                }
            )
            data = resp.json()

            if "candidates" in data and data["candidates"]:
                cand = data["candidates"][0]
                if "content" in cand and "parts" in cand["content"]:
                    answer = cand["content"]["parts"][0].get("text", "")
                    if answer.strip():
                        return {"answer": answer.strip()}

            if "error" in data:
                err = data["error"].get("message", "")
                print(f"Gemini error: {err}")
                if "quota" in err.lower() or "429" in str(resp.status_code):
                    return {"answer": "Too many requests right now. Please wait a moment and try again."}

            return {"answer": "Sorry, I couldn't generate a response. Please try again."}

    except httpx.TimeoutException:
        return {"answer": "Taking too long to respond. Please try again."}
    except Exception as e:
        print(f"Error: {e}")
        return {"answer": "Something went wrong. Please try again or call SJU at 080-2227-4079."}


@app.get("/health")
def health():
    count = 0
    if sb:
        try:
            r = sb.table("sju_knowledge").select("id", count="exact").limit(1).execute()
            count = r.count or 0
        except Exception:
            pass
    return {
        "status": "running",
        "ai": "gemini-2.5-flash",
        "supabase": sb is not None,
        "gemini_configured": bool(GEMINI_KEY),
        "knowledge_chunks": count,
    }


@app.get("/")
def root():
    return FileResponse("static/index.html")
