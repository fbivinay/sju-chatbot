"""
SJU Chatbot
Strong built-in knowledge that ALWAYS answers common questions.
Also checks Supabase for extra info if available.
Answers stream from Gemini, rotating across free-tier models as limits fill up.
"""
import asyncio
import json
import os
import time
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

try:
    from supabase import create_client
except Exception:
    create_client = None

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")

sb = None
if create_client and SUPABASE_URL and SUPABASE_KEY:
    try:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase connected!")
    except Exception as e:
        print(f"Supabase error: {e}")

# ════════════════════════════════════════════════════════════════════════════
# BUILT-IN KNOWLEDGE — this ALWAYS works, no database needed
# ════════════════════════════════════════════════════════════════════════════
KNOWLEDGE = """
=== ABOUT ST JOSEPH'S UNIVERSITY (SJU) ===
- Full name: St Joseph's University, Bengaluru
- Address: 36, Lalbagh Road (corner of Langford Road), Bengaluru - 560027, Karnataka
- Phone: +91 80 2227 4079 | Email: pro@sju.edu.in
- WhatsApp (admissions): 9480811912
- Website: sju.edu.in | Admissions portal: admissions.sju.edu.in
- Founded 1882 by French Catholic missionaries; managed by Jesuits since 1937
- Became India's first Public-Private University under RUSA 2.0 on 2 July 2022
- Inaugurated by President Droupadi Murmu on 27 September 2022
- Motto: "Fide et Labore" (Faith and Toil)
- NAAC Grade A++ | UGC recognised | College of Excellence
- Located opposite Lalbagh Botanical Garden, near Lalbagh metro station

=== RANKINGS (The Week University Ranking 2026) ===
- 49th: Multidisciplinary Universities (All India)
- 19th: Multidisciplinary Universities (South Zone)
- 18th: Private & Deemed Multidisciplinary (All India)
- 8th: Private & Deemed Multidisciplinary (South Zone)
- 4th: Private & Deemed Multidisciplinary (Karnataka)
- India Today 2025: 6th BCA, 8th BSc, 18th Arts

=== ALL COURSES OFFERED ===
SCHOOL OF INFORMATION TECHNOLOGY:
- BCA (Bachelor of Computer Applications) - 3 years
- MCA (Master of Computer Applications) - 2 years
- MSc Computer Science - 2 years
- MSc Big Data Analytics - 2 years

SCHOOL OF BUSINESS:
- BBA (Bachelor of Business Administration) - 3 years
- BCom (Bachelor of Commerce) - 3 years
- MBA (Master of Business Administration) - 2 years
- MCom (Master of Commerce) - 2 years

SCHOOL OF PHYSICAL SCIENCES:
- BSc in Physics, Mathematics, Statistics, Electronics - 3 years
- MSc in Physics, Mathematics, Statistics - 2 years

SCHOOL OF LIFE SCIENCES:
- BSc in Biotechnology, Microbiology, Food Science & Technology - 3 years
- MSc in Biotechnology, Microbiology, Food Science & Technology - 2 years

SCHOOL OF CHEMICAL SCIENCES:
- BSc in Chemistry - 3 years
- MSc in Organic Chemistry, Analytical Chemistry - 2 years

SCHOOL OF HUMANITIES & SOCIAL SCIENCES:
- BA in Psychology, Economics, History, Sociology - 3 years
- MA in Psychology, Economics - 2 years

SCHOOL OF COMMUNICATION & MEDIA STUDIES:
- BA in Visual Communication, Journalism - 3 years
- MA in Media Studies - 2 years

SCHOOL OF LANGUAGES & LITERATURES:
- BA in English, Kannada, French, Hindi - 3 years
- MA in English, Kannada - 2 years

SCHOOL OF SOCIAL WORK:
- BSW (Bachelor of Social Work) - 3 years
- MSW (Master of Social Work) - 2 years

ALSO OFFERED: PhD programmes in most departments, PG Diplomas (Data Science, Cybersecurity, HR Management, Financial Management), Certificate courses, Lateral Entry

=== ADMISSIONS 2026-27 ===
- Apply online at admissions.sju.edu.in
- Eligibility: minimum 50% marks in qualifying exam (for both UG and PG)
- UG selection: merit + entrance test (SJUET for some courses) + interview
- PG selection: bachelor's degree merit + SJUET + interview
- UG applications usually open December-January
- PG applications usually open February-April
- Application fee: ₹800 for UG, ₹1000 for PG/PhD; extra ₹200 if entrance test needed
- Documents: previous mark sheets, ID proof, passport photos, caste/income certificate if applicable
- Some courses require SJUET (SJU Entrance Test): BA Visual Communication, BA Journalism, B.Voc, PG Diploma, and Media/Psychology/English PG courses

=== FEES (approximate totals for full course - confirm exact at admissions.sju.edu.in) ===
Note: fees change each year and vary by specialisation. These are approximate ranges:
- BCA: approximately ₹5 Lakhs total (3 years)
- BBA: approximately ₹4.5-7 Lakhs total (3 years)
- BCom: approximately ₹3.8-6.5 Lakhs total (3 years)
- BSc: approximately ₹1.8-3.9 Lakhs total (3 years), varies by specialisation
- BA: approximately ₹74,000 per year, varies by specialisation
- BSW: approximately ₹71,500 per year
- MSc: approximately ₹1.8-4.5 Lakhs total (2 years), varies by specialisation
- MCA: approximately ₹4.5 Lakhs total (2 years)
- MBA: approximately ₹7 Lakhs total (2 years)
- MCom: approximately ₹2.6 Lakhs total (2 years)
- MSW: approximately ₹1.1 Lakhs total (2 years)
- Karnataka students (studied 7 years in Karnataka) get fee relaxation on UG courses
- NRI/Foreign students pay higher fees
- IMPORTANT: Always tell students to confirm exact current fees at admissions.sju.edu.in or by calling 080-2227-4079, since fees are updated each year

=== PLACEMENTS ===
- Handled by Centre for Student Placements and Skill Development
- Top recruiters: Cognizant, Deloitte, Accenture, EY, KPMG, Britannia, Federal Bank, HP India, BioCon, MuSigma, Ditto Insurance, Infosys, Wipro, TCS, Amazon
- Activities: industry visits, guest lectures, resume preparation, mock interviews, skill workshops, internship facilitation
- Placements happen in the final year of each programme
- Placement page: sju.edu.in/placements/about-placements.php

=== HOSTEL ===
- Separate hostels for boys and girls on campus
- Facilities: furnished rooms, mess/dining hall, Wi-Fi, 24/7 CCTV, warden support, reading room
- Hostel fees approximately ₹35,000 to ₹1.4 Lakhs per year (varies by room type, includes mess)
- Apply at sju.edu.in/services/hostel/university-hostel.php
- Contact hostel office for current availability

=== SCHOLARSHIPS ===
- Karnataka State SSP Portal: ssp.postmatric.karnataka.gov.in (for SC/ST/OBC/minority)
- Ishan Uday: for students from North East India
- PG Indira Gandhi Scholarship: for single girl child
- Vidyaposhak: merit + financial need basis
- UGC PG Scholarships: for university rank holders
- Fee exemptions for students from marginalised communities
- Details: sju.edu.in/student-support/scholarships_page

=== CAMPUS FACILITIES ===
- Digitized smart classrooms, campus-wide Wi-Fi
- Science and IT laboratories
- Central Library with digital resources and e-journals
- Auditorium, seminar halls, cafeteria/canteen
- Sports: football, cricket, basketball, volleyball, badminton courts, athletics
- Observatory (rare in Bangalore colleges)
- Health/medical facilities, counselling centre
- NSS and NCC units
- CCTV surveillance, green eco-friendly campus
- Anti-ragging cell, gender sensitisation cell, equal opportunity cell

=== SPORTS ===
- Active sports: football, cricket, basketball, volleyball, badminton, athletics
- Sports selections and trials announced at the start of each academic semester
- Watch for announcements at sju.edu.in/announcements.php
- Sports page: sju.edu.in/services/sports
- Contact the Physical Education department on campus for trial dates

=== FACULTY ===
- 300+ teaching faculty across 9 schools
- Many faculty hold PhDs from reputed universities
- Active in research through SJRIC (SJU Research Innovation Centre): sjric.res.in
- Full faculty list: sju.edu.in/about/faculty-members.php
- For specific department faculty, check that department's page or call 080-2227-4079

=== EXAMINATIONS ===
- Exam timetable: sju.edu.in/examination/exam-time-table.php
- Exam notices: sju.edu.in/examination/examinationnotices.php
- Seating arrangements: sju.edu.in/examination/sjuexamseatingarrangement.php
- Results and rank holders: sju.edu.in/examination/rank-holders.php

=== STUDENT SUPPORT ===
- Counselling: sju.edu.in/student-support/counselling-services.php
- Anti-Ragging Cell (zero tolerance): sju.edu.in/student-support/antiraggingcell.php
- Grievance Redressal: sju.edu.in/student-support/student-grievance-redressal.php
- Facilities for Differently Abled students
- Health facilities on campus

=== RESEARCH ===
- SJU was the first college in Karnataka to have a Research Centre (1988)
- PhD programmes in most departments
- Research Innovation Centre: sjric.res.in

=== NSS & NCC ===
- NSS (National Service Scheme): active unit, open for enrolment
- NCC (National Cadet Corps): active unit, open for enrolment

=== LATEST ANNOUNCEMENTS (June 2026) ===
- Orientation Notice to all First Year Students 2026-27 (25 May 2026)
- Extension of Last Date for Convocation/Degree Completion Certificates to 13 June 2026
- Admissions 2026-27 are OPEN
- SJU ranked 4th in Karnataka (The Week 2026)

=== OTHER USEFUL INFO ===
- Class timetable 2026: sju.edu.in/services/timetable/time-table-2026.php
- Academic calendar: sju.edu.in/about/calendar.php
- Certificate courses: sju.edu.in/services/certificate-courses.php
- Alumni portal: alumni.sju.edu.in
- International students: sju.edu.in/internationalstudents/internationalstudents.php
- Library: sju.edu.in/library/library.php
- FAQ: sju.edu.in/faq.php
- Fee refund policy: available on the SJU website
"""

