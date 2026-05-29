"""
retry_none_metadata.py

Targeted retry for the ~20 books_metadata.json entries with metadata_source='none'.
Uses Google Books only (OL is rate-limited) with slower pacing and multiple
search strategies (full title, short title, ISBN query, author+keyword).

Run after OL rate-limit window has passed or with GOOGLE_BOOKS_API_KEY set.

    python retry_none_metadata.py
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
GB_PAUSE   = 1.5    # generous delay to avoid 429
GB_THRESH  = 0.55   # lower threshold for difficult/series titles
OL_PAUSE   = 1.2    # also try OL but with a long pause


# ── Helpers ───────────────────────────────────────────────────────────────────

def norm_key(s):
    s = re.sub(r'\b(?:the|a|an)\b', s.lower(), s.lower())
    s = re.sub(r'[^a-z0-9]', '', s)
    return s[:40]

def similarity(a, b):
    def clean(s):
        s = re.sub(r'\b(?:the|a|an)\b', '', s.lower())
        s = re.sub(r'[^a-z0-9\s]', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()
    return SequenceMatcher(None, clean(a), clean(b)).ratio()

def fetch_json(url, retries=3, pause_on_429=30):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "LennysBookEnricher/1.0 (research project)"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"      429 rate-limited — waiting {pause_on_429}s …")
                time.sleep(pause_on_429)
                pause_on_429 = min(pause_on_429 * 2, 120)
            elif attempt < retries - 1:
                time.sleep(5)
            else:
                print(f"      fetch error: {e}")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5)
            else:
                print(f"      fetch error: {e}")
    return None

def trunc_desc(s, n=500):
    if not s or len(s) <= n:
        return s.strip()
    cut = s[:n].rsplit('. ', 1)
    return (cut[0] + '.') if len(cut) > 1 else (s[:n].strip() + '…')

def clean_subjects(raw):
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


# ── Google Books (multi-strategy) ─────────────────────────────────────────────

GB_URL = "https://www.googleapis.com/books/v1/volumes?q={q}&maxResults=5{key_param}"

def _gb_result(query, ref_title, threshold):
    key_param = f"&key={GOOGLE_KEY}" if GOOGLE_KEY else ""
    url = GB_URL.format(q=urllib.parse.quote(query), key_param=key_param)
    data = fetch_json(url)
    if not data or not data.get('items'):
        return None, 0.0
    best, best_score = None, 0.0
    for item in data['items']:
        info = item.get('volumeInfo', {})
        score = similarity(ref_title, info.get('title', ''))
        if score > best_score:
            best_score, best = score, item
    if best and best_score >= threshold:
        return best, best_score
    return None, best_score

def gb_metadata_multi(title, author="", threshold=GB_THRESH):
    """Try several Google Books queries; return best matching result."""
    # Strategy 1: intitle + inauthor
    strategies = []
    if author:
        words = [w for w in re.split(r'[\s,]+', author.strip()) if len(w) > 3]
        if words:
            strategies.append(f"intitle:{title} inauthor:{words[-1]}")
    strategies.append(f"intitle:{title}")

    # Strategy 2: strip "series" / "trilogy" / ": ..." and retry
    short = re.sub(r'\s+(series|trilogy|duology|omnibus)\b.*', '', title, flags=re.I)
    short = re.sub(r'\s*:.*', '', short).strip()
    if short and short.lower() != title.lower():
        if author:
            words = [w for w in re.split(r'[\s,]+', author.strip()) if len(w) > 3]
            if words:
                strategies.append(f"intitle:{short} inauthor:{words[-1]}")
        strategies.append(f"intitle:{short}")

    # Strategy 3: just plain text search
    if author:
        words = [w for w in re.split(r'[\s,]+', author.strip()) if len(w) > 3]
        if words:
            strategies.append(f"{short} {words[-1]}")
    strategies.append(short if short else title)

    best_item, best_score = None, 0.0
    for query in strategies:
        print(f"        GB query: {query[:70]}")
        item, score = _gb_result(query, title if short == title else short, threshold)
        if item and score > best_score:
            best_score, best_item = score, item
        if best_score >= 0.85:
            break   # good enough, stop
        time.sleep(GB_PAUSE)

    if not best_item:
        return {}

    info   = best_item['volumeInfo']
    result = {}

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


# ── Open Library (retry) ──────────────────────────────────────────────────────

OL_SEARCH = (
    "https://openlibrary.org/search.json?title={q}&limit=5"
    "&fields=title,author_name,key,cover_i,isbn,number_of_pages_median,subject,first_publish_year"
)
OL_THRESH = 0.72

def ol_metadata_retry(title, author=""):
    short = re.sub(r'\s+(series|trilogy|duology|omnibus)\b.*', '', title, flags=re.I)
    short = re.sub(r'\s*:.*', '', short).strip()
    queries = list(dict.fromkeys([title, short]))  # deduplicate, preserve order

    best, best_score = None, 0.0
    for q in queries:
        url = OL_SEARCH.format(q=urllib.parse.quote(q))
        data = fetch_json(url, pause_on_429=60)
        if not data:
            continue
        for doc in data.get('docs', []):
            score = similarity(title if q == title else short, doc.get('title', ''))
            ol_authors = ' '.join(doc.get('author_name') or []).lower()
            if author:
                parts = [p for p in re.split(r'[\s,]+', author) if len(p) > 3]
                if any(p.lower() in ol_authors for p in parts):
                    score = min(score + 0.08, 1.0)
            if score > best_score:
                best_score, best = score, doc
        if best_score >= OL_THRESH:
            break
        time.sleep(OL_PAUSE)

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
    ol_key = best.get('key')
    if ol_key:
        time.sleep(OL_PAUSE * 0.5)
        work = fetch_json(f"https://openlibrary.org{ol_key}.json", pause_on_429=60)
        if work:
            raw_desc = work.get('description', '')
            if isinstance(raw_desc, dict):
                raw_desc = raw_desc.get('value', '')
            desc = trunc_desc(str(raw_desc))
            if desc:
                result['description'] = desc

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

records  = json.loads(CLEAN.read_text(encoding='utf-8'))
meta_db  = json.loads(META_FILE.read_text(encoding='utf-8'))

# Build a title→(title,author) map from clean records
title_map = {}
seen = set()
for r in records:
    k = norm_key(r['book'])
    if k not in seen:
        seen.add(k)
        title_map[k] = (r['book'], r.get('author', ''))

none_keys = [k for k, v in meta_db.items() if v.get('metadata_source') == 'none']
print(f"Retrying {len(none_keys)} source=none entries\n")
if not GOOGLE_KEY:
    print("Tip: set GOOGLE_BOOKS_API_KEY for higher Google rate limits.\n")

FIELDS = ('cover_url', 'description', 'pages', 'subjects', 'isbn', 'published_year')
n_filled = 0

for i, key in enumerate(none_keys, 1):
    title, author = title_map.get(key, (key, ''))
    print(f"  [{i:2d}/{len(none_keys)}]  '{title}' / '{author}'")

    filled = {}
    source = ''

    # Try OL first (with longer pause to be kind to their servers)
    print("      Trying Open Library …")
    time.sleep(OL_PAUSE)
    ol = ol_metadata_retry(title, author)
    if ol:
        filled = {k: v for k, v in ol.items() if k in FIELDS and v}
        source  = 'ol' if filled else ''

    # Google Books for anything missing
    missing = [f for f in FIELDS if f not in filled]
    if missing:
        print("      Trying Google Books …")
        time.sleep(GB_PAUSE)
        gb = gb_metadata_multi(title, author)
        for f in missing:
            if gb.get(f):
                filled[f] = gb[f]
        if any(gb.get(f) for f in missing):
            source = 'ol+google' if source == 'ol' else 'google_books'

    entry = dict(filled)
    entry['metadata_source'] = source or 'none'
    meta_db[key] = entry

    has = [f for f in FIELDS if entry.get(f)]
    print(f"      → source={source or 'none':12s}  got={has}")
    if has:
        n_filled += 1

    # Save after every book (these are precious retries)
    META_FILE.write_text(
        json.dumps(meta_db, indent=2, ensure_ascii=False), encoding='utf-8')

print(f"\nFilled {n_filled}/{len(none_keys)} previously-empty entries")
print(f"Metadata store: {len(meta_db)} entries → {META_FILE.name}")

# Regenerate books_clean.json + HTML
print("\n" + "="*60)
print("Regenerating books_clean.json and books_table.html …")
print("="*60)
import os as _os
_os.environ["LENNY_RAW_SOURCE"] = str(BASE / "books_candidates.json")
exec(
    (BASE / "clean_books.py").read_text(encoding='utf-8'),
    {"__name__": "__main__", "__file__": str(BASE / "clean_books.py")}
)
