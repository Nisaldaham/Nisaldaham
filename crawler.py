
import sqlite3
import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

# --- Configuration ---
DATABASE_FILE = 'search_engine.db'
# List of seed URLs to start crawling
SEED_URLS = [
    "http://103.145.232.246/Data/tvseries/English/",
    "http://103.145.232.246/Data/tvseries/new/",
    "https://storage.kanzaki.ru/ANIME___/",
    "http://103.145.232.246/Data/movies/Bollywood/",
    "http://103.145.232.246/Data/movies/Chinese/",
    "http://103.145.232.246/Data/movies/Hindi%20dubbed/",
    "http://103.145.232.246/Data/movies/animation/",
    "http://103.145.232.246/Data/movies/korean/",
    "http://103.145.232.246/Data/movies/Hollywood/",
    "https://edge12.105.ir.cdn.ir/hosein/Animation/",
]

# --- Database Setup ---
def initialize_database():
    """Creates the database and the files table if they don't exist."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        source_url TEXT NOT NULL,
        category TEXT,
        year INTEGER,
        quality TEXT,
        season INTEGER,
        episode INTEGER
    )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized.")

# --- HTML Parser ---
class LinkFinder(HTMLParser):
    """A simple HTML parser to find all links (hrefs) in a page."""
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    # Join relative URLs with the base URL
                    full_url = urljoin(self.base_url, value)
                    self.links.add(full_url)

# --- Metadata Parsing ---
def parse_metadata(filename):
    """Extracts metadata like year, quality, season, and episode from a filename."""
    # Simple regex patterns, can be improved
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', filename)
    quality_match = re.search(r'\b(720p|1080p|4K|2160p)\b', filename, re.IGNORECASE)
    season_match = re.search(r'[sS](\d{1,2})', filename)
    episode_match = re.search(r'[eE](\d{1,3})', filename)

    return {
        'year': int(year_match.group(1)) if year_match else None,
        'quality': quality_match.group(1) if quality_match else None,
        'season': int(season_match.group(1)) if season_match else None,
        'episode': int(episode_match.group(1)) if episode_match else None,
    }

# --- Crawler Logic ---
def crawl(urls_to_visit, conn, visited_urls=set()):
    """Recursively crawls URLs, extracts file information, and stores it in the database."""
    cursor = conn.cursor()

    if not urls_to_visit:
        return

    url = urls_to_visit.pop(0)
    if url in visited_urls or not url.startswith("http"):
        crawl(urls_to_visit, conn, visited_urls)
        return

    print(f"Crawling: {url}")
    visited_urls.add(url)

    try:
        with urllib.request.urlopen(url) as response:
            if 'text/html' in response.headers.get('Content-Type', ''):
                html = response.read().decode('utf-8', errors='ignore')
                parser = LinkFinder(url)
                parser.feed(html)

                new_links = list(parser.links - visited_urls)
                urls_to_visit.extend(new_links) # Add new links to the queue

                for link in parser.links:
                    # Basic check to identify file links vs. directory links
                    if not link.endswith('/') and urlparse(link).path:
                        filename = link.split('/')[-1]
                        metadata = parse_metadata(filename)

                        # Simple category detection
                        category = "Movies"
                        if "tvseries" in link.lower() or metadata['season']:
                            category = "TV Series"
                        elif "anime" in link.lower():
                            category = "Anime"

                        try:
                            cursor.execute('''
                            INSERT INTO files (title, url, source_url, category, year, quality, season, episode)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (filename, link, url, category, metadata['year'], metadata['quality'], metadata['season'], metadata['episode']))
                        except sqlite3.IntegrityError:
                            # URL is already in the database, skip it
                            pass
            conn.commit()

    except Exception as e:
        print(f"Error crawling {url}: {e}")

    # Continue crawling
    crawl(urls_to_visit, conn, visited_urls)


if __name__ == '__main__':
    initialize_database()
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        crawl(list(SEED_URLS), conn)
    finally:
        conn.close()
        print("Crawling finished.")