SYSTEM_PROMPT = """You are the official AI assistant for St Joseph's University (SJU), Bengaluru.
You help students in a warm, friendly, helpful way - like a knowledgeable senior student.

Use the SJU knowledge below to answer questions. The knowledge is accurate and comprehensive.

RULES:
1. ALWAYS give a direct, helpful answer using the knowledge below. You have lots of information - use it.
2. For courses, admissions, placements, hostel, scholarships, sports, facilities - you have full details, so answer confidently.
3. For fees: if the SJU CONTENT above contains a fee table or figures, quote the EXACT amounts (category-wise and year-wise, e.g. Karnataka/Non-Karnataka/NRI). Do NOT invent or round to a vague range. Add one short line that fees may change yearly - confirm at admissions.sju.edu.in.
4. If the SJU CONTENT above contains names, dates, or details, USE them (e.g. the Dean's or faculty names). Only say you don't have something when it is genuinely absent from the content above - then point to the right page or phone number.
5. If student says "yes", "tell me more", "go on" - continue the previous topic.
6. Use bullet points for lists - NEVER Markdown tables, the chat window can't display them; give fee figures as bullets (one line per category or year). Keep answers under 250 words. Be friendly and warm.
7. NEVER just say "I couldn't find that" for common topics - you HAVE the information, use it.
8. When your answer draws on the SJU CONTENT above, cite its source URL as a Markdown link, e.g. [MSc Big Data Analytics](https://www.sju.edu.in/programmes/msc-in-big-data-analytics).

{extra}

=== SJU KNOWLEDGE BASE ===
""" + KNOWLEDGE


