
import http.server
import socketserver
import json
import sqlite3
from urllib.parse import urlparse, parse_qs

PORT = 8000

class SearchRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # API requests
        if self.path.startswith('/api/search'):
            query_components = parse_qs(urlparse(self.path).query)
            search_term = query_components.get("q", [""])[0]

            results = self.search_database(search_term)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(results).encode())
            return

        # Serve static files from the 'app' directory
        if self.path == "/":
            self.path = "/app/templates/index.html"
        else:
            self.path = "/app" + self.path

        super().do_GET()

    def search_database(self, term):
        """Searches the database for a given term and returns the results."""
        conn = sqlite3.connect('search_engine.db')
        cursor = conn.cursor()

        # Use LIKE for partial matches
        cursor.execute("SELECT title, url, source_url, category, year, quality, season, episode FROM files WHERE title LIKE ?", ('%' + term + '%',))

        rows = cursor.fetchall()
        conn.close()

        # Convert results to a list of dictionaries for JSON serialization
        results = []
        for row in rows:
            results.append({
                "title": row[0],
                "url": row[1],
                "source_url": row[2],
                "category": row[3],
                "year": row[4],
                "quality": row[5],
                "season": row[6],
                "episode": row[7],
            })
        return results

with socketserver.TCPServer(("", PORT), SearchRequestHandler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()
