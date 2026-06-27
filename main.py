"""
SJU Chatbot - Production Server
Uses Google Gemini 2.5 Flash (free tier - 1500 req/day, no credit card)
Much more reliable than OpenRouter free models
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

SUPABASE_URL   = os.getenv("https://mvszfevopamhkratxeak.supabase.co", "")
SUPABASE_KEY   = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im12c3pmZXZvcGFtaGtyYXR4ZWFrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MjU1MDA2MiwiZXhwIjoyMDk4MTI2MDYyfQ.QJbCXfRHjwlIl2HpkAavoPPbGGeDLsjWyc3mzvY9D8Y", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
# Connect to Supabase
try:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    print("Supabase connected!" if sb else "Supabase not configured")
except Exception as e:
    sb = None
    print(f"Supabase error: {e}")

SYSTEM_PROMPT = """You are the official AI assistant for St Joseph's University (SJU), Bengaluru.
You are having a friendly conversation with a student. You remember the full conversation history.

Use the SJU knowledge base below to answer questions accurately.

IMPORTANT RULES:
1. Only state facts that are in the knowledge base below. Never invent fees, dates, or names.
2. If you don't know an exact figure (like a specific fee amount), say so honestly and give the right page or phone number to check.
3. If the student says "yes", "tell me more", "explain more" — continue the topic from the previous message.
4. Be warm, friendly, and helpful like a helpful senior student.
5. Use bullet points for lists. Keep answers under 200 words.
6. Always end with a next step: a link, phone number, or what to do.
7. For fees — always say "check admissions.sju.edu.in for exact current fees" since fees change each year.

SJU KNOWLEDGE BASE:
===================

CONTACT & LOCATION:
- Address: 36, Lalbagh Road (corner of Langford Road), Bengaluru - 560027
- Phone: +91 80 2227 4079
- Email: pro@sju.edu.in
- WhatsApp (admissions): 9480811912
- Website: sju.edu.in
- Admissions portal: admissions.sju.edu.in
- Opposite Lalbagh Botanical Garden | Near Lalbagh metro station

ABOUT SJU:
- Founded: 1882 by Paris Foreign Missionary Fathers
- Managed by Jesuits (Society of Jesus) since 1937
- Became India's first Public-Private University under RUSA 2.0 on 2 July 2022
- Inaugurated by President Droupadi Murmu on 27 September 2022
- Motto: "Fide et Labore" (Faith and Toil)
- NAAC Grade: A++ | UGC Recognised | College of Excellence

RANKINGS (The Week Magazine University Ranking 2026):
- 49th: Multidisciplinary Universities (All India)
- 19th: Multidisciplinary Universities (South Zone)
- 18th: Private & Deemed Multidisciplinary (All India)
- 8th: Private & Deemed Multidisciplinary (South Zone)
- 4th: Private & Deemed Multidisciplinary (Karnataka)
- India Today 2025: 6th BCA | 8th BSc | 18th Arts | 44th BCom

SCHOOLS AND ALL PROGRAMMES OFFERED:
School of Information Technology:
- BCA (Bachelor of Computer Applications) — 3 years
- MCA (Master of Computer Applications) — 2 years
- MSc Computer Science — 2 years
- MSc Big Data Analytics — 2 years

School of Business:
- BBA (Bachelor of Business Administration) — 3 years
- BCom (Bachelor of Commerce) — 3 years
- MBA — 2 years
- MCom — 2 years

School of Physical Sciences:
- BSc: Physics, Mathematics, Statistics, Electronics — 3 years
- MSc: Physics, Mathematics, Statistics — 2 years

School of Life Sciences:
- BSc: Biotechnology, Microbiology, Food Science & Technology — 3 years
- MSc: Biotechnology, Microbiology, Food Science & Technology — 2 years

School of Chemical Sciences:
- BSc Chemistry — 3 years
- MSc: Organic Chemistry, Analytical Chemistry — 2 years

School of Humanities & Social Sciences:
- BA: Psychology, Economics, History, Sociology — 3 years
- MA: Psychology, Economics — 2 years

School of Communication & Media Studies:
- BA: Visual Communication, Journalism — 3 years
- MA Media Studies — 2 years

School of Languages & Literatures:
- BA: English Literature, Kannada, French, Hindi — 3 years
- MA: English, Kannada — 2 years

School of Social Work:
- BSW (Bachelor of Social Work) — 3 years
- MSW (Master of Social Work) — 2 years

