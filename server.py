import http.server
import json
import os
import sys
import sqlite3
import urllib.parse
import mimetypes
import io

PORT = int(os.environ.get('PORT', 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            location TEXT,
            requester TEXT,
            phone TEXT,
            priority TEXT,
            description TEXT,
            images TEXT,
            status TEXT,
            date TEXT,
            completedDate TEXT,
            startDate TEXT,
            note TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            user TEXT,
            action TEXT,
            requestId TEXT,
            detail TEXT
        )
    ''')
    try:
        c.execute('ALTER TABLE requests ADD COLUMN invUsed TEXT DEFAULT "[]"')
    except:
        pass
    conn.commit()
    conn.close()

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn

class APIHandler:
    @staticmethod
    def handle(parsed_path, method, body):
        path = parsed_path.path
        parts = path.strip('/').split('/')

        if method == 'GET' and path == '/api/requests':
            conn = get_conn()
            rows = conn.execute('SELECT * FROM requests ORDER BY date DESC').fetchall()
            for r in rows:
                if r['images']:
                    try:
                        r['images'] = json.loads(r['images'])
                    except:
                        r['images'] = []
                else:
                    r['images'] = []
                if r['invUsed']:
                    try:
                        r['invUsed'] = json.loads(r['invUsed'])
                    except:
                        r['invUsed'] = []
                else:
                    r['invUsed'] = []
            conn.close()
            return 200, rows

        if method == 'POST' and path == '/api/requests':
            data = json.loads(body)
            conn = get_conn()
            conn.execute('''
                INSERT INTO requests (id, title, category, location, requester, phone, priority, description, images, status, date, completedDate, startDate, note, invUsed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['id'], data['title'], data['category'], data['location'],
                data['requester'], data.get('phone', ''), data['priority'],
                data.get('description', ''), json.dumps(data.get('images', [])),
                data['status'], data['date'], data.get('completedDate'),
                data.get('startDate'), data.get('note', ''),
                json.dumps(data.get('invUsed', []))
            ))
            conn.commit()
            conn.close()
            return 200, {'ok': True, 'id': data['id']}

        if method == 'PUT' and len(parts) == 3 and parts[0] == 'api' and parts[1] == 'requests':
            req_id = parts[2]
            data = json.loads(body)
            conn = get_conn()
            existing = conn.execute('SELECT * FROM requests WHERE id = ?', (req_id,)).fetchone()
            if not existing:
                conn.close()
                return 404, {'error': 'Not found'}
            conn.execute('''
                UPDATE requests SET status=?, note=?, completedDate=?, startDate=?, invUsed=?
                WHERE id=?
            ''', (
                data['status'], data.get('note', ''),
                data.get('completedDate'), data.get('startDate'),
                json.dumps(data.get('invUsed', [])),
                req_id
            ))
            conn.commit()
            conn.close()
            return 200, {'ok': True}

        if method == 'DELETE' and len(parts) == 3 and parts[0] == 'api' and parts[1] == 'requests':
            req_id = parts[2]
            conn = get_conn()
            conn.execute('DELETE FROM requests WHERE id = ?', (req_id,))
            conn.commit()
            conn.close()
            return 200, {'ok': True}

        if method == 'GET' and path == '/api/audit':
            conn = get_conn()
            rows = conn.execute('SELECT * FROM audit_log ORDER BY id DESC').fetchall()
            conn.close()
            return 200, rows

        if method == 'POST' and path == '/api/audit':
            data = json.loads(body)
            conn = get_conn()
            conn.execute('''
                INSERT INTO audit_log (time, user, action, requestId, detail)
                VALUES (?, ?, ?, ?, ?)
            ''', (data['time'], data['user'], data['action'], data.get('requestId', ''), data.get('detail', '')))
            conn.commit()
            conn.close()
            return 200, {'ok': True}

        return None

class ServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith('/api/'):
            status, data = APIHandler.handle(parsed, 'GET', None)
            if status:
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404)
                self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode() if content_len else '{}'
        status, data = APIHandler.handle(parsed, 'POST', body)
        if status:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode() if content_len else '{}'
        status, data = APIHandler.handle(parsed, 'PUT', body)
        if status:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        status, data = APIHandler.handle(parsed, 'DELETE', None)
        if status:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    init_db()
    server = http.server.HTTPServer(('0.0.0.0', PORT), ServerHandler)
    print(f'Server berjalan di http://localhost:{PORT}')
    print(f'Buka browser dan pergi ke http://localhost:{PORT}')
    server.serve_forever()
