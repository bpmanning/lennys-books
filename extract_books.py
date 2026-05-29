"""
Extract book recommendations from Lenny's Newsletter & Podcast data.

Passes:
 A – podcast lightning-round (Lenny asks "what books have you recommended?")
 B – guest's own book (intro paragraph)
 C – any line containing 'book' + a 'Title by Author' pattern
 D – newsletter explicit book sections
"""

import re, json
from pathlib import Path

BASE = Path(r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData\lennys-newsletterpodcastdata-all")

# ── frontmatter ──────────────────────────────────────────────────────────────
def parse_frontmatter(text):
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        kv = re.match(r'^(\w+):\s*"?([^"]*)"?\s*$', line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip()
    return meta, text[m.end():]

# ── Skip-line guard: ignore lines that are clearly navigation / URLs ─────────
SKIP_LINE = re.compile(
    r"(?i)(https?://|www\.|\.com\b|\.org\b|\.pdf|\.jpg|\.png|"
    r"dp/[A-Z0-9]{10}|qid=|&sr=|UTF8|btkr|"
    r"subscribe\b|apple podcast|spotify|lennyspodcast\.com|"
    r"lennysnewsletter\.com|substack\.com|\[.*?\]\()"
)

# ── A well-formed book title:
#    - 1-8 words, starts with A-Z or ' or "
#    - no embedded sentence-ending punctuation (". " "? " "! " in middle)
#    - total 2-90 chars
def looks_like_title(s):
    s = s.strip()
    if not s or not s[0].isupper() and s[0] not in ("'", '"'):
        return False
    # No embedded sentence breaks
    if re.search(r'[.?!]\s', s):
        return False
    # Not too long (8 words max)
    if len(s.split()) > 9:
        return False
    # Not too short
    if len(s) < 2:
        return False
    # Not a URL fragment
    if re.search(r'[/%?=#&]', s):
        return False
    # Doesn't look like a sentence opener (very common connectors)
    if re.match(r'(?i)^(sponsored\b|brought\b|powered\b|hosted\b|presented\b|'
                r'created by lenny|produced by|supported by|distributed by|'
                r'published by|illustrated by|reply to|sent by|join us|'
                r'subscribe|find us|follow us)', s):
        return False
    return True

# ── A well-formed author name:
#    1-4 words, each starting with a capital letter
AUTHOR_RE = re.compile(
    r'^[A-Z][a-zA-Z\.\-\']{0,25}(\s+[A-Z][a-zA-Z\.\-\']{0,25}){0,3}$'
)
def looks_like_author(s):
    s = s.strip(" .,;:")
    if not s:
        return False
    if re.search(r'[%?=#&/]', s):
        return False
    return bool(AUTHOR_RE.match(s))

# ── Core "Title by Author" extractor ─────────────────────────────────────────
# Finds all plausible (title, author) pairs in a block of text
# Handles:
#   - plain:      Title by Author
#   - italic:     *Title* by Author
#   - bold:       **Title** by Author
#   - in quotes:  "Title" by Author

# One pattern to capture them all, non-greedy
BOOK_BY = re.compile(
    # optional emphasis open
    r'(?:^|[\s\(\[,;])'
    r'(\*{0,2}_{0,1}"?'
    # Title: starts with capital, non-greedy, no embedded sentence breaks
    r'(?:[A-Z\'"‘’][^*_\n]{1,88}?)'
    r'"?_{0,1}\*{0,2})'
    # separator
    r'\s+[Bb]y\s+'
    # Author
    r'([A-Z][A-Za-z\.\-\']{0,25}(?:\s+[A-Z][A-Za-z\.\-\']{0,25}){0,3})'
    # lookahead – can't be followed by another lower-case word (would be mid-sentence)
    r'(?=[\s,\.\n\)\[\]]|$)'
    ,
    re.MULTILINE
)

def extract_title_author_pairs(text):
    """Return list of (title, author) found in text, cleaned and validated."""
    pairs = []
    for m in BOOK_BY.finditer(text):
        raw_title  = re.sub(r'^[\*_"\']+|[\*_"\']+$', '', m.group(1)).strip(" ,;")
        raw_author = m.group(2).strip(" ,;.")

        # Clean title: if there's a ". " or ": " or ", " mid-title that splits
        # a preamble clause from the real title, take the last capitalized chunk
        cleaned = clean_title(raw_title)

        if looks_like_title(cleaned) and looks_like_author(raw_author):
            pairs.append((cleaned, raw_author))
    return pairs

def clean_title(raw):
    """
    Strip preamble context that got swept into the title by the greedy regex.
    e.g. "Europe. And so I read a book called I think The Splendid and the Vile"
         → "The Splendid and the Vile"
    """
    # After 'called', 'titled', 'named', 'read', 'is', 'was', 'book' – take what follows
    m = re.search(
        r'(?i)\b(?:called|titled|named|is|was|book|read|recommend(?:ed|ing)?|like)\s+'
        r'([A-Z\'"][^.!?]{2,80})',
        raw
    )
    if m:
        candidate = m.group(1).strip(" ,;")
        if looks_like_title(candidate):
            return candidate

    # After ". " take capitalized remainder
    parts = re.split(r'\.\s+', raw)
    for part in reversed(parts):
        part = part.strip()
        if part and part[0].isupper() and looks_like_title(part):
            return part

    # After ", " take capitalized remainder
    parts = re.split(r',\s+', raw)
    for part in reversed(parts):
        part = part.strip()
        if part and part[0].isupper() and looks_like_title(part):
            return part

    return raw.strip()

# ── Speaker/lightning-round helpers ──────────────────────────────────────────
SPEAKER_HDR = re.compile(r'^\*\*([^*\n]+)\*\*\s*\([\d:]+\):\s*$')

def is_lenny(name):
    return bool(re.match(r'(?i)^lenny', name.strip()))

BOOK_QUESTION = re.compile(
    r'(?i)('
    r'what.{0,15}book.{0,60}(recommend|reading|been reading|love|suggest)'
    r'|books?.{0,30}recommend.{0,20}most'
    r'|what.{0,20}(are you |have you been |recently |lately )?(reading|read)'
    r'|books?.{0,20}(do you|would you) recommend'
    r'|book.{0,20}you.{0,10}(love|recommend|suggest)'
    r')'
)

def collect_guest_answer(lines, question_idx, max_turns=5, max_lines=60):
    """
    Walk forward from question_idx, skip Lenny's follow-ups,
    and collect the raw text of the next max_turns guest speaker turns.
    Returns (guest_name, combined_text).
    """
    guest_name = ""
    blocks = []
    current_block = []
    current_speaker = ""
    turns_collected = 0
    i = question_idx + 1
    end = min(len(lines), question_idx + max_lines)

    while i < end and turns_collected < max_turns:
        line = lines[i]
        m = SPEAKER_HDR.match(line)
        if m:
            # Flush previous block
            if current_block and current_speaker:
                if not is_lenny(current_speaker):
                    blocks.append("\n".join(current_block))
                    turns_collected += 1
                    if not guest_name:
                        guest_name = current_speaker
            current_speaker = m.group(1).strip()
            current_block = []
        else:
            current_block.append(line)
        i += 1

    # Flush last block
    if current_block and current_speaker and not is_lenny(current_speaker):
        blocks.append("\n".join(current_block))

    return guest_name, "\n".join(blocks)

def ctx_window(lines, idx, before=2, after=10):
    return "\n".join(lines[max(0, idx-before): min(len(lines), idx+after+1)])

# ── Also catch italic titles without explicit 'by Author' ────────────────────
ITALIC_TITLE = re.compile(r'\*([A-Z][^*\n]{2,80}?)\*')

# ── Main extractor ────────────────────────────────────────────────────────────
def extract(fpath):
    text = fpath.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(text)

    title    = meta.get("title", fpath.stem)
    subtitle = meta.get("subtitle", "")
    date     = meta.get("date", "")
    ftype    = meta.get("type", "")
    post_url = meta.get("post_url", "")
    youtube  = meta.get("youtube_url", "")
    guest    = meta.get("guest", "")

    lines = body.splitlines()
    results = []
    seen = set()   # normalised title → already added

    def add(book, author, quote, source):
        book   = book.strip(" *_\"',.")
        author = author.strip(" *_\"',.")
        if not looks_like_title(book):
            return
        if not looks_like_author(author):
            return
        if SKIP_LINE.search(book) or SKIP_LINE.search(author):
            return
        key = re.sub(r'[^a-z0-9]', '', book.lower())[:40]
        if key in seen:
            return
        seen.add(key)
        # Truncate long quotes
        q = quote.strip()
        if len(q) > 1200:
            q = q[:1200] + "…"
        results.append({
            "book": book, "author": author, "quote": q, "source": source,
            "title": title, "subtitle": subtitle, "date": date,
            "type": ftype, "guest": guest,
            "post_url": post_url, "youtube_url": youtube,
            "file": str(fpath.relative_to(BASE))
        })

    # ── PODCASTS ──────────────────────────────────────────────────────────────
    if ftype == "podcast":

        # Pass A: lightning-round book questions
        for idx, line in enumerate(lines):
            if SKIP_LINE.search(line):
                continue
            if not BOOK_QUESTION.search(line):
                continue
            _guest, answer_text = collect_guest_answer(lines, idx)
            if not answer_text.strip():
                continue
            for (t, a) in extract_title_author_pairs(answer_text):
                ctx = ctx_window(lines, idx, before=1, after=15)
                add(t, a, ctx, "lightning_round")

        # Pass B: guest's own book – scan intro (lines 3-100)
        intro_text = "\n".join(
            l for l in lines[3:100] if not SKIP_LINE.search(l)
        )
        if re.search(r'(?i)(author of|wrote|new book|his book|her book|my book|co-author)', intro_text):
            for (t, a) in extract_title_author_pairs(intro_text):
                add(t, a, intro_text[:600], "guest_book")

        # Pass C: any line containing 'book' anywhere
        for idx, line in enumerate(lines):
            if SKIP_LINE.search(line):
                continue
            nearby = " ".join(lines[max(0,idx-2):min(len(lines),idx+3)])
            if not re.search(r'(?i)\bbook\b', nearby):
                continue
            for (t, a) in extract_title_author_pairs(line):
                ctx = ctx_window(lines, idx, before=2, after=5)
                add(t, a, ctx, "mention")

    # ── NEWSLETTERS ───────────────────────────────────────────────────────────
    else:
        for idx, line in enumerate(lines):
            if SKIP_LINE.search(line):
                continue
            nearby = " ".join(lines[max(0,idx-3):min(len(lines),idx+4)])
            if not re.search(r'(?i)\b(book|recommend|read|reading)\b', nearby):
                continue
            for (t, a) in extract_title_author_pairs(line):
                ctx = ctx_window(lines, idx, before=3, after=5)
                add(t, a, ctx, "newsletter")

    return results

# ── Run ───────────────────────────────────────────────────────────────────────
all_files = list(BASE.glob("newsletters/*.md")) + list(BASE.glob("podcasts/*.md"))
print(f"Processing {len(all_files)} files…")

all_books, errors = [], []
for fpath in all_files:
    try:
        all_books.extend(extract(fpath))
    except Exception as e:
        errors.append(f"{fpath.name}: {e}")

print(f"Total extractions: {len(all_books)}")
if errors:
    print(f"Errors ({len(errors)}): {errors[:5]}")

out = BASE.parent / "books_raw.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(all_books, f, indent=2, ensure_ascii=False)
print(f"Saved -> {out}")

from collections import Counter
src = Counter(b["source"] for b in all_books)
typ = Counter(b["type"]   for b in all_books)
print(f"\nBy type: {dict(typ)}  |  By source: {dict(src)}")

print("\n=== ALL EXTRACTIONS ===")
for b in sorted(all_books, key=lambda x: (x["type"], x["date"])):
    print(f"  [{b['type']:10s}] '{b['book']}' by {b['author']}")
    print(f"             guest={b['guest'] or 'n/a'}  date={b['date']}  src={b['source']}")
