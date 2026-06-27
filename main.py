"""
SJU Chatbot — Production Server
Uses Supabase pgvector for RAG + OpenRouter for AI responses.
"""
import os
import httpx
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from supabase import create_client
from sentence_transformers import SentenceTransformer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Environment variables (set these in Railway) ───────────────────────────────
SUPABASE_URL      = os.getenv("SUPABASE_URL", "https://mvszfevopamhkratxeak.supabase.co")
SUPABASE_KEY      = os.getenv("SUPABASE_KEY", "")
OPENROUTER_KEY    = os.getenv("OPENROUTER_API_KEY", "")

# ── Free models to try in order ────────────────────────────────────────────────
FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-4b-it:free",
    "openrouter/auto",
]

# ── Load embedding model at startup ───────────────────────────────────────────
print("Loading embedding model...")
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
print("Embedding model ready!")

# ── Connect to Supabase ────────────────────────────────────────────────────────
print("Connecting to Supabase...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Supabase connected!")

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are the official AI assistant for St Joseph's University (SJU), Bengaluru.
Your job is to help students with accurate, friendly answers.

Use ONLY the context provided below to answer the question.
If the context does not contain the answer, say:
"I don't have that specific information. Please check sju.edu.in or call 080-2227-4079."

Rules:
- Never make up information, dates, or numbers not in the context
- Be friendly and concise
- Use bullet points for lists
- End with a helpful next step (link or phone number)
- Keep answers under 200 words
- Never confuse topics (sports question = sports answer only)

Context from SJU website:
{context}"""

def get_relevant_context(question: str, top_k: int = 5) -> str:
    """Search Supabase for the most relevant chunks"""
    try:
        # Convert question to vector
        question_vector = embedder.encode(question).tolist()

        # Search Supabase using pgvector similarity
        result = supabase.rpc(
            "match_sju_knowledge",
            {
                "query_embedding": question_vector,
                "match_count": top_k,
            }
        ).execute()

        if not result.data:
            return "No relevant information found."

        # Join the top results into one context block
        chunks = [row["content"] for row in result.data]
        return "\n\n---\n\n".join(chunks)

    except Exception as e:
        print(f"Supabase search error: {e}")
        return ""

class ChatRequest(BaseModel):
    question: str

@app.post("/chat")
async def chat(req: ChatRequest):
    q = req.question.strip()

    if not q:
        return {"answer": "Please type a question!"}
    if len(q) > 500:
        return {"answer": "Please keep your question a bit shorter."}
    if not OPENROUTER_KEY:
        return {"answer": "API key not configured. Please add OPENROUTER_API_KEY in Railway."}

    # Step 1: Get relevant context from Supabase
    context = get_relevant_context(q)

    # Step 2: Build prompt with context
    system_with_context = SYSTEM_PROMPT.format(context=context)

    # Step 3: Ask AI using context
    last_error = ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for model in FREE_MODELS:
            try:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://sju-chatbot.up.railway.app",
                        "X-Title": "SJU Chatbot",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_with_context},
                            {"role": "user",   "content": q},
                        ],
                        "max_tokens": 400,
                        "temperature": 0.1,
                    }
                )

                data = resp.json()

                if "choices" in data and len(data["choices"]) > 0:
                    answer = data["choices"][0]["message"]["content"]
                    if answer and answer.strip():
                        return {"answer": answer.strip()}

                if "error" in data:
                    last_error = data["error"].get("message", "")
                    continue

            except httpx.TimeoutException:
                last_error = "timeout"
                continue
            except Exception as e:
                last_error = str(e)
                continue

    return {
        "answer": (
            "I'm having trouble right now. Please try again in a moment.\n\n"
            "Or contact SJU directly:\n"
            "📞 080-2227-4079\n"
            "🌐 sju.edu.in\n"
            "💬 WhatsApp: 9480811912"
        )
    }

@app.get("/health")
def health():
    return {
        "status": "running",
        "supabase": bool(SUPABASE_KEY),
        "openrouter": bool(OPENROUTER_KEY),
    }

@app.get("/")
def root():
    return FileResponse("static/index.html")
