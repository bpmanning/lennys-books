"""
enrich_metadata.py

Enriches every unique book in books_clean.json with rich metadata,
storing results in books_metadata.json (a persistent key→metadata cache).

Fields added per book:
  cover_url       — book cover image URL
  description     — plot/summary (≤500 chars)
  pages           — page count
  subjects        — list of genre/subject tags (up to 5)
  isbn            — ISBN-13 preferred, ISBN-10 fallback
  published_year  — first publication year
  metadata_source — "ol" | "google_books" | "ol+google" | "none"

Strategy:
  1. Open Library — expanded search fields + Works API for description
  2. Google Books — fallback for records OL couldn't fill / match

books_metadata.json is keyed by normalised title (no articles, alphanumeric only).
clean_books.py merges it back in when regenerating books_clean.json.

Re-run safe: titles already in books_metadata.json are skipped.
Optional: set GOOGLE_BOOKS_API_KEY env var for higher rate limits.

Run order:
    python enrich_books.py      # fills in authors (run first)
    python enrich_metadata.py   # fills in cover/description/etc (this script)

Usage:
    python enrich_metadata.py
"""

import re, json, time, os, sys, urllib.request, urllib.parse
from pathlib import Path
from difflib import SequenceMatcher

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE      = Path(r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData")
CLEAN     = BASE / "books_clean.json"
META_FILE = BASE / "books_metadata.json"

GOOGLE_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
OL_PAUSE   = 0.6    # seconds between OL requests (~100 req/min)
GB_PAUSE   = 0.25   # Google Books is more permissive
SAVE_EVERY = 10
OL_THRESH  = 0.78
GB_THRESH  = 0.72

# ── Helpers ───────────────────────────────────────────────────────────────────

def norm_key(s):
    """Normalised title key: strip articles, lowercase, alphanumeric only, max 40 chars."""
    s = re.sub(r'\b(?:the|a|an)\b', s.lower(), s.lower())
    s = re.sub(r'[^a-z0-9]', '', s)
    return s[:40]

def similarity(a, b):
    def clean(s):
        s = re.sub(r'\b(?:the|a|an)\b', '', s.lower())
        s = re.sub(r'[^a-z0-9\s]', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()
    return SequenceMatcher(None, clean(a), clean(b)).ratio()

def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "LennysBookEnricher/1.0 (research project)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                print(f"      fetch error: {e}")
    return None

def trunc_desc(s, n=500):
    """Truncate to n chars at a sentence boundary."""
    if not s or len(s) <= n:
        return s.strip()
    cut = s[:n].rsplit('. ', 1)
    return (cut[0] + '.') if len(cut) > 1 else (s[:n].strip() + '…')

def clean_subjects(raw):
    """Filter/deduplicate subject tags; return up to 5 readable ones."""
    SKIP = re.compile(
        r'(?i)^(fiction|nonfiction|juvenile|accessible book|protected daisy|'
        r'in library|overdrive|large print|general|electronic books|'
        r'open library staff picks)$'
    )
    seen, out = set(), []
    for s in raw:
        s = s.strip()
        key = s.lower()
        if key in seen or len(s) > 60 or re.search(r'\d{4}', s) or SKIP.match(s):
            continue
        seen.add(key)
        out.append(s)
        if len(out) == 5:
            break
    return out

# ── Open Library ──────────────────────────────────────────────────────────────

OL_SEARCH = (
    "https://openlibrary.org/search.json?title={q}&limit=5"
    "&fields=title,author_name,key,cover_i,isbn,number_of_pages_median,subject,first_publish_year"
)

def ol_metadata(title, author=""):
    """Query OL search + Works API. Return partial metadata dict."""
    queries = [title]
    if ':' in title:
        queries.append(title.split(':')[0].strip())

    best, best_score = None, 0.0

    for q in queries:
        url = OL_SEARCH.format(q=urllib.parse.quote(q))
        data = fetch_json(url)
        if not data:
            continue
        for doc in data.get('docs', []):
            score = similarity(title, doc.get('title', ''))
            # Small author-match bonus
            ol_authors = ' '.join(doc.get('author_name') or []).lower()
            if author:
                parts = [p for p in re.split(r'[\s,]+', author) if len(p) > 3]
                if any(p.lower() in ol_authors for p in parts):
                    score = min(score + 0.08, 1.0)
            if score > best_score:
                best_score, best = score, doc
        if best_score >= OL_THRESH:
            break

    if not best or best_score < OL_THRESH:
        return {}

    result = {}

    cover_i = best.get('cover_i')
    if cover_i:
        result['cover_url'] = f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg"

    pages = best.get('number_of_pages_median')
    if pages:
        result['pages'] = int(pages)

    isbns = best.get('isbn') or []
    isbn = (next((i for i in isbns if len(i) == 13), None) or
            next((i for i in isbns if len(i) == 10), None))
    if isbn:
        result['isbn'] = isbn

    subjects = clean_subjects(best.get('subject') or [])
    if subjects:
        result['subjects'] = subjects

    yr = best.get('first_publish_year')
    if yr:
        result['published_year'] = int(yr)

    # Description via Works API (separate call)
    ol_key = best.get('key')
    if ol_key:
        time.sleep(OL_PAUSE * 0.6)
        work = fetch_json(f"https://openlibrary.org{ol_key}.json")
        if work:
            raw_desc = work.get('description', '')
            if isinstance(raw_desc, dict):
                raw_desc = raw_desc.get('value', '')
            desc = trunc_desc(str(raw_desc))
            if desc:
                result['description'] = desc

    return result

# ── Google Books ──────────────────────────────────────────────────────────────

GB_URL = "https://www.googleapis.com/books/v1/volumes?q={q}&maxResults=5{key_param}"

def gb_metadata(title, author=""):
    """Query Google Books API. Return partial metadata dict."""
    parts = [f"intitle:{urllib.parse.quote(title)}"]
    if author:
        # Use last non-trivial word as surname
        words = [w for w in re.split(r'[\s,]+', author.strip()) if len(w) > 3]
        if words:
            parts.append(f"inauthor:{urllib.parse.quote(words[-1])}")
    q = '+'.join(parts)
    key_param = f"&key={GOOGLE_KEY}" if GOOGLE_KEY else ""
    url = GB_URL.format(q=q, key_param=key_param)

    data = fetch_json(url)
    if not data or not data.get('items'):
        return {}

    best, best_score = None, 0.0
    for item in data['items']:
        info = item.get('volumeInfo', {})
        score = similarity(title, info.get('title', ''))
        if score > best_score:
            best_score, best = score, item

    if not best or best_score < GB_THRESH:
        return {}

    info  = best['volumeInfo']
    result = {}

    # Cover: get thumbnail and upgrade to medium size
    imgs  = info.get('imageLinks', {})
    cover = imgs.get('thumbnail') or imgs.get('smallThumbnail')
    if cover:
        cover = re.sub(r'&edge=curl', '', cover)
        cover = re.sub(r'zoom=\d', 'zoom=1', cover)
        cover = cover.replace('http://', 'https://')
        result['cover_url'] = cover

    desc = info.get('description', '')
    if desc:
        result['description'] = trunc_desc(desc)

    if info.get('pageCount'):
        result['pages'] = info['pageCount']

    cats = clean_subjects(info.get('categories') or [])
    if cats:
        result['subjects'] = cats

    for iid in (info.get('industryIdentifiers') or []):
        if iid.get('type') == 'ISBN_13':
            result['isbn'] = iid['identifier']
            break
    if 'isbn' not in result:
        for iid in (info.get('industryIdentifiers') or []):
            if iid.get('type') == 'ISBN_10':
                result['isbn'] = iid['identifier']
                break

    m = re.match(r'(\d{4})', info.get('publishedDate', ''))
    if m:
        result['published_year'] = int(m.group(1))

    return result

# ── Load / init ───────────────────────────────────────────────────────────────

if not CLEAN.exists():
    raise SystemExit(f"ERROR: {CLEAN} not found.\nRun clean_books.py first.")

records = json.loads(CLEAN.read_text(encoding='utf-8'))
print(f"Unique books in books_clean.json : {len(records)}")

meta_db = {}
if META_FILE.exists():
    meta_db = json.loads(META_FILE.read_text(encoding='utf-8'))
    print(f"Existing metadata entries        : {len(meta_db)}")
else:
    print("No books_metadata.json found — starting fresh.")

# Collect unique titles that still need enrichment
need, seen_keys = [], set()
for rec in records:
    key = norm_key(rec['book'])
    if key not in seen_keys:
        seen_keys.add(key)
        if key not in meta_db:
            need.append(rec)

print(f"Titles needing metadata          : {len(need)}")
if not need:
    print("Nothing to do — all titles already in metadata store.")
else:
    est = len(need) * (OL_PAUSE + 0.5 + GB_PAUSE) / 60
    print(f"Estimated time                   : ~{est:.0f} min\n")
    if not GOOGLE_KEY:
        print("Tip: set GOOGLE_BOOKS_API_KEY env var for higher Google rate limits.\n")

# ── Enrichment loop ───────────────────────────────────────────────────────────

FIELDS  = ('cover_url', 'description', 'pages', 'subjects', 'isbn', 'published_year')
n_ol, n_gb, n_none = 0, 0, 0

for i, rec in enumerate(need, 1):
    title  = rec['book']
    author = rec.get('author', '')
    key    = norm_key(title)
    print(f"  [{i:3d}/{len(need)}]  '{title}'", flush=True)

    # Pass 1: Open Library
    time.sleep(OL_PAUSE)
    ol     = ol_metadata(title, author)
    filled = {k: v for k, v in ol.items() if k in FIELDS and v}
    source = 'ol' if filled else ''

    # Pass 2: Google Books for any fields OL missed
    missing = [f for f in FIELDS if f not in filled]
    if missing:
        time.sleep(GB_PAUSE)
        gb = gb_metadata(title, author)
        for f in missing:
            if gb.get(f):
                filled[f] = gb[f]
        if any(gb.get(f) for f in missing):
            source = 'ol+google' if source == 'ol' else 'google_books'

    entry = dict(filled)
    entry['metadata_source'] = source or 'none'
    meta_db[key] = entry

    has = [f for f in FIELDS if entry.get(f)]
    if source == 'ol':          n_ol   += 1
    elif 'google' in source:    n_gb   += 1
    else:                       n_none += 1
    print(f"         source={source or 'none':12s}  got={has}")

    if i % SAVE_EVERY == 0:
        META_FILE.write_text(
            json.dumps(meta_db, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"    [checkpoint saved at {i}]")

# Final save of metadata store
META_FILE.write_text(
    json.dumps(meta_db, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"\nOL only             : {n_ol}")
print(f"Google (partial/full): {n_gb}")
print(f"No metadata found   : {n_none}")
print(f"Metadata store      : {len(meta_db)} entries → {META_FILE.name}")

# ── Regenerate books_clean.json + HTML with metadata merged in ────────────────
print("\n" + "="*60)
print("Regenerating books_clean.json and books_table.html ...")
print("="*60)
import os as _os
_os.environ["LENNY_RAW_SOURCE"] = str(BASE / "books_candidates.json")
exec(
    (BASE / "clean_books.py").read_text(encoding='utf-8'),
    {"__name__": "__main__", "__file__": str(BASE / "clean_books.py")}
)
