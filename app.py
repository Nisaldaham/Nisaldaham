import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
import sqlite3
import threading
import warnings
import asyncio
import re
import json
import random
import time
from bs4 import XMLParsedAsHTMLWarning
from concurrent.futures import ThreadPoolExecutor
from thefuzz import fuzz
from flask import Flask, render_template_string, request, jsonify, redirect

# Ignore the XML parsing warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# --- TMDb API Configuration ---
TMDB_API_KEY = "YOUR_TMDB_API_KEY"  # Replace with your actual TMDb API key
TMDB_API_URL = "https://api.themoviedb.org/3"

# Targeted Sources (Imported from your scan.py)
SOURCES = [
    {"category": "TV Series", "name": "TV English", "url": "http://103.145.232.246/Data/tvseries/English/"},
    {"category": "TV Series", "name": "TV New", "url": "http://103.145.232.246/Data/tvseries/new/"},
    {"category": "Anime", "name": "Kanzaki Anime", "url": "https://storage.kanzaki.ru/ANIME___/"},
    {"category": "Movies", "name": "Bollywood", "url": "http://103.145.232.246/Data/movies/Bollywood/"},
    {"category": "Movies", "name": "Chinese", "url": "http://103.145.232.246/Data/movies/Chinese/"},
    {"category": "Movies", "name": "Hindi Dubbed", "url": "http://103.145.232.246/Data/movies/Hindi%20dubbed/"},
    {"category": "Movies", "name": "Korean", "url": "http://103.145.232.246/Data/movies/korean/"},
    {"category": "Movies", "name": "Hollywood", "url": "http://103.145.232.246/Data/movies/Hollywood/"},
    {"category": "Animation", "name": "Animation 1", "url": "http://103.145.232.246/Data/movies/animation/"},
    {"category": "Animation", "name": "Animation 2", "url": "https://edge12.105.ir.cdn.ir/hosein/Animation/"},
    {"category": "Anime", "name": "Inukami Anime", "url": "https://storage.inukami.ru/ANIME___/"},
    {"category": "Movies", "name": "Papion Media", "url": "http://ir2.papionvod.ir/Media/"},
    {"category": "TV Series", "name": "3RVer DL3", "url": "https://dl3.3rver.org/"},
    {"category": "Mixed", "name": "DYM1 Collection", "url": "https://dym1.site/"},
    {"category": "Anime", "name": "Calm Snow Media", "url": "https://calm-snow-9de3.evohmodz.workers.dev/0:/Media/"},
    {"category": "Movies", "name": "Ace Net Public", "url": "http://ace-net.net/stream/Movies/PublicMovies/"},
    {"category": "TV Series", "name": "High-Speed TV Packs", "url": "http://72.21.17.51:15588/TV/"},
    {"category": "Animation", "name": "Edge Animation Extra", "url": "https://edge12.105.ir.cdn.ir/hosein/ExtraAnimation/"},
    {"category": "Movies", "name": "Global Hollywood Mirror", "url": "http://103.145.232.246/Data/movies/ExtraHollywood/"},
    {"category": "Mixed", "name": "Large Media Archive", "url": "https://large-archive.example.com/Media/"}
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

app = Flask(__name__)
# Status tracking for UI monitoring
indexing_status = {"status": "Idle", "count": 0, "logs": [], "health": {}}
db_lock = threading.Lock()

# --- Metadata Parsing Logic ---
def extract_metadata(filename):
    meta = {'title': None, 'year': None, 'quality': 'Unknown', 'season': None, 'episode': None, 'type': 'Movie'}

    # Clean up filename for title extraction
    clean_name = re.sub(r'\b(19\d{2}|20\d{2})\b', '', filename) # Remove year
    clean_name = re.sub(r'\b(4k|2160p|1080p|720p|480p)\b', '', clean_name, flags=re.IGNORECASE) # Remove quality
    clean_name = re.sub(r'[\.\[\]_]', ' ', clean_name) # Replace delimiters with spaces

    # Season/Episode (S01E01 pattern)
    se_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', clean_name)
    if se_match:
        meta['type'] = 'Episode'
        meta['season'], meta['episode'] = int(se_match.group(1)), int(se_match.group(2))
        title_candidate = clean_name.split(se_match.group(0))[0]
        meta['title'] = title_candidate.strip()
    else:
        # If no season/episode, assume it's a movie
        meta['title'] = clean_name.strip()

    # Extract Year (19xx-20xx)
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', filename)
    if year_match: meta['year'] = year_match.group(1)

    f_lower = filename.lower()
    # Extract Quality
    if '4k' in f_lower or '2160p' in f_lower: meta['quality'] = '4K'
    elif '1080p' in f_lower: meta['quality'] = '1080p'
    elif '720p' in f_lower: meta['quality'] = '720p'
    elif '480p' in f_lower: meta['quality'] = '480p'

    # Final title cleanup
    if meta['title']:
       meta['title'] = re.sub(r'\s+', ' ', meta['title']).strip() # Consolidate whitespace

    return meta

# --- Database Management ---
def get_db_connection():
    conn = sqlite3.connect('file_index_v4.db', check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        cursor = conn.cursor()

        # New Media Table for grouped shows/movies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT NOT NULL, -- 'Movie' or 'TV Show'
                year INTEGER,
                poster_url TEXT,
                summary TEXT,
                tmdb_id INTEGER UNIQUE,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_media_title_type_year ON media (title, type, year)')

        # Core Files Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                source_name TEXT,
                file_name TEXT,
                file_url TEXT UNIQUE,
                year INTEGER,
                quality TEXT,
                meta_json TEXT,
                media_id INTEGER,
                FOREIGN KEY (media_id) REFERENCES media (id)
            )
        ''')

        # Add media_id column to files table if it doesn't exist (for migration)
        cursor.execute('PRAGMA table_info(files)')
        columns = [row['name'] for row in cursor.fetchall()]
        if 'media_id' not in columns:
            cursor.execute('ALTER TABLE files ADD COLUMN media_id INTEGER REFERENCES media(id)')

        # Watch History Progress Tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watch_history (
                file_url TEXT PRIMARY KEY,
                title TEXT,
                progress_time FLOAT,
                duration FLOAT,
                last_watched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # FTS5 for smart search
        try:
            # FTS for media table
            cursor.execute('CREATE VIRTUAL TABLE IF NOT EXISTS media_fts USING fts5(title, year, summary, content="media", content_rowid="id")')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS media_ai AFTER INSERT ON media BEGIN
                    INSERT INTO media_fts(rowid, title, year, summary)
                    VALUES (new.id, new.title, new.year, new.summary);
                END;
            ''')

            # Original FTS for files
            cursor.execute('CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(file_name, category, quality, year, content="files", content_rowid="id")')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                    INSERT INTO files_fts(rowid, file_name, category, quality, year)
                    VALUES (new.id, new.file_name, new.category, new.quality, new.year);
                END;
            ''')
        except sqlite3.OperationalError: pass
        conn.commit()
    finally:
        conn.close()

# --- Metadata Enrichment ---
async def fetch_tmdb_metadata(title, year, is_tv_show):
    if TMDB_API_KEY == "YOUR_TMDB_API_KEY": return None # Don't run if key is not set
    search_type = 'tv' if is_tv_show else 'movie'
    async with httpx.AsyncClient() as client:
        try:
            search_url = f"{TMDB_API_URL}/search/{search_type}?api_key={TMDB_API_KEY}&query={title}&year={year}"
            response = await client.get(search_url)
            if response.status_code != 200 or not response.json().get('results'):
                return None

            top_result = response.json()['results'][0]
            poster_path = top_result.get('poster_path')
            return {
                "tmdb_id": top_result['id'],
                "poster_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
                "summary": top_result.get('overview', ''),
            }
        except Exception:
            return None

def process_and_enrich_media():
    while True:
        time.sleep(30) # Run periodically
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE media_id IS NULL LIMIT 20")
            files_to_process = cursor.fetchall()

            for file_row in files_to_process:
                meta = extract_metadata(file_row['file_name'])
                if not meta['title']: continue

                # Check for existing media entry
                media_type = 'TV Show' if meta['type'] == 'Episode' else 'Movie'
                cursor.execute("SELECT id FROM media WHERE title = ? AND type = ? AND year = ?", (meta['title'], media_type, meta['year']))
                media_entry = cursor.fetchone()

                media_id = None
                if media_entry:
                    media_id = media_entry['id']
                else:
                    # Fetch from TMDb and create new media entry
                    tmdb_data = asyncio.run(fetch_tmdb_metadata(meta['title'], meta['year'], media_type == 'TV Show'))
                    poster_url = tmdb_data['poster_url'] if tmdb_data else None
                    summary = tmdb_data['summary'] if tmdb_data else ''
                    tmdb_id = tmdb_data['tmdb_id'] if tmdb_data else None

                    insert_cursor = conn.cursor()
                    insert_cursor.execute('''
                        INSERT OR IGNORE INTO media (title, type, year, poster_url, summary, tmdb_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (meta['title'], media_type, meta['year'], poster_url, summary, tmdb_id))
                    conn.commit()
                    media_id = insert_cursor.lastrowid

                if media_id:
                    # Link file to media entry
                    conn.execute("UPDATE files SET media_id = ? WHERE id = ?", (media_id, file_row['id']))
                    conn.commit()
        finally:
            conn.close()

