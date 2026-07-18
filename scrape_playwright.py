"""
SJU PLAYWRIGHT SCRAPER  (renders JavaScript in a real browser - FREE, no credits)

Pulls every real page from SJU's sitemap.xml, opens each in a real headless
Chrome, waits for JS content to load, strips navigation with BeautifulSoup,
and loads the raw text into Supabase for Postgres full-text search (no embeddings).

SETUP (run these on your laptop, in order):
    pip install playwright beautifulsoup4 supabase defusedxml
    playwright install chromium          <-- IMPORTANT: downloads the browser (~150MB, one time)
    export SUPABASE_URL=...  SUPABASE_KEY=...
    python scrape_playwright.py

This is laptop-only. Don't push it to GitHub with keys in it.
"""
import os
import re
import json
import time
import urllib.request
import defusedxml.ElementTree as ET
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from supabase import create_client

# ── SET THESE IN YOUR SHELL ENVIRONMENT (laptop only) ────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SITEMAP_URL = "https://www.sju.edu.in/sitemap.xml"
# events/news churn constantly and go stale fast — skip the sitemap's copies,
# the small curated EVENT_URLS list below covers current highlights instead
SITEMAP_SKIP = ("/events-detail", "/news-detail")
CACHE_FILE = "scraped_chunks.json"


def fetch_sitemap_urls():
    """Pull every real page URL from SJU's sitemap.xml (stdlib only, no new deps)."""
    try:
        req = urllib.request.Request(SITEMAP_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
        urls = [u for u in urls if not any(p in u for p in SITEMAP_SKIP)]
        print(f"  Sitemap: {len(urls)} usable URLs (events/news pages skipped)")
        return urls
    except Exception as e:
        print(f"  Sitemap fetch failed ({e}) — using curated URL list only")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# IMPORTANT INFO PAGES (high-value content)
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
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-information-technology/advanced-computing",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-information-technology/computer-science-and-computer-application",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-business-administration/commerce-and-management",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-humanities-and-social-sciences/economics",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-humanities-and-social-sciences/psychology",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-life-sciences/biotechnology",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-life-sciences/microbiology",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-physical-sciences/physics",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-physical-sciences/mathematics",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-physical-sciences/statistics",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-chemical-sciences/chemistry",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-social-work/social-work",
    "https://www.sju.edu.in/departments/st-joseph-university/school--of-commerce/commerce",
]

# ── PASTE EXTRA URLs YOU HARVEST (course / department / programme detail pages) ──
EXTRA_URLS = [
    # "https://www.sju.edu.in/departments/...",
    # "https://www.sju.edu.in/programmes/...",
]

# ── STAFF LISTINGS ── each person is a data-category card; scraped specially so
# faculty end up grouped by department (see extract_faculty_chunks).
FACULTY_URLS = [
    "https://www.sju.edu.in/about/faculty-members.php",
    "https://www.sju.edu.in/about/non-teaching-staff.php",
]

# Bridge programme names -> department, so a query like "MSc Big Data Analytics
# faculty" retrieves the right department roster even though the roster text only
# names the department. Only departments whose programme names differ from the
# department name need an entry.
DEPT_KEYWORDS = {
    "advanced-computing": "Programmes: MSc Big Data Analytics (BDA), Data Science, PhD. School of Information Technology.",
    "computer-science": "Programmes: BCA, BSc Computer Science, MSc Computer Science, MCA, Data Analytics. School of Information Technology.",
}

# ── RECENT 2026 EVENTS (pre-filled) ──
_EVENT_SLUGS_2026 = [
    "office-for-international-affairs-welcomes-professor-till-rachmann-and-dr-maneesh-pauls",
    "a-talk-on-women-empowerment-by-ms-nazneen-banu",
    "academic--industrial-connect-initiative-2026",
    "footprints-2026",
    "expert-talk-on-alternative-proteins",
    "department-colloquium",
    "visages-2026",
    "national-science-day-celebrations",
    "career-opportunities-in-pharma-and-chemical-industries",
    "inter-collegiate-fest---emporio",
    "ai-for-atmanirbhar-bharat-hei-engagements-towards-indiaai-impact-summit-2026",
    "scms-international-conference-and-association-fests-2026",
    "the-oxford-sju-debate",
    "international-conference---smartchem-2026-chains",
    "sparks26---inaugural-ceremony",
]
EVENT_URLS = [f"https://www.sju.edu.in/events-detail.php?slug={s}" for s in _EVENT_SLUGS_2026]


def extract_clean_text(html):
    """Strip navigation/boilerplate, return clean main text."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content tags entirely
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "noscript", "iframe", "svg", "form", "button"]):
        tag.decompose()

    # Remove elements whose class/id looks like navigation/boilerplate
    junk = re.compile(r"nav|menu|header|footer|breadcrumb|sidebar|cookie|"
                      r"popup|modal|banner|social|topbar|dropdown|search", re.I)
    for el in soup.find_all(attrs={"class": junk}):
        el.decompose()
    for el in soup.find_all(attrs={"id": junk}):
        el.decompose()

    # Prefer a main content container if the page has one
    main = (soup.find("main")
            or soup.find("article")
            or soup.find(attrs={"class": re.compile(r"content|main-content|page-content|container", re.I)})
            or soup.body
            or soup)

    text = main.get_text(separator="\n", strip=True)
    # Keep only meaningful lines
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 3]
    return "\n".join(lines)


def extract_faculty_chunks(page, url):
    """The staff pages render each person as a `.data-item[data-category]` card,
    where data-category is the department slug. Group people by department so
    full-text search can match e.g. 'advanced computing faculty' to the right
    names — no tab-clicking needed, the whole roster is already in the DOM."""
    groups = page.evaluate("""() => {
        const g = {};
        document.querySelectorAll('.data-item[data-category]').forEach(item => {
            const card = item.querySelector('.data-card');
            if (!card) return;  // skip the filter chips (no card inside)
            const cat = item.getAttribute('data-category') || 'other';
            const txt = card.innerText.replace(/\\s+/g, ' ').trim();
            if (txt) (g[cat] = g[cat] || []).push(txt);
        });
        return g;
    }""")
    kind = "non-teaching staff" if "non-teaching" in url else "teaching faculty"
    chunks = []
    for cat, people in (groups or {}).items():
        label = cat.replace("-", " ").strip().title() or "University"
        extra = DEPT_KEYWORDS.get(cat, "")  # programme names to aid retrieval
        # ~12 people per chunk so a big department isn't one oversized row
        for i in range(0, len(people), 12):
            content = (f"{label} department — {kind} at St Joseph's University "
                       f"(SJU), Bengaluru. {extra} " + "; ".join(people[i:i + 12]))
            chunks.append({"content": content.replace("  ", " "), "source_url": url,
                           "page_name": f"{label} {kind}"})
    return chunks


def chunk_text(text, url):
    words = text.split()
    chunks, size, step = [], 400, 350
    name = url.rstrip("/").split("/")[-1].replace(".php", "").replace("-", " ")[:120] or "page"
    for i in range(0, len(words), step):
        piece = " ".join(words[i:i + size])
        if len(piece) >= 40:
            chunks.append({"content": piece, "source_url": url, "page_name": name})
    return chunks


def main():
    print("=" * 60)
    print("  SJU PLAYWRIGHT SCRAPER (real browser -> Supabase)")
    print("=" * 60)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("\nERROR: SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
        print("  export SUPABASE_URL=https://your-project.supabase.co")
        print("  export SUPABASE_KEY=your-service-role-key")
        return
    print("\nConnecting to Supabase...")
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("  Ready!")

    if os.path.exists(CACHE_FILE):
        print(f"\nFound cached scrape ({CACHE_FILE}) — skipping the browser pass, uploading from cache.")
        print("  (delete this file to force a fresh scrape)")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            all_chunks = json.load(f)
    else:
        print("\nFetching sitemap...")
        sitemap_urls = fetch_sitemap_urls()

        urls = []
        seen = set()
        for u in INFO_URLS + FACULTY_URLS + EXTRA_URLS + EVENT_URLS + sitemap_urls:
            if u not in seen:
                seen.add(u); urls.append(u)
        print(f"\nPages to scrape: {len(urls)}")

        print("\nLaunching headless browser and scraping (renders JavaScript)...")
        all_chunks = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
            page = ctx.new_page()

            for idx, url in enumerate(urls, 1):
                short = url.replace("https://www.sju.edu.in", "")[:50]
                print(f"  [{idx}/{len(urls)}] {short} ...", end=" ")
                try:
                    is_faculty = any(f in url for f in ("faculty-members", "non-teaching-staff"))
                    # the staff pages are heavy and flaky on networkidle; domcontentloaded
                    # is enough since we read the already-rendered card DOM.
                    page.goto(url, wait_until="domcontentloaded" if is_faculty else "networkidle", timeout=60000)
                    page.wait_for_timeout(3500 if is_faculty else 2500)  # let late JS content settle
                    if is_faculty:
                        ch = extract_faculty_chunks(page, url)
                        all_chunks.extend(ch)
                        print(f"{len(ch)} faculty chunks")
                    else:
                        html = page.content()
                        text = extract_clean_text(html)
                        if text and len(text) > 80:
                            ch = chunk_text(text, url)
                            all_chunks.extend(ch)
                            print(f"{len(ch)} chunks ({len(text)} chars)")
                        else:
                            print("thin/empty")
                except Exception as e:
                    print(f"error: {str(e)[:50]}")

            browser.close()

        print(f"\nTotal chunks of real content: {len(all_chunks)}")
        if all_chunks:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(all_chunks, f)
            print(f"  Cached to {CACHE_FILE} (safe to re-run upload if this fails)")

    if not all_chunks:
        print("  Nothing captured. Tell me and we'll adjust the page-waiting/selectors.")
        return

    print("\nClearing old data from sju_knowledge...")
    try:
        sb.table("sju_knowledge").delete().neq("id", 0).execute()
        print("  Cleared!")
    except Exception as e:
        print(f"  Note: {e}")

    print("\nUploading to Supabase (full-text search, no embeddings)...")
    B, up = 100, 0
    for i in range(0, len(all_chunks), B):
        batch = all_chunks[i:i + B]
        rows = [{
            "content": c["content"],
            "source_url": c["source_url"],
            "page_name": c["page_name"],
        } for c in batch]
        # Retry the whole batch until it lands — never silently drop chunks.
        for attempt in range(1, 6):
            try:
                sb.table("sju_knowledge").insert(rows).execute()
                up += len(batch)
                print(f"  Uploaded {up}/{len(all_chunks)}...")
                break
            except Exception as e:
                wait = 3 * attempt
                print(f"  batch {i//B+1} attempt {attempt}/5 failed: {str(e)[:120]} — retrying in {wait}s")
                time.sleep(wait)
        else:
            # ponytail: abort loud instead of finishing with holes; re-run resumes from the scrape cache.
            raise SystemExit(f"Batch at offset {i} failed 5x — aborting so the table isn't left incomplete.")

    print("\n" + "=" * 60)
    print(f"  DONE! {up} chunks of REAL SJU content in Supabase.")
    print("=" * 60)
    print("\n  Your bot reads Supabase live - test it now, no redeploy needed.")


if __name__ == "__main__":
    main()
