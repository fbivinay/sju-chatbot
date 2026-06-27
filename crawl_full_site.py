"""
SJU FULL WEBSITE CRAWLER using Firecrawl (FIXED metadata handling)
Crawls the ENTIRE sju.edu.in website and loads into Supabase.
Run: python crawl_full_site.py
"""
import os

# ── PASTE YOUR KEYS HERE ──────────────────────────────────────────────────────
FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY", "fc-86c9fc0de15a42438925ddf0f3980df2")
SUPABASE_URL  = os.getenv("SUPABASE_URL", "https://mvszfevopamhkratxeak.supabase.co")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im12c3pmZXZvcGFtaGtyYXR4ZWFrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MjU1MDA2MiwiZXhwIjoyMDk4MTI2MDYyfQ.QJbCXfRHjwlIl2HpkAavoPPbGGeDLsjWyc3mzvY9D8Y")

from firecrawl import Firecrawl
from supabase import create_client
from sentence_transformers import SentenceTransformer


def get_attr(obj, key, default=""):
    """Safely get a value from either a dict or an object"""
    if obj is None:
        return default
    # Try dictionary access
    if isinstance(obj, dict):
        return obj.get(key, default)
    # Try object attribute access
    if hasattr(obj, key):
        val = getattr(obj, key)
        return val if val is not None else default
    return default


def main():
    print("=" * 60)
    print("  SJU FULL WEBSITE CRAWLER (Firecrawl + Supabase)")
    print("=" * 60)

    print("\n[1/5] Connecting...")
    app = Firecrawl(api_key=FIRECRAWL_KEY)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("      Connected!")

    print("\n[2/5] Loading embedding model...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    print("      Ready!")

    print("\n[3/5] Clearing old data...")
    try:
        sb.table("sju_knowledge").delete().neq("id", 0).execute()
        print("      Cleared!")
    except Exception as e:
        print(f"      Note: {e}")

    print("\n[4/5] Crawling the ENTIRE sju.edu.in website...")
    print("      Takes 5-15 minutes. Please wait...")

    crawl_result = app.crawl(
        "https://www.sju.edu.in",
        limit=300,
        scrape_options={
            "formats": ["markdown"],
            "onlyMainContent": True,
        }
    )

    # Get the pages list
    pages = get_attr(crawl_result, "data", [])
    if not pages and isinstance(crawl_result, dict):
        pages = crawl_result.get("data", [])
    print(f"      Crawled {len(pages)} pages!")

    print("\n[5/5] Processing and uploading...")
    all_chunks = []

    for page in pages:
        # Get markdown content
        content = get_attr(page, "markdown", "")

        # Get metadata - handle both object and dict
        metadata = get_attr(page, "metadata", None)
        url = get_attr(metadata, "sourceURL", "")
        if not url:
            url = get_attr(metadata, "url", "")
        title = get_attr(metadata, "title", "")

        if not content or len(content) < 50:
            continue

        # Split into chunks of ~400 words
        words = content.split()
        chunk_size = 400
        step = 350

        for i in range(0, len(words), step):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) < 20:
                continue
            chunk_text = " ".join(chunk_words)

            # Build a clean page name
            page_name = title
            if not page_name and url:
                page_name = url.rstrip("/").split("/")[-1].replace(".php", "").replace("-", " ")
            if not page_name:
                page_name = "SJU page"

            all_chunks.append({
                "content": chunk_text,
                "source_url": url,
                "page_name": page_name,
            })

    print(f"      Created {len(all_chunks)} chunks from all pages")

    if not all_chunks:
        print("      WARNING: No content found. Check Firecrawl output.")
        return

    # Embed and upload in batches
    print("      Creating embeddings and uploading...")
    batch_size = 50
    uploaded = 0

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        texts = [c["content"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False)

        rows = []
        for chunk, emb in zip(batch, embeddings):
            rows.append({
                "content": chunk["content"],
                "source_url": chunk["source_url"],
                "page_name": chunk["page_name"],
                "embedding": emb.tolist(),
            })

        try:
            sb.table("sju_knowledge").insert(rows).execute()
            uploaded += len(batch)
            print(f"      Uploaded {uploaded}/{len(all_chunks)}...")
        except Exception as e:
            print(f"      Upload error on batch: {e}")

    print("\n" + "=" * 60)
    print(f"  DONE! {uploaded} chunks from the FULL SJU website in Supabase!")
    print("=" * 60)
    print("\n  Your chatbot now knows the real website content.")
    print("  Push to GitHub or restart Railway to use it.")


if __name__ == "__main__":
    main()
