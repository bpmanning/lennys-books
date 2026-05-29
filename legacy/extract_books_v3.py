#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive book extraction from Lenny's newsletter and podcast markdown files.
v3 - Fixed bugs, improved filtering, better quote extraction.
"""

import os
import re
import json

BASE_DIR = r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData\lennys-newsletterpodcastdata-all"
NEWSLETTERS_DIR = os.path.join(BASE_DIR, "newsletters")
PODCASTS_DIR = os.path.join(BASE_DIR, "podcasts")


def parse_frontmatter(content):
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith('---'):
        return {}, content
    end = content.find('\n---', 3)
    if end == -1:
        return {}, content
    yaml_str = content[3:end].strip()
    fm = {}
    for line in yaml_str.split('\n'):
        line = line.strip()
        if ':' in line:
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            fm[key] = val
    body = content[end+4:].strip()
    return fm, body


def clean_text(text):
    """Remove markdown formatting from text."""
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def is_lenny(speaker):
    """Check if speaker is Lenny."""
    s = speaker.strip().lower()
    return s in ['lenny', 'lenny rachitsky'] or s.startswith('lenny (')


def clean_author(author):
    """Clean up author name."""
    if not author:
        return 'Unknown'
    author = re.sub(r'[,\.\!\?\;:]+$', '', author).strip()
    author = re.sub(r'\*+', '', author).strip()
    author = re.sub(r'\s+', ' ', author).strip()
    if len(author) < 2:
        return 'Unknown'
    if len(author.split()) > 6:
        return 'Unknown'
    return author


def should_skip_title(title):
    """Return True if title is not a real book."""
    if not title or len(title) < 4:
        return True
    if len(title) > 130:
        return True

    lower = title.lower()

    # Skip if starts lowercase
    if title[0].islower():
        return True

    # Skip image/URL artifacts
    if any(x in lower for x in ['.png', '.jpg', '.gif', '.svg', '.jpeg', '.webp',
                                   'image from', 'http', 'www.', 'substack',
                                   'amazon.com', 'soundcloud', '.mp3']):
        return True

    # Skip obvious non-book items: milestone numbers
    if re.match(r'^\d[\d,]+$', title):
        return True
    # Skip things starting with numbers like "First 100", "Next 1,000"
    if re.match(r'^(?:First|Next|Last)\s+\d', title):
        return True

    # Skip navigation/UI elements
    skip_starts = [
        'Leave a comment', 'Subscribe', 'Share', 'Follow', 'Click here',
        'Read more', 'See more', 'Learn more', 'Sign up', 'Get started',
        'Loading', 'Posted', 'Published', 'Written', 'Edited',
        'Podcast', 'Newsletter', 'Episode', 'Issue', 'Vol.', 'Volume',
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December',
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
    ]
    for s in skip_starts:
        if title.startswith(s):
            return True

    # Skip very generic single words that are not known book titles
    generic_words = {
        'Yes', 'No', 'Not', 'So', 'Well', 'Just', 'Still', 'Also', 'Even',
        'Some', 'Many', 'Most', 'More', 'Less', 'Few', 'All', 'Any',
        'Here', 'There', 'Now', 'Then', 'Soon', 'Today', 'Yesterday',
        'Something', 'Nothing', 'Everything', 'Anything',
        'Someone', 'Anyone', 'Everyone', 'Nobody',
        'This', 'That', 'These', 'Those', 'Which', 'What', 'How', 'Why',
        'When', 'Where', 'Who', 'Whom', 'Whose',
        'Thank', 'Thanks', 'Please', 'Sorry', 'Hello', 'Goodbye',
        'Overview', 'Summary', 'Conclusion', 'Introduction', 'Background',
        'Context', 'Update', 'Version', 'Final', 'Draft', 'Note', 'Notes',
        'Example', 'Examples', 'Case', 'Cases', 'Study', 'Studies',
        'Part', 'Chapter', 'Section', 'Page', 'Slide',
        'Table', 'Figure', 'Chart', 'Graph', 'Image', 'Photo', 'Picture',
        'Link', 'Links', 'Reference', 'References', 'Source', 'Sources',
        'Product', 'Products', 'Company', 'Companies', 'Team', 'Teams',
        'People', 'Person', 'User', 'Users', 'Customer', 'Customers',
        'Market', 'Markets', 'Business', 'Businesses', 'Service', 'Services',
        'Platform', 'Platforms', 'App', 'Apps', 'Tool', 'Tools',
        'Feature', 'Features', 'Function', 'Functions', 'Option', 'Options',
        'Error', 'Errors', 'Bug', 'Bugs', 'Fix', 'Fixes', 'Issue', 'Issues',
        'Test', 'Tests', 'Testing', 'Result', 'Results', 'Data', 'Analysis',
        'Report', 'Reports', 'Research', 'Study', 'Findings',
        'Interview', 'Interviews', 'Conversation', 'Discussion',
        'Talk', 'Talks', 'Advice', 'Tips', 'Tricks', 'Hacks',
    }
    if title in generic_words:
        return True

    # Skip if it looks like a markdown heading artifact
    if title.startswith('#'):
        return True

    # Skip if it looks like a person's name only (no book-like structure)
    # Book titles usually have articles, prepositions, or multiple meaningful words
    # A name alone like "John Smith" isn't a book title
    # But single-word book titles like "Sapiens", "Educated" are fine

    return False


# Patterns to find book titles - ordered from most specific/reliable to least
TITLE_PATTERNS = [
    # [Book Title](amazon/goodreads/bookshop URL) - very reliable
    (r'\[([A-Z][^\]\n]{3,100})\]\(https?://(?:www\.)?(?:amazon\.com|goodreads\.com|bookshop\.org|shop\.app/products|books\.google\.com)[^\)]+\)',
     'linked_amazon_goodreads'),

    # "Title" by Author or "Title" by Author (curly quotes)
    (r'["“]([A-Z][^”"\n]{3,100})["”]\s+by\s+([A-Z][a-zA-Z\-\.\s]{2,50}?)(?=[,\.\n\(\[]|$)',
     'quoted_by_author'),

    # *Title* by Author
    (r'\*([A-Z][^*\n]{3,100})\*\s+by\s+([A-Z][a-zA-Z\-\.\s]{2,50}?)(?=[,\.\n\(\[]|$)',
     'italic_by_author'),

    # **Title** by Author
    (r'\*\*([A-Z][^*\n]{3,100})\*\*\s+by\s+([A-Z][a-zA-Z\-\.\s]{2,50}?)(?=[,\.\n\(\[]|$)',
     'bold_by_author'),

    # book called/titled/named "Title"
    (r'book\s+(?:called|titled|named)\s+["“]([A-Z][^”"\n]{3,100})["”]',
     'book_called_quoted'),

    # my/his/her/their/new book "Title" or my/his/her book called "Title"
    (r'(?:my|his|her|their|a|the|new|this)\s+book[,\s]+(?:called\s+|titled\s+)?["“]([A-Z][^”"\n]{3,100})["”]',
     'possessive_book'),

    # wrote/authored/published "Title" or book "Title"
    (r'(?:wrote|authored|published|released|written)\s+(?:a\s+)?book[,\s]+(?:called\s+|titled\s+)?["“]([A-Z][^”"\n]{3,100})["”]',
     'wrote_book'),

    # "Title", a book about / "Title" is a book
    (r'["“]([A-Z][^”"\n]{5,100})["”][,\s]+(?:a|the|is a|was a)\s+book',
     'title_is_a_book'),

    # read "Title" / recommend "Title" / loved "Title"
    (r'(?:read|reading|recommend(?:ed)?|loved|enjoyed|re-read|finished|started)\s+["“]([A-Z][^”"\n]{3,100})["”]',
     'read_title'),

    # **Read**: [Title](url) - Lenny's newsletter recommendation format
    (r'\*\*Read\*\*:\s+\[([A-Z][^\]\n]{3,100})\]\([^\)]+\)',
     'read_link_format'),

    # **"Title"** - bold quoted title
    (r'\*\*["“]([A-Z][^”"\n]{3,100})["”]\*\*',
     'bold_quoted_title'),

    # author of "Title"
    (r'author(?:ed)? of\s+["“]([A-Z][^”"\n]{3,100})["”]',
     'author_of'),

    # - **Title** by Author (list item)
    (r'^\s*[-•*]\s+\*\*([A-Z][^*\n]{3,100})\*\*\s+by\s+([A-Z][a-zA-Z\-\.\s]{2,50}?)(?=[,\.\n\(\[]|$)',
     'list_bold_by'),

    # [Title](url) where url doesn't have to be amazon/goodreads
    # but context suggests book (e.g. preceded by "book" or "read")
    (r'(?:book|read|recommend)[^\[]*\[([A-Z][^\]\n]{3,100})\]\(https?://[^\)]+\)',
     'context_linked'),

    # his/her book, Title (comma after "book")
    (r'(?:my|his|her|their|a|the|new|this)\s+book,\s+([A-Z][a-zA-Z0-9 \-:\'\.]{3,100}?)(?=[,\.\n\(]|$)',
     'book_comma_title'),

    # wrote a book called Title (unquoted)
    (r'(?:wrote|authored|published)\s+(?:a\s+)?book\s+(?:called|titled|named)\s+([A-Z][a-zA-Z0-9 \-:\'\.]{3,100}?)(?=[,\.\n\(]|$)',
     'wrote_book_unquoted'),
]


def find_book_mentions(body, doc_type, guest_name):
    """Find all book mentions. Returns list of book dicts."""
    results = []
    seen_titles = set()

    for pattern, kind in TITLE_PATTERNS:
        try:
            for m in re.finditer(pattern, body, re.MULTILINE | re.IGNORECASE):
                raw_title = m.group(1).strip()

                # Clean title
                title = raw_title.strip('"').strip('“').strip('”').strip('*').strip()

                if should_skip_title(title):
                    continue

                # Get author if second group exists
                try:
                    author = m.group(2).strip() if m.lastindex and m.lastindex >= 2 and m.group(2) else 'Unknown'
                    author = clean_author(author)
                except (IndexError, AttributeError):
                    author = 'Unknown'

                title_key = title.lower()[:60]
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                # Get context around the mention for quotes
                pos = m.start()
                ctx_start = max(0, pos - 700)
                ctx_end = min(len(body), pos + 700)
                ctx = body[ctx_start:ctx_end]

                lenny_q, guest_q = extract_quotes(ctx, title, doc_type, guest_name)

                results.append({
                    "book_title": title,
                    "book_author": author,
                    "lenny_quote": lenny_q,
                    "guest_quote": guest_q,
                })

        except Exception as e:
            # Skip pattern errors silently
            pass

    return results


def extract_quotes(ctx, book_title, doc_type, guest_name):
    """Extract Lenny and guest quotes from context window."""
    lenny_quote = ''
    guest_quote = ''

    book_lower = book_title.lower()[:20]

    if doc_type == 'podcast':
        speaker_seg_pattern = r'\*\*([^*\n]+)\*\*\s*(?:\(\d+:\d+:\d+\))?\s*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)'

        # First pass: find segments that directly mention the book
        for m in re.finditer(speaker_seg_pattern, ctx):
            speaker = m.group(1).strip()
            text = m.group(2).strip()

            if book_lower not in text.lower():
                continue

            clean = clean_text(text)[:600]

            if is_lenny(speaker) and not lenny_quote:
                lenny_quote = clean
            elif not is_lenny(speaker) and speaker and not guest_quote:
                guest_quote = clean

        # Second pass: if no direct quote, get nearest segment
        book_pos_in_ctx = ctx.lower().find(book_lower)
        if book_pos_in_ctx < 0:
            book_pos_in_ctx = len(ctx) // 2

        if not lenny_quote:
            lenny_pattern = r'\*\*Lenny\*\*\s*(?:\([^)]*\))?\s*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)'
            lenny_segs = [(m.start(), clean_text(m.group(1)).strip()[:600])
                          for m in re.finditer(lenny_pattern, ctx)]
            if lenny_segs:
                closest = min(lenny_segs, key=lambda x: abs(x[0] - book_pos_in_ctx))
                lenny_quote = closest[1]

        if not guest_quote and guest_name:
            # Try full guest name
            guest_pattern = rf'\*\*{re.escape(guest_name)}\*\*\s*(?:\([^)]*\))?\s*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)'
            guest_segs = [(m.start(), clean_text(m.group(1)).strip()[:600])
                          for m in re.finditer(guest_pattern, ctx)]
            if not guest_segs:
                # Try first name
                guest_first = guest_name.split()[0]
                guest_pattern2 = rf'\*\*{re.escape(guest_first)}[^*]*\*\*\s*(?:\([^)]*\))?\s*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)'
                guest_segs = [(m.start(), clean_text(m.group(1)).strip()[:600])
                              for m in re.finditer(guest_pattern2, ctx)]
            if guest_segs:
                closest = min(guest_segs, key=lambda x: abs(x[0] - book_pos_in_ctx))
                guest_quote = closest[1]

    else:
        # Newsletter - Lenny is the author
        book_pos = ctx.lower().find(book_lower)
        if book_pos >= 0:
            s = max(0, book_pos - 200)
            e = min(len(ctx), book_pos + 400)
            lenny_quote = clean_text(ctx[s:e]).strip()[:600]
        else:
            lenny_quote = clean_text(ctx[:400]).strip()[:600]

    return lenny_quote[:700], guest_quote[:700]


def process_all_files():
    """Process all markdown files and return book mentions."""
    all_results = []
    errors = []

    for dir_path in [NEWSLETTERS_DIR, PODCASTS_DIR]:
        dir_name = os.path.basename(dir_path)
        files = sorted([f for f in os.listdir(dir_path) if f.endswith('.md')])
        print(f"Processing {len(files)} files in {dir_name}...", flush=True)

        for filename in files:
            filepath = os.path.join(dir_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                fm, body = parse_frontmatter(content)

                doc_type = fm.get('type', 'newsletter')
                guest_name = fm.get('guest', '')
                source_title = fm.get('title', '')
                source_subtitle = fm.get('subtitle', '') or ''
                date_val = fm.get('date', '')
                post_url = fm.get('post_url', '')
                youtube_url = fm.get('youtube_url', '') or ''

                if len(body) < 200:
                    continue

                books = find_book_mentions(body, doc_type, guest_name)

                for book in books:
                    entry = {
                        "book_title": book['book_title'],
                        "book_author": book['book_author'],
                        "lenny_quote": book['lenny_quote'],
                        "guest_quote": book['guest_quote'],
                        "source_title": source_title,
                        "source_subtitle": source_subtitle,
                        "guest": guest_name,
                        "date": str(date_val),
                        "type": doc_type,
                        "post_url": str(post_url),
                        "youtube_url": str(youtube_url),
                    }
                    all_results.append(entry)

            except Exception as e:
                errors.append((filename, str(e)))

    if errors:
        print(f"\nErrors in {len(errors)} files:")
        for fn, err in errors[:10]:
            print(f"  {fn}: {err}")

    return all_results


if __name__ == '__main__':
    results = process_all_files()

    print(f"\nTotal book mentions found: {len(results)}")

    by_type = {}
    for r in results:
        t = r['type']
        by_type[t] = by_type.get(t, 0) + 1
    print(f"By type: {by_type}")

    print("\nSample entries (first 10):")
    for e in results[:10]:
        print(f"  [{e['type']}] '{e['book_title']}' by {e['book_author']}")
        print(f"    Source: {e['source_title'][:70]}")
        if e['lenny_quote']:
            print(f"    Lenny: {e['lenny_quote'][:80]}...")
        if e['guest_quote']:
            print(f"    Guest: {e['guest_quote'][:80]}...")

    output_path = r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData\books_extracted_v3.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to {output_path}")
