"""
SJU URL-LIST CRAWLER  (crawl once -> serve many)
Feeds Firecrawl an EXACT list of real content URLs, renders each (JS included),
and loads the real text into Supabase (sju_knowledge table).

Run on your laptop:
    pip install requests supabase sentence-transformers
    python crawl_urls.py

This is laptop-only. Never push it to GitHub with keys in it.
"""
import os
import time
import requests
from supabase import create_client
from sentence_transformers import SentenceTransformer

# ── PASTE YOUR KEYS HERE (laptop only) ────────────────────────────────────────
FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY", "fc-YOUR_KEY_HERE")
SUPABASE_URL  = os.getenv("SUPABASE_URL", "https://mvszfevopamhkratxeak.supabase.co")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_SERVICE_ROLE_KEY")

# ══════════════════════════════════════════════════════════════════════════════
# 1) IMPORTANT INFO PAGES  (the high-value content for a chatbot)
# ══════════════════════════════════════════════════════════════════════════════
INFO_URLS = [
    "https://www.sju.edu.in/",
    "https://www.sju.edu.in/admissions",
    "https://www.sju.edu.in/about/about-the-university.php",
    "https://www.sju.edu.in/about/sju-schools.php",
    "https://www.sju.edu.in/about/vision-and-mission.php",
    "https://www.sju.edu.in/about/milestones.php",
    "https://www.sju.edu.in/hostel",
    "https://www.sju.edu.in/library",
    "https://www.sju.edu.in/campus-facilities",
    "https://www.sju.edu.in/counselling",
    "https://www.sju.edu.in/grievance",
    "https://www.sju.edu.in/medicalfacilities",
    "https://www.sju.edu.in/differently-abled",
    "https://www.sju.edu.in/lateralentry",
    "https://www.sju.edu.in/student-support/scholarships_page",
    "https://www.sju.edu.in/placements/about-placements.php",
    "https://www.sju.edu.in/school-of-information-technology/school-of-information-technology.php",
    "https://www.sju.edu.in/school-of-business/school-of-business.php",
    "https://www.sju.edu.in/school-of-physical-sciences/school-of-physical-sciences.php",
    "https://www.sju.edu.in/school-of-life-sciences/school-of-life-sciences.php",
    "https://www.sju.edu.in/school-of-chemical-sciences/school-of-chemical-sciences.php",
    "https://www.sju.edu.in/school-of-humanities-and-social-sciences/school-of-humanities-and-social-sciences.php",
    "https://www.sju.edu.in/school-of-communication-media-studies/school-of-communication-media-studies.php",
    "https://www.sju.edu.in/school-of-social-work/school-of-social-work.php",
    "https://www.sju.edu.in/examination/exam-time-table.php",
    "https://www.sju.edu.in/examination/examinationnotices.php",
    "https://www.sju.edu.in/services/certificate-courses.php",
    "https://www.sju.edu.in/services/sports",
]

# ══════════════════════════════════════════════════════════════════════════════
# 2) PASTE EXTRA URLs YOU HARVEST  (course/department/programme detail pages)
#    Use Instant Data Scraper on the Academics listing pages to grab these,
#    then paste them here. Leave empty if you don't have them yet.
# ══════════════════════════════════════════════════════════════════════════════
EXTRA_URLS = [
    # "https://www.sju.edu.in/departments/...",
    # "https://www.sju.edu.in/programmes/...",
]

# ══════════════════════════════════════════════════════════════════════════════
# 3) RECENT 2026 EVENTS  (pre-filled from your scrape)
# ══════════════════════════════════════════════════════════════════════════════
_EVENT_SLUGS_2026 = [
    "office-for-international-affairs-welcomes-professor-till-rachmann-and-dr-maneesh-pauls",
    "a-talk-on-women-empowerment-by-ms-nazneen-banu",
    "academic--industrial-connect-initiative-2026",
    "footprints-2026",
    "expert-talk-on-alternative-proteins",
    "on-representation-discourse-and-power-with-dr-etienne-rassendran",
    "department-colloquium",
    "visages-2026",
    "neerathon-26",
    "national-science-day-celebrations",
    "career-opportunities-in-pharma-and-chemical-industries",
    "open-heart26",
    "inter-collegiate-fest---emporio",
    "educational-and-industrial-visit",
    "cinema-caste-critique",
    "hrd-expert-talk",
    "ai-for-atmanirbhar-bharat-hei-engagements-towards-indiaai-impact-summit-2026",
    "prayaag-60",
    "national-symposium",
    "scms-international-conference-and-association-fests-2026",
    "the-oxford-sju-debate",
    "two-day-national-level--workshop-on-innovative-and-sustainable-processing-of-fruits-and-vegetables",
    "conversations-with-a-mathematician",
    "international-conference---smartchem-2026-chains",
    "fr-ambrose-pinto-memorial-lecture",
    "sparks26---inaugural-ceremony",
]
EVENT_URLS = [f"https://www.sju.edu.in/events-detail.php?slug={s}" for s in _EVENT_SLUGS_2026]


