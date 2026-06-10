# Project Tracker — Lenny's Books

Running log of every meaningful change, decision, and rationale.
Entries are **newest-first**. Never overwrite — append new entries at the top under a new date/commit heading.

To activate the pre-commit reminder hook after a fresh clone:
```
git config core.hooksPath .githooks
```

---

## 2026-06-09 — Timeline scrubber and duplicate check

**Commits:** `(next)`

- Added dual-handle range scrubber below the "Published across the ages" scatterplot — drag handles to zoom into any date range; axis labels regenerate based on view span; Reset zoom link appears when zoomed
- Verified book grid deduplication: `aggregate()` keys on lowercased title+author, so duplicates in raw data are merged; no rendering path re-introduces dupes

---

## 2026-06-09 — Fix filter counts and dropdown styling

**Commits:** `(next)`

- Fixed source filter chip counts: were counting raw recommendation records, now count unique books per source
- Added `drop-btn` style for Genres and Sort controls — dashed border, transparent background — to visually distinguish them from the solid source filter chips

---

## 2026-06-09 — Remove metadata gremlin note from Published Across the Ages card

**Commits:** `(next)`

- Removed the "Alice in Wonderland lists a publish year of 1865 — almost certainly a metadata gremlin" note from the timeline card

---

## 2026-06-09 — Rename to index.html for GitHub Pages

**Commits:** `(next)`

- Renamed `lennysbooks.html` → `index.html` so GitHub Pages serves it at the root URL instead of the README

---

## 2026-06-09 — lennysbooks.html website

**Commits:** `a5cad00`

- Added `lennysbooks.html` — fully self-contained books website built and iteratively refined across multiple Claude Design sessions
- Single HTML file, no build step; fetches `books_clean.json` for data; GitHub Pages ready

---

## 2026-05-29 — Claude Design prompt

**Commits:** `(next)`

- Added `claude-design-prompt.md` — a full design brief for rebuilding `books_table.html` as a deployable website using Claude Design
- Brief covers: site structure (hero stats bar, insights dashboard, book browser), design direction (dark-mode-first, serif + grotesque + mono type stack, warm amber accent, cover-art fallbacks, card hover physics), technical requirements (single HTML file, no build step, fetch-based JSON loading, GitHub Pages ready), and specific insight sections to build (top books, top recommenders, books by job role, genre breakdown, published timeline, source mix)
- Key stats surfaced for the prompt from `books_clean.json` analysis: 4× most-recommended titles, top 8 recommenders, oldest books, subject distribution

---

## 2026-05-29 — README and pre-commit hook

**Commits:** `da9714b`

- Added `README.md` covering dataset stats (306 records, 257 unique titles, Dec 2020–May 2026), record schema, full pipeline diagram, per-script descriptions, run instructions, and dev setup
- Added `.githooks/pre-commit` — prints a non-blocking reminder when `PROJECT_TRACKER.md` isn't staged; activate once per clone with `git config core.hooksPath .githooks`

---

## 2026-05-29 — Repo correction & legacy folder cleanup

**Commits:** `3983655`

- Discovered the initial pipeline commit had been pushed to the wrong repo (`bpmanning/Data-Storytelling` instead of `bpmanning/lennys-books`)
- Cloned the empty `lennys-books` repo to `LennysBooks/`, copied all pipeline files, and committed there first to preserve the working files on disk
- Hard-reset `Data-Storytelling` to `HEAD~1` and force-pushed to restore the 27 deleted negawatt site files
- Moved 7 superseded files into `legacy/` to clean up the root:
  - Scripts: `extract_books.py`, `extract_books_v2.py`, `extract_books_v3.py`
  - Data: `books_raw.json`, `books_extracted.json`, `books_extracted_v2.json`, `books_list.txt`

**Active pipeline after cleanup:**
```
extract_titles.py → books_candidates.json
enrich_books.py   → fills missing authors in-place
clean_books.py    → books_clean.json + books_table.html
enrich_metadata.py → books_metadata.json (persistent cache)
retry_none_metadata.py → targeted retry for rate-limited misses
```

---

## 2026-05-29 — Initial commit: full pipeline to lennys-books

**Commits:** `f224758`

All pipeline scripts and output data committed to `bpmanning/lennys-books` for the first time.

