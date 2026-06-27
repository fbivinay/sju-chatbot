"""
SJU Chatbot - Production Server (Fixed)
Uses OpenRouter with multiple fallback models.
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

app.mount("/static", StaticFiles(directory="static"), name="static")

# Try these models in order until one works
FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-3-4b-it:free",
    "openrouter/auto",
]

SJU_KNOWLEDGE = """
You are the official AI assistant for St Joseph's University (SJU), Bengaluru.
Answer students questions accurately and helpfully using this knowledge:

ABOUT SJU:
- Full name: St Joseph's University, Bengaluru
- Address: 36, Lalbagh Road (corner of Langford Road), Langford Gardens, Bengaluru - 560027
- Phone: +91 80 2227 4079 | Email: pro@sju.edu.in | Website: sju.edu.in
- WhatsApp for admissions: 9480811912
- Founded: 1882 by Paris Foreign Missionary Fathers. Managed by Jesuits since 1937
- Became India's first Public-Private University under RUSA 2.0 on 2 July 2022
- Motto: Fide et Labore (Faith and Toil)
- NAAC Grade: A++ | UGC Recognised | College of Excellence by UGC

RANKINGS (The Week Magazine University Ranking 2026):
- 49th Rank: Multidisciplinary Universities All India
- 19th Rank: Multidisciplinary Universities South Zone
- 18th Rank: Private & Deemed Multidisciplinary Universities All India
- 8th Rank: Private & Deemed Multidisciplinary Universities South Zone
- 4th Rank: Private & Deemed Multidisciplinary Universities Karnataka
- India Today 2025: 6th BCA, 8th BSc, 18th Arts

SCHOOLS AND PROGRAMMES:
1. School of Information Technology: BCA, MCA, MSc Computer Science, MSc Big Data Analytics
2. School of Business: BBA, BCom, MBA, MCom
3. School of Physical Sciences: BSc/MSc Physics, Mathematics, Statistics, Electronics
4. School of Life Sciences: BSc/MSc Biotechnology, Microbiology, Food Science
5. School of Chemical Sciences: BSc/MSc Chemistry (Organic, Analytical)
6. School of Humanities & Social Sciences: BA/MA Psychology, Economics, History, Sociology
7. School of Communication & Media Studies: BA Visual Communication, Journalism, MA Media Studies
8. School of Languages & Literatures: BA/MA English, Kannada, French, Hindi
9. School of Social Work: BSW, MSW
Also: PhD programmes in most departments, Certificate courses, Lateral Entry options

ADMISSIONS 2026-27:
- Apply online: admissions.sju.edu.in
- Eligibility: Minimum 50% in qualifying exam
- UG: merit + entrance test + interview
- PG: bachelor's degree merit + SJUET + interview
- UG applications: December - January
- PG applications: February - April
- Contact: 080-2227-4079 or WhatsApp 9480811912

FEES (approximate):
- BSc: 65,000 to 1.5 Lakh per year
- BCA: 1.5 Lakh per year
- BBA/BCom: 80,000 to 1.2 Lakh per year
- BA: 50,000 to 80,000 per year
- PG fees: check admissions.sju.edu.in

PLACEMENTS:
- Department: Centre for Student Placements and Skill Development
- Top recruiters: Cognizant, Deloitte, Accenture, EY, KPMG, Britannia, Federal Bank, HP India, BioCon, MuSigma, Ditto, Infosys, Wipro, TCS
- Activities: industry visits, guest lectures, resume prep, mock interviews, internships

HOSTEL:
- Separate hostels for boys and girls on campus
- Facilities: rooms, mess, Wi-Fi, 24/7 CCTV, warden support
- Apply: sju.edu.in/services/hostel/university-hostel.php