Also available: PhD programmes in most departments, Short-term certificate courses, Lateral Entry

ADMISSIONS 2026-27:
- Apply online: admissions.sju.edu.in
- Eligibility: Minimum 50% marks in qualifying exam (UG and PG both)
- UG admission process: Merit + SJU Entrance Test (for some courses) + Personal Interview
- PG admission process: Bachelor's degree merit + SJUET (SJU Entrance Test) + Interview
- UG application window: December - January each year
- PG application window: February - April each year
- Lateral entry available for selected programmes
- Documents needed: Previous mark sheets, ID proof, passport photos, caste/income certificate if applicable
- For queries: call 080-2227-4079 or WhatsApp 9480811912

FEES:
- Fees vary by programme and change each academic year
- For exact current fees: visit admissions.sju.edu.in or call 080-2227-4079
- Scholarships and fee exemptions available for eligible students

PLACEMENTS:
- Department: Centre for Student Placements and Skill Development
- Top recruiters include: Cognizant, Deloitte, Accenture, EY, KPMG, Britannia, Federal Bank, HP India, BioCon, MuSigma, Ditto Insurance, Infosys, Wipro, TCS, Amazon
- Placement activities: industry visits, guest lectures, resume preparation, mock interviews, skill development workshops, internship facilitation
- Placements happen in the final year of each programme
- Placement page: sju.edu.in/placements/about-placements.php

HOSTEL:
- Separate hostels for boys and girls on campus
- Facilities: furnished rooms, dining/mess hall, Wi-Fi, 24/7 CCTV, warden support, reading room
- Hostel page: sju.edu.in/services/hostel/university-hostel.php
- Contact hostel office for current availability and fees

SCHOLARSHIPS:
- Karnataka State SSP Portal: ssp.postmatric.karnataka.gov.in (SC/ST/OBC/minority students)
- Ishan Uday Special Scholarship: for students from North East India
- PG Indira Gandhi Scholarship: for single girl child
- Vidyaposhak Scholarship: merit + financial need basis
- UGC PG Scholarships: for university rank holders
- Fee exemptions available for students from marginalised communities
- Full details: sju.edu.in/student-support/scholarships_page

CAMPUS FACILITIES:
- Digitized classrooms with projectors and smart boards
- Campus-wide Wi-Fi
- Well-equipped science and IT laboratories
- Central Library with digital resources and e-journals
- Auditorium and seminar halls
- Cafeteria and canteen
- Sports: football ground, cricket ground, basketball courts, volleyball courts, badminton courts, athletics track
- Observatory (unique to SJU — rare in Bangalore colleges)
- Health and medical facilities on campus
- Counselling and psychological support centre
- CCTV surveillance across campus
- Green, eco-friendly campus

SPORTS:
- Active sports programmes: football, cricket, basketball, volleyball, badminton, athletics
- Sports selections and trials announced at the start of each academic semester
- Check for announcements: sju.edu.in/announcements.php
- Sports page: sju.edu.in/services/sports
- Contact the Physical Education department on campus for specific trial dates

EXAMINATIONS:
- Exam timetable: sju.edu.in/examination/exam-time-table.php
- Exam notices: sju.edu.in/examination/examinationnotices.php
- Seating arrangements: sju.edu.in/examination/sjuexamseatingarrangement.php
- Results and rank holders: sju.edu.in/examination/rank-holders.php
- Exam manual: sju.edu.in/examination/examinationmanual.php

FACULTY:
- 300+ teaching faculty across 9 schools
- Many faculty hold PhDs from reputed universities
- Active in research through SJRIC (SJU Research Innovation Centre): sjric.res.in
- Faculty page: sju.edu.in/about/faculty-members.php

STUDENT SUPPORT:
- Counselling Services: sju.edu.in/student-support/counselling-services.php
- Anti-Ragging Cell (zero tolerance): sju.edu.in/student-support/antiraggingcell.php
- Student Grievance Redressal: sju.edu.in/student-support/student-grievance-redressal.php
- Gender Sensitisation Cell available
- Equal Opportunity Cell available
- Mid Day Meals programme available
- Facilities for Differently Abled students

NSS AND NCC:
- NSS (National Service Scheme): active unit, open for enrolment
- NCC (National Cadet Corps): active unit, open for enrolment
- NSS page: sju.edu.in/services/sju-nss/national-service-scheme.php

RESEARCH:
- SJU was first college in Karnataka to have a Research Centre (1988)
- PhD programmes available in most departments
- Research Innovation Centre: sjric.res.in