**Files included:**
- 8 Python scripts (see pipeline above)
- `books_candidates.json` — 549 raw extracted candidates, cleaned to 339 after filters
- `books_clean.json` — 306 deduplicated, normalized records with full metadata merged
- `books_metadata.json` — persistent OL + Google Books cache (243/255 titles enriched, 95%)
- `books_table.html` — searchable HTML table with cover thumbnails, descriptions, genre tags, and year/page pills
- `.gitignore` — excludes `__pycache__/` and `lennys-newsletterpodcastdata-all/` (raw data has its own git repo)

---

## 2026-05-29 — Metadata retry: targeted OL-only pass for rate-limited books

- After two failed retry runs (all 20 hitting HTTP 429 from Open Library), a third targeted run succeeded once the rate-limit window expired
- Switched to OL-only (skipping Google Books, which was also 429ing) with 1.5s inter-request pause
- Filled 4 more entries per run across two passes: went from 20 → 16 → 12 `source=none` entries
- Books still without metadata (12/255) fall into four categories:
  - **OL findable but rate-limited at time of run:** Build, Kafka on the Shore, Powerful, Tools of Conviviality, The Rigor of Angels
  - **Combined/series titles** with no single-book OL match: The Wool Trilogy, The Beginning of Infinity and The Fabric of Reality
  - **HBR article, not a standalone book:** The New New Product Development Game (1986 Takeuchi & Nonaka)
  - **Possibly too new or obscure for OL:** Decision Stack, The Value Flywheel Effect, The Experience Machine, The First 50 Years of Apple

**`retry_none_metadata.py` design:**
- Skips GB entirely (still rate-limited); OL only
- Multiple query strategies per title: full title → strip subtitle → strip "series/trilogy" suffix → author+keyword
- Saves after every single book so partial progress is never lost on interrupt
- Calls `clean_books.py` at the end to regenerate outputs

---

## 2026-05-29 — Metadata enrichment: Open Library + Google Books

- Built `enrich_metadata.py` — new fourth stage in the pipeline
- Adds 6 fields per book: `cover_url`, `description`, `pages`, `subjects`, `isbn`, `published_year`
- **Strategy:** Open Library first (free, no key required); Google Books fallback for any fields OL couldn't fill; result cached in `books_metadata.json` keyed by normalized title
- `books_metadata.json` is persistent — re-runs never re-fetch already-cached titles
- First full run enriched 235/255 unique titles; 20 got HTTP 429 from OL during the Works API description fetch
- `GOOGLE_BOOKS_API_KEY` env var is optional but raises Google's rate limit if set

**OL enrichment details:**
- Search API returns `cover_i`, `isbn`, `number_of_pages_median`, `subject`, `first_publish_year` in one call
- Second call to `/works/{key}.json` for description — this is the endpoint that triggers 429s under load
- Similarity threshold 0.78 for OL, 0.72 for Google Books; small bonus (+0.08) if author name matches

**Updated `clean_books.py`** to merge `books_metadata.json` at regeneration time:
- `_norm_key()` function mirrors `norm_key()` in `enrich_metadata.py` exactly to ensure cache keys match
- Metadata fields applied after dedup so nothing overwrites author/title corrections

**Updated `books_table.html`** to display enriched metadata:
- 48×70px cover thumbnails with lazy loading; grey placeholder for missing covers
- 140-char description snippet below each title
- Genre tag pills (up to 3) and blue year + page-count pills in a flex meta row

---

## 2026-05-28 — Data audit: full TITLE_FIX / AUTHOR_FIX pass on clean_books.py

**~110 fixes applied across three audit rounds.** All fixes applied in `clean_books.py` before `clean_title()` processing.

**TITLE_FIX drops (~54 entries)** — removed non-books:
- Products/apps: Alive OS, Aura Frames, Bison Trails, Stripe Press, Dreaming Spanish
- Shows/podcasts: Top Gun, Top Gear, Veep on HBO, The West Wing Weekly, The Ezra Klein Show
- Person names mistaken for titles: Adam Grant's, Jeff Bezos, Roald Dahl
- Sentence fragments: "I'm reading on Instagram", "Andrew Roberts latest book on Winston Churchill", "Deepen Your Learning"

