# SJU Chatbot — Live Website
AI chatbot demo for St Joseph's University, Bengaluru.
Deployable to Railway.app for a free public URL.

---

## Deploy to Railway (get a live URL in 5 minutes)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "SJU chatbot - initial deploy"
# Go to github.com → New repository → name: sju-chatbot → Create
git remote add origin https://github.com/YOURUSERNAME/sju-chatbot.git
git push -u origin main
```

### Step 2 — Deploy on Railway
1. Go to **railway.app** → Sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `sju-chatbot` repo
4. Railway auto-detects Python and deploys it

### Step 3 — Add your OpenRouter API key
1. In Railway dashboard → click your project → **Variables** tab
2. Add variable:
   - Name: `OPENROUTER_API_KEY`
   - Value: your OpenRouter key (get free at openrouter.ai)
3. Railway automatically redeploys

### Step 4 — Get your URL
Railway gives you a URL like: `sju-chatbot.up.railway.app`
Share this with anyone — it works on any device, anywhere in the world.

---

## Get your free OpenRouter API key
1. Go to openrouter.ai
2. Sign up with Google (no credit card needed)
3. Click your profile → Keys → Create Key
4. Copy the key (starts with sk-or-...)
5. Paste it in Railway environment variables

Free tier: 200 requests/day, 20/minute — more than enough for a demo.

---

## File structure
```
sju-chatbot/
├── main.py          ← FastAPI server + chat API
├── requirements.txt ← Python dependencies
├── Procfile         ← tells Railway how to start
├── .gitignore
├── static/
│   └── index.html   ← the full SJU website clone + chatbot
└── README.md
```

---

## Tech stack (for your GitHub / CV)
- **Backend**: FastAPI + Python
- **AI**: DeepSeek R1 via OpenRouter API (free tier)
- **Frontend**: HTML/CSS/JavaScript — no framework needed
- **Hosting**: Railway.app (free tier)
- **Design**: Pixel-faithful replica of sju.edu.in

Built by: [Your Name] — MSc Big Data Analytics, SJU Bengaluru 2025-26