def save_to_db(entries):
    with db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.executemany(
                'INSERT OR IGNORE INTO files (category, source_name, file_name, file_url, year, quality, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)',
                entries
            )
            conn.commit()
        finally:
            conn.close()

# --- Async Scraper ---
async def scrape_url_async(client, category, source_name, url, depth=0, max_depth=3):
    if depth > max_depth: return
    try:
        start_time = asyncio.get_event_loop().time()
        response = await client.get(url, timeout=12.0, follow_redirects=True)
        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        indexing_status['health'][source_name] = {'status': 'Online', 'latency': int(latency)}

        if response.status_code != 200:
            indexing_status['health'][source_name]['status'] = 'Error'
            return

        soup = BeautifulSoup(response.text, 'lxml')
        files_to_save, tasks = [], []

        for link in soup.find_all('a', href=True):
            href, text = link['href'], link.get_text(strip=True)
            if href.startswith(('?', '/')) or 'Parent' in text or 'Name' in text: continue

            full_url = urljoin(url, href)
            if href.endswith('/'):
                tasks.append(scrape_url_async(client, category, source_name, full_url, depth + 1, max_depth))
            else:
                display_name = unquote(href.rstrip('/'))
                if len(text) > 4: display_name = text
                meta = extract_metadata(display_name)
                files_to_save.append((category, source_name, display_name, full_url, meta['year'], meta['quality'], json.dumps(meta)))

                # Live logging for terminal UI
                indexing_status['logs'].append(f"Parsed: {display_name[:40]}")
                if len(indexing_status['logs']) > 15: indexing_status['logs'].pop(0)

        if files_to_save:
            save_to_db(files_to_save)
            indexing_status["count"] += len(files_to_save)
        if tasks: await asyncio.gather(*tasks)
    except Exception:
        indexing_status['health'][source_name] = {'status': 'Offline', 'latency': 0}

