# Claude Design Prompt — Lenny's Books Website

---

## Brief

Build a polished, standalone HTML website called **Lenny's Books** — a curated dataset of every book recommended on Lenny Rachitsky's *Lenny's Newsletter & Podcast*, one of the most-read product and growth publications in tech.

The data lives in `books_clean.json` (306 records). The site should feel like a beautifully designed editorial product — think *The Browser* meets *Are.na* meets a Stripe-quality dashboard. It should ooze taste: generous whitespace, confident typography, purposeful color, and zero clutter.

---

## Data

Load `books_clean.json` (fetch or inline it). Each record has:

```json
{
  "book":            "Shoe Dog",
  "author":          "Phil Knight",
  "guest":           "Garrett Lord",
  "date":            "2025-08-14",
  "type":            "podcast",
  "source":          "lightning_round",
  "title":           "Episode title | Guest Name (Job Title, Company)",
  "youtube_url":     "https://youtube.com/...",
  "cover_url":       "https://covers.openlibrary.org/b/id/...-L.jpg",
  "description":     "A memoir about building Nike...",
  "pages":           386,
  "published_year":  2016,
  "subjects":        ["Business", "Entrepreneurship", "Biography"],
  "isbn":            "9781501135910",
  "metadata_source": "ol"
}
```

**Source types** (the `source` field):
- `lightning_round` — Lenny's closing question to every guest: *"What books do you find yourself recommending most?"*
- `mention` — referenced organically mid-conversation
- `guest_book` — a book the guest themselves wrote
- `newsletter` — recommended in a written issue

**Job roles** are embedded in the `title` field after the `|` separator, e.g. `"How Netflix builds culture | Elizabeth Stone (CTO)"`. Parse these to extract titles like CEO, CTO, CPO, CMO, VP Product, Founder, etc.

**Known stats to highlight:**
- 306 total recommendations across 257 unique titles
- 248 unique recommenders (guests)
- Coverage: December 2020 – May 2026
- Most recommended: *Build*, *Man's Search for Meaning*, *Shoe Dog*, *Thinking in Systems* (4× each)
- Oldest book: *Tao Te Ching* (~500 BC); oldest with a year: *The Inner Game of Tennis* (1834 — note: likely a data quirk; surface it with a wink)
- Top recommenders: Will Larson (6), Gustav Söderström (6), Arielle Jackson (6)

---

## Site Structure

### 1. Hero / Stats Bar
Full-width header. Site name and one-line description. Then a tight horizontal row of animated count-up stats:
- **306** recommendations
- **257** unique titles
- **248** guests
- **5 years** of episodes
- **95%** with cover art

### 2. Insights Dashboard
A visually rich section — not a table, more like a curated editorial spread. Sections:

**Top Books** — Horizontal bar chart or large typographic list of the 10 most-recommended titles with recommendation count badges.

**Top Recommenders** — Card grid of the 8 guests who recommended the most books. Show name, rec count, and their episode title excerpt.

**Books by Role** — Parse the job title from each episode's `title` field. Group into: Founder/CEO, CPO/Head of Product, CTO/Engineering, CMO/Marketing, VC/Investor, Other. Show which books appear most within each role category as a small ranked list per column.

**Genre Breakdown** — Donut or horizontal bars of top subjects: Leadership, Business, Biography, History, Marketing, Entrepreneurship, Decision Making, etc. (derived from `subjects` field).

**Timeline** — Scatter or small dot-plot of `published_year` for all books. Show the full sweep from antiquity (Tao Te Ching) to 2024. Highlight outliers with tooltips.

**Source Mix** — Simple visual breakdown: 90% lightning round, 6% mention, 2% guest book, 1% newsletter.

### 3. Book Browser
The main browsable grid. Default: masonry or uniform card grid sorted by most-recommended → alphabetical.

Each card shows:
- Cover image (fallback: colored initial tile based on title)
- Title + Author
- Recommendation count badge if > 1
- Up to 2 genre tags
- On hover: expand to show description snippet, year, pages, and who recommended it

**Filter / Sort bar** (sticky):
- Search box (title or author)
- Filter chips: All · Lightning Round · Mention · Guest Book
- Genre filter dropdown (multi-select)
- Sort: Most Recommended · Alphabetical · Oldest Published · Newest Published
- Results count: "Showing 257 of 257 books"

### 4. Footer
Quiet footer: data sourced from Lenny's Newsletter & Podcast · pipeline on GitHub.

---

## Design Direction

**Aesthetic:** Confident, editorial, dark-mode-first (with a tasteful light mode toggle). Think a product built by someone who has strong opinions about font stacks.

**Typography:**
- Headlines: a high-contrast serif (e.g. *Playfair Display* or *DM Serif Display*)
- Body + UI: a clean grotesque (e.g. *Inter* or *DM Sans*)
- Monospace accents for counts/stats (e.g. *JetBrains Mono* or *IBM Plex Mono*)

**Color palette (dark mode):**
- Background: `#0f0f0f` or `#111318`
- Surface: `#1a1a1f`
- Accent: warm amber or terracotta — `#e86c3a` or `#d4884a`
- Text: `#f0ede8` primary, `#888` secondary
- Tags/pills: muted `#2a2a30` background with `#666` text

**Motion:** Subtle. Stagger-fade cards on load. Count-up animation on stats. Smooth filter transitions — cards don't jump, they fade/reflow.

**Cover art fallbacks:** When `cover_url` is missing, generate a colored tile using the book title's initials. Use a consistent palette of 8–10 muted colors derived from the title string.

**Details that elevate it:**
- Book cards have a very slight tilt/shadow on hover, like picking up a physical book
- The insights section uses large typographic numbers as visual anchors, not just chart labels
- Empty search state has a friendly message, not just nothing
- Recommendation context: clicking a book shows a modal or drawer with the full list of who recommended it, their episode, and the date

---

## Technical Requirements

- **Single HTML file** — all CSS and JS inline or in `<style>`/`<script>` tags. No build step, no framework, no CDN dependencies beyond Google Fonts.
- Loads `books_clean.json` via `fetch('./books_clean.json')` (works when served locally or deployed to GitHub Pages / Netlify).
- Fully responsive: mobile, tablet, desktop. The book grid collapses gracefully.
- Accessible: keyboard-navigable filters, proper ARIA labels on interactive elements, sufficient color contrast.
- No external charting library required — build the simple charts with SVG or CSS directly.
- Performance: lazy-load cover images (`loading="lazy"`). The JSON is ~450KB so parse it once and cache in memory.

---

## Deliverable

A single `books_table.html` file (replacing the existing one) ready to open in a browser or deploy to GitHub Pages by dropping it alongside `books_clean.json`.
