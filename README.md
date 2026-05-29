# Lenny's Books

A structured dataset of every book recommended on [Lenny's Newsletter & Podcast](https://www.lennysnewsletter.com) — extracted from full transcript archives, enriched with metadata, and published as a searchable HTML table.

---

## Dataset

| Stat | Value |
|---|---|
| Total recommendations | 306 |
| Unique titles | 257 |
| Unique authors | 248 |
| Coverage | Dec 2020 – May 2026 |
| Sources | 304 podcast episodes, 2 newsletters |
| Titles with cover images | 261 / 257 (95%) |
| Titles with descriptions | 187 / 257 |

Books are sourced from three contexts:
- **Lightning round** — Lenny's standard closing question: *"What are two or three books you find yourself recommending most?"*
- **Guest book** — A book the guest wrote themselves, mentioned in the intro
- **Mention** — Referenced organically during the conversation

---

## Output Files

| File | Description |
|---|---|
| `books_clean.json` | 306 records — normalized titles, authors, guest, date, episode, source context, and all metadata fields |
| `books_metadata.json` | Persistent OL + Google Books cache keyed by normalized title — never re-fetched on re-runs |
| `books_table.html` | Standalone searchable HTML table with cover thumbnails, descriptions, genre tags, and year/page pills |

### Record schema (`books_clean.json`)

```json
{
  "book":            "The Hard Thing About Hard Things",
  "author":          "Ben Horowitz",
  "guest":           "Matt Mochary",
  "date":            "2022-11-10",
  "type":            "podcast",
  "source":          "lightning_round",
  "title":           "Episode title",
  "youtube_url":     "https://...",
  "cover_url":       "https://covers.openlibrary.org/b/id/...-L.jpg",
  "description":     "A memoir and management guide...",
  "pages":           304,
  "published_year":  2014,
  "subjects":        ["Business", "Leadership", "Startups"],
  "isbn":            "9780062273208",
  "metadata_source": "ol"
}
```

---

## Pipeline

```
lennys-newsletterpodcastdata-all/   ← raw source (not in this repo)
        │
        ▼
extract_titles.py   →  books_candidates.json   (549 raw candidates, 6-pass extractor)
        │
        ▼
enrich_books.py     →  books_candidates.json   (fills missing authors via Open Library)
        │
        ▼
clean_books.py      →  books_clean.json        (normalize, deduplicate, apply fix tables)
                    →  books_table.html         (rendered HTML output)
        ↑
books_metadata.json  ←  enrich_metadata.py     (OL + Google Books; persistent cache)
                     ←  retry_none_metadata.py  (targeted retry for rate-limited misses)
```

### Scripts

| Script | Purpose |
|---|---|
| `extract_titles.py` | 6-pass extractor covering all recommendation patterns in transcripts |
| `enrich_books.py` | Fills blank authors using the Open Library search API |
| `clean_books.py` | Normalizes titles, fixes authors, deduplicates, merges metadata, generates HTML |
| `enrich_metadata.py` | Enriches every unique title with cover, description, pages, genres, ISBN, year |
| `retry_none_metadata.py` | OL-only retry pass for titles that hit rate limits during the main enrichment run |

### Running the pipeline

```bash
# Prerequisites: Python 3.9+, internet access (no pip installs required)

# 1. Point BASE path in each script to your local copy of lennys-newsletterpodcastdata-all/

# 2. Extract raw candidates
python extract_titles.py

# 3. Fill missing authors
python enrich_books.py

# 4. Enrich with metadata (takes ~10 min for 255 titles; re-run safe)
python enrich_metadata.py

# 5. If some titles hit 429s, retry after ~1 hour
python retry_none_metadata.py

# clean_books.py is called automatically at the end of enrich_metadata.py,
# or run it standalone to regenerate books_clean.json + books_table.html:
python clean_books.py
```

**Optional:** Set `GOOGLE_BOOKS_API_KEY` for higher Google Books rate limits:
```bash
export GOOGLE_BOOKS_API_KEY=your_key_here
python enrich_metadata.py
```

---

## Source Data

The raw source — `lennys-newsletterpodcastdata-all/` — is a full transcript archive of Lenny's Newsletter and Podcast in markdown format (~60MB, 549+ files). It has its own git history and is excluded from this repo via `.gitignore`. Keep it as a sibling directory to this repo for the pipeline scripts to find it.

---

## Dev Setup

After cloning, activate the pre-commit tracker reminder:
```bash
git config core.hooksPath .githooks
```

See `PROJECT_TRACKER.md` for the full development history.