def run_async_scraper():
    async def main():
        indexing_status["status"] = "Indexing"
        indexing_status["count"] = 0
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
        async with httpx.AsyncClient(headers=HEADERS, limits=limits, http2=True) as client:
            tasks = [scrape_url_async(client, s['category'], s['name'], s['url']) for s in SOURCES]
            await asyncio.gather(*tasks)
        indexing_status["status"] = "Ready"
    asyncio.run(main())

# --- Search API Logic ---
def parse_natural_query(query):
    filters = {}
    # Year filter
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', query)
    if year_match:
        filters['year'] = year_match.group(1)
        query = query.replace(year_match.group(1), '')

    # Quality filters
    q_map = {'4k': '4K', '2160p': '4K', '1080p': '1080p', '720p': '720p', '480p': '480p'}
    for key, val in q_map.items():
        if key in query.lower():
            filters['quality'] = val
            query = query.replace(key, '')
            break

    return query.strip(), filters

def perform_search(raw_query, category_filter):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        clean_query, filters = parse_natural_query(raw_query)

        # Tokenize for FTS5
        tokens = [f'"{word}*"' for word in clean_query.split() if len(word) > 1]
        fts_query = " OR ".join(tokens) if tokens else f'"{clean_query}"'

        sql_parts = ["SELECT m.*, (SELECT f.file_url FROM files f WHERE f.media_id = m.id LIMIT 1) AS file_url FROM media m JOIN media_fts ON m.id = media_fts.rowid WHERE media_fts MATCH ?"]
        params = [fts_query]

        if category_filter and category_filter != "All":
            # Assuming 'category_filter' maps to media 'type', e.g., 'Movies' or 'TV Series'
            sql_parts.append("AND m.type = ?")
            params.append(category_filter)
        if 'year' in filters:
            sql_parts.append("AND m.year = ?")
            params.append(filters['year'])

        # Note: Quality filter is removed as we search on media, not individual files.
        # This could be added back with a more complex query if needed.

        sql_parts.append("ORDER BY rank LIMIT 50")
        cursor.execute(" ".join(sql_parts), params)
        rows = cursor.fetchall()

        results = [dict(row) for row in rows]
        return results
    finally:
        conn.close()

