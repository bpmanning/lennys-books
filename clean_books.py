"""
Post-process books_raw.json → clean titles, fix authors, remove false positives,
add known guest-book entries, deduplicate, write books_clean.json + books_table.html
"""

import re, json, os, sys
from pathlib import Path
from datetime import date

# Force UTF-8 output so names with non-ASCII chars (e.g. Rúnar Bjarnason) print fine
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE  = Path(r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData")
CLEAN = BASE / "books_clean.json"
HTML  = BASE / "books_table.html"

# Allow enrich_books.py (or the user) to point at books_candidates.json
_raw_override = os.environ.get("LENNY_RAW_SOURCE")
if _raw_override:
    RAW = Path(_raw_override)
else:
    cands = BASE / "books_candidates.json"
    RAW   = cands if cands.exists() else BASE / "books_raw.json"

raw = json.loads(RAW.read_text(encoding="utf-8"))
print(f"Raw records ({RAW.name}): {len(raw)}")

# ── helpers ─────────────────────────────────────────────────────────────────
def strip_md(s):
    return re.sub(r'[\*_]', '', s).strip(" \t\r\n\"',;.")

def clean_title(raw_t):
    """Strip preamble sentence context from a raw matched title."""
    t = strip_md(raw_t)
    # After a known trigger word/phrase → take what follows (up to 9 words, no sent-break)
    m = re.search(
        r'(?i)\b(?:called|titled|named|is|was|love|loved|like|liked|enjoy|enjoyed|'
        r'suggest(?:ed)?|recommend(?:ed|ing)?|read|reading|try|tried|finish(?:ed)?|'
        r'start(?:ed)?|know|check out|pick up|picked up)\s+'
        r'([A-Z\'"''][^.!?\n]{2,75})',
        t
    )
    if m:
        c = m.group(1).strip(" ,;\"'")
        if 1 <= len(c.split()) <= 9:
            return c
    # After sentence boundaries
    for sep in ['. ', '! ', '? ', '; ', ', ']:
        parts = t.split(sep)
        for part in reversed(parts):
            p = part.strip()
            if p and p[0].isupper() and 1 <= len(p.split()) <= 9 and not re.search(r'[.?!]\s', p):
                return p
    return t

def clean_author(raw_a):
    """Remove trailing sentence fragments but preserve name initials like 'F. Scott', 'A.G. Lafley'."""
    a = strip_md(raw_a)
    # Remove trailing newlines and anything after them
    a = re.sub(r'\s*\n.*$', '', a, flags=re.DOTALL)
    # Find the first ". " in the string.
    # If the word that ends before the period has more than 2 non-dot chars,
    # it's a full word (e.g. "Meadows") → treat the period as a sentence break and strip.
    # If the word is a short initial or abbreviation (e.g. "F", "M", "A.G"),
    # it's part of the name → keep going.
    m = re.search(r'\.\s+', a)
    if m:
        before_dot = a[:m.start()]
        last_word  = before_dot.split()[-1] if before_dot.split() else ''
        non_dot    = re.sub(r'\.', '', last_word)   # strip embedded dots (e.g. "A.G" → "AG")
        if len(non_dot) > 2:   # full word, not an initial/abbreviation → strip
            a = before_dot
    a = a.strip(" ,;.\n")
    return a

# ── title / author manual overrides ─────────────────────────────────────────
# None = drop record entirely
TITLE_FIX = {
    # Needs title extracted from sentence
    "And I also love the Culture series":                    "The Culture Series",
    "And I love Designing Your Life":                        "Designing Your Life",
    "And then Better Business Writing":                      "Better Business Writing",
    "And then God Saved Texas":                              "God Saved Texas",
    "And then in a super different direction, Power Broker": "The Power Broker",
    "And then more on the psychology side Mindset":          "Mindset",
    "And then Powerful":                                     "Powerful",
    "And then second, Myth of Sisyphus":                     "The Myth of Sisyphus",
    "And then Start At The End":                             "Start at the End",
    "And then the last is called Die with Zero":             "Die with Zero",
    "And then the other one is a book":                      None,  # title unknown from context
    "And and more recently":                                 None,
    "And more recently":                                     None,
    "And so":                                                None,
    "And so some of my favorite books are":                  None,
    "And then anything":                                     None,
    "And then Le Ton beau de Marot":                         "Le Ton beau de Marot",
    "And then third, Le Ton beau de Marot":                  "Le Ton beau de Marot",
    "And he had me read this book called Range":             "Range",
    "And he said, \"Go to the beach.\" We were":             None,
    "And it was taught":                                     None,
    "Another really influential book was Only the Paranoid Survive": "Only the Paranoid Survive",
    "Another recent marketing book is Alchemy":              "Alchemy",
    "As a marketer, Storyworthy":                            "Storyworthy",
    "At least it did for me":                                None,
    "Couple that come to mind Team of Teams":                "Team of Teams",
    "Clay Christensen's books":                              None,
    "Dune, Frank Herbert or Foundation":                     None,  # two books mixed
    "Elements of Typographic Style":                         "The Elements of Typographic Style",
    "Europe":                                               None,  # incomplete; actual title lost
    "Failing Forward":                                      "Failing Forward",
    "For fun, The Wool Trilogy":                             "The Wool Trilogy",
    "For those who don't know, it was written":              None,
    "For writing, On Writing Well":                          "On Writing Well",
    "How They Tell Me the World Ends":                       "This Is How They Tell Me the World Ends",
    "I actually have always really liked The Great Gatsby":  "The Great Gatsby",
    "I actually read a post":                                None,
    "I did this and no one cared":                           None,
    "I had advised a company which was acquired":            None,
    "I imagine has come up before in your podcast":          None,
    "I like to ask":                                         None,
    "I love a book called Name of the Wind":                 "The Name of the Wind",
    "I love any book":                                       None,
    "I love Getting Things Done":                            "Getting Things Done",
    "I love High Output Management":                         "High Output Management",
    "I love so much":                                        None,
    "I love the Design Sprint":                              None,
    "I love Thinking in Systems":                            "Thinking in Systems",
    "I now have on my desk":                                 None,
    "I often reference the book":                            None,
    "I read this great book, Range":                         "Range",
    "I read, recommended actually":                          None,
    "I really like actually is Never Split The Difference":  "Never Split the Difference",
    "I really like":                                         None,
    "I recently read a business book":                       None,
    "I recommend almost anything":                           None,
    "I recommend to folks":                                  None,
    "I remember one of them":                                None,
    "I think":                                               None,
    "I think for product folks is a classic one":            None,
    "I think I got introduced to you":                       None,
    "I think it's":                                          None,
    "I think it's a very interesting book about transitions": None,
    "I think Pachinko":                                      "Pachinko",
    "I think Radical Candor":                                "Radical Candor",
    "I think that Orlando":                                  "Orlando",
    "I was like":                                            None,
    "I would recommend The Laws of Human Nature":            "The Laws of Human Nature",
    "I would say is End of Average":                         "The End of Average",
    "I'm no longer paid":                                    None,
    "I've been buying products":                             None,
    "I've met":                                              None,
    "I've read a lot of them":                               None,
    "I've read more than any other book":                    "How to Win Friends and Influence People",
    "I've really enjoyed Build":                             "Build",
    "I was inspired actually":                               None,
    "inspired actually":                                     None,
    "It is we're going to grow our revenue":                 None,
    "It was recommended to me":                              None,
    "It Was the Worst of Sentences":                         "It Was the Best of Sentences, It Was the Worst of Sentences",
    "It was written":                                        None,
    "It's 76 pages long, co-authored":                       None,
    "It's a book":                                           None,
    "It's a book called Computing Taste":                    "Computing Taste",
    "It's a book called Untethered Soul":                    "Untethered Soul",
    "It's a great book":                                     None,
    "It's a short read, but Lessons From History":           "The Lessons of History",
    "It's about the Wright Brothers":                        "The Wright Brothers",
    "It's The New Product Development Game, published":      "The New New Product Development Game",
    "It's written":                                          None,
    "Lex Fridman":                                           None,
    "Magic Box Paradigm":                                    "Magic Box Paradigm",
    "Management Science":                                    None,   # false positive: Alisa Cohn meant Amazon's management approach, not a book
    "Maybe outside of tech, Waking Up is a book":            "Waking Up",
    "My favorite is a quote":                                None,
    "My go-to book recommendation for other PMs is inspired":"Inspired",
    "Nathan Seward seven years ago called The Big Leap":     "The Big Leap",
    "Nudge":                                                 "Nudge",
    "On a personal basis, recent books would be Seveneves":  "Seveneves",
    "On the business book standpoint":                       None,
    "One is the series published":                           None,
    "One is, I love this, When Breath Becomes Air":          "When Breath Becomes Air",
    "One, a recent Pulitzer Prize winner, Demon Copperhead": "Demon Copperhead",
    "One recently, Great":                                   None,
    "Persuasion":                                            "Influence",
    "Post-product market fit, there's a book called 7 Powers": "7 Powers",
    "Right now, I'm actually rereading Giovanni's Room":     "Giovanni's Room",
    "Second book is Thinking, Fast and Slow":                "Thinking, Fast and Slow",
    "Shoe Dog, which is written":                            "Shoe Dog",
    "Slack":                                                 None,
    "So Code":                                               "Code",
    "So I was introduced to the guys":                       None,
    "So in fiction, I love The Fountainhead":                "The Fountainhead",
    "So Obviously Awesome":                                  "Obviously Awesome",
    "So one book was recommended to me":                     None,
    "So probably through the years in that category":        None,
    "So that's":                                             None,
    "So there's a book called Small Data":                   "Small Data",
    "So there's a great book":                               None,
    "So this is awesome":                                    None,
    "So when first we were approached":                      None,
    "So yeah, having said that, the Master in Margarita":    "The Master and Margarita",
    "So, I like Playing to Win":                             "Playing to Win",
    "So, the software company was eventually acquired":      None,
    "Spafford":                                              None,
    "Stories of Your Life and Others":                       "Stories of Your Life and Others",
    "Story of Real Life":                                    "Story of Your Life",
    "The books that I recommend the most":                   None,
    "The first book":                                        None,
    "The first book is Constellations":                      "Consolations",
    "The first one I mentioned before, Replacing Guilt":     "Replacing Guilt",
    "The Flywheel from Good to Great":                       "Good to Great",
    "The other book":                                        None,
    "The other one is pretty much anything":                 None,
    "The other one that I love is a book":                   None,
    "The second is a fiction book":                          None,
    "The second one is called When Things Fall Apart":       "When Things Fall Apart",
    "Then a book":                                           None,
    "There was a book written":                              None,
    "There was XP, extreme programming, that was started":   None,
    "There's a book":                                        None,
    "There's Technology Strategy Patterns":                  "Technology Strategy Patterns",
    "Time in the Art of Living":                             "Time and the Art of Living",   # Bob Baxley transcript typo; correct is "Time and the Art of Living" by Robert Grudin
    "There's this book called Alchemy":                      "Alchemy",
    "There's this book called Invisible Cities":             "Invisible Cities",
    "They set out to surround themselves":                   None,
    "This book was given to me":                             None,
    "This Is How They Tell Me the World Ends":               "This Is How They Tell Me the World Ends",
    "This one is a very classic one, Machine Learning":      "Machine Learning",
    "This one youlikely heard of, it's Influence":           "Influence",
    "Value Flywheel effect":                                 "The Value Flywheel Effect",
    "Well":                                                  None,
    "Well, first, I love the book, Quiet":                   "Quiet",
    "Yeah":                                                  None,
    "Yes":                                                   None,
    "You Win":                                               None,
    "Your list is reminding me of a new book":               None,
    "Again":                                                 None,
    "AI":                                                    None,
    "Anything":                                              None,
    "British":                                               None,
    "Hard":                                                  None,
    "Great":                                                 None,
    "Totally":                                               None,
    "A Chinese sci-fi movie, \"The Wandering Earth 2,\" written": "The Wandering Earth",
    # Author fragments as titles
    "Thinking In Systems":                                   "Thinking in Systems",
    "Creativity Inc":                                        "Creativity, Inc.",
    "Selling the Dream":                                     "Selling the Dream",
    "Consolidating (David Whyte)":                           "Consolations",

    # ── Person names OL matched to biographies (not what guests meant) ─────────
    "Alex Honnold":                                          None,
    "Anthony Horowitz":                                      None,
    "Bill Gates":                                            None,
    "Byron Sharp":                                           None,
    "Christopher Alexander":                                 None,
    "James Spader":                                          None,
    "Shonda Rhimes":                                         None,

    # ── TV shows / films / anime (not books) ─────────────────────────────────
    "Alien Romulus":                                         None,
    "Cosmos on Netflix":                                     None,
    "Doctor Foster on Netflix":                              None,
    "Emily in Paris on Netflix":                             None,
    "Extraordinary Attorney Woo":                            None,
    "John Wick 4":                                           None,
    "Jujutsu Kaisen":                                        None,
    "KPop Demon Hunters":                                    None,
    "Last Dance":                                            None,
    "Last of Us":                                            None,
    "Mythic Quest":                                          None,
    "Mythic Quests on Apple TV":                             None,
    "New Amsterdam":                                         None,
    "Silicon Valley":                                        None,

    # ── Transcript fragments / artifacts ─────────────────────────────────────
    "And Alias":                                             None,
    "But B":                                                 None,
    "Ethical Cult Building":                                 None,
    "Geoffrey Moore wrote":                                  None,
    "I [inaudible 01:17:02":                                 None,
    "I find the Tesla":                                      None,
    "I think Stripe":                                        None,
    "I'm in":                                                None,

    # ── Partial / garbled titles → correct title ─────────────────────────────
    "Search for Meaning":                                    "Man's Search for Meaning",
    "Man's Search For Meaning because at":                   "Man's Search for Meaning",
    "Viktor Frankl's Man's Search For Meaning because at":   "Man's Search for Meaning",
    "Girdle Escher Bach":                                    "Gödel, Escher, Bach",

    # ── Products / apps / services (not books) ───────────────────────────────
    "Alive OS":                                              None,
    "Suzy Batiz course called Alive OS":                     None,   # raw title in candidates
    "Aura Frames":                                           None,
    "Bison Trails":                                          None,
    "Boost Mobile put out on YouTube":                       None,
    "Looker Studio":                                         None,
    "Magic Mind":                                            None,
    "Manta Sleep":                                           None,
    "Nara Baby":                                             None,
    "Pack Gear Hanging Suitcase":                            None,
    "Stripe Press":                                          None,
    "Thrive Stack":                                          None,
    "World Labs":                                            None,

    # ── Podcasts / shows / courses (not books) ───────────────────────────────
    "Hundred Foot Wave where":                               None,
    "I'm a Virgo":                                           None,
    "Last One of Us":                                        None,
    "Movie Club":                                            None,
    "Nervous System Mastery course":                         None,
    "Netflix's Breakpoint because":                          None,
    "Rob Walling's podcast":                                 None,
    "Scaling Entrepreneurial Ventures":                      None,
    "The Ezra Klein Show":                                   None,
    "The Martyr Made Podcast":                               None,
    "The West Wing Weekly":                                  None,
    "Top Gear":                                              None,
    "Top Gun":                                               None,
    "Veep on HBO":                                           None,

    # ── More person names extracted as titles ────────────────────────────────
    "Adam Grant's":                                          None,
    "Ben Horowitz's book":                                   None,
    "Brandon Sanderson's books":                             None,
    "Darryl Cooper":                                         None,
    "Helen Rosner":                                          None,
    "Ian Banks":                                             None,
    "Jeff Bezos":                                            None,
    "Jeremy Clarkson":                                       None,
    "Kim Scott's writing on":                                None,
    "Nickey Skarstad":                                       None,
    "Owen Van Natta":                                        None,
    "Professor Pfeffer":                                     None,
    "Roald Dahl":                                            None,
    "Taylor Francis":                                        None,

    # ── More transcript fragments / artifacts ────────────────────────────────
    "Club at Rippling":                                      None,
    "David shoots at Goliath":                               None,
    "Dune II as well":                                       None,
    "Hedonic Engineering":                                   None,
    "I said before, The 15 Commitments of Conscious Leaders": None,
    "I think The Splendid":                                  None,
    "I've been to in Europe":                                None,
    "Investor Service":                                      None,
    "Las Azules":                                            None,
    "Lex Fridman can":                                       None,
    "Martin Eriksson's Decision Stack":                      None,
    "Marty Supreme":                                         None,
    "Neuro Sim":                                             None,
    "Oliver Sacks died":                                     None,
    "on Instagram":                                          None,
    "I'm reading on Instagram":                              None,   # raw title in candidates
    "Andrew Roberts latest book on Winston Churchill":       None,   # fragment (not a book title)
    "Dreaming Spanish":                                      None,   # language-learning YouTube channel
    "Slow Art Day":                                          None,
    "Solution from Clayton Christensen":                     None,
    "Steve Jobs biography":                                  None,
    "Tinder 2":                                              None,
    "Toni Morrison wrote":                                   None,
    "Versus LinkedIn":                                       None,
    "We Crushed":                                            None,
    "West Wing":                                             None,

    # ── Garbled / partial titles → correct title (batch 2) ───────────────────
    "Ate the Whale":                                         "The Fish That Ate the Whale",
    "Big Short":                                             "The Big Short",
    "Deepen Your Learning":                                  None,   # phrase, not a book title
    "A Corporate Fool's Guide to Surviving with Grace, I":   "Orbiting the Giant Hairball",
    "Guide to Surviving with Grace":                         "Orbiting the Giant Hairball",
    "I recommend a lot is Range: Why Generalists Triumph":   "Range",
    "All The Light We Cannot See about World War":           "All the Light We Cannot See",
    "Andy Grove's book Only the Paranoid Survive":           "Only the Paranoid Survive",
    "Anna Akhmatova's You Will":                             "You Will Hear Thunder",
    "Anything, finding Intangibles or Finding the Value of Intangibles": "How to Measure Anything",
    "I love called Hard Facts":                              "Hard Facts, Dangerous Half-Truths and Total Nonsense",
    "Elad Gil's High Growth Handbook":                       "High Growth Handbook",
    "From the nonfiction world, How Will You Measure Your":  "How Will You Measure Your Life",
    "From Third to First World":                             "From Third World to First",
    "From Animals to Gods":                                  "Sapiens",
    "Misbehaving: The Makings of Behavioral Economics":      "Misbehaving: The Making of Behavioral Economics",
    "Not How Good You Are":                                  "It's Not How Good You Are",
    "Not How Good You":                                      "It's Not How Good You Are",
    "The Almanack Of Naval":                                 "The Almanack of Naval Ravikant",
    "Was the Best of Sentences":                             "It Was the Best of Sentences, It Was the Worst of Sentences",
    "Was the Worst of Sentences":                            "It Was the Best of Sentences, It Was the Worst of Sentences",
    "The Contrarians Guide to Leadership awesome book":      "The Contrarian's Guide to Leadership",
    "The Elements of Thinking in Systems":                   "Thinking in Systems",
    "The New Product Development Game":                      "The New New Product Development Game",
    "Katherine Morgan Schafler called The Perfectionist's Guide to Losing": "The Perfectionist's Guide to Losing Control",
    "The Score Takes Care of":                               "The Score Takes Care of Itself",
    "Thinking Slow":                                         "Thinking, Fast and Slow",
    "Timeless Way of Building":                              "The Timeless Way of Building",
    "I've been recommending What I Talk About When I":       "What I Talk About When I Talk About Running",
    "Wisdom of Insecurity":                                  "The Wisdom of Insecurity",
    "Start With Why":                                        "Start With Why",   # bypass clean_title() stripping "Start" as trigger word
    "Stumbling Upon Happiness":                              "Stumbling on Happiness",
    "Robert Frank as an author in Darwin Economy":           "The Darwin Economy",
    # ── clean_title() (?i) bug strips correctly capitalised word ─────────────
    "Dare to Lead Like a Girl":                              "Dare to Lead Like a Girl",  # "Like" trigger + (?i) eats "a Girl"
    # ── Partial title renames (batch 3) ──────────────────────────────────────
    "Guide to Losing Control":                               "The Perfectionist's Guide to Losing Control",
    "Will Never Work":                                       "That Will Never Work",
    "Top Five Regrets of the Dying":                         "The Top Five Regrets of the Dying",
    "A book called The Five Regrets of the Dying":           "The Top Five Regrets of the Dying",
    "The Five Regrets of the Dying":                         "The Top Five Regrets of the Dying",
}

# Author corrections (applied AFTER clean_author, keyed by cleaned author)
AUTHOR_FIX = {
    "Mistry":                     "Rohinton Mistry",
    "Stross":                     "Charles Stross",
    "Thaler":                     "Richard Thaler",
    "Bessal":                     "Bessel van der Kolk",
    "Bessel":                     "Bessel van der Kolk",
    "Cialdini":                   "Robert Cialdini",
    "Clayton Christiansen":       "Clayton Christensen",
    "Camus":                      "Albert Camus",
    "Goldratt":                   "Eliyahu M. Goldratt",
    "Murakami":                   "Haruki Murakami",
    "Dobelli":                    "Rolf Dobelli",
    "Lafley":                     "A.G. Lafley",
    "Christensen":                "Clayton Christensen",
    "Christiane":                 None,
    "Christiansen":               "Clayton Christensen",
    "Hubbard":                    "Douglas Hubbard",
    "Russ":                       None,
    "Anthony":                    "Anthony de Mello",
    "Peter Zion":                 "Peter Zeihan",
    "Mitchell":                   "Tom M. Mitchell",
    "David Deutch":               "David Deutsch",
    "David White":                "David Whyte",
    "Goodwin":                    "Doris Kearns Goodwin",
    "Doris Goodwin":              "Doris Kearns Goodwin",
    "Liu Cixin":                  "Cixin Liu",
    "JL Collins":                               "JL Collins",
    "Robert Bringhurst, Robert Bringhurst":     "Robert Bringhurst",  # OL duplicate in author_name list
    "Ted Chang":                                "Ted Chiang",
    "Anderson":                   "David Anderson, Mark McCann & Michael O'Reilly",
    "June-":                      "June Casagrande",
    "Kim":                        "Gene Kim, Kevin Behr & George Spafford",
    "Tony Fidel":                 "Tony Fadell",
    "F":                          "F. Scott Fitzgerald",
    "I":                          None,
    "Me":                         None,
    "Chip":                       None,
    "Rawls":                      "John Rawls",
    "Chris Dixon":                None,
    "Chris Dixon's":              None,
    "Claude Shannon":             None,
    "Bryan Schreier":             None,
    "Shashir":                    None,
    "Jenny Yarden":               None,
    "Harry":                      None,
    "Philip":                     None,
    "Jerzy Gregorek":             None,
    "Goldsmith Marshall":         "Sally Helgesen and Marshall Goldsmith",
    "Horowitz Anthony":           "Anthony Horowitz",
    "Patti Smith, Patti Smith":   "Patti Smith",
    "Walsh, Bill":                "Bill Walsh",
    "Ian Banks":                  "Iain Banks",
}

# Per-(book, cleaned_author) remaps: avoids clobbering other books by the same author.
# Applied AFTER AUTHOR_FIX.  Key = (book_title_after_fix, cleaned_author_after_AUTHOR_FIX)
SPECIFIC_BOOK_AUTHOR_FIX = {
    # "Children of Time" was extracted with "Stephen King" as author (wrong context)
    ("Children of Time", "Stephen King"):            "Adrian Tchaikovsky",
    # "The Death of Ivan Ilyich" was mentioned by George Saunders; real author is Tolstoy
    ("The Death of Ivan Ilyich", "George Saunders"): "Leo Tolstoy",
    # "Time and the Art of Living" — OL couldn't match (ol_score=0); real author is Robert Grudin
    # (Bob Baxley said "Time in the Art of Living by Robert Gruden" — both title and author are typos)
    ("Time and the Art of Living", ""):                      "Robert Grudin",
    # "Search for Meaning" is a partial title; OL matched Webb's "Gifted Adults" book instead of Frankl
    ("Man's Search for Meaning", "James T. Webb"):           "Viktor Frankl",
    ("Man's Search for Meaning", ""):                        "Viktor Frankl",
    # OL matched a different "Positioning" book for the Ries & Trout classic
    ("Positioning: The Battle for Your Mind", "Luke Swift"):  "Al Ries and Jack Trout",
    # OL matched Piers Anthony (sci-fi) instead of Tim Harford's 2020 nonfiction
    ("Cautionary Tales", "Piers Anthony"):                   "Tim Harford",
    # OL matched the Epictetus translation; guest (Ben Horowitz) meant Shaka Senghor
    ("How to Be Free", "Epictetus, Anthony Long"):           "Shaka Senghor",
    # "Girdle Escher Bach" is a transcript mishearing of "Gödel, Escher, Bach"
    ("Gödel, Escher, Bach", ""):                            "Douglas Hofstadter",
    # OL couldn't match author for these; correct authors added manually
    ("All the Light We Cannot See", ""):                    "Anthony Doerr",
    ("Misbehaving: The Making of Behavioral Economics", ""): "Richard Thaler",
    ("Sapiens", ""):                                        "Yuval Noah Harari",
    ("Stumbling on Happiness", ""):                         "Daniel Gilbert",
    ("The Darwin Economy", ""):                             "Robert Frank",
    # OL wrong match: "The Goal" fetched a romance novel by Elle Kennedy
    ("The Goal", "Elle Kennedy"):                           "Eliyahu M. Goldratt",
    # OL wrong match: "The Good Nurse" fetched a different book
    ("The Good Nurse", "Vincent Courtenay"):                "Charles Graeber",
    # OL wrong match: "Innovator's Dilemma" variant fetched supply-chain book
    ("Innovators Dilemma", "Kate Vitasek, Jeanne Kling"):   "Clayton Christensen",
    # Blank authors for well-known books where OL didn't match
    ("Only the Paranoid Survive", ""):                       "Andy Grove",
    ("The Almanack of Naval Ravikant", ""):                  "Eric Jorgenson",
    ("The Contrarian's Guide to Leadership", ""):            "Steven Sample",
    ("The Perfectionist's Guide to Losing Control", ""):     "Katherine Morgan Schafler",
    ("Hard Facts, Dangerous Half-Truths and Total Nonsense", ""): "Jeffrey Pfeffer and Robert Sutton",
    ("You Will Hear Thunder", ""):                           "Anna Akhmatova",
    ("That Will Never Work", ""):                            "Marc Randolph",
    # OL fetched translator credit instead of the author
    ("The Big Short", "Michael Lewis, Francisco José Ramos Mena"): "Michael Lewis",
    # OL matched a different book; real author is Rich Cohen
    ("The Fish That Ate the Whale", "Timea Thompson"):       "Rich Cohen",
    # Additional blank-author fills for well-known books OL didn't match
    ("Alice in Wonderland", ""):                             "Lewis Carroll",
    ("From Third World to First", ""):                       "Lee Kuan Yew",
    ("High Growth Handbook", ""):                            "Elad Gil",
    ("Kafka on the Shore", ""):                              "Haruki Murakami",
    ("Thinking, Fast and Slow", ""):                         "Daniel Kahneman",
    ("The Rigor of Angels", ""):                             "William Egginton",
}

# ── Manual guest-book additions (episodes where the guest IS the author) ─────
# Extracted from known podcast context where Pass B missed the "by Author" form
MANUAL_ADDITIONS = [
    {
        "book": "The Lean Startup",
        "author": "Eric Ries",
        "quote": '**Lenny Rachitsky** (00:00:43):\nThis new book, Incorruptible, is about helping you protect what you\'ve built. What is it that you need protection from?\n\n**Eric Ries** (00:00:07):\n... all kinds of famous companies. The thing that destroyed them was not competition. Their very success became a liability.',
        "source": "guest_book",
        "title": "How to build a company that withstands any era | Eric Ries, Lean Startup author",
        "subtitle": "",
        "guest": "Eric Ries",
        "date": "2026-05-10",
        "type": "podcast",
        "post_url": "https://www.lennysnewsletter.com/p/how-to-build-a-company-that-withstands",
        "youtube_url": "",
    },
    {
        "book": "Incorruptible",
        "author": "Eric Ries",
        "quote": '**Lenny Rachitsky** (01:37:32):\nIf any of this is at all interesting to you ... buy Eric\'s book, Incorruptible, is there a website to look at?\n\n**Eric Ries** (01:37:42):\nYes, of course you can find it anywhere books are sold. incorruptible.co.',
        "source": "guest_book",
        "title": "How to build a company that withstands any era | Eric Ries, Lean Startup author",
        "subtitle": "",
        "guest": "Eric Ries",
        "date": "2026-05-10",
        "type": "podcast",
        "post_url": "https://www.lennysnewsletter.com/p/how-to-build-a-company-that-withstands",
        "youtube_url": "",
    },
    {
        "book": "Radical Candor",
        "author": "Kim Scott",
        "quote": '**Lenny** (01:19:54):\nKim, I know you have to run. Two final questions. Where can folks find you … Kim Scott, thank you so much for being here.\n\n**Kim Scott** (01:25:18):\nRadicalcandor.com is our website.',
        "source": "guest_book",
        "title": "Radical Candor — Being a Kickass Boss Without Losing Your Humanity | Kim Scott",
        "subtitle": "",
        "guest": "Kim Scott",
        "date": "2023-12-10",
        "type": "podcast",
        "post_url": "",
        "youtube_url": "",
    },
    {
        "book": "Scaling People",
        "author": "Claire Hughes Johnson",
        "quote": '**Lenny** (01:19:41):\nAnyone listening, you got to buy this book. Like I\'ve said at the beginning, if you like my newsletter, it\'s exactly my newsletter, but as a book about operations.\n\n**Claire Hughes Johnson** (01:19:54):\nThank you. Scaling People.',
        "source": "guest_book",
        "title": "Operating Well — What I Learned at Stripe | Claire Hughes Johnson",
        "subtitle": "",
        "guest": "Claire Hughes Johnson",
        "date": "2023-01-12",
        "type": "podcast",
        "post_url": "",
        "youtube_url": "",
    },
    # ── Missed by extractor ((?i) scope bug / no author spoken) ──────────────
    {
        "book": "Designing Your Life",
        "author": "Bill Burnett and Dave Evans",
        "quote": "**Lenny** (01:11:17):\nWhat are two or three books that you've recommended most to other people?\n\n**Ada Chen Rekhi** (01:11:43):\nOh, yeah. It's a great book. Yeah. The next book that I also recommend is a book called Designing Your Life, and it's out of the Stanford Design School. And it's by, let me look, Bill Burnett and Dave Evans. They're two Stanford D School professors, and what they're doing is they're applying design principles to life design.",
        "source": "lightning_round",
        "title": "How to make better decisions and build a joyful career | Ada Chen Rekhi (Notejoy, LinkedIn, SurveyMonkey)",
        "subtitle": "",
        "guest": "Ada Chen Rekhi",
        "date": "2023-04-16",
        "type": "podcast",
        "post_url": "",
        "youtube_url": "https://www.youtube.com/watch?v=N64vIY2nJQo",
        "file": "podcasts/ada-chen-rekhi.md",
    },
    {
        "book": "Functional Programming in Scala",
        "author": "Paul Chiusano and Rúnar Bjarnason",
        "quote": "**Lenny** (01:29:59):\nFirst question, what are two or three books that you find yourself recommending most to other people?\n\n**Boris Cherny** (01:30:07):\nI'm a big reader. I would start with a technical book. It is Functional Programming in Scala. This is the single best technical book I have ever read. It's very weird, because you're probably not going to use Scala. And I don't know how much this matters in the future now, but there's this just elegance to functional programming and thinking in types, and this is just the way that I code.",
        "source": "lightning_round",
        "title": "Boris Cherny",
        "subtitle": "",
        "guest": "Boris Cherny",
        "date": "2026-02-19",
        "type": "podcast",
        "post_url": "",
        "youtube_url": "",
        "file": "podcasts/boris-cherny.md",
    },
    {
        "book": "Radical Candor",
        "author": "Kim Scott",
        "quote": "**Lenny** (01:03:54):\nHere we go. First question, are there two or three books that you find yourself most recommending to other people?\n\n**Alisa Cohn** (01:03:57):\nSo we already talked about Kim Scott, the wonderful, amazing Kim Scott and her book, Radical Candor, is one I recommend a lot to people. It's fantastic.",
        "source": "lightning_round",
        "title": "Scripts for difficult conversations: Giving hard feedback, navigating defensiveness, the three questions you should end every meeting with, more | Alisa Cohn (executive coach)",
        "subtitle": "",
        "guest": "Alisa Cohn",
        "date": "2025-01-05",
        "type": "podcast",
        "post_url": "",
        "youtube_url": "https://www.youtube.com/watch?v=bvF0ZM8DjuI",
        "file": "podcasts/alisa-cohn.md",
    },
    {
        "book": "Working Backwards",
        "author": "Colin Bryar and Bill Carr",
        "quote": "**Alisa Cohn** (01:03:57):\nWorking Backwards by gosh, Colin Bryar and Bill something, is about sort of the Amazon way of working backwards from the customer. Super geeky and tactical. I love it. I slurp it up like Harry Potter. It's so good. And I definitely recommend to my clients about Amazon's Management Science.",
        "source": "lightning_round",
        "title": "Scripts for difficult conversations: Giving hard feedback, navigating defensiveness, the three questions you should end every meeting with, more | Alisa Cohn (executive coach)",
        "subtitle": "",
        "guest": "Alisa Cohn",
        "date": "2025-01-05",
        "type": "podcast",
        "post_url": "",
        "youtube_url": "https://www.youtube.com/watch?v=bvF0ZM8DjuI",
        "file": "podcasts/alisa-cohn.md",
    },
    {
        "book": "Zen and the Art of Motorcycle Maintenance",
        "author": "Robert M. Pirsig",
        "quote": "**Lenny** (01:04:50):\nOkay, first question, what are two or three books that you find yourself recommending most to other people?\n\n**Bob Baxley** (01:05:03):\nSecond book, Zen and the Motorcycle Maintenance. Many people may know ultimately a philosophy book, but it's about the concept of quality, which I think is a very important topic. So it talks about quality and the importance of how things integrate into cohesive whole, which I believe is the main challenge facing most software teams.",
        "source": "lightning_round",
        "title": "35 years of product design wisdom from Apple, Disney, Pinterest, and beyond | Bob Baxley",
        "subtitle": "",
        "guest": "Bob Baxley",
        "date": "2025-06-12",
        "type": "podcast",
        "post_url": "",
        "youtube_url": "https://www.youtube.com/watch?v=X-83gvgVaWc",
        "file": "podcasts/bob-baxley.md",
    },
]

# ── FALSE-POSITIVE author patterns (single-word companies / non-persons) ─────
COMPANY_AUTHORS = re.compile(
    r'^(Google|Amazon|Apple|Microsoft|LinkedIn|Twitter|Facebook|Instagram|'
    r'Netflix|Spotify|Slack|Atlassian|OpenAI|Anthropic|First Round|Silicon Valley|'
    r'Cambridge|Monster Worldwide|Square|PetSmart|Amplitude|Persona|Cloudinary|'
    r'SVPG|Harvard Business Press|X|OpenAI|Rawls|Molly Graham|'
    r'Bryan Schreier|Jenny Yarden|Harry|Philip|Shashir|Rahul)$',
    re.IGNORECASE
)

def is_fp(book, author):
    # Blank author is allowed (OL enrichment may fill it later)
    if author and COMPANY_AUTHORS.match(author):
        return True
    # Only hard-reject a non-blank author that's clearly wrong
    if author and len(author) < 2:
        return True
    if re.search(r'(?i)^(this episode|brought to you|sponsored|acquired|funded)', book):
        return True
    if re.search(r'(?i)\b(acquired|funded|bought by|sold to|invested by|episode is)\b', book):
        return True
    if len(book.split()) > 9:
        return True
    if len(book.strip()) < 3:
        return True
    if re.match(r"^(It's|She's|He's|That's|There's|Here's)$", book):
        return True
    return False

# ── Process raw records ──────────────────────────────────────────────────────
cleaned = []

for rec in raw:
    raw_book   = rec["book"].strip()
    raw_author = rec["author"].strip()

    # Title fix
    if raw_book in TITLE_FIX:
        new_t = TITLE_FIX[raw_book]
        if new_t is None:
            continue
        book = new_t
    else:
        book = clean_title(raw_book)

    # Author: clean first, then apply AUTHOR_FIX, then per-(book,author) fix
    author = clean_author(raw_author)
    author = AUTHOR_FIX.get(author, author)
    if author is None:
        continue
    # Per-book specific author correction (avoids clobbering other books by same author)
    author = SPECIFIC_BOOK_AUTHOR_FIX.get((book, author), author)

    # False positive check
    if is_fp(book, author):
        continue

    # Clean up the quote
    q = rec.get("quote", "")
    q_lines = [l for l in q.splitlines()
               if not re.search(r'(?i)(!\[|subscribe|annual subscriber|paid edition|'
                                r'lennybot|lennyswag|apple podcast|spotify|'
                                r'lennyspodcast\.com|substack|brought to you)', l)]
    q = "\n".join(q_lines).strip()
    if len(q) > 800:
        q = q[:800].rsplit('\n', 1)[0] + "…"

    # Blank author is OK (will be shown as pending in table)
    cleaned.append({
        "book":      book,
        "author":    author,
        "quote":     q,
        "source":    rec["source"],
        "title":     rec["title"],
        "subtitle":  rec.get("subtitle", ""),
        "guest":     rec.get("guest", ""),
        "date":      rec.get("date", ""),
        "type":      rec.get("type", ""),
        "post_url":  rec.get("post_url", ""),
        "youtube_url": rec.get("youtube_url", ""),
        "file":      rec.get("file", ""),
    })

# Add manual additions
for m in MANUAL_ADDITIONS:
    m.setdefault("file", "")
    cleaned.append(m)

print(f"After cleanup + additions: {len(cleaned)}")

# Dedup: same (file, normalised_book)
seen = set()
deduped = []
for r in cleaned:
    key = (r.get("file",""), re.sub(r'[^a-z0-9]', '', r["book"].lower())[:40])
    if key not in seen:
        seen.add(key)
        deduped.append(r)

print(f"After dedup:               {len(deduped)}")
deduped.sort(key=lambda x: (x["book"].lower(), x.get("date","") or ""))

# ── Merge metadata from books_metadata.json (if present) ──────────────────
META_FILE = BASE / "books_metadata.json"

def _norm_key(s):
    """Must match norm_key() in enrich_metadata.py exactly."""
    s = re.sub(r'\b(?:the|a|an)\b', s.lower(), s.lower())
    return re.sub(r'[^a-z0-9]', '', s)[:40]

META_FIELDS = ('cover_url', 'description', 'pages', 'subjects', 'isbn',
               'published_year', 'metadata_source')

meta_merged = 0
if META_FILE.exists():
    meta_db = json.loads(META_FILE.read_text(encoding="utf-8"))
    for r in deduped:
        key = _norm_key(r["book"])
        entry = meta_db.get(key)
        if entry:
            for f in META_FIELDS:
                if f in entry:
                    r[f] = entry[f]
            meta_merged += 1
    print(f"Metadata merged            : {meta_merged}/{len(deduped)} records")
else:
    print("No books_metadata.json found — run enrich_metadata.py to add covers/descriptions")

CLEAN.write_text(json.dumps(deduped, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved clean JSON -> {CLEAN}")

# ── HTML table ───────────────────────────────────────────────────────────────
def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def fmt_q(q):
    q = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', q)
    return q.replace("\n", "<br>")

SRC_LABEL = {
    "lightning_round": "⚡ Lightning Round",
    "guest_book":      "📖 Guest Book",
    "mention":         "💬 Mid-Episode",
    "newsletter":      "📰 Newsletter",
}

rows = []
for i, r in enumerate(deduped, 1):
    url = r.get("post_url") or r.get("youtube_url") or ""
    ep  = f'<a href="{esc(url)}" target="_blank">{esc(r["title"])}</a>' if url else esc(r["title"])
    sub = f'<div class="sub">{esc(r["subtitle"])}</div>' if r.get("subtitle") else ""
    guest = esc(r["guest"]) if r.get("guest") else "<em>Lenny</em>"
    dt  = (r.get("date") or "")[:7]
    typ = "🎙 Podcast" if r.get("type") == "podcast" else "✉️ Newsletter"
    src = esc(SRC_LABEL.get(r.get("source",""), r.get("source","")))
    author_str = esc(r["author"]) if r.get("author") else '<em style="color:#bbb">author pending</em>'

    # Cover image
    if r.get("cover_url"):
        cover_html = f'<img class="cover" src="{esc(r["cover_url"])}" alt="" loading="lazy">'
    else:
        cover_html = '<div class="no-cover"></div>'

    # Description snippet (max 140 chars)
    desc = r.get("description", "")
    desc_html = ""
    if desc:
        snippet = desc[:140].rsplit(' ', 1)[0] + ('…' if len(desc) > 140 else '')
        desc_html = f'<div class="desc">{esc(snippet)}</div>'

    # Subject tags (up to 3)
    tags_html = ""
    for tag in (r.get("subjects") or [])[:3]:
        tags_html += f'<span class="tag">{esc(tag)}</span>'

    # Year / pages pills
    meta_pills = ""
    yr = r.get("published_year") or (r.get("date","")[:4] if r.get("date") else "")
    if yr:
        meta_pills += f'<span class="pill">{yr}</span>'
    if r.get("pages"):
        meta_pills += f'<span class="pill">{r["pages"]}p</span>'

    meta_row = f'<div class="meta-row">{tags_html}{meta_pills}</div>' if (tags_html or meta_pills) else ""

    rows.append(f"""  <tr>
    <td class="n">{i}</td>
    <td class="bk">
      <div class="bk-wrap">
        {cover_html}
        <div class="bk-info">
          <strong>{esc(r["book"])}</strong>
          <span class="by">by {author_str}</span>
          {desc_html}
          {meta_row}
        </div>
      </div>
    </td>
    <td class="ep">{ep}{sub}</td>
    <td class="gu">{guest}</td>
    <td class="dt">{dt}</td>
    <td class="tp">{typ}<br><small>{src}</small></td>
    <td class="qu">{fmt_q(esc(r["quote"]))}</td>
  </tr>""")

total   = len(deduped)
sources = len(set(r.get("file","") for r in deduped))
today   = date.today().isoformat()

HTML.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Book Recommendations — Lenny's Newsletter & Podcast</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f5;color:#222;padding:20px}}
header{{margin-bottom:14px}}
h1{{font-size:1.3rem;margin-bottom:4px}}
.meta{{font-size:11px;color:#888}}
#search{{padding:6px 10px;width:320px;border:1px solid #ccc;border-radius:4px;font-size:13px;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 6px rgba(0,0,0,.1)}}
th{{background:#111;color:#fff;padding:8px 10px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;text-align:left;white-space:nowrap}}
td{{padding:8px 10px;border-bottom:1px solid #eee;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#fafafe}}
.n{{width:28px;color:#bbb;font-size:11px;text-align:right}}
.bk{{min-width:220px;max-width:280px}}
.bk-wrap{{display:flex;gap:10px;align-items:flex-start}}
.cover{{width:48px;min-width:48px;height:70px;object-fit:cover;border-radius:3px;box-shadow:0 1px 4px rgba(0,0,0,.2)}}
.no-cover{{width:48px;min-width:48px;height:70px;background:#eee;border-radius:3px}}
.bk-info{{flex:1;min-width:0}}
.bk-info strong{{font-size:13px;display:block}}
.by{{font-size:11px;color:#666;display:block;margin-top:2px}}
.desc{{font-size:11px;color:#888;margin-top:4px;line-height:1.4}}
.meta-row{{margin-top:5px;display:flex;flex-wrap:wrap;gap:3px}}
.tag{{font-size:10px;background:#f0f0f0;color:#555;padding:1px 6px;border-radius:10px;white-space:nowrap}}
.pill{{font-size:10px;background:#e8f0fe;color:#1a56db;padding:1px 6px;border-radius:10px;white-space:nowrap}}
.ep{{max-width:210px}}
.ep a{{color:#0055aa;text-decoration:none;font-size:12px;line-height:1.4;display:block}}
.ep a:hover{{text-decoration:underline}}
.sub{{font-size:11px;color:#888;margin-top:2px}}
.gu{{font-size:12px;max-width:130px}}
.dt{{font-size:11px;color:#888;white-space:nowrap}}
.tp{{font-size:12px;white-space:nowrap}}
.tp small{{display:block;font-size:10px;color:#888;margin-top:2px}}
.qu{{font-size:11px;color:#444;max-width:360px;line-height:1.55}}
.qu strong{{color:#111}}
.hidden{{display:none!important}}
</style>
</head>
<body>
<header>
  <h1>📚 Book Recommendations — Lenny's Newsletter &amp; Podcast</h1>
  <p class="meta">{total} recommendations across {sources} episodes/newsletters &nbsp;·&nbsp; Extracted {today}</p>
</header>
<input id="search" type="text" placeholder="Filter by book, author, guest…" oninput="filter(this.value)">
<table id="t">
  <thead><tr>
    <th>#</th><th>Book &amp; Author</th><th>Episode / Newsletter</th>
    <th>Guest</th><th>Date</th><th>Type</th><th>Quote</th>
  </tr></thead>
  <tbody>
{"".join(rows)}
  </tbody>
</table>
<script>
function filter(q){{
  q=q.toLowerCase();
  document.querySelectorAll('#t tbody tr').forEach(r=>{{
    r.classList.toggle('hidden', q.length>0 && !r.textContent.toLowerCase().includes(q));
  }});
}}
</script>
</body>
</html>
""", encoding="utf-8")
print(f"Saved HTML -> {HTML}")

from collections import Counter
print(f"\nBy type:   {dict(Counter(r['type'] for r in deduped))}")
print(f"By source: {dict(Counter(r.get('source','') for r in deduped))}")
print(f"\n=== FINAL BOOK LIST ({len(deduped)}) ===")
for r in deduped:
    print(f"  '{r['book']}' by {r['author']}")
    print(f"     [{r.get('type')}] {r.get('guest') or 'Lenny'} | {r.get('date','')[:7]} | {r.get('source')}")
