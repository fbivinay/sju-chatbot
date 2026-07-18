# SJU Chatbot — Live Website
AI chatbot demo for St Joseph's University, Bengaluru.
Deployable to Vercel for a free public URL.

---

## Deploy to Vercel (get a live URL in 5 minutes)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "SJU chatbot - initial deploy"
# Go to github.com → New repository → name: sju-chatbot → Create
git remote add origin https://github.com/YOURUSERNAME/sju-chatbot.git
git push -u origin main
```

### Step 2 — Deploy on Vercel
1. Go to **vercel.com** → Sign in with GitHub
2. Click **Add New** → **Project** → **Import** your `sju-chatbot` repo
3. Vercel reads `vercel.json` and deploys `main.py` as a Python serverless function automatically — no build command needed

### Step 3 — Add your Google Gemini API key
1. In the Vercel dashboard → your project → **Settings** → **Environment Variables**
2. Add:
   - Name: `GEMINI_API_KEY`
   - Value: your Gemini key (get free at ai.google.dev)
3. (Optional, for the knowledge base) Also add `SUPABASE_URL` and `SUPABASE_KEY`
4. Redeploy (**Deployments** tab → **...** → **Redeploy**) so the new env vars take effect

### Step 4 — Get your URL
Vercel gives you a URL like: `sju-chatbot.vercel.app`
Share this with anyone — it works on any device, anywhere in the world.

---

## Get your free Google Gemini API key
1. Go to ai.google.dev
2. Click **Get API Key** (Google account required)
3. Copy the key (starts with AIza...)
4. Paste it in Vercel environment variables

Free tier: up to 15 requests/minute — more than enough for a demo.

---

## File structure
```
sju-chatbot/
├── main.py            ← FastAPI server + chat API
├── vercel.json         ← tells Vercel how to build/route main.py
├── requirements.txt   ← Python dependencies
├── .gitignore
├── static/
│   └── index.html     ← the full SJU website clone + chatbot
└── README.md
```

---

## Tech stack (for your GitHub / CV)
- **Backend**: FastAPI + Python
- **AI**: Google Gemini 2.5 Flash (free tier)
- **Frontend**: HTML/CSS/JavaScript — no framework needed
- **Hosting**: Vercel (free tier, Python serverless functions)
- **Design**: Pixel-faithful replica of sju.edu.in
- **Database**: Supabase with pgvector (optional, for RAG knowledge base)

Built by: [Your Name] — MSc Big Data Analytics, SJU Bengaluru 2025-26