LIBRARY:
- Central Library with books, journals, digital resources
- Library page: sju.edu.in/library/library.php

ANNOUNCEMENTS (June 2026):
- 25 May 2026: Orientation Notice to all First Year Students 2026-27
- 27 May 2026: Extension of Last Date for Convocation and Degree Completion Certificates to 13.06.2026
- Admissions 2026-27 are OPEN
- The Week Rankings 2026: SJU ranked 4th in Karnataka

TIMETABLE AND CALENDAR:
- Class timetable 2026: sju.edu.in/services/timetable/time-table-2026.php
- Academic calendar: sju.edu.in/about/calendar.php

CERTIFICATE COURSES:
- Short-term certificate and skill-based courses available
- Details: sju.edu.in/services/certificate-courses.php

ALUMNI:
- Active alumni network
- Alumni portal: alumni.sju.edu.in

INTERNATIONAL STUDENTS:
- SJU welcomes international students
- Page: sju.edu.in/internationalstudents/internationalstudents.php
"""


def search_supabase(question: str) -> str:
    """Search Supabase for relevant chunks to add as extra context"""
    if not sb:
        return ""
    try:
        stop_words = {"what","when","where","how","is","are","the","a","an","at","in",
                      "of","for","to","do","does","tell","me","about","i","can","will",
                      "which","who","many","much","sju","college","university","joseph",
                      "st","please","give","yes","no","more","explain","ok","sure","hi","hello"}
        words = [w.lower().strip("?.,!") for w in question.split()
                 if w.lower() not in stop_words and len(w) > 2]

        if not words:
            return ""

        all_results = []
        term = " ".join(words[:4])
        r = sb.table("sju_knowledge").select("content, page_name") \
            .ilike("content", f"%{term}%").limit(4).execute()
        if r.data:
            all_results.extend(r.data)

        if not all_results:
            for word in words[:3]:
                r = sb.table("sju_knowledge").select("content, page_name") \
                    .ilike("content", f"%{word}%").limit(2).execute()
                if r.data:
                    all_results.extend(r.data)

        if all_results:
            seen = set()
            chunks = []
            for row in all_results:
                if row["content"] not in seen:
                    seen.add(row["content"])
                    chunks.append(f"[From SJU website - {row['page_name']}]\n{row['content']}")
            return "\n\n".join(chunks[:4])
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
        return {"answer": "Gemini API key not configured. Please add GEMINI_API_KEY in Railway variables."}

    # Get extra context from Supabase if available
    extra_context = search_supabase(q)
    full_system = SYSTEM_PROMPT
    if extra_context:
        full_system += f"\n\nADDITIONAL CONTEXT FROM SJU WEBSITE:\n{extra_context}"

    # Build conversation for Gemini
    # Gemini uses "contents" format with "parts"
    contents = []

    # Add conversation history
    if req.history:
        for msg in req.history[-12:]:
            if msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})

    # Add current question
    contents.append({"role": "user", "parts": [{"text": q}]})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {
                        "parts": [{"text": full_system}]
                    },
                    "contents": contents,
                    "generationConfig": {
                        "maxOutputTokens": 400,
                        "temperature": 0.2,
                    }
                }
            )

            data = resp.json()

            # Extract answer from Gemini response
            if "candidates" in data and data["candidates"]:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    answer = candidate["content"]["parts"][0].get("text", "")
                    if answer.strip():
                        return {"answer": answer.strip()}

            # Handle errors
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                print(f"Gemini error: {error_msg}")
                if "quota" in error_msg.lower() or "429" in str(resp.status_code):
                    return {"answer": (
                        "I'm getting too many requests right now. Please wait a moment and try again.\n\n"
                        "Or contact SJU directly:\n"
                        "📞 080-2227-4079\n"
                        "🌐 sju.edu.in"
                    )}

            return {"answer": "Sorry, I couldn't generate a response. Please try again."}

    except httpx.TimeoutException:
        return {"answer": "Taking too long to respond. Please try again in a moment."}
    except Exception as e:
        print(f"Error: {e}")
        return {"answer": "Something went wrong. Please try again or call SJU at 080-2227-4079."}


@app.get("/health")
def health():
    return {
        "status": "running",
        "ai_model": "gemini-2.5-flash (free tier)",
        "supabase": sb is not None,
        "gemini_configured": bool(GEMINI_KEY),
    }


@app.get("/")
def root():
    return FileResponse("static/index.html")