# --- Flask Routes ---
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def api_status(): return jsonify(indexing_status)

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '')
    c = request.args.get('c', 'All')
    return jsonify(perform_search(q, c))

@app.route('/api/recommend')
def api_recommend():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetch random media items that have a poster
    cursor.execute("SELECT m.*, (SELECT f.file_url FROM files f WHERE f.media_id = m.id LIMIT 1) AS file_url FROM media m WHERE m.poster_url IS NOT NULL ORDER BY RANDOM() LIMIT 12")
    res = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(res)

@app.route('/api/progress', methods=['GET', 'POST'])
def api_progress():
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.json
        conn.execute('''
            INSERT OR REPLACE INTO watch_history (file_url, title, progress_time, duration, last_watched)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (data['url'], data['title'], data['time'], data['duration']))
        conn.commit()
        conn.close()
        return jsonify({"status": "saved"})
    else:
        cursor = conn.execute("SELECT * FROM watch_history ORDER BY last_watched DESC LIMIT 10")
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(history)

@app.route('/api/media/<int:media_id>/episodes')
def api_get_episodes(media_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE media_id = ? ORDER BY meta_json", (media_id,))

    seasons = {}
    for row in cursor.fetchall():
        meta = json.loads(row['meta_json'])
        season_num = meta.get('season')
        episode_num = meta.get('episode')

        if season_num is not None:
            if season_num not in seasons:
                seasons[season_num] = []
            seasons[season_num].append({
                'episode': episode_num,
                'file_name': row['file_name'],
                'file_url': row['file_url'],
                'quality': row['quality']
            })

    # Sort episodes within each season
    for season_num in seasons:
        seasons[season_num].sort(key=lambda x: x['episode'])

    conn.close()
    return jsonify(seasons)

@app.route('/api/media/<int:media_id>/download')
def download_series(media_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_name, file_url FROM files WHERE media_id = ? ORDER BY file_name", (media_id,))
    files = cursor.fetchall()
    conn.close()

    html = "<h1>Download Links</h1><ul>"
    for file in files:
        html += f'<li><a href="{file["file_url"]}" download>{file["file_name"]}</a></li>'
    html += "</ul>"
    return html

# --- The UI Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="netflix">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Extreme Media Hub</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root { --bg: #141414; --sidebar: #000; --card: #1f1f1f; --text: #fff; --accent: #e50914; --border: #333; --glow: 0 0 15px rgba(229, 9, 20, 0.4); }
        [data-theme="cyberpunk"] { --bg: #050505; --sidebar: #0a0a0a; --card: #111; --text: #00ff9d; --accent: #00ff9d; --glow: 0 0 15px rgba(0, 255, 157, 0.4); }

        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; transition: 0.3s; margin: 0; }
        .app-container { display: flex; min-height: 100vh; }

        /* Sidebar Styles */
        .sidebar { width: 280px; background: var(--sidebar); padding: 25px; position: fixed; height: 100vh; border-right: 1px solid var(--border); display: flex; flex-direction: column; z-index: 1000; }
        .brand { font-size: 2rem; font-weight: 900; color: var(--accent); margin-bottom: 40px; letter-spacing: -1px; text-shadow: var(--glow); cursor: pointer; }
        .nav-btn { padding: 12px 15px; margin-bottom: 8px; border-radius: 10px; cursor: pointer; color: #aaa; transition: 0.2s; display: flex; align-items: center; }
        .nav-btn:hover, .nav-btn.active { background: rgba(255,255,255,0.08); color: #fff; }
        .nav-btn i { width: 25px; font-size: 1.1rem; }

        /* Main Content */
        .main-content { margin-left: 280px; flex: 1; padding: 40px; width: calc(100% - 280px); }
        .search-box { position: relative; max-width: 900px; margin: 0 auto 50px; }
        .search-input { width: 100%; background: #222; border: 1px solid var(--border); padding: 18px 60px; border-radius: 15px; color: #fff; font-size: 1.2rem; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
        .search-input:focus { outline: none; border-color: var(--accent); }

        /* Grid & Cards */
        .media-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 25px; }
        .media-card { background: var(--card); border-radius: 12px; overflow: hidden; border: 1px solid var(--border); transition: 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); cursor: pointer; position: relative; }
        .media-card:hover { transform: translateY(-8px) scale(1.02); border-color: var(--accent); box-shadow: var(--glow); }
        .poster-mock { height: 160px; background: linear-gradient(45deg, #222, #333); display: flex; align-items: center; justify-content: center; font-size: 3rem; color: #444; position: relative; }
        .card-body { padding: 15px; }
        .card-title { font-weight: 600; font-size: 0.95rem; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; height: 2.8em; }

        /* Badges */
        .quality-tag { font-size: 0.7rem; background: var(--accent); color: #000; padding: 2px 8px; border-radius: 4px; font-weight: 800; margin-right: 5px; }
        .year-tag { font-size: 0.8rem; color: #888; }

        /* Resume Progress */
        .progress-container { height: 4px; background: #333; width: 100%; position: absolute; bottom: 0; left: 0; }
        .progress-fill { height: 100%; background: var(--accent); box-shadow: var(--glow); }

        /* Monitor Widgets */
        .monitor-panel { margin-top: auto; padding-top: 20px; border-top: 1px solid var(--border); }
        .terminal { background: #000; font-family: 'Consolas', monospace; font-size: 0.7rem; color: #0f0; padding: 12px; border-radius: 8px; height: 150px; overflow-y: auto; border: 1px solid #222; margin-bottom: 15px; }
        .health-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 8px; }
        .bg-online { background: #0f0; box-shadow: 0 0 8px #0f0; }
        .bg-offline { background: #f00; }

        /* Animations */
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade { animation: fadeIn 0.5s ease forwards; }

        .download-icon { position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.7); color: #fff; width: 35px; height: 35px; display: flex; align-items: center; justify-content: center; border-radius: 50%; text-decoration: none; transition: 0.2s; }
        .download-icon:hover { background: var(--accent); }

        .episode-list-item { display: flex; align-items: center; padding: 12px; border-radius: 8px; transition: 0.2s; }
        .episode-list-item:hover { background: rgba(255,255,255,0.08); }
    </style>
</head>
<body>
<div class="app-container">
    <div class="sidebar">
        <div class="brand" onclick="loadHome()">EXTREME</div>

        <div class="nav-btn active" id="btnHome" onclick="loadHome()"><i class="fas fa-house"></i> Home</div>
        <div class="nav-btn" onclick="toggleTheme()"><i class="fas fa-wand-magic-sparkles"></i> Switch Theme</div>

        <div class="mt-4 mb-2 small text-muted text-uppercase fw-bold" style="font-size: 0.65rem">Server Health</div>
        <div id="healthMonitor" class="mb-3"></div>

        <div class="mt-2 mb-2 small text-muted text-uppercase fw-bold" style="font-size: 0.65rem">Indexing Logs</div>
        <div class="terminal" id="term"></div>

        <div class="mt-auto pt-3 text-center">
            <small class="text-muted" id="totalCount">0 files indexed</small>
        </div>
    </div>

    <div class="main-content">
        <div class="search-box d-flex" style="max-width: 900px; margin: 0 auto 50px;">
            <div class="flex-grow-1 position-relative">
                <i class="fas fa-search position-absolute" style="left:22px; top: 22px; color:#666; font-size: 1.2rem;"></i>
                <input type="text" id="searchInput" class="search-input" placeholder="Search movies, series, or try '2024 4K'..." style="border-radius: 15px 0 0 15px; padding-left: 55px;">
            </div>
            <button id="searchButton" class="btn btn-danger" style="border-radius: 0 15px 15px 0; font-size: 1.2rem; padding: 0 30px;">
                <i class="fas fa-arrow-right"></i>
            </button>
        </div>

        <div id="viewArea">
            <!-- Content Loads Here -->
        </div>
    </div>
</div>

<!-- Series Episode Modal -->
<div class="modal fade" id="seriesModal" tabindex="-1">
    <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
        <div class="modal-content" style="background: #181818; color: #fff;">
            <div class="modal-header border-0">
                <h5 class="modal-title" id="seriesModalTitle">Episodes</h5>
                <a href="#" id="seriesDownloadLink" class="btn btn-sm btn-outline-danger ms-auto me-3"><i class="fas fa-download me-2"></i>Download Series</a>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body" id="seriesModalBody" style="background: #141414;">
                <!-- Episode list will be injected here -->
            </div>
        </div>
    </div>
</div>

<!-- Video Player Modal -->
<div class="modal fade" id="videoModal" data-bs-backdrop="static" tabindex="-1">
    <div class="modal-dialog modal-fullscreen">
        <div class="modal-content bg-black border-0">
            <div class="modal-header border-0 p-3 position-absolute top-0 w-100" style="z-index: 10; background: linear-gradient(to bottom, rgba(0,0,0,0.8), transparent)">
                <h5 class="modal-title text-white" id="videoTitle">Playing...</h5>
                <div class="ms-auto">
                    <a id="videoDownloadLink" href="#" class="btn btn-outline-light me-3" download><i class="fas fa-download me-2"></i>Download</a>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" onclick="stopVideo()"></button>
                </div>
            </div>
            <div class="modal-body p-0 d-flex align-items-center justify-content-center">
                <video id="player" controls style="width:100%; max-height: 100vh;" autoplay></video>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    let currentTheme = 'netflix';
    let searchTimer;
    let activeVideo = null;

    async function init() {
        await loadHome();
        startStatusLoop();
    }

    async function loadHome() {
        document.getElementById('viewArea').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-danger"></div></div>';

        // Load History
        const hRes = await fetch('/api/progress');
        const history = await hRes.json();

        // Load Recommendations
        const rRes = await fetch('/api/recommend');
        const recommended = await rRes.json();

        let html = '';

        if (history.length > 0) {
            html += `<h4 class="mb-4">Continue Watching</h4><div class="media-grid mb-5">`;
            html += history.map(item => renderCard({
                file_name: item.title,
                file_url: item.file_url,
                progress: (item.progress_time / item.duration) * 100,
                resumeTime: item.progress_time
            })).join('');
            html += `</div>`;
        }

        html += `<h4 class="mb-4">Recommended For You</h4><div class="media-grid">`;
        html += recommended.map(item => renderCard(item)).join('');
        html += `</div>`;

        document.getElementById('viewArea').innerHTML = html;
        document.getElementById('btnHome').classList.add('active');
    }

    function renderCard(item) {
        const isMovie = item.type === 'Movie';
        const posterUrl = item.poster_url || 'https://via.placeholder.com/500x750.png?text=No+Image';

        return `
            <div class="media-card animate-fade" onclick="${isMovie ? `play('${item.file_url}', '${item.title.replace(/'/g, "\\'")}')` : `openSeriesModal(${item.id}, '${item.title.replace(/'/g, "\\'")}')`}">
                <div class="poster-mock" style="background-image: url('${posterUrl}'); background-size: cover; background-position: center;">
                    <a href="${item.file_url}" download class="download-icon"><i class="fas fa-download"></i></a>
                </div>
                <div class="card-body">
                    <div class="card-title" title="${item.title}">${item.title}</div>
                    <div class="d-flex align-items-center">
                        <span class="year-tag">${item.year || ''}</span>
                    </div>
                </div>
            </div>
        `;
    }

    function play(url, title, startTime = 0) {
        if (!url) { // Handle series where the card itself is not playable
            alert("Please select an episode to play.");
            return;
        }
        activeVideo = { url, title };
        const v = document.getElementById('player');
        document.getElementById('videoTitle').innerText = title;
        document.getElementById('videoDownloadLink').href = url;
        v.src = url;
        v.currentTime = startTime;

        const modal = new bootstrap.Modal('#videoModal');
        modal.show();

        // Save progress every 10 seconds
        v.ontimeupdate = () => {
            if (v.currentTime > 0 && Math.floor(v.currentTime) % 10 === 0) {
                saveProgress(url, title, v.currentTime, v.duration);
            }
        };
    }

    async function openSeriesModal(mediaId, title) {
        document.getElementById('seriesModalTitle').innerText = title;
        document.getElementById('seriesDownloadLink').href = `/api/media/${mediaId}/download`;
        const body = document.getElementById('seriesModalBody');
        body.innerHTML = '<div class="text-center p-5"><div class="spinner-border"></div></div>';

        const seriesModal = new bootstrap.Modal('#seriesModal');
        seriesModal.show();

        const res = await fetch(`/api/media/${mediaId}/episodes`);
        const seasons = await res.json();

        let html = '';
        for (const seasonNum in seasons) {
            html += `<h5 class="mt-4 mb-3">Season ${seasonNum}</h5>`;
            seasons[seasonNum].forEach(ep => {
                html += `
                    <div class="episode-list-item">
                        <div class="fw-bold me-3" style="width: 25px;">${ep.episode}</div>
                        <div class="flex-grow-1">${ep.file_name}</div>
                        <div class="text-muted small me-3">${ep.quality}</div>
                        <button class="btn btn-sm btn-outline-light" onclick="play('${ep.file_url}', '${ep.file_name.replace(/'/g, "\\'")}')"><i class="fas fa-play"></i></button>
                    </div>
                `;
            });
        }
        body.innerHTML = html;
    }

    function stopVideo() {
        const v = document.getElementById('player');
        saveProgress(activeVideo.url, activeVideo.title, v.currentTime, v.duration);
        v.pause();
        v.src = "";
        activeVideo = null;
    }

    async function saveProgress(url, title, time, duration) {
        if (!time || !duration) return;
        await fetch('/api/progress', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url, title, time, duration})
        });
    }

    function toggleTheme() {
        currentTheme = currentTheme === 'netflix' ? 'cyberpunk' : 'netflix';
        document.documentElement.setAttribute('data-theme', currentTheme);
    }

    function triggerSearch() {
        const q = document.getElementById('searchInput').value;
        document.getElementById('btnHome').classList.remove('active');
        if (q.length < 2) {
            loadHome();
            return;
        }
        clearTimeout(searchTimer);
        searchTimer = setTimeout(async () => {
            const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            renderResults(`Results for "${q}"`, data);
        }, 300);
    }

    document.getElementById('searchInput').addEventListener('input', triggerSearch);
    document.getElementById('searchButton').addEventListener('click', triggerSearch);

    function renderResults(title, items) {
        if (items.length === 0) {
            document.getElementById('viewArea').innerHTML = `<h4>${title}</h4><p class="text-muted">No matches found.</p>`;
            return;
        }
        let html = `<h4 class="mb-4">${title}</h4><div class="media-grid">`;
        html += items.map(item => renderCard(item)).join('');
        document.getElementById('viewArea').innerHTML = html + '</div>';
    }

    function startStatusLoop() {
        setInterval(async () => {
            const res = await fetch('/api/status');
            const data = await res.json();

            // Terminal Logs
            const term = document.getElementById('term');
            term.innerHTML = data.logs.map(l => `<div>> ${l}</div>`).join('');
            term.scrollTop = term.scrollHeight;

            // Health Monitor
            let hHtml = '';
            for (const [name, info] of Object.entries(data.health)) {
                const cls = info.status === 'Online' ? 'bg-online' : 'bg-offline';
                hHtml += `
                    <div class="d-flex justify-content-between align-items-center mb-1" style="font-size:0.75rem">
                        <span><span class="health-dot ${cls}"></span>${name}</span>
                        <span class="text-muted">${info.latency}ms</span>
                    </div>
                `;
            }
            document.getElementById('healthMonitor').innerHTML = hHtml;
            document.getElementById('totalCount').innerText = `${data.count.toLocaleString()} files indexed`;
        }, 2000);
    }

    init();
</script>
</body>
</html>
"""

if __name__ == '__main__':
    init_db()
    # Start high-speed background scraper thread
    threading.Thread(target=run_async_scraper, daemon=True).start()
    # Start metadata enrichment thread
    threading.Thread(target=process_and_enrich_media, daemon=True).start()
    app.run(port=5000)