"""
SJU Chatbot - RELIABLE VERSION
Strong built-in knowledge that ALWAYS answers common questions.
Also checks Supabase for extra info if available.
Uses Gemini 2.5 Flash (free tier).
"""
import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

try:
    from supabase import create_client
except Exception:
    create_client = None

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mvszfevopamhkratxeak.supabase.co")
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
3. For exact fees: give the approximate figures from the knowledge, but ALWAYS add that they should confirm exact current fees at admissions.sju.edu.in since fees change yearly.
4. For very specific things you genuinely don't have (like a specific professor's name or a specific date), point them to the right page or phone number - but still be helpful.
5. If student says "yes", "tell me more", "go on" - continue the previous topic.
6. Use bullet points for lists. Keep answers under 250 words. Be friendly and warm.
7. NEVER just say "I couldn't find that" for common topics - you HAVE the information, use it.

{extra}

=== SJU KNOWLEDGE BASE ===
""" + KNOWLEDGE


# Common student abbreviations -> how the website actually writes them
ABBREV = {
    "bda": "big data analytics",
    "msc": "m.sc",
    "mca": "computer applications",
    "bca": "computer applications",
    "cs": "computer science",
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "eco": "economics",
    "psych": "psychology",
    "biotech": "biotechnology",
    "micro": "microbiology",
    "mba": "business administration",
    "bba": "business administration",
    "mcom": "commerce",
    "bcom": "commerce",
    "msw": "social work",
    "bsw": "social work",
    "dept": "department",
    "fees": "fee",
}

def search_supabase(question: str) -> str:
    """Get real crawled content from Supabase relevant to the question."""
    if not sb:
        return ""
    try:
        stop = {"what","when","where","how","is","are","the","a","an","at","in","of",
                "for","to","do","does","tell","me","about","i","can","will","which",
                "who","sju","college","university","please","give","yes","more","many","much"}
        raw = [w.lower().strip("?.,!:;") for w in question.split()
               if w.lower() not in stop and len(w) > 1]
        # Expand abbreviations: 'bda' also searches 'big data analytics'
        words = []
        for w in raw:
            if w in ABBREV:
                words.extend(ABBREV[w].split())
            if len(w) > 2:
                words.append(w)
        # de-duplicate, keep order
        seen_w = set()
        words = [w for w in words if not (w in seen_w or seen_w.add(w))]
        if not words:
            return ""

        results = []
        # 1) try the most specific combined phrase first
        term = " ".join(words[:4])
        r = sb.table("sju_knowledge").select("content, page_name") \
            .ilike("content", f"%{term}%").limit(4).execute()
        if r.data:
            results.extend(r.data)

        # 2) if thin, search each keyword individually
        if len(results) < 3:
            for w in words[:4]:
                r = sb.table("sju_knowledge").select("content, page_name") \
                    .ilike("content", f"%{w}%").limit(3).execute()
                if r.data:
                    results.extend(r.data)

        if results:
            seen = set()
            chunks = []
            for row in results:
                key = row["content"][:80]
                if key not in seen:
                    seen.add(key)
                    page = row.get("page_name", "")
                    chunks.append(f"[{page}] {row['content'][:600]}")
                if len(chunks) >= 6:
                    break
            return "=== REAL CONTENT FROM SJU WEBSITE (use this first) ===\n" + "\n\n".join(chunks)
    except Exception as e:
        print(f"Supabase search error: {e}")
    return ""


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
        return {"answer": "Gemini API key not configured in Railway. Please add GEMINI_API_KEY."}

    extra = search_supabase(q)
    system = SYSTEM_PROMPT.format(extra=extra)

    contents = []
    if req.history:
        for m in req.history[-12:]:
            if m.role == "user":
                contents.append({"role": "user", "parts": [{"text": m.content}]})
            elif m.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": m.content}]})
    contents.append({"role": "user", "parts": [{"text": q}]})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": contents,
                    "generationConfig": {"maxOutputTokens": 500, "temperature": 0.3},
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
                if "quota" in err.lower():
                    return {"answer": "Getting too many requests right now. Please wait a moment and try again."}
            return {"answer": "Sorry, please try asking again."}
    except httpx.TimeoutException:
        return {"answer": "That took too long. Please try again."}
    except Exception as e:
        print(f"Error: {e}")
        return {"answer": "Something went wrong. Please try again or call SJU at 080-2227-4079."}


@app.get("/health")
def health():
    return {
        "status": "running",
        "ai": "gemini-2.5-flash",
        "has_builtin_knowledge": True,
        "supabase_extra": sb is not None,
        "gemini_configured": bool(GEMINI_KEY),
    }


@app.get("/")
def root():
    return FileResponse("static/index.html")
