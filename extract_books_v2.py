#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive book extraction from Lenny's newsletter and podcast markdown files.
"""

import os
import re
import json
import sys

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
    # Remove markdown links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove bold/italic
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # Remove images
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_sentence_context(text, book_title, window_chars=400):
    """Get the sentence(s) around where book_title appears in text."""
    # Find the book title in the text
    lower_text = text.lower()
    lower_title = book_title.lower()

    # Try exact match first
    pos = lower_text.find(lower_title)
    if pos == -1:
        # Try first 3 words of title
        words = lower_title.split()[:3]
        if words:
            pos = lower_text.find(' '.join(words))
    if pos == -1:
        return ''

    start = max(0, pos - window_chars)
    end = min(len(text), pos + window_chars)
    snippet = text[start:end].strip()
    return clean_text(snippet)


def split_podcast_segments(body):
    """
    Split podcast transcript into (speaker, text) segments.
    Returns list of (speaker, full_text) tuples.
    """
    # Pattern: **SpeakerName** (HH:MM:SS): or **SpeakerName**:
    pattern = r'(\*\*[^*\n]+\*\*\s*(?:\(\d+:\d+:\d+\))?\s*:)'
    parts = re.split(pattern, body)

    segments = []
    i = 0
    # First part before any speaker tag
    if parts and not parts[0].startswith('**'):
        i = 1  # skip preamble

    i = 0
    while i < len(parts):
        part = parts[i]
        if re.match(r'\*\*[^*\n]+\*\*', part):
            # This is a speaker tag
            speaker_match = re.match(r'\*\*([^*\n]+)\*\*', part)
            speaker = speaker_match.group(1).strip() if speaker_match else ''
            text = parts[i+1].strip() if i+1 < len(parts) else ''
            segments.append((speaker, text))
            i += 2
        else:
            i += 1

    return segments


def is_lenny(speaker):
    """Check if speaker is Lenny."""
    return speaker.strip().lower() in ['lenny', 'lenny rachitsky', 'lenny (00']


# ─── Book recognition patterns ───────────────────────────────────────────────
# These are patterns that indicate a real book mention with a title

TITLE_PATTERNS = [
    # "Title" by Author
    (r'"([A-Z][^"\n]{3,80})" by ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,4})', 'dquote_by'),
    (r'“([A-Z][^”\n]{3,80})” by ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,4})', 'dquote_by'),
    # *Title* by Author (italic book title)
    (r'\*([A-Z][^*\n]{3,80})\* by ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,4})', 'italic_by'),
    # **Title** by Author (bold book title)
    (r'\*\*([A-Z][^*\n]{3,80})\*\* by ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,4})', 'bold_by'),
    # book called/titled/named "X"
    (r'book\s+(?:called|titled|named)\s+"([A-Z][^"\n]{3,80})"', 'book_called'),
    (r'book\s+(?:called|titled|named)\s+“([A-Z][^”\n]{3,80})”', 'book_called'),
    # book called/titled X (no quotes)
    (r'book\s+(?:called|titled|named)\s+([A-Z][a-zA-Z0-9 :,\-\']{3,80}?)(?=[,\.!\?\n]|$)', 'book_called_bare'),
    # "X" (with title case, standalone, not followed by noise)
    # book "X" or book called "X"
    (r'my book[,\s]+"([A-Z][^"\n]{3,80})"', 'my_book'),
    (r'my book[,\s]+“([A-Z][^”\n]{3,80})”', 'my_book'),
    (r'his book[,\s]+"([A-Z][^"\n]{3,80})"', 'his_book'),
    (r'her book[,\s]+"([A-Z][^"\n]{3,80})"', 'her_book'),
    (r'their book[,\s]+"([A-Z][^"\n]{3,80})"', 'their_book'),
    (r'new book[,\s]+"([A-Z][^"\n]{3,80})"', 'new_book'),
    (r'new book[,\s]+“([A-Z][^”\n]{3,80})”', 'new_book'),
    (r'new book[,\s]+called[,\s]+"([A-Z][^"\n]{3,80})"', 'new_book'),
    (r'book[,\s]+“([A-Z][^”\n]{3,80})”', 'book_dquote'),
    # [Title](amazon/goodreads/bookshop link)
    (r'\[([A-Z][^\]\n]{3,80})\]\(https?://(?:www\.)?(?:amazon|goodreads|bookshop|shop\.app|books\.google)[^\)]+\)', 'linked_book'),
    # wrote a book called X
    (r'wrote\s+(?:a|the|his|her|this)\s+book[,\s]+"([A-Z][^"\n]{3,80})"', 'wrote_book'),
    (r'wrote\s+(?:a|the|his|her|this)\s+book[,\s]+“([A-Z][^”\n]{3,80})”', 'wrote_book'),
    # authored X
    (r'author(?:ed)? of "([A-Z][^"\n]{3,80})"', 'author_of'),
    (r'author(?:ed)? of “([A-Z][^”\n]{3,80})”', 'author_of'),
    # "X", a book
    (r'"([A-Z][^"\n]{3,80})",?\s+(?:a|the)\s+book', 'book_after'),
    (r'“([A-Z][^”\n]{3,80})”,?\s+(?:a|the)\s+book', 'book_after'),
    # read "X"
    (r'(?:read|reading|recommend(?:ed)?|loved|enjoyed|liked)\s+"([A-Z][^"\n]{3,80})"', 'read_book'),
    (r'(?:read|reading|recommend(?:ed)?|loved|enjoyed|liked)\s+“([A-Z][^”\n]{3,80})”', 'read_book'),
    # "X" by Author, no qualifier but has "by"
    (r'"([A-Z][^"\n]{5,80})" by ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,3})', 'generic_by'),
    # the book "X" or a book "X"
    (r'(?:the|a|this)\s+book\s+"([A-Z][^"\n]{3,80})"', 'the_book'),
    (r'(?:the|a|this)\s+book\s+“([A-Z][^”\n]{3,80})”', 'the_book'),
    # specifically formatted: **"Book Title"**
    (r'\*\*"([A-Z][^"\n]{3,80})"\*\*', 'bold_quoted'),
    # Book: by listing format like "- **Book Title** by Author"
    (r'[-•]\s+\*\*([A-Z][^*\n]{3,80})\*\*(?:\s+by\s+([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,3}))?', 'list_bold'),
    # Read: [Book Title](url)
    (r'\*\*Read\*\*:\s+\[([A-Z][^\]\n]{3,80})\]\([^\)]+\)', 'read_link'),
    # recommendation lists: **Book Title** by Author (in list)
    (r'^\s*\*\*([A-Z][^*\n]{3,80})\*\*\s+by\s+([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,3})', 'list_entry'),
]

# Patterns for book series / well-known titles that appear without author
STANDALONE_KNOWN_BOOKS = [
    r'The Lean Startup',
    r'Zero to One',
    r'Good to Great',
    r'Inspired(?:\s+by)?',
    r'Continuous Discovery Habits',
    r'Hooked(?:\s+by)?',
    r'Measure What Matters',
    r'The Hard Thing About Hard Things',
    r'High Output Management',
    r'Thinking in Bets',
    r'The Mom Test',
    r'Competing Against Luck',
    r'Crossing the Chasm',
    r"The Innovator'?s? Dilemma",
    r'Blue Ocean Strategy',
    r'Blitzscaling',
    r'Trillion Dollar Coach',
    r'Radical Candor',
    r'Never Split the Difference',
    r'Thinking, Fast and Slow',
    r'Atomic Habits',
    r'Deep Work',
    r'The Power of Habit',
    r'Grit(?:\s+by)?',
    r'Mindset(?:\s+by)?',
    r'Outliers(?:\s+by)?',
    r'Blink(?:\s+by)?',
    r'The Tipping Point',
    r'No Rules Rules',
    r'Shoe Dog',
    r'Creativity, Inc\.',
    r'Creativity Inc\b',
    r'The Everything Store',
    r'Poor Charlie\'s Almanack',
    r'The Psychology of Money',
    r'Principles(?:\s+by)?',
    r'The Almanack of Naval Ravikant',
    r'Tools of Titans',
    r'How to Win Friends and Influence People',
    r'The 7 Habits of Highly Effective People',
    r'Essentialism(?:\s+by)?',
    r'Getting Things Done',
    r'Building a Second Brain',
    r'So Good They Can\'t Ignore You',
    r'The Obstacle Is the Way',
    r'An Elegant Puzzle',
    r'The Manager\'?s? Path',
    r'The Making of a Manager',
    r'Multipliers(?:\s+by)?',
    r'The First 90 Days',
    r'Dare to Lead',
    r'Extreme Ownership',
    r'The Effective Executive',
    r'Drive(?:\s+by)?',
    r'Flow(?:\s+by)?',
    r'Man\'?s? Search for Meaning',
    r'Sapiens(?:\s+by)?',
    r'The Art of War',
    r'The 48 Laws of Power',
    r'Only the Paranoid Survive',
    r'Running Lean',
    r'Shape Up',
    r'Empowered(?:\s+by)?',
    r'Obviously Awesome',
    r'Hacking Growth',
    r'Contagious(?:\s+by)?',
    r'Made to Stick',
    r'The Culture Code',
    r'The Five Dysfunctions of a Team',
    r'Turn the Ship Around',
    r'Leaders Eat Last',
    r'Good Strategy Bad Strategy',
    r'7 Powers',
    r'Hamilton\'?s? Corollary',
    r'Traction(?:\s+by)?',
    r'Range(?:\s+by)?',
    r'The Checklist Manifesto',
    r'Difficult Conversations',
    r'Thanks for the Feedback',
    r'Nonviolent Communication',
    r'Being Mortal',
    r'When Breath Becomes Air',
    r'The Gene(?:\s+by)?',
    r'Four Thousand Weeks',
    r'Indistractable(?:\s+by)?',
    r'Digital Minimalism',
    r'Antifragile(?:\s+by)?',
    r'The Black Swan',
    r'Skin in the Game',
    r'Predictably Irrational',
    r'Thinking in Systems',
    r'The Fifth Discipline',
    r'Work Rules!',
    r'The Power Broker',
    r'ReWork(?:\s+by)?',
    r"It Doesn't Have to Be Crazy at Work",
    r"Badass(?:\s+by)?",
    r'Amp It Up',
    r'The Cold Start Problem',
    r'Obviously Awesome',
    r'The Startup Way',
    r'Playing to Win',
    r'Staff Engineer',
    r'Peak(?:\s+by)?',
    r'Mastery(?:\s+by)?',
    r'Influence(?:\s+by)?',
    r'Switch(?:\s+by)?',
    r'Nudge(?:\s+by)?',
    r'Freakonomics(?:\s+by)?',
    r'Algorithms to Live By',
    r'The Power of Moments',
    r'The Second Mountain',
    r"When(?:\s+by)?",
    r'Triggers(?:\s+by)?',
    r'Emotional Intelligence',
    r'Perennial Seller',
    r'This Is Marketing',
    r'Purple Cow',
    r'Permission Marketing',
    r'All Marketers Are Liars',
    r'Linchpin(?:\s+by)?',
    r'What Got You Here Won\'?t? Get You There',
    r'The Score Takes Care of Itself',
    r"Poor Charlie's Almanack",
    r'The Practicing Mind',
    r'The Artist\'?s? Way',
    r'Bird by Bird',
    r'On Writing',
    r'The Elements of Style',
    r'Show Your Work',
    r'Steal Like an Artist',
    r'The War of Art',
    r'Big Magic',
    r'Positioning(?:\s+by)?',
    r'Demand-Side Sales',
    r'Jobs to Be Done',
    r'Crucial Conversations',
    r'The Coaching Habit',
    r'Meditations(?:\s+by)?',
    r'A Guide to the Good Life',
    r'Stillness Is the Key',
    r'The Ego Is the Enemy',
    r'Never Split the Difference',
    r'Talking to Strangers',
    r'Bossypants(?:\s+by)?',
    r'The Hard Thing About Hard Things',
    r'Shoe Dog',
    r'Pour Your Heart Into It',
    r'The Lean Six Sigma',
    r'Getting to Yes',
    r'Presence(?:\s+by)?',
    r'Dare to Lead',
    r'Braving the Wilderness',
    r'The Gifts of Imperfection',
    r'Rising Strong',
    r'Leadership and Self.Deception',
    r'The Anatomy of Peace',
    r'Conscious Business',
    r'The Open Organization',
    r'Who(?:\s+by Geoff Smart)?',
    r'Topgrading(?:\s+by)?',
    r'Work the System',
    r'Simple Numbers',
    r'Simple Numbers, Straight Talk',
    r'Scaling Up',
    r'Traction(?:\s+by Gino Wickman)?',
    r'EOS',
    r'The Advantage',
    r'The Leadership Pipeline',
    r'The Effective Executive',
    r'Results Without Authority',
    r'The Power of Full Engagement',
    r'The 4 Disciplines of Execution',
    r'The 12 Week Year',
    r'Measure What Matters',
    r'Radical Focus',
    r'The OKR Playbook',
    r'Superbosses(?:\s+by)?',
    r'Rocket Fuel',
    r'The E.Myth Revisited',
    r'Built to Sell',
    r'Company of One',
    r'The \$100 Startup',
    r'Profit First',
    r'Never Enough',
    r'Working Backwards',
    r'Invent and Wander',
    r'The Amazon Way',
    r'The Bezos Letters',
    r'The WEIRDest People in the World',
    r'Blueprint(?:\s+by)?',
    r'The Extended Mind',
    r'How Minds Change',
    r'The Intelligence Trap',
    r'The Knowledge Illusion',
    r'The Righteous Mind',
    r'Behave(?:\s+by)?',
    r'The Blank Slate',
    r'Incognito(?:\s+by)?',
    r'Stumbling on Happiness',
    r'Emotional Agility',
    r'Why We Work',
    r'The Willpower Instinct',
    r'Tiny Habits',
    r'Atomic Habits',
    r'The Compound Effect',
    r'Mini Habits',
    r'The 5 Second Rule',
    r'Indistractable',
    r'The Shallows',
    r'How to Think',
    r'Clear Thinking',
    r'The Intelligence Trap',
    r'Thinking Like Einstein',
    r"Thinking About Thinking",
    r'Super Thinking',
    r'The Great Mental Models',
    r'Seeking Wisdom',
    r'Think Again',
    r'Being Wrong',
    r'How to Change Your Mind',
    r'The Body Keeps the Score',
    r'Why Zebras Don\'?t? Get Ulcers',
    r'The Molecule of More',
    r'Brain Rules',
    r'Feeling Good',
    r'The Brain That Changes Itself',
    r'Incognito',
    r'Default World',
    r'Stealing Fire',
    r"Waking Up",
    r"The Practicing Mind",
    r"The Inner Game of Tennis",
    r'The 10X Rule',
    r'10x Is Easier Than 2x',
    r'The Gap and The Gain',
    r'The One Thing',
    r'Win Without Pitching',
    r"The Pumpkin Plan",
    r"Fix This Next",
    r"Clockwork",
    r"Buy Back Your Time",
    r"Who Not How",
    r'The 80/20 Principle',
    r'The 4-Hour Workweek',
    r'The 4-Hour Body',
    r'The 4-Hour Chef',
    r'Start with Why',
    r'Find Your Why',
    r'The Infinite Game',
    r'This Is Marketing',
    r'The Icarus Deception',
    r'Tribes(?:\s+by)?',
    r'Poke the Box',
    r'Small is the New Big',
    r'Meatball Sundae',
    r'Permission Marketing',
    r'Unleashing the Ideavirus',
    r'The Big Moo',
    r'The Dip(?:\s+by)?',
    r'Survival Is Not Enough',
    r'The Bootstrapper\'?s? Bible',
    r'Do the Work',
    r'Turning Pro',
    r'The Authentic Swing',
    r'The Legend of Bagger Vance',
    r'Gates of Fire',
    r'The Gardens of the Moon',
    r"The Name of the Wind",
    r'Words of Radiance',
    r"Oathbringer",
    r"The Way of Kings",
    r'Stormlight Archive',
    r'Mistborn(?:\s+by)?',
    r'Elantris(?:\s+by)?',
    r'Foundation(?:\s+by)?',
    r'Dune(?:\s+by)?',
    r"Ender's Game",
    r'Speaker for the Dead',
    r'Xenocide(?:\s+by)?',
    r'Children of the Mind',
    r'Snow Crash',
    r'Cryptonomicon',
    r'Neuromancer',
    r'The Diamond Age',
    r"The Hitchhiker's Guide to the Galaxy",
    r'Slaughterhouse.Five',
    r'Catch.22',
    r'Lord of the Flies',
    r'1984(?:\s+by)?',
    r'Brave New World',
    r'Fahrenheit 451',
    r'The Handmaid\'?s? Tale',
    r'Atlas Shrugged',
    r'The Fountainhead',
    r'Lolita(?:\s+by)?',
    r'The Great Gatsby',
    r'To Kill a Mockingbird',
    r'Of Mice and Men',
    r'East of Eden',
    r'Grapes of Wrath',
    r'For Whom the Bell Tolls',
    r'A Farewell to Arms',
    r'The Sun Also Rises',
    r'The Old Man and the Sea',
    r'One Hundred Years of Solitude',
    r'Love in the Time of Cholera',
    r'Ficciones(?:\s+by)?',
    r'Invisible Man',
    r"The Remains of the Day",
    r'Never Let Me Go',
    r'The Buried Giant',
    r"Klara and the Sun",
    r'Piranesi(?:\s+by)?',
    r'Jonathan Strange',
    r'The Night Circus',
    r"The Goldfinch",
    r'All the Light We Cannot See',
    r"The Kite Runner",
    r"A Thousand Splendid Suns",
    r'Educated(?:\s+by)?',
    r'Becoming(?:\s+by)?',
    r'Open(?:\s+by)?',
    r'Born a Crime',
    r'Maybe You Should Talk to Someone',
    r'The Glass Castle',
    r'Hillbilly Elegy',
    r'Evicted(?:\s+by)?',
    r'Talking to Strangers',
    r'The Warmth of Other Suns',
    r'Between the World and Me',
    r'The New Jim Crow',
    r'Killers of the Flower Moon',
    r'The Splendid and the Vile',
    r'Team of Rivals',
    r'Grant(?:\s+by)?',
    r'Hamilton(?:\s+by Ron Chernow)?',
    r'Washington(?:\s+by)?',
    r'John Adams',
    r'The Power Broker',
    r'Working(?:\s+by Studs Terkel)?',
    r'The Autobiography of Malcolm X',
    r'Long Walk to Freedom',
    r'My Brilliant Career',
    r'The Innovators',
    r'Hackers(?:\s+by)?',
    r'Soul of a New Machine',
    r"The Dream Machine",
    r'Superintelligence(?:\s+by)?',
    r'The Alignment Problem',
    r'Human Compatible',
    r'Life 3.0',
    r"The Coming Wave",
    r'Power and Progress',
    r'The Age of AI',
    r'AI Superpowers',
    r"Weapons of Math Destruction",
    r'Prediction Machines',
    r'The Second Machine Age',
    r'The Technology Trap',
    r'The Inevitable',
    r'Out of Control',
    r'What Technology Wants',
    r'The Shockwave Rider',
    r'Wired for Story',
    r'Save the Cat',
    r'Story(?:\s+by Robert McKee)?',
    r'The Hero with a Thousand Faces',
    r"Campbell's Hero",
    r'The War of Art',
    r'The Creative Habit',
    r'A Whack on the Side of the Head',
    r'Think Like Da Vinci',
    r'The Art of Possibility',
    r'Art and Fear',
    r'The Courage to Create',
    r'The Creative Brain',
    r'Where Good Ideas Come From',
    r'The Innovator\'?s? Solution',
    r'Seeing What Others Don\'?t',
    r'The Opposable Mind',
    r'Six Thinking Hats',
    r'Lateral Thinking',
    r'How to Solve It',
    r'Thinking in Systems',
    r'Limits to Growth',
    r'The Systems Bible',
    r'An Introduction to General Systems Thinking',
    r'The Fifth Discipline',
    r"Presence(?:\s+by Peter Senge)?",
    r'Reinventing Organizations',
    r'Holacracy(?:\s+by)?',
    r'The People\'?s Platform',
    r'Winners Take All',
    r'Bullshit Jobs',
    r'The Precariat(?:\s+by)?',
    r'Nice Guys Finish Last',
    r'Give and Take',
    r'Influence(?:\s+by Cialdini)?',
    r'Pre-Suasion(?:\s+by)?',
    r'Yes!(?:\s+by)?',
    r'Cialdini',
    r'Made to Stick',
    r'Switch(?:\s+by Chip Heath)?',
    r'Decisive(?:\s+by)?',
    r'The Power of Moments',
    r'The Paradox of Choice',
    r'Predictably Irrational',
    r'Misbehaving(?:\s+by)?',
    r'Nudge(?:\s+by)?',
    r'Freakonomics',
    r'SuperFreakonomics',
    r'Think Like a Freak',
    r'When to Rob a Bank',
    r'The Upside of Irrationality',
    r'The (Con)?Honest Truth About Dishonesty',
    r'Are We Smart Enough',
    r'The Goodness Paradox',
    r'Blueprint(?:\s+by)?',
    r'Humankind(?:\s+by)?',
    r'Less Is More',
    r'The Overshoot',
    r'Speed and Scale',
    r'How to Avoid a Climate Disaster',
    r'The New Climate Economy',
    r'Doughnut Economics',
    r'Sacred Economics',
    r'The Value of Everything',
    r'Debt(?:\s+by David Graeber)?',
    r'Capital in the 21st Century',
    r'The Price of Everything',
    r'The Wealth of Nations',
    r'Poor Economics',
    r'The End of Poverty',
    r'The White Man\'?s? Burden',
    r'Scarcity(?:\s+by)?',
    r'Bottlenecks(?:\s+by)?',
    r'Overcoming Bias',
    r'The Elephant in the Brain',
    r'The Parasitic Mind',
    r'Survival of the Friendliest',
    r'The Social Instinct',
    r'Grooming, Gossip, and the Evolution of Language',
    r'The Language Instinct',
    r'Surfaces and Essences',
    r'G.del, Escher, Bach',
    r"Gödel, Escher, Bach",
    r'Metamagical Themas',
    r'The Mind\'?s? I',
    r'Hofstadter',
    r'The Big Picture',
    r'Something Deeply Hidden',
    r'The Order of Time',
    r'Seven Brief Lessons on Physics',
    r'Astrophysics for People in a Hurry',
    r'What Is Real\?',
    r'The Demon-Haunted World',
    r'A Brief History of Time',
    r'The Grand Design',
    r'The Elegant Universe',
    r'The Fabric of the Cosmos',
    r'The Future of Humanity',
    r'Parallel Worlds',
    r'Hyperspace(?:\s+by)?',
    r'The Physics of the Future',
    r'Michio Kaku',
    r'The Vital Question',
    r'Life Ascending',
    r'The Selfish Gene',
    r'The Extended Phenotype',
    r'The Blind Watchmaker',
    r'Climbing Mount Improbable',
    r'Unweaving the Rainbow',
    r'A Devil\'?s? Chaplain',
    r'The God Delusion',
    r'Why Evolution Is True',
    r'Your Inner Fish',
    r'The Ancestor\'?s? Tale',
    r'Genome(?:\s+by)?',
    r'The Double Helix',
    r'The Eighth Day of Creation',
    r'Molecular Biology of the Gene',
    r'A Crack in Creation',
    r'Regenesis(?:\s+by)?',
    r'The Code Breaker',
    r'Inferior(?:\s+by)?',
    r'The Epigenetics Revolution',
    r'Lifespan(?:\s+by)?',
    r'Ageless(?:\s+by)?',
    r'The Longevity Paradox',
    r'Outlive(?:\s+by)?',
    r'Lifespan(?:\s+by)?',
    r'Why We Sleep',
    r'The Sleep Revolution',
    r'Spark(?:\s+by)?',
    r'Brain Rules',
    r'Head Strong',
    r'Boundless(?:\s+by Ben Greenfield)?',
    r'The Bulletproof Diet',
    r'How Not to Die',
    r'The China Study',
    r'Grain Brain',
    r'Wheat Belly',
    r'The Plant Paradox',
    r'Fiber Fueled',
    r'The Carnivore Code',
    r'Sacred Cow',
    r'Eat to Beat Disease',
    r'The Obesity Code',
    r'The Diabetes Code',
    r'The Cancer Code',
    r'Fast. Feast. Repeat.',
    r'The Circadian Code',
    r'When(?:\s+by Satchin Panda)?',
    r'The 4-Hour Body',
    r'Tribe(?:\s+by Sebastian Junger)?',
    r'Sebastian Junger',
    r'War(?:\s+by Sebastian Junger)?',
    r'The Perfect Storm',
    r'Into the Wild',
    r'Into Thin Air',
    r'Touching the Void',
    r'Endurance(?:\s+by)?',
    r'In the Kingdom of Ice',
    r'The Lost City of Z',
    r'The River of Doubt',
    r'Shackleton\'?s? Way',
    r'South(?:\s+by Shackleton)?',
    r'West with the Night',
    r'Undaunted Courage',
    r'The Oregon Trail',
    r'Destiny of the Republic',
    r'Dead Wake',
    r'Devil in the White City',
    r'Thunderstruck(?:\s+by)?',
    r'In the Garden of Beasts',
    r'Isaac\'?s? Storm',
    r'Columbine(?:\s+by Dave Cullen)?',
    r'Helter Skelter',
    r'I Am Pilgrim',
    r'The Girl with the Dragon Tattoo',
    r'Gone Girl',
    r'The Da Vinci Code',
    r'Angels and Demons',
    r'Inferno(?:\s+by Dan Brown)?',
    r'The Firm(?:\s+by)?',
    r'The Pelican Brief',
    r'The Client(?:\s+by John Grisham)?',
    r'A Time to Kill',
    r'The Runaway Jury',
    r'The Broker',
    r'The Rainmaker',
    r'The Street Lawyer',
    r'A Painted House',
    r'Skipping Christmas',
    r'The Appeal',
    r'The Associate',
    r'The Confession',
    r'Calico Joe',
    r'The Racketeer',
    r'Sycamore Row',
    r'Rogue Lawyer',
    r'The Whistler',
    r'Camino Island',
    r'The Rooster Bar',
    r'The Reckoning',
    r'A Time for Mercy',
    r'Sooley(?:\s+by)?',
    r'The Judge\'?s? List',
    r'Sparring Partners',
    r'The Tumor',
    r'The Litigators',
    r'Ford County',
    r'Theodore Boone',
    r'Bleachers(?:\s+by)?',
    r'Playing for Pizza',
    r'The Last Juror',
    r'The Summons',
    r'The King of Torts',
    r'Bleachers',
    r'The Chamber',
    r'The Testament',
    r'The Partner',
    r'The Street Lawyer',
    r'A Time to Kill',
    r"Pillars of the Earth",
    r"World Without End",
    r"A Column of Fire",
    r"Fall of Giants",
    r"Winter of the World",
    r"Edge of Eternity",
    r"Code to Zero",
    r"Jackdaws(?:\s+by Ken Follett)?",
    r'Hornet Flight',
    r'Whiteout(?:\s+by Ken Follett)?',
    r'Triple(?:\s+by)?',
    r'The Key to Rebecca',
    r'The Man from St. Petersburg',
    r'On Wings of Eagles',
    r'Night Over Water',
    r'The Third Twin',
    r'The Hammer of Eden',
    r'Lie Down with Lions',
    r'The Modigliani Scandal',
    r'Paper Money',
    r'Eye of the Needle',
]


def find_book_mentions(body, doc_type, guest_name):
    """
    Find all book mentions in the document body.
    Returns list of (book_title, book_author, lenny_quote, guest_quote) tuples.
    """
    results = []
    seen = set()

    # For podcasts, split by speaker
    if doc_type == 'podcast':
        segments = split_podcast_segments(body)
        # Full text for context lookups
        full_text = body
    else:
        segments = [('Lenny', body)]
        full_text = body

    # Apply title patterns to full text
    for pattern, kind in TITLE_PATTERNS:
        for m in re.finditer(pattern, full_text, re.MULTILINE):
            try:
                raw_title = m.group(1).strip()
            except IndexError:
                continue

            # Clean title
            title = raw_title.strip('"').strip('“').strip('”').strip('*').strip()

            # Filter out non-book titles
            if should_skip_title(title):
                continue

            # Get author if captured
            try:
                author = m.group(2).strip() if m.lastindex >= 2 and m.group(2) else 'Unknown'
                author = clean_author(author)
            except IndexError:
                author = 'Unknown'

            title_key = title.lower()[:50]
            if title_key in seen:
                continue
            seen.add(title_key)

            # Get context around the mention
            pos = m.start()
            ctx_start = max(0, pos - 600)
            ctx_end = min(len(full_text), pos + 600)
            ctx = full_text[ctx_start:ctx_end]

            lenny_q, guest_q = extract_quotes(ctx, title, doc_type, guest_name, segments, pos)

            results.append({
                "book_title": title,
                "book_author": author,
                "lenny_quote": lenny_q,
                "guest_quote": guest_q,
            })

    return results


def should_skip_title(title):
    """Return True if this title should be skipped (not a real book)."""
    if len(title) < 3:
        return True

    # Too long - likely a sentence, not a title
    if len(title) > 120:
        return True

    lower = title.lower()

    # Skip if it looks like an image reference
    if any(x in lower for x in ['.png', '.jpg', '.gif', '.svg', '.jpeg', '.webp', 'image from', 'http']):
        return True

    # Skip if starts with lowercase (not a proper title)
    if title[0].islower():
        return True

    # Skip very generic words that aren't book titles
    skip_words = {
        'the', 'a', 'an', 'this', 'that', 'these', 'those',
        'my', 'your', 'our', 'their', 'his', 'her',
        'new', 'old', 'big', 'small', 'good', 'great', 'best',
        'yes', 'no', 'not', 'so', 'well', 'just', 'still',
        'i', 'we', 'you', 'he', 'she', 'they', 'it',
        'what', 'how', 'why', 'when', 'where', 'who', 'which',
        'read', 'write', 'work', 'use', 'get', 'make', 'do',
        'podcast', 'newsletter', 'article', 'post', 'essay',
        'episode', 'video', 'course', 'series', 'show',
        'product', 'company', 'startup', 'team', 'person',
        'email', 'slack', 'twitter', 'linkedin',
    }

    if lower in skip_words:
        return True

    # Skip if it looks like a URL-type string
    if re.match(r'^[\w\-]+$', title) and len(title) < 6:
        return True

    # Skip obvious non-titles (lowercase fragments)
    if re.match(r'^[a-z]', title):
        return True

    # Skip things that are clearly navigation items or UI elements
    nav_patterns = [r'^Leave a comment', r'^Subscribe', r'^Share', r'^Follow', r'^Click here']
    for p in nav_patterns:
        if re.match(p, title, re.IGNORECASE):
            return True

    return False


def clean_author(author):
    """Clean up author name."""
    if not author:
        return 'Unknown'

    # Remove trailing punctuation
    author = re.sub(r'[,\.\!\?\;:]+$', '', author).strip()
    # Remove markdown
    author = re.sub(r'\*+', '', author).strip()
    # Normalize whitespace
    author = re.sub(r'\s+', ' ', author).strip()

    if len(author) < 2:
        return 'Unknown'

    # Skip if it looks like a sentence (too many words)
    if len(author.split()) > 5:
        return 'Unknown'

    return author


def extract_quotes(ctx, book_title, doc_type, guest_name, all_segments, mention_pos):
    """Extract Lenny and guest quotes from context."""
    lenny_quote = ''
    guest_quote = ''

    if doc_type == 'podcast':
        # Find the segment that contains this mention
        # We need to find which speaker segment is at mention_pos

        # Parse speaker segments with positions from ctx
        speaker_seg_pattern = r'\*\*([^*\n]+)\*\*\s*(?:\(\d+:\d+:\d+\))?\s*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)'

        book_lower = book_title.lower()[:25]

        # Find segments that mention the book
        for m in re.finditer(speaker_seg_pattern, ctx):
            speaker = m.group(1).strip()
            text = m.group(2).strip()

            text_lower = text.lower()
            if book_lower not in text_lower and book_title.lower()[:15] not in text_lower:
                continue

            clean = clean_text(text)[:600]

            if is_lenny(speaker) and not lenny_quote:
                lenny_quote = clean
            elif not is_lenny(speaker) and speaker and not guest_quote:
                guest_quote = clean

        # If no direct quote found, get nearest segment for each speaker
        if not lenny_quote:
            # Find Lenny's nearest utterance
            lenny_segs = [(m.start(), clean_text(m.group(2)).strip()[:600])
                          for m in re.finditer(r'\*\*Lenny\*\*\s*(?:\([^)]*\))?\s*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)', ctx)]
            if lenny_segs:
                # Pick the one closest to the mention
                book_pos_in_ctx = ctx.lower().find(book_title.lower()[:15])
                if book_pos_in_ctx < 0:
                    book_pos_in_ctx = len(ctx) // 2
                closest = min(lenny_segs, key=lambda x: abs(x[0] - book_pos_in_ctx))
                lenny_quote = closest[1]

        if not guest_quote and guest_name:
            # Find guest's nearest utterance
            guest_first = guest_name.split()[0]
            guest_pattern = rf'\*\*{re.escape(guest_name)}\*\*\s*(?:\([^)]*\))?\s*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)'
            guest_segs = [(m.start(), clean_text(m.group(1)).strip()[:600])
                          for m in re.finditer(guest_pattern, ctx)]
            if not guest_segs:
                # Try partial match
                guest_pattern2 = rf'\*\*{re.escape(guest_first)}[^*]*\*\*\s*(?:\([^)]*\))?\s*:\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)'
                guest_segs = [(m.start(), clean_text(m.group(1)).strip()[:600])
                              for m in re.finditer(guest_pattern2, ctx)]
            if guest_segs:
                book_pos_in_ctx = ctx.lower().find(book_title.lower()[:15])
                if book_pos_in_ctx < 0:
                    book_pos_in_ctx = len(ctx) // 2
                closest = min(guest_segs, key=lambda x: abs(x[0] - book_pos_in_ctx))
                guest_quote = closest[1]

    else:
        # Newsletter - Lenny is the author, grab surrounding text
        book_pos = ctx.lower().find(book_title.lower()[:15])
        if book_pos >= 0:
            s = max(0, book_pos - 200)
            e = min(len(ctx), book_pos + 400)
            lenny_quote = clean_text(ctx[s:e]).strip()[:600]
        else:
            # Just use a chunk from ctx
            lenny_quote = clean_text(ctx[:400]).strip()[:600]

    return lenny_quote, guest_quote


def process_all_files():
    """Process all files and return results."""
    all_results = []
    error_files = []

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

                # Skip very short files
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
                error_files.append((filename, str(e)))

    if error_files:
        print(f"\nErrors in {len(error_files)} files:")
        for fn, err in error_files[:5]:
            print(f"  {fn}: {err}")

    return all_results


if __name__ == '__main__':
    results = process_all_files()

    print(f"\nTotal book mentions found: {len(results)}")

    # Stats
    by_type = {}
    for r in results:
        t = r['type']
        by_type[t] = by_type.get(t, 0) + 1
    print(f"By type: {by_type}")

    # Sample results
    print("\nSample entries:")
    for e in results[:5]:
        print(f"  [{e['type']}] '{e['book_title']}' by {e['book_author']} - source: {e['source_title'][:50]}")

    # Write output
    output_path = r"C:\Users\bpman\OneDrive\Documents\Claude\Projects\LennysData\books_extracted_v2.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to {output_path}")