**TITLE_FIX renames (~30 entries)** — canonical title normalization:
- `"Will Never Work"` → `"That Will Never Work"`
- `"Guide to Losing Control"` → `"The Perfectionist's Guide to Losing Control"`
- `"Top Five Regrets of the Dying"` + two variants → `"The Top Five Regrets of the Dying"`
- `"Ate the Whale"` → `"The Fish That Ate the Whale"`
- `"Big Short"` → `"The Big Short"`
- `"Stumbling Upon Happiness"` → `"Stumbling on Happiness"`
- `"Robert Frank as an author in Darwin Economy"` → `"The Darwin Economy"`
- `"Dare to Lead Like a Girl"` → identity fix to bypass a `(?i)` regex bug in `clean_title()` that truncated the title to `"a Girl"`

**AUTHOR_FIX (~5 entries):**
- `"Goldsmith Marshall"` → `"Sally Helgesen and Marshall Goldsmith"`
- `"Ian Banks"` → `"Iain Banks"` (OL returns the wrong spelling)
- `"Patti Smith, Patti Smith"` → `"Patti Smith"` (deduplication artifact)
- `"Walsh, Bill"` → `"Bill Walsh"`

**SPECIFIC_BOOK_AUTHOR_FIX (~20 entries)** — title+wrong-author → correct author pairs:
- `("The Big Short", "Michael Lewis, Francisco José Ramos Mena")` → `"Michael Lewis"` (OL returned Spanish edition with translator credit)
- `("The Fish That Ate the Whale", "Timea Thompson")` → `"Rich Cohen"`
- `("The Goal", "Elle Kennedy")` → `"Eliyahu M. Goldratt"`
- `("Sapiens", "")` → `"Yuval Noah Harari"`
- `("Thinking, Fast and Slow", "")` → `"Daniel Kahneman"`
- + 15 more pairings for books where OL returned no author or the wrong author

**Bug discovered:** `clean_title()` has a `(?i)` scope issue — the flag makes a subsequent `[A-Z]` capture group match lowercase too. Workaround: add an identity TITLE_FIX entry for any title that triggers the bug.

**Final record count after audit:** 306 clean records (down from 387 raw candidates after drops + deduplication)

---

## 2026-05-28 — Author enrichment via Open Library

- Built `enrich_books.py` — queries OL search API for any book with a missing or placeholder author
- Fuzzy title-match with `SequenceMatcher`; threshold 0.72; author-name match adds +0.08 bonus
- Results written back to `books_candidates.json` in-place; re-run safe (skips already-filled entries)
- Caught and fixed several OL quirks: translator credits, inverted "Surname First" formats, series entries returning wrong book's author

---

## 2026-05-28 — Comprehensive extraction: extract_titles.py (6-pass)

- Replaced the v1–v3 extraction scripts with `extract_titles.py` — a purpose-built 6-pass extractor
- **Pass 1:** `"Title by Author"` pattern (inherited from v1)
- **Pass 2:** After trigger keywords: *called / reading / recommend / suggest / favorite*
- **Pass 3:** After enumeration cues: *one is / another is / it's called*
- **Pass 4:** Sentence-initial phrase followed by `, which` or `, that`
- **Pass 5:** `*Italic*` or `**bold**` title in transcript markdown
- **Pass 6:** Possessive `"Author's Title"` pattern
- Output: `books_candidates.json` — 549 raw candidates with `book`, `author`, `file`, `date`, `source_type`, `mention_type` fields
- `clean_books.py` deduplicates by `(file, normalized_title)` key so the same book recommended in the same episode isn't double-counted, but the same book recommended by two different guests is counted separately

---

## 2026-05-28 — Initial extraction pipeline (v1–v3)

Three iterative extraction attempts before settling on the 6-pass approach:

**`extract_books.py` (v1):**
- Simple regex for `"Title by Author"` pattern across all podcast/newsletter markdown
- Output: `books_raw.json` — broad but noisy; many false positives from image captions and sponsor copy

**`extract_books_v2.py` (v2):**
- Added frontmatter parsing, newsletter-specific sections, and guest-book detection
- Output: `books_extracted.json` — better precision but still missing titles without explicit author attribution

**`extract_books_v3.py` (v3):**
- Bug-fixed v2 with improved quote extraction and filtering
- Still limited by the fundamental `"Title by Author"` constraint — superseded by `extract_titles.py`

**Source data:** `lennys-newsletterpodcastdata-all/` — full Lenny Rachitsky newsletter and podcast transcript archive (60MB, ~549 episodes and newsletters as markdown files). Excluded from this repo via `.gitignore` since it has its own git history.
