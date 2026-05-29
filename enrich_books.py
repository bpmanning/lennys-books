"""
enrich_books.py

For every record in books_candidates.json whose author is blank, query the
Open Library search API (free, no API key) to fill in the author name and
basic publication data.

Skips records that already have an author or an 'ol_score' field (meaning
they were already looked up in a previous run — re-run safe).

Saves results back to books_candidates.json after every batch so the run
can be interrupted and resumed without losing work.

After enrichment, regenerates books_clean.json and books_table.html by
importing and running the logic from clean_books.py.

Usage:
    python enrich_books.py
"""

import re
import json
import time
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from difflib import SequenceMatcher

# Force UTF-8 output so author names with non-ASCII chars (e.g. Pema Chödrön) print fine
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE    = Path(r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData")
CANDS   = BASE / "books_candidates.json"

OL_URL  = "https://openlibrary.org/search.json?title={q}&limit=5&fields=title,author_name,first_publish_year,key"
PAUSE   = 0.75     # seconds between requests (~80 req/min; OL asks for reasonable use)
SAVE_EVERY = 20    # checkpoint every N lookups
THRESHOLD  = 0.82  # minimum title-similarity score to accept a match

# ── Pre-filter: skip OL query for obviously-not-a-book candidates ─────────────
# These are marked ol_score=0 immediately without any network call.
SKIP_OL = re.compile(
    r'(?i)'
    r'on\s+(?:netflix|hbo|amazon|apple\s+tv|youtube|hulu|disney)'  # streaming shows
    r'|\[inaudible'                  # transcript artifacts
    r'|podcast$'                     # podcast names
    r'|course$'                      # online courses
    r"'s\s+books?$"                  # "Author's book(s)" — fragment, not a title
    r'|wrote$|said$'                 # sentence fragments
    r'|\bon\s+instagram\b'
    r'|\bwith\s+ben\s+gilbert\b'     # "Acquired with Ben Gilbert" = podcast
)

# ── Helpers ───────────────────────────────────────────────────────────────────
def normalize(s):
    """Lowercase, strip leading articles and punctuation for comparison."""
    s = s.lower()
    s = re.sub(r'\b(?:the|a|an)\b', '', s)
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def query_ol(title):
    """
    Search Open Library for *title*.
    Returns a dict with author / first_publish_year / ol_key / ol_score,
    or None if no confident match was found.
    """
    # Try full title first; if it has a subtitle ("Title: Subtitle") also try
    # just the main part in case OL indexed it differently.
    queries = [title]
    if ":" in title:
        queries.append(title.split(":")[0].strip())

    for q in queries:
        url = OL_URL.format(q=urllib.parse.quote(q))
        for attempt in range(3):
            try:
                req = urllib.request.Request(url,
                    headers={"User-Agent": "LennysBookExtractor/1.0 (research project)"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break   # success
            except Exception as e:
                if attempt < 2:
                    time.sleep(3)
                else:
                    print(f"    OL error after 3 tries: {e}")
                    return None
        else:
            return None

        docs = data.get("docs", [])
        if not docs:
            continue

        # Pick the doc with the highest title similarity
        best, best_score = None, 0.0
        for doc in docs:
            ol_title = doc.get("title", "")
            score = similarity(title, ol_title)
            if score > best_score:
                best_score = score
                best = doc

        if best_score >= THRESHOLD:
            authors = best.get("author_name") or []
            author_str = ", ".join(authors[:2])   # at most two authors
            return {
                "author":              author_str,
                "first_publish_year":  best.get("first_publish_year", ""),
                "ol_key":              best.get("key", ""),
                "ol_title":            best.get("title", title),
                "ol_score":            round(best_score, 3),
            }

    return None   # nothing exceeded the threshold

# ── Load candidates ───────────────────────────────────────────────────────────
if not CANDS.exists():
    raise SystemExit(
        f"ERROR: {CANDS} not found.\n"
        "Run  python extract_titles.py  first."
    )

records = json.loads(CANDS.read_text(encoding="utf-8"))
print(f"Total records in books_candidates.json : {len(records)}")

# Records that still need a lookup:
#   - author is blank  AND
#   - 'ol_score' key is absent (never looked up) OR ol_score is None
need_lookup = [
    r for r in records
    if not r.get("author") and "ol_score" not in r
]
already_done = sum(1 for r in records if "ol_score" in r and not r.get("author"))

print(f"Already looked up (no match found) : {already_done}")
print(f"Need OL lookup now                 : {len(need_lookup)}")
if not need_lookup:
    print("Nothing to look up — skipping OL pass.")
else:
    est_min = len(need_lookup) * PAUSE / 60
    print(f"Estimated time                     : {est_min:.1f} min\n")

# ── Open Library pass ─────────────────────────────────────────────────────────
enriched   = 0
not_found  = []

for i, rec in enumerate(need_lookup, 1):
    title = rec["book"]
    print(f"  [{i:3d}/{len(need_lookup)}]  '{title}'", end="  ", flush=True)

    # Skip obvious non-books without hitting the network
    if SKIP_OL.search(title):
        rec["ol_score"] = 0.0
        print("-> pre-filtered (not a book)")
        not_found.append(title)
        continue

    result = query_ol(title)

    if result:
        rec["author"]             = result["author"]
        rec["first_publish_year"] = result.get("first_publish_year", "")
        rec["ol_key"]             = result.get("ol_key", "")
        rec["ol_score"]           = result["ol_score"]
        print(f"-> {result['author']}  (score={result['ol_score']})")
        enriched += 1
    else:
        rec["ol_score"] = 0.0     # mark as attempted; skip on re-run
        print("-> not found in OL")
        not_found.append(title)

    # Checkpoint save
    if i % SAVE_EVERY == 0:
        CANDS.write_text(json.dumps(records, indent=2, ensure_ascii=False),
                         encoding="utf-8")
        print(f"    [checkpoint saved at {i}]")

    time.sleep(PAUSE)

# Final save
CANDS.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nEnriched  : {enriched} / {len(need_lookup)}")
print(f"Not found : {len(not_found)}")

if not_found:
    print("\nTitles Open Library could not match:")
    for t in sorted(not_found):
        print(f"  - {t}")

# ── Regenerate clean JSON + HTML ──────────────────────────────────────────────
print("\n" + "="*60)
print("Regenerating books_clean.json and books_table.html ...")
print("="*60)

# Run clean_books.py in the same process by temporarily patching its RAW path.
import importlib, sys, types

# Point clean_books at books_candidates.json for this run
# We do this by setting an env variable that clean_books.py checks
import os
os.environ["LENNY_RAW_SOURCE"] = str(CANDS)

# Execute clean_books.py as a script
exec(
    (BASE / "clean_books.py").read_text(encoding="utf-8"),
    {"__name__": "__main__", "__file__": str(BASE / "clean_books.py")}
)
