"""
SETUP — run this ONCE on your laptop
Scrapes SJU website → splits into chunks → creates embeddings → stores in Supabase
Run: python setup_database.py
"""
import os, time, requests
from bs4 import BeautifulSoup
from supabase import create_client
from sentence_transformers import SentenceTransformer

# ── Your Supabase credentials (set these as environment variables) ──
SUPABASE_URL = "https://mvszfevopamhkratxeak.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im12c3pmZXZvcGFtaGtyYXR4ZWFrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MjU1MDA2MiwiZXhwIjoyMDk4MTI2MDYyfQ.QJbCXfRHjwlIl2HpkAavoPPbGGeDLsjWyc3mzvY9D8Y"

# ── All SJU pages to scrape ──
PAGES = [
    ("home",           "https://www.sju.edu.in/"),
    ("about",          "https://www.sju.edu.in/about/about-the-university.php"),
    ("history",        "https://www.sju.edu.in/about/milestones.php"),
    ("vision",         "https://www.sju.edu.in/about/vision-and-mission.php"),
    ("schools",        "https://www.sju.edu.in/about/sju-schools.php"),
    ("management",     "https://www.sju.edu.in/about/management.php"),
    ("faculty",        "https://www.sju.edu.in/about/faculty-members.php"),
    ("contact",        "https://www.sju.edu.in/about/contact-us.php"),
    ("admissions",     "https://www.sju.edu.in/admissions/admissions.php"),
    ("placements",     "https://www.sju.edu.in/placements/about-placements.php"),
    ("hostel",         "https://www.sju.edu.in/services/hostel/university-hostel.php"),
    ("scholarships",   "https://www.sju.edu.in/student-support/scholarships_page"),
    ("campus",         "https://www.sju.edu.in/services/sju-campus-facilities.php"),
    ("it_school",      "https://www.sju.edu.in/school-of-information-technology/school-of-information-technology.php"),
    ("business",       "https://www.sju.edu.in/school-of-business/school-of-business.php"),
    ("life_sciences",  "https://www.sju.edu.in/school-of-life-sciences/school-of-life-sciences.php"),
    ("physical_sci",   "https://www.sju.edu.in/school-of-physical-sciences/school-of-physical-sciences.php"),
    ("chemical_sci",   "https://www.sju.edu.in/school-of-chemical-sciences/school-of-chemical-sciences.php"),
    ("humanities",     "https://www.sju.edu.in/school-of-humanities-and-social-sciences/school-of-humanities-and-social-sciences.php"),
    ("media",          "https://www.sju.edu.in/school-of-communication-media-studies/school-of-communication-media-studies.php"),
    ("social_work",    "https://www.sju.edu.in/school-of-social-work/school-of-social-work.php"),
    ("announcements",  "https://www.sju.edu.in/announcements.php"),
    ("exam_timetable", "https://www.sju.edu.in/examination/exam-time-table.php"),
    ("exam_notices",   "https://www.sju.edu.in/examination/examinationnotices.php"),
    ("certificates",   "https://www.sju.edu.in/services/certificate-courses.php"),
    ("sports",         "https://www.sju.edu.in/services/sports"),
    ("nss",            "https://www.sju.edu.in/services/sju-nss/national-service-scheme.php"),
    ("ncc",            "https://www.sju.edu.in/services/sju-national-cadet-corps.php"),
    ("counselling",    "https://www.sju.edu.in/student-support/counselling-services.php"),
    ("antiragging",    "https://www.sju.edu.in/student-support/antiraggingcell.php"),
    ("lateral_entry",  "https://www.sju.edu.in/student-support/lateralentry.php"),
    ("library",        "https://www.sju.edu.in/library/library.php"),
    ("calendar",       "https://www.sju.edu.in/about/calendar.php"),
    ("timetable",      "https://www.sju.edu.in/services/timetable/time-table-2026.php"),
]

def scrape_page(url):
    """Download a page and return clean text"""
    try:
        r = requests.get(url, timeout=12,
            headers={"User-Agent": "SJU-Student-Project/1.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        # Remove nav, scripts, footer — keep real content
        for tag in soup(["script","style","nav","footer","header","noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Keep only lines with real content
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 20]
        return "\n".join(lines)
    except Exception as e:
        print(f"    Failed: {e}")
        return ""

def split_into_chunks(text, url, page_name, chunk_size=400):
    """Split text into overlapping chunks of ~400 words"""
    words = text.split()
    chunks = []
    step = chunk_size - 50  # 50 word overlap
    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        if len(chunk_words) < 30:  # skip tiny chunks
            continue
        chunk_text = " ".join(chunk_words)
        chunks.append({
            "content": chunk_text,
            "source_url": url,
            "page_name": page_name,
        })
    return chunks

def main():
    print("=" * 55)
    print("  SJU Chatbot — Supabase Database Setup")
    print("=" * 55)

    # Connect to Supabase
    print("\nConnecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("  Connected!")

    # Load embedding model (free, local)
    print("\nLoading embedding model...")
    print("  (Downloads ~90MB the first time)")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    print("  Embedding model ready!")

    # Scrape all pages
    print(f"\nScraping {len(PAGES)} SJU website pages...")
    all_chunks = []
    for name, url in PAGES:
        print(f"  Scraping: {name}...", end=" ")
        text = scrape_page(url)
        if text:
            chunks = split_into_chunks(text, url, name)
            all_chunks.extend(chunks)
            print(f"{len(chunks)} chunks")
        else:
            print("skipped")
        time.sleep(1)  # be polite to the server

    print(f"\nTotal chunks created: {len(all_chunks)}")

    # Create embeddings and upload to Supabase
    print("\nCreating embeddings and uploading to Supabase...")
    print("  (This takes 3-5 minutes)")

    # Upload in batches of 50
    batch_size = 50
    uploaded = 0
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]

        # Create embeddings for this batch
        texts = [c["content"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False)

        # Prepare rows for Supabase
        rows = []
        for chunk, embedding in zip(batch, embeddings):
            rows.append({
                "content":    chunk["content"],
                "source_url": chunk["source_url"],
                "page_name":  chunk["page_name"],
                "embedding":  embedding.tolist(),
            })

        # Insert into Supabase
        supabase.table("sju_knowledge").insert(rows).execute()
        uploaded += len(batch)
        print(f"  Uploaded {uploaded}/{len(all_chunks)} chunks...")

    print("\n" + "=" * 55)
    print(f"  Done! {uploaded} chunks stored in Supabase.")
    print("  Your chatbot now knows everything on SJU's website!")
    print("=" * 55)
    print("\nNext: push your code to GitHub and Railway will redeploy.")

if __name__ == "__main__":
    main()