# Informal short-forms students use that never appear verbatim on the real SJU
# pages (which spell programmes out in full) - full-text search can't match
# "BDA" to "Big Data Analytics" on its own, so widen the query with the expansion.
QUERY_ABBREVIATIONS = {
    "bda": "big data analytics",
}


def search_supabase(question: str) -> str:
    """Full-text search over real crawled SJU content in Supabase (no embeddings)."""
    if not sb:
        return ""
    words = question.lower().split()
    expansions = {QUERY_ABBREVIATIONS[w] for w in words if w in QUERY_ABBREVIATIONS}
    query = question if not expansions else question + " " + " ".join(expansions)
    try:
        r = sb.rpc("match_sju_knowledge", {"query": query, "match_count": 6}).execute()
        rows = r.data or []
        if not rows:
            return ""
        chunks = []
        for row in rows:
            pg = row.get("page_name", "")
            url = row.get("source_url", "")
            # Keep enough text that fee tables / details aren't cut off, and pass the
            # source URL so the model can link to it.
            chunks.append(f"[{pg}] (source: {url})\n{row['content'][:2000]}")
        return ("=== REAL CONTENT FROM SJU WEBSITE (use this first; quote exact figures "
                "and link the source URL) ===\n" + "\n\n".join(chunks))
    except Exception as e:
        print(f"Supabase search error: {e}")
    return ""


# ════════════════════════════════════════════════════════════════════════════
# GEMINI MODEL ROTATION
# ════════════════════════════════════════════════════════════════════════════
# Every free-tier model has its own quota, so rotating through several multiplies
# capacity. The limits are this key's free tier (AI Studio > Rate limits, Oct 2026);
# update them here if Google changes them.
#
# Order = fastest first: the first six start answering in ~1-2s. The last two reject
# thinkingLevel "minimal", and "low" adds ~8s before the first word.
# Left out: gemini-2.5-flash / 2.5-flash-lite (404 "no longer available to new
# users") and gemma-4-31b-it (17-30s before the first word).
# "wait" = seconds to wait for the first word before moving on to the next model.
#
#  model                     RPM     RPD      TPM  wait  thinkingLevel
MODELS = [
    ("gemini-3.6-flash",        5,     20, 250_000,   6, "minimal"),
    ("gemini-3-flash-preview",  5,     20, 250_000,   6, "minimal"),
    ("gemini-3.5-flash",        5,     20, 250_000,   6, "minimal"),
    ("gemini-3.5-flash-lite",  15,    500, 250_000,   6, "minimal"),
    ("gemini-3.1-flash-lite",  15,    500, 250_000,   6, "minimal"),
    ("gemma-4-26b-a4b-it",     30, 14_400,  16_000,   6, "minimal"),
    ("gemini-3.8-flash",        5,     20, 250_000,  15, "low"),
    ("gemini-3.7-flash",        5,     20, 250_000,  15, "low"),
]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:streamGenerateContent?alt=sse"
BUSY_MSG = ("Lots of students are asking questions right now - please try again in a minute, "
            "or call SJU at 080-2227-4079.")

# Usage is tracked in memory so a request goes straight to a model with room left,
# instead of finding out from a 429. Each Vercel instance keeps its own counts, so
# when several run at once Google can still say no - the 429 handling covers that.
_recent = {m[0]: [] for m in MODELS}        # (time, tokens) sent in the last 60s
_today = {m[0]: 0 for m in MODELS}          # requests since the daily reset
_skip_until = {m[0]: 0.0 for m in MODELS}   # time before which a model isn't tried
_quota_day = 0

# Google resets daily quotas at midnight Pacific: 08:00 UTC, or 07:00 UTC during
# daylight saving. Rolling over at 08:00 year-round means a model can look used up
# for an hour after it actually reset - never the other way round.
DAY_START = 8 * 3600