SCHOLARSHIPS:
- Karnataka SSP portal: ssp.postmatric.karnataka.gov.in
- Ishan Uday: for students from North East India
- PG Indira Gandhi Scholarship: for single girl child
- SC/ST Scholarships: via state government portal
- Vidyaposhak Scholarship: merit + financial need
- UGC PG Scholarships: for university rank holders
- More info: sju.edu.in/student-support/scholarships_page

CAMPUS FACILITIES:
- Digitized classrooms, campus Wi-Fi, science and IT labs
- Central Library, Auditorium, Cafeteria
- Sports: football, cricket, basketball, volleyball, badminton courts
- Observatory, NSS, NCC, Counselling centre, Health facilities
- Green eco-friendly campus with CCTV surveillance

SPORTS AT SJU:
- Active sports: football, cricket, basketball, volleyball, badminton, athletics
- Sports selections and trials announced at the start of each academic semester
- Check announcements: sju.edu.in/announcements.php
- Contact Physical Education department on campus
- Sports page: sju.edu.in/services/sports

STUDENT SUPPORT:
- Counselling: sju.edu.in/student-support/counselling-services.php
- Anti-Ragging: sju.edu.in/student-support/antiraggingcell.php
- Grievance: sju.edu.in/student-support/student-grievance-redressal.php
- Mid Day Meals programme available
- Facilities for Differently Abled students

EXAMINATIONS:
- Timetables: sju.edu.in/examination/exam-time-table.php
- Notices: sju.edu.in/examination/examinationnotices.php
- Seating: sju.edu.in/examination/sjuexamseatingarrangement.php
- Results: sju.edu.in/examination/rank-holders.php

LATEST NOTICES (June 2026):
- Orientation Notice to all First Year Students 2026-27 (25 May 2026)
- Extension of Last Date for Convocation and Degree Completion Certificates to 13 June 2026
- Admissions 2026-27 are open

RULES:
1. Only use the information above. Never make up dates, fees, or names.
2. If you don't know something specific, say so honestly and give the right contact or link.
3. Never confuse topics. Sports question = sports answer only.
4. Be friendly and concise. Use bullet points for lists.
5. End every answer with a helpful next step.
6. Keep answers under 200 words.
"""

class ChatRequest(BaseModel):
    question: str

@app.post("/chat")
async def chat(req: ChatRequest):
    q = req.question.strip()
    if not q:
        return {"answer": "Please type a question!"}
    if len(q) > 500:
        return {"answer": "Please keep your question a bit shorter."}

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        return {"answer": "API key not configured. Please add OPENROUTER_API_KEY in Railway environment variables."}

    # Try each model until one works
    last_error = ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for model in FREE_MODELS:
            try:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openrouter_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://sju-chatbot.up.railway.app",
                        "X-Title": "SJU Chatbot",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SJU_KNOWLEDGE},
                            {"role": "user",   "content": q}
                        ],
                        "max_tokens": 400,
                        "temperature": 0.1,
                    }
                )

                data = resp.json()

                # Check for valid response
                if "choices" in data and len(data["choices"]) > 0:
                    answer = data["choices"][0]["message"]["content"]
                    if answer and answer.strip():
                        return {"answer": answer.strip(), "model": model}

                # If this model failed, note the error and try next
                if "error" in data:
                    last_error = data["error"].get("message", "Unknown error")
                    continue

            except httpx.TimeoutException:
                last_error = "timeout"
                continue
            except Exception as e:
                last_error = str(e)
                continue

    # All models failed
    return {
        "answer": (
            "I'm having trouble connecting to the AI right now. "
            "This is usually temporary — please try again in a moment.\n\n"
            "Or contact SJU directly:\n"
            "📞 080-2227-4079\n"
            "🌐 sju.edu.in\n"
            "💬 WhatsApp: 9480811912"
        )
    }

@app.get("/health")
def health():
    key_set = bool(os.getenv("OPENROUTER_API_KEY"))
    return {
        "status": "running",
        "api_key_configured": key_set,
        "models_available": FREE_MODELS
    }

@app.get("/")
def root():
    return FileResponse("static/index.html")
