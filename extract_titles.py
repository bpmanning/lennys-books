"""
extract_titles.py

Extended book-title extractor.  Supplements the original "Title by Author"
regex with five additional patterns so we catch book titles even when the
guest never states the author's name.

Pass 1  (inherited)  – "Title by Author"
Pass 2  (new)        – After trigger keywords: called / reading / recommend …
Pass 3  (new)        – After enumeration cues: one is / another is / it's called …
Pass 4  (new)        – Sentence-initial phrase followed by ", which" or ", that"
Pass 5  (new)        – *Italic* or **bold** title in transcript
Pass 6  (new)        – Possessive  "Author's Title"

Output:  books_candidates.json
         = existing books_raw.json  +  new finds
         New records have  author=""  when the author wasn't spoken.
"""

import re
import json
from pathlib import Path
from collections import Counter

BASE     = Path(r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData"
                r"\lennys-newsletterpodcastdata-all")
RAW_OLD  = Path(r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData\books_raw.json")
OUT      = Path(r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData\books_candidates.json")

# ── Frontmatter ───────────────────────────────────────────────────────────────
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

# ── URL / navigation line filter ──────────────────────────────────────────────
SKIP_LINE = re.compile(
    r"(?i)(https?://|www\.|\.com\b|\.org\b|\.pdf|\.jpg|\.png|"
    r"dp/[A-Z0-9]{10}|qid=|&sr=|UTF8|btkr|"
    r"subscribe\b|apple podcast|spotify|lennyspodcast\.com|"
    r"lennysnewsletter\.com|substack\.com|\[.*?\]\()"
)

# ── Speaker-header detection ──────────────────────────────────────────────────
SPEAKER_HDR = re.compile(r'^\*\*([^*\n]+)\*\*\s*\([\d:]+\):\s*$')

def is_lenny(name):
    return bool(re.match(r'(?i)^lenny', name.strip()))

# ── Lenny's book question ─────────────────────────────────────────────────────
BOOK_QUESTION = re.compile(
    r'(?i)('
    r'what.{0,15}book.{0,60}(recommend|reading|been reading|love|suggest)'
    r'|books?.{0,30}recommend.{0,20}most'
    r'|what.{0,20}(are you |have you been |recently |lately )?(reading|read)'
    r'|books?.{0,20}(do you|would you) recommend'
    r'|book.{0,20}you.{0,10}(love|recommend|suggest)'
    r')'
)

# ── Collect guest answer ──────────────────────────────────────────────────────
def collect_guest_answer(lines, question_idx, max_turns=7, max_lines=100):
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

    if current_block and current_speaker and not is_lenny(current_speaker):
        blocks.append("\n".join(current_block))

    return guest_name, "\n".join(blocks)

# ── Existing "Title by Author" pattern (Pass 1) ───────────────────────────────
BOOK_BY = re.compile(
    r'(?:^|[\s\(\[,;])'
    r'(\*{0,2}_{0,1}"?(?:[A-Z\'""][^*_\n]{1,88}?)"?_{0,1}\*{0,2})'
    r'\s+[Bb]y\s+'
    r'([A-Z][A-Za-z\.\-\']{0,25}(?:\s+[A-Z][A-Za-z\.\-\']{0,25}){0,3})'
    r'(?=[\s,\.\n\)\[\]]|$)',
    re.MULTILINE
)

AUTHOR_RE = re.compile(
    r'^[A-Z][a-zA-Z\.\-\']{0,25}(\s+[A-Z][a-zA-Z\.\-\']{0,25}){0,3}$'
)
def looks_like_author(s):
    s = s.strip(" .,;:")
    if not s or re.search(r'[%?=#&/]', s):
        return False
    return bool(AUTHOR_RE.match(s))

# ── Title boundary: stop a captured phrase here ───────────────────────────────
# (used as lookahead in patterns below)
TITLE_STOP = (
    r'(?='
    r'\s*[,\.\n\)\[\]]'                                   # punctuation
    r'|\s+(?:by|which|that|who|but|and|or|so|'           # connectors
    r'is|was|are|were|has|have|had|'
    r'it\'?s?|he\'?s?|she\'?s?|they\'?re|'
    r'[–—]|\()'
    r'|$'
    r')'
)

# ── Pass 2: after trigger keywords ────────────────────────────────────────────
# NOTE: (?i:...) scopes case-insensitivity to ONLY the keyword group.
# The capture group is intentionally outside so [A-Z] requires a real capital.
# Without this, (?i) would let "recommend is a book called X" match "is a book
# called X" as the title (lowercase start), consuming the text before "called X"
# can be matched separately.
AFTER_TRIGGER = re.compile(
    r'(?i:\b(?:'
    r'books?\s+(?:called|titled|named)\s+'
    r'|books?\s+(?:that\s+)?I\s+(?:love|recommend|read|suggest)\s+(?:is\s+)?'
    r'|(?:his|her|their|my)\s+book,?\s+'          # "her book, Radical Candor"
    r'|(?:called|titled|named)\s+'
    r'|(?:reading|re-?reading|recommend(?:ed|ing)?|suggest(?:ed)?)\s+'
    r'(?:(?:a|the|this|that|an)\s+)?'
    r'|(?:love[sd]?|loved)\s+(?:(?:a|the|this|that|an)\s+)?'
    r'|(?:enjoy(?:ed)?)\s+(?:(?:a|the|this|that|an)\s+)?'
    r'|(?:finish(?:ed)?|picked?\s+up|started?\s+reading)\s+'
    r'))'
    r'([A-Z\'""][^.!?\n*_]{2,80}?)'
    + TITLE_STOP,
    re.MULTILINE
)

# ── Pass 3: enumeration & sentence-starter cues ───────────────────────────────
# NOTE: same (?i:...) scoping as AFTER_TRIGGER — keeps [A-Z] case-sensitive.
AFTER_ENUM = re.compile(
    r'(?i:\b(?:'
    # "one is X", "another is X", "one book is X"
    r'(?:one|another)\s+(?:[^.!?\n]{0,25}?\s+)?(?:is\b|recommend\b)\s*'
    # "first/second/third is X"  or  "Second book, X"
    r'|(?:the\s+)?(?:first|second|third|fourth|fifth)\s+(?:one\s+)?(?:is\b|book\s+is\b)\s*'
    r'|(?:the\s+)?(?:first|second|third|fourth|fifth)\s+book[,:]?\s*'
    # "it's (called) X", "It is X", "that's X"
    r"|it'?s?\s+(?:called\s+|titled\s+)?"
    r'|it\s+is\s+(?:called\s+|titled\s+)?'        # "It is Functional Programming…"
    r"|that'?s?\s+"
    # "probably/maybe/perhaps X"
    r'|(?:probably|maybe|perhaps)\s+'
    # "my go-to is X", "my favorite is X"
    r'|my\s+(?:go-to\s+(?:is\s+)?|favorite\s+(?:is\s+)?|recommendation\s+(?:is\s+)?)'
    r'))'
    r'([A-Z\'""][^.!?\n*_]{2,80}?)'
    + TITLE_STOP,
    re.MULTILINE
)

# ── Pass 4: sentence-initial title followed by ", which/that/it" ─────────────
# Handles: "Competing Against Luck, which was the book that..."
# Handles: "The Weirdest People in the World, which it's a kind of..."
INITIAL_RELATIVE = re.compile(
    r'(?:^|\n)'
    r'([A-Z][a-z]+(?:(?:\s+[a-z]{1,4})?'    # first word + optional articles
    r'\s+[A-Z0-9][a-zA-Z0-9]*){1,7})'        # 1-7 more words
    r'\s*,\s*(?:which|that|it\'?s?|he\'?s?|she|they)\b',
    re.MULTILINE
)

# ── Pass 5: italic / bold titles ──────────────────────────────────────────────
ITALIC_TITLE_RE = re.compile(r'\*{1,2}([A-Z][^*\n]{2,80}?)\*{1,2}')

# ── Pass 6: possessive "Author's Title" ───────────────────────────────────────
# e.g. "Susan Cain's Quiet" → captures "Quiet"
POSSESSIVE_TITLE = re.compile(
    r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\'s\s+'
    r'([A-Z][^.!?\n*_]{2,60}?)'
    + TITLE_STOP,
    re.MULTILINE
)

# ── Candidate title cleaning ──────────────────────────────────────────────────
def clean_candidate(raw):
    """Strip noise captured alongside the title."""
    t = re.sub(r'[\*_]+', '', raw)
    t = t.strip(' ,;.:\'"')
    # Strip "by a/an/the [anything]" (e.g. "by a professor called Byron Sharp")
    t = re.sub(r'\s+by\s+(?:a\s+|an\s+|the\s+)?[A-Za-z].*$', '', t, flags=re.IGNORECASE)
    # Strip relative clauses
    t = re.sub(r'\s*,\s*(?:which|that|it\'?s?|who|where)\b.*$', '', t, flags=re.IGNORECASE)
    # Strip em-dash continuations
    t = re.sub(r'\s+[–—].*$', '', t)
    # Strip orphaned trailing connectors
    t = re.sub(r'\s+(?:and|or|but|so|is|was)\s*$', '', t, flags=re.IGNORECASE)
    # Limit to 9 words
    words = t.split()
    if len(words) > 9:
        t = ' '.join(words[:9])
    return t.strip(' ,;.\'"')

# ── Not-a-title guard ─────────────────────────────────────────────────────────
_NOT_TITLE_FIRST = re.compile(
    r'(?i)^(?:'
    r'lenny|podcast|episode|newsletter|substack|'
    r'apple|google|spotify|amazon|kindle|audible|youtube|'
    r'sponsored|subscribe|follow|join|find|'
    r'honestly|basically|actually|definitely|obviously|certainly|'
    r'something|anything|everything|nothing|someone|everyone|'
    r'startup|company|business|product|team|customer|user|'
    r'additional|action|activity|example|feature|output|'
    r'section|chapter|part|step|note|tip|summary|overview|intro'
    r')$'
)

# Words that are "significant" for title-case scoring (not articles/prepositions)
_ARTICLES = frozenset(
    'a an the of in on at to for by with and or but nor so yet from'
    ' as into through during before after above below between among'.split()
)

def title_case_score(t):
    """Fraction of non-article words that start with a capital letter."""
    significant = [w for w in t.split() if w.lower() not in _ARTICLES]
    if not significant:
        return 0.0
    caps = sum(1 for w in significant if w and (w[0].isupper() or w[0].isdigit()))
    return caps / len(significant)

def is_valid_candidate(t):
    """Return True if t looks like a plausible book title."""
    if not t or len(t) < 4:
        return False
    words = t.split()
    # Require at least 2 words — single-word titles are too ambiguous without an author
    if len(words) < 2:
        return False
    if len(words) > 9:
        return False
    if not (t[0].isupper() or t[0].isdigit() or t[0] in ('"', "'")):
        return False
    if _NOT_TITLE_FIRST.match(words[0]):
        return False
    if re.search(r'[%/?=#&]', t):
        return False
    if re.search(r'[.?!]\s', t):          # embedded sentence break
        return False
    # Title-case check: ≥60 % of significant words must start with a capital
    if title_case_score(t) < 0.6:
        return False
    return True

# ── Extract all candidate (title, author) pairs from a window of text ─────────
def extract_candidates(text):
    """Return list of (title, author) from a block of guest-answer text."""
    results = []
    seen = set()

    def add(raw_title, author=""):
        t = clean_candidate(raw_title)
        if not is_valid_candidate(t):
            return
        key = re.sub(r'[^a-z0-9]', '', t.lower())[:40]
        if key in seen:
            return
        seen.add(key)
        results.append((t, author))

    # Pass 1: Title by Author
    for m in BOOK_BY.finditer(text):
        raw_t = re.sub(r'^[\*_"\']+|[\*_"\']+$', '', m.group(1)).strip()
        raw_a = m.group(2).strip()
        if looks_like_author(raw_a):
            add(raw_t, raw_a)
        else:
            add(raw_t)

    # Pass 2: trigger keywords
    for m in AFTER_TRIGGER.finditer(text):
        add(m.group(1))

    # Pass 3: enumeration cues
    for m in AFTER_ENUM.finditer(text):
        add(m.group(1))

    # Pass 4: sentence-initial + relative clause
    for m in INITIAL_RELATIVE.finditer(text):
        add(m.group(1))

    # Pass 5: italic / bold
    for m in ITALIC_TITLE_RE.finditer(text):
        add(m.group(1))

    # Pass 6: possessive
    for m in POSSESSIVE_TITLE.finditer(text):
        add(m.group(1))

    return results

# ── Per-file extraction ───────────────────────────────────────────────────────
def extract_file(fpath):
    text = fpath.read_text(encoding='utf-8', errors='replace')
    meta, body = parse_frontmatter(text)

    ep_title  = meta.get("title", fpath.stem)
    subtitle  = meta.get("subtitle", "")
    date      = meta.get("date", "")
    ftype     = meta.get("type", "podcast")
    post_url  = meta.get("post_url", "")
    youtube   = meta.get("youtube_url", "")
    guest     = meta.get("guest", "")

    lines = body.splitlines()
    results = []
    seen_file = set()   # dedup within this file

    def emit(book, author, quote, source):
        if SKIP_LINE.search(book):
            return
        key = re.sub(r'[^a-z0-9]', '', book.lower())[:40]
        if key in seen_file:
            return
        seen_file.add(key)
        q = quote.strip()
        if len(q) > 1000:
            q = q[:1000] + "..."
        results.append({
            "book": book, "author": author, "quote": q, "source": source,
            "title": ep_title, "subtitle": subtitle, "date": date,
            "type": ftype, "guest": guest,
            "post_url": post_url, "youtube_url": youtube,
            "file": str(fpath.relative_to(BASE)),
        })

    # ── Podcast: lightning round ──
    if ftype == "podcast":
        for idx, line in enumerate(lines):
            if SKIP_LINE.search(line):
                continue
            if not BOOK_QUESTION.search(line):
                continue
            _guest, answer = collect_guest_answer(lines, idx)
            if not answer.strip():
                continue
            ctx_start = max(0, idx - 1)
            ctx_end   = min(len(lines), idx + 20)
            ctx = "\n".join(lines[ctx_start:ctx_end])
            for (t, a) in extract_candidates(answer):
                emit(t, a, ctx, "lightning_round")

        # Guest's own book in intro
        intro = "\n".join(l for l in lines[3:100] if not SKIP_LINE.search(l))
        if re.search(r'(?i)(author of|wrote|new book|his book|her book|my book|co-author)', intro):
            for m in BOOK_BY.finditer(intro):
                raw_t = re.sub(r'^[\*_"\']+|[\*_"\']+$', '', m.group(1)).strip()
                raw_a = m.group(2).strip()
                t = clean_candidate(raw_t)
                if is_valid_candidate(t) and looks_like_author(raw_a):
                    emit(t, raw_a, intro[:600], "guest_book")

    # Newsletters: skip here — the original extract_books.py already handles
    # newsletters with the strict "Title by Author" pattern.  The broader
    # patterns used above produce too many newsletter section-header false
    # positives (e.g. "Action items", "Additional reading").

    return results

# ── Main ──────────────────────────────────────────────────────────────────────
existing = json.loads(RAW_OLD.read_text(encoding='utf-8'))
print(f"Existing raw records : {len(existing)}")

# Build dedup set from existing records
existing_keys = set()
for r in existing:
    k = (r.get("file", ""), re.sub(r'[^a-z0-9]', '', r["book"].lower())[:40])
    existing_keys.add(k)

all_files = list(BASE.glob("podcasts/*.md"))
# Newsletters excluded: broader patterns produce too many section-header false
# positives; newsletter books are already covered by extract_books.py.
print(f"Files to process     : {len(all_files)}")

new_records = []
files_with_new = 0
source_counter = Counter()

for fpath in all_files:
    try:
        found = extract_file(fpath)
    except Exception as e:
        print(f"  ERROR {fpath.name}: {e}")
        continue

    added = 0
    for r in found:
        k = (r["file"], re.sub(r'[^a-z0-9]', '', r["book"].lower())[:40])
        if k not in existing_keys:
            new_records.append(r)
            existing_keys.add(k)
            source_counter[r["source"]] += 1
            added += 1
    if added:
        files_with_new += 1

print(f"\nNew records found    : {len(new_records)}  from {files_with_new} files")
print(f"  By source: {dict(source_counter)}")
new_blank_author = sum(1 for r in new_records if not r["author"])
print(f"  With author  : {len(new_records) - new_blank_author}")
print(f"  Blank author : {new_blank_author}  (will be looked up via Open Library)")

combined = existing + new_records
print(f"\nTotal candidates     : {len(combined)}")
print(f"Need OL author lookup: {sum(1 for r in combined if not r.get('author'))}")

OUT.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"Saved -> {OUT}")

print("\n=== NEW TITLES (no author yet) ===")
for r in sorted(new_records, key=lambda x: x["book"].lower()):
    status = r["author"] if r["author"] else "[author blank - OL lookup needed]"
    print(f"  '{r['book']}' by {status}")
    print(f"     [{r['type']}] {r.get('guest') or 'n/a'} | {r.get('date','')[:7]} | {r['source']}")