def scrape_one(url):
    """Scrape a single URL via Firecrawl (renders JavaScript). Returns markdown text."""
    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v2/scrape",
            headers={
                "Authorization": f"Bearer {FIRECRAWL_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
            timeout=90,
        )
        data = resp.json()
        # response shape: {"success": true, "data": {"markdown": "...", "metadata": {...}}}
        d = data.get("data", data)
        if isinstance(d, dict):
            md = d.get("markdown", "") or d.get("content", "")
            meta = d.get("metadata", {}) or {}
            title = meta.get("title", "") if isinstance(meta, dict) else ""
            return md, title
        return "", ""
    except Exception as e:
        print(f"      error: {e}")
        return "", ""


def chunk_text(text, url, title):
    """Split a page into ~350-word chunks."""
    words = text.split()
    chunks = []
    size, step = 400, 350
    for i in range(0, len(words), step):
        piece = " ".join(words[i:i + size])
        if len(piece) < 40:
            continue
        name = title or url.rstrip("/").split("/")[-1].replace(".php", "").replace("-", " ")
        chunks.append({"content": piece, "source_url": url, "page_name": name[:120]})
    return chunks


def main():
    print("=" * 60)
    print("  SJU URL-LIST CRAWLER (Firecrawl -> Supabase)")
    print("=" * 60)

    all_urls = INFO_URLS + EXTRA_URLS + EVENT_URLS
    # de-duplicate while keeping order
    seen = set()
    urls = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            urls.append(u)
    print(f"\nURLs to fetch: {len(urls)} "
          f"({len(INFO_URLS)} info + {len(EXTRA_URLS)} extra + {len(EVENT_URLS)} events)")

    print("\nConnecting to Supabase and loading embedding model...")
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    print("  Ready!")

    print("\nClearing old data from sju_knowledge...")
    try:
        sb.table("sju_knowledge").delete().neq("id", 0).execute()
        print("  Cleared!")
    except Exception as e:
        print(f"  Note: {e}")

    print("\nFetching pages via Firecrawl (renders JavaScript)...")
    all_chunks = []
    for idx, url in enumerate(urls, 1):
        short = url.replace("https://www.sju.edu.in", "")[:55]
        print(f"  [{idx}/{len(urls)}] {short} ...", end=" ")
        md, title = scrape_one(url)
        if md and len(md) > 60:
            ch = chunk_text(md, url, title)
            all_chunks.extend(ch)
            print(f"{len(ch)} chunks")
        else:
            print("thin/empty")
        time.sleep(1)  # be polite

    print(f"\nTotal chunks of real content: {len(all_chunks)}")
    if not all_chunks:
        print("  Nothing captured. Check your Firecrawl key and try a couple of URLs.")
        return

    print("\nEmbedding and uploading to Supabase...")
    B = 50
    up = 0
    for i in range(0, len(all_chunks), B):
        batch = all_chunks[i:i + B]
        embs = model.encode([c["content"] for c in batch], show_progress_bar=False)
        rows = [{
            "content": c["content"],
            "source_url": c["source_url"],
            "page_name": c["page_name"],
            "embedding": e.tolist(),
        } for c, e in zip(batch, embs)]
        try:
            sb.table("sju_knowledge").insert(rows).execute()
            up += len(batch)
            print(f"  Uploaded {up}/{len(all_chunks)}...")
        except Exception as e:
            print(f"  upload error: {e}")

    print("\n" + "=" * 60)
    print(f"  DONE! {up} chunks of REAL SJU content loaded into Supabase.")
    print("=" * 60)
    print("\n  Your chatbot's keyword search now has real content to find.")
    print("  No code change needed - just refresh/redeploy isn't even required;")
    print("  the bot reads Supabase live on each question.")


if __name__ == "__main__":
    main()