def _roll_day(now: float):
    global _quota_day
    day = int((now - DAY_START) // 86400)
    if day != _quota_day:
        _quota_day = day
        for model in _today:
            _today[model] = 0


def _pick(tokens: int, tried: set):
    """Reserve the first model with room under all of its limits."""
    now = time.time()
    _roll_day(now)
    for model, rpm, rpd, tpm, wait, thinking in MODELS:
        if model in tried or _skip_until[model] > now:
            continue
        recent = _recent[model] = [(t, n) for t, n in _recent[model] if now - t < 60]
        if len(recent) < rpm and _today[model] < rpd and sum(n for _, n in recent) + tokens <= tpm:
            recent.append((now, tokens))
            _today[model] += 1
            return model, wait, thinking
    return None


def _skip(model: str, seconds: float, why: str):
    _skip_until[model] = time.time() + seconds
    print(f"Gemini {model}: {why} - skipping it for {seconds:.0f}s")


async def gemini_stream(body: dict):
    """Stream the answer from the first model that can take this request."""
    tokens = len(json.dumps(body)) // 3   # measured ~3.6 chars per token; errs high
    deadline = time.monotonic() + 30
    tried, rejected = set(), []
    async with httpx.AsyncClient() as client:
        while pick := _pick(tokens, tried):
            model, wait, thinking = pick
            tried.add(model)
            left = deadline - time.monotonic()
            if left < 2:
                print("Gemini: out of time before any model answered")
                break
            payload = {**body, "generationConfig": {"maxOutputTokens": 800, "temperature": 0.3,
                                                    "thinkingConfig": {"thinkingLevel": thinking}}}
            started = time.monotonic()
            answered = False
            try:
                # Key in a header, not the URL - httpx logs request URLs to Vercel logs.
                async with client.stream("POST", GEMINI_URL.format(model), json=payload,
                                         headers={"x-goog-api-key": GEMINI_KEY},
                                         timeout=httpx.Timeout(min(wait, left), connect=3.0)) as resp:
                    if resp.status_code != 200:
                        err = (await resp.aread()).decode(errors="replace")
                        msg = f"HTTP {resp.status_code} {err[:300]}"
                        if resp.status_code == 429:
                            now = time.time()
                            if "PerDay" in err:
                                next_reset = (int((now - DAY_START) // 86400) + 1) * 86400 + DAY_START
                                _skip(model, next_reset - now, "daily quota used up")
                            else:
                                _skip(model, 60, "per-minute limit hit")
                        elif resp.status_code == 404:   # model withdrawn or renamed
                            _skip(model, 3600, msg)
                        elif resp.status_code in (400, 403):
                            # Could be this model (e.g. a thinking level it no longer
                            # accepts) or this request; only bench the model if another
                            # model then answers the same request.
                            print(f"Gemini {model}: {msg}")
                            rejected.append(model)
                        else:                           # 5xx: overloaded
                            _skip(model, 20, msg)
                        continue
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        chunk = json.loads(line[6:])
                        if "error" in chunk:
                            print(f"Gemini {model}: error mid-stream {chunk['error']}")
                            break
                        for part in (chunk.get("candidates") or [{}])[0].get("content", {}).get("parts", []):
                            if part.get("text") and not part.get("thought"):
                                if not answered:
                                    print(f"Gemini {model}: first words after {time.monotonic() - started:.1f}s")
                                answered = True
                                yield part["text"]
            except httpx.HTTPError as e:   # timed out or connection dropped
                if answered:
                    print(f"Gemini {model}: stream broke - {type(e).__name__}")
                    yield "\n\n(The connection dropped - please ask again.)"
                    return
                _skip(model, 20, f"no answer - {type(e).__name__}")
                continue
            if answered:
                for m in rejected:
                    _skip(m, 600, "rejected a request another model answered")
                return
            print(f"Gemini {model}: empty answer")
    yield BUSY_MSG


class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Message]] = []


async def answer_stream(req: ChatRequest):
    q = req.question.strip()[:2000]
    if not q:
        yield "Please type a question!"
        return
    if not GEMINI_KEY:
        yield "Gemini API key not configured. Please add GEMINI_API_KEY in Vercel environment variables."
        return

    history = [m for m in (req.history or [])[-12:] if m.content.strip()]
    contents = [{"role": "user" if m.role == "user" else "model", "parts": [{"text": m.content[:4000]}]}
                for m in history if m.role in ("user", "assistant")]
    contents.append({"role": "user", "parts": [{"text": q}]})

    # Short follow-ups ("fees", "and hostel?") carry no topic on their own -
    # fold in the previous user turn so search still finds the right programme.
    prev_user_msg = next((m.content for m in reversed(history) if m.role == "user"), None)
    search_query = f"{prev_user_msg} {q}" if prev_user_msg and prev_user_msg != q else q

    # The Supabase client is synchronous; run it off the event loop so other
    # students' answers keep streaming meanwhile.
    extra = await asyncio.to_thread(search_supabase, search_query)
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT.format(extra=extra)}]},
        "contents": contents,
    }
    try:
        async for text in gemini_stream(body):
            yield text
    except Exception as e:
        print(f"Error: {e}")
        yield "Something went wrong. Please try again or call SJU at 080-2227-4079."


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def events():
        async for text in answer_stream(req):
            yield f"data: {json.dumps(text)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# Whole answer in one JSON reply - for API clients and any browser still holding
# the pre-streaming embed.html in its cache.
@app.post("/chat")
async def chat(req: ChatRequest):
    return {"answer": "".join([text async for text in answer_stream(req)])}


@app.get("/health")
def health():
    now = time.time()
    _roll_day(now)
    return {
        "status": "running",
        "supabase_extra": sb is not None,
        "gemini_configured": bool(GEMINI_KEY),
        # This instance's own counts; AI Studio > Rate limits is the full picture.
        "models": {
            model: {
                "last_minute": f"{sum(1 for t, _ in _recent[model] if now - t < 60)}/{rpm}",
                "today": f"{_today[model]}/{rpd}",
                "skipped_for_s": max(0, round(_skip_until[model] - now)),
            }
            for model, rpm, rpd, *_ in MODELS
        },
    }


@app.get("/")
def root():
    return FileResponse("static/index.html")
