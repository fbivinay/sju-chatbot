"""
SJU Chatbot - Production Server
Uses OpenRouter API (free tier) for AI responses.
No database needed — AI answers from built-in SJU knowledge.
"""
import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (CSS, images etc if needed)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── SJU Knowledge Base — baked in so no DB needed on free hosting ─────────────
SJU_KNOWLEDGE = """
You are the official AI assistant for St Joseph's University (SJU), Bengaluru.
Answer students questions accurately and helpfully using this knowledge:

ABOUT SJU:
- Full name: St Joseph's University, Bengaluru
- Address: 36, Lalbagh Road (corner of Langford Road), Langford Gardens, Bengaluru - 560027
- Phone: +91 80 2227 4079 | Email: pro@sju.edu.in | Website: sju.edu.in
- WhatsApp for admissions: 9480811912
- Founded: 1882 by Paris Foreign Missionary Fathers. Managed by Jesuits (Society of Jesus) since 1937
- Became India's first Public-Private University under RUSA 2.0 on 2 July 2022
- Inaugurated by President of India Droupadi Murmu on 27 September 2022
- Motto: "Fide et Labore" (Faith and Toil)
- NAAC Grade: A++ | UGC Recognised | College of Excellence by UGC

RANKINGS (The Week Magazine University Ranking 2026):
- 49th Rank: Multidisciplinary Universities (All India)
- 19th Rank: Multidisciplinary Universities (South Zone)
- 18th Rank: Private & Deemed Multidisciplinary Universities (All India)
- 8th Rank: Private & Deemed Multidisciplinary Universities (South Zone)
- 4th Rank: Private & Deemed Multidisciplinary Universities (Karnataka Statewise)
India Today 2025: #6 BCA, #8 BSc, #18 Arts, #44 BCom, #18 MSW

SCHOOLS AND PROGRAMMES:
1. School of Information Technology
   - BCA (Bachelor of Computer Applications) - 3 years
   - MCA (Master of Computer Applications) - 2 years
   - MSc Computer Science - 2 years
   - MSc Big Data Analytics - 2 years

2. School of Business
   - BBA (Bachelor of Business Administration) - 3 years
   - BCom (Bachelor of Commerce) - 3 years
   - MBA - 2 years
   - MCom - 2 years

3. School of Physical Sciences
   - BSc Physics, Mathematics, Statistics, Electronics - 3 years
   - MSc Physics, Mathematics, Statistics - 2 years

4. School of Life Sciences
   - BSc Biotechnology, Microbiology, Food Science & Technology - 3 years
   - MSc Biotechnology, Microbiology, Food Science & Technology - 2 years

5. School of Chemical Sciences
   - BSc Chemistry - 3 years
   - MSc Organic Chemistry, Analytical Chemistry - 2 years

6. School of Humanities & Social Sciences
   - BA Psychology, Economics, History, Sociology - 3 years
   - MA Psychology, Economics - 2 years

7. School of Communication & Media Studies
   - BA Visual Communication, Journalism - 3 years
   - MA Media Studies - 2 years

8. School of Languages & Literatures
   - BA English Literature, Kannada, French, Hindi - 3 years
   - MA English, Kannada - 2 years

9. School of Social Work
   - BSW (Bachelor of Social Work) - 3 years
   - MSW (Master of Social Work) - 2 years

Also offers: PhD programmes in most departments, Certificate courses, Lateral Entry

ADMISSIONS 2026-27:
- Apply online: admissions.sju.edu.in
- Eligibility: Minimum 50% marks in qualifying exam for both UG and PG
- UG admission: based on merit + SJU Entrance Test (for some courses) + interview
- PG admission: based on bachelor's degree merit + SJUET (SJU Entrance Test) + interview
- UG applications open: December - January
- PG applications open: February - April
- Application fee: varies by course, check admissions.sju.edu.in
- Documents needed: Mark sheets of previous exams, ID proof, passport photos, caste/income certificate if applicable
- Lateral entry admissions available for selected programmes

FEES (approximate, verify at admissions.sju.edu.in):
- BSc: ₹65,000 - ₹1.5 Lakh per year (depending on specialisation)
- BCA: ₹1.5 Lakh per year
- BBA/BCom: ₹80,000 - ₹1.2 Lakh per year
- BA: ₹50,000 - ₹80,000 per year
- MSc: varies by specialisation, check admissions portal
- MCA: contact admissions office
- MBA/MCom: contact admissions office
- For exact fees: admissions.sju.edu.in or call 080-2227-4079

PLACEMENTS:
- Department: Centre for Student Placements and Skill Development
- Top recruiters: Cognizant, Deloitte, Accenture, EY, KPMG, Britannia Industries, Federal Bank, HP India, BioCon, MuSigma, Ditto Insurance, Infosys, Wipro, TCS, Amazon
- Activities: Industry visits, guest lectures, resume preparation, mock interviews, skill development workshops, internship facilitation
- Placement starts in final year of each programme

HOSTEL:
- Separate hostels for boys and girls on campus
- Facilities: Furnished rooms, mess/dining hall, Wi-Fi, 24/7 CCTV, warden support, reading room
- Apply: sju.edu.in/services/hostel/university-hostel.php
- Contact hostel office directly for current availability and fees

SCHOLARSHIPS:
- Government scholarships via Karnataka SSP portal: ssp.postmatric.karnataka.gov.in
- Ishan Uday Scholarship: for students from North East India
- PG Indira Gandhi Scholarship: for single girl child
- SC/ST Scholarships: via state government portal
- Vidyaposhak Scholarship: merit + financial need basis
- UGC PG Scholarships: for university rank holders
- Fee exemptions available for students from marginalised communities
- More info: sju.edu.in/student-support/scholarships_page

CAMPUS FACILITIES:
- Digitized classrooms with projectors and smart boards
- Campus-wide Wi-Fi
- Well-equipped science and IT laboratories
- Central Library with digital resources and e-journals
- Auditorium and multiple seminar halls
- Cafeteria / canteen
- Sports facilities: football ground, cricket ground, basketball courts, volleyball courts, badminton courts
- Observatory (unique to SJU)
- NSS (National Service Scheme) unit
- NCC (National Cadet Corps) unit
- Counselling and psychological support centre
- Health and medical facilities on campus
- Green, eco-friendly campus with CCTV surveillance
- Anti-ragging cell
- Gender Sensitisation Cell
- Equal Opportunity Cell
- Internal Complaints Committee

SPORTS AT SJU:
- Active sports programmes including football, cricket, basketball, volleyball, badminton, athletics
- Sports selections and trials are announced at the start of each academic semester
- Check for announcements: sju.edu.in/announcements.php
- Or contact the Physical Education / Sports department directly on campus
- Sports page: sju.edu.in/services/sports

STUDENT SUPPORT:
- Counselling Services: sju.edu.in/student-support/counselling-services.php
- Anti-Ragging Cell: sju.edu.in/student-support/antiraggingcell.php
- Student Grievance: sju.edu.in/student-support/student-grievance-redressal.php
- Mid Day Meals programme available
- Facilities for Differently Abled students
- Campus Ministry for spiritual support

EXAMINATIONS:
- Exam timetables: sju.edu.in/examination/exam-time-table.php
- Exam notices: sju.edu.in/examination/examinationnotices.php
- Seating arrangements: sju.edu.in/examination/sjuexamseatingarrangement.php
- Results and rank holders: sju.edu.in/examination/rank-holders.php

LATEST ANNOUNCEMENTS (as of June 2026):
- Orientation Notice to all First Year Students 2026-27 (25 May 2026)
- Extension of Last Date for Convocation and Degree Completion Certificates — 27.05.2026 to 13.06.2026
- Admissions 2026-27 are open

IMPORTANT RULES FOR YOUR RESPONSES:
1. Only answer based on the above information. Do not make up dates, fees, or names.
2. If you don't have specific information (like exact upcoming sports trial dates), honestly say so and direct the user to the right page or phone number.
3. Never confuse topics — sports question gets sports answer, scholarship question gets scholarship answer.
4. Be friendly, warm, and concise. Use bullet points for lists.
5. Always end with a helpful next step: a link, phone number, or what to do next.
6. Keep answers under 200 words unless the question genuinely needs more detail.
"""

# ── Chat endpoint ──────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str

@app.post("/chat")
async def chat(req: ChatRequest):
    q = req.question.strip()
    if not q:
        return {"answer": "Please type a question!"}
    if len(q) > 500:
        return {"answer": "Please keep your question shorter."}

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        return {"answer": "⚠️ API key not configured. Please set OPENROUTER_API_KEY in Railway environment variables."}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://sju-chatbot.up.railway.app",
                    "X-Title": "SJU Chatbot",
                },
                json={
                    "model": "meta-llama/llama-3.3-70b-instruct:free",
                    "messages": [
                        {"role": "system", "content": SJU_KNOWLEDGE},
                        {"role": "user",   "content": q}
                    ],
                    "max_tokens": 400,
                    "temperature": 0.1,
                }
            )
            data = resp.json()

            if "error" in data:
                # Fallback to another free model if first fails
                resp2 = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openrouter_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "mistralai/mistral-7b-instruct:free",
                        "messages": [
                            {"role": "system", "content": SJU_KNOWLEDGE},
                            {"role": "user",   "content": q}
                        ],
                        "max_tokens": 400,
                        "temperature": 0.1,
                    }
                )
                data = resp2.json()

            answer = data["choices"][0]["message"]["content"]
            return {"answer": answer}

    except httpx.TimeoutException:
        return {"answer": "The AI is taking too long to respond. Please try again in a moment."}
    except Exception as e:
        return {"answer": f"Something went wrong. Please try again or visit sju.edu.in directly. (Error: {str(e)[:80]})"}

# ── Serve the frontend ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    key_set = bool(os.getenv("OPENROUTER_API_KEY"))
    return {"status": "running", "api_key_configured": key_set}
