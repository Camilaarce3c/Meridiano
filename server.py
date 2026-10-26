"""Meridiano: servidor con base de datos SQLite. Solo usa la biblioteca estándar de Python."""
import json, os, re, secrets, sqlite3, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, 'meridiano.db')
PASS = os.environ.get('MERIDIANO_PASS', 'meridiano2026')
PORT = int(os.environ.get('PORT', 5002))
SESS = set()
STATIC = {'.html': 'text/html; charset=utf-8', '.png': 'image/png', '.webmanifest': 'application/manifest+json', '.js': 'text/javascript'}

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS dest(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,region TEXT,emoji TEXT,color TEXT,descr TEXT,tips TEXT,price REAL,ex TEXT);
    CREATE TABLE IF NOT EXISTS media(id INTEGER PRIMARY KEY AUTOINCREMENT,src TEXT,cap TEXT,dn TEXT,status TEXT,created TEXT);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,cid TEXT,dest INTEGER,name TEXT,amount REAL,fmt TEXT,created TEXT);''')
    if not c.execute('SELECT 1 FROM dest').fetchone():
        seed = json.load(open(os.path.join(ROOT, 'seed.json'), encoding='utf-8'))
        for d in seed['dest']:
            ex = seed['ex'].get(str(d['id']))
            c.execute('INSERT INTO dest(id,name,region,emoji,color,descr,tips,price,ex) VALUES(?,?,?,?,?,?,?,?,?)',
                (d['id'], d['name'], d['region'], d['emoji'], d.get('c', ''), d['desc'], json.dumps(d['tips'], ensure_ascii=False), d['price'],
                 json.dumps(ex, ensure_ascii=False) if ex else None))
    c.commit(); c.close()

def now(): return time.strftime('%d/%m/%Y %H:%M')

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, obj, extra=None):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def sid(self):
        m = re.search(r'sid=([A-Za-z0-9_-]+)', self.headers.get('Cookie', ''))
        return m.group(1) if m else None
    def admin(self): return self.sid() in SESS
    def cid(self): return re.sub(r'[^A-Za-z0-9_-]', '', self.headers.get('X-Client', ''))[:40]
    def body(self):
        n = int(self.headers.get('Content-Length', 0))
        if n > 3000000: raise ValueError('grande')
        return json.loads(self.rfile.read(n) or b'{}')

    def do_GET(self):
        p = urlparse(self.path).path
        if p == '/api/state': return self.state()
        if p.startswith('/api/'): return self.send(404, {'error': 'no'})
        p = 'index.html' if p == '/' else p.lstrip('/')
        f = os.path.normpath(os.path.join(ROOT, p))
        ext = os.path.splitext(f)[1]
        if not f.startswith(ROOT) or ext not in STATIC or not os.path.isfile(f):
            self.send_response(404); self.end_headers(); return
        data = open(f, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', STATIC[ext]); self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers(); self.wfile.write(data)

    def state(self):
        adm, cid, c = self.admin(), self.cid(), db()
        rows = c.execute('SELECT * FROM dest ORDER BY id').fetchall()
        dest = [{'id': r['id'], 'name': r['name'], 'region': r['region'], 'emoji': r['emoji'], 'c': r['color'], 'desc': r['descr'], 'tips': json.loads(r['tips'] or '[]'), 'price': r['price']} for r in rows]
        ex = {r['id']: json.loads(r['ex']) for r in rows if r['ex']}
        q = "SELECT * FROM media WHERE status='ok'" + (" OR status='pending'" if adm else '') + ' ORDER BY id DESC'
        media = [{'id': r['id'], 'src': r['src'], 'cap': r['cap'], 'dn': r['dn'], 'status': r['status']} for r in c.execute(q)]
        om = lambda r: {'dest': r['dest'], 'name': r['name'], 'amount': r['amount'], 'fmt': r['fmt'], 'status': 'paid', 'date': r['created']}
        mine = [om(r) for r in c.execute('SELECT * FROM orders WHERE cid=?', (cid,))] if cid else []
        allo = [om(r) for r in c.execute('SELECT * FROM orders ORDER BY id DESC')] if adm else []
        c.close()
        self.send(200, {'dest': dest, 'ex': ex, 'media': media, 'orders': mine, 'allOrders': allo, 'admin': adm})

    def do_POST(self): self.mut('POST')
    def do_DELETE(self): self.mut('DELETE')
    def do_PUT(self): self.mut('PUT')

    def mut(self, verb):
        p = urlparse(self.path).path
        try:
            b = self.body() if verb in ('POST', 'PUT') else {}
            if p == '/api/login':
                if not secrets.compare_digest(str(b.get('password', '')), PASS): return self.send(401, {'error': 'clave'})
                s = secrets.token_urlsafe(24); SESS.add(s)
                return self.send(200, {'ok': 1}, {'Set-Cookie': 'sid=%s; HttpOnly; SameSite=Lax; Path=/' % s})
            if p == '/api/logout':
                SESS.discard(self.sid()); return self.send(200, {'ok': 1}, {'Set-Cookie': 'sid=; Max-Age=0; Path=/'})
            if p == '/api/media' and verb == 'POST':
                src = str(b.get('src', ''))
                if not re.match(r'^data:image/(jpeg|png);base64,[A-Za-z0-9+/=]+$', src): return self.send(400, {'error': 'imagen'})
                c = db(); c.execute('INSERT INTO media(src,cap,dn,status,created) VALUES(?,?,?,?,?)', (src, str(b.get('cap', ''))[:120], str(b.get('dn', ''))[:60], 'pending', now())); c.commit(); c.close()
                return self.send(200, {'ok': 1})
            if p == '/api/order' and verb == 'POST':
                c = db(); d = c.execute('SELECT * FROM dest WHERE id=?', (b.get('dest'),)).fetchone()
                if not d or not self.cid(): c.close(); return self.send(400, {'error': 'pedido'})
                c.execute('INSERT INTO orders(cid,dest,name,amount,fmt,created) VALUES(?,?,?,?,?,?)', (self.cid(), d['id'], d['name'], d['price'], str(b.get('fmt', ''))[:40], now())); c.commit(); c.close()
                return self.send(200, {'ok': 1})
            if not self.admin(): return self.send(401, {'error': 'admin'})
            c = db()
            m = re.match(r'^/api/media/(\d+)/(ok|no)$', p)
            if m and verb == 'POST':
                if m.group(2) == 'ok': c.execute("UPDATE media SET status='ok' WHERE id=?", (m.group(1),))
                else: c.execute('DELETE FROM media WHERE id=?', (m.group(1),))
            elif p == '/api/dest' and verb == 'POST':
                name = str(b.get('name', '')).strip()[:60]
                if not name: c.close(); return self.send(400, {'error': 'nombre'})
                tips = [str(t)[:120] for t in b.get('tips', [])][:12]
                c.execute('INSERT INTO dest(name,region,emoji,color,descr,tips,price) VALUES(?,?,?,?,?,?,?)', (name, str(b.get('region', ''))[:60], str(b.get('emoji') or '')[:8], '#e7e3ee', str(b.get('desc', ''))[:2000], json.dumps(tips, ensure_ascii=False), max(0, float(b.get('price', 0) or 0))))
            else:
                m = re.match(r'^/api/dest/(\d+)$', p)
                if m and verb == 'DELETE': c.execute('DELETE FROM dest WHERE id=?', (m.group(1),))
                elif m and verb == 'PUT':
                    name = str(b.get('name', '')).strip()[:60]
                    if not name: c.close(); return self.send(400, {'error': 'nombre'})
                    ex = b.get('ex') or {}
                    st = lambda v, n=300: str(v or '')[:n]
                    ls = lambda v: [str(t)[:600] for t in (v or [])][:15]
                    exo = {'best': st(ex.get('best'), 80), 'days': st(ex.get('days'), 40), 'bud': max(0, float(ex.get('bud') or 0)), 'mon': st(ex.get('mon'), 40), 'lang': st(ex.get('lang'), 40), 'ver': ls(ex.get('ver')), 'dias': ls(ex.get('dias')), 'comer': ls(ex.get('comer'))}
                    has = exo['best'] or exo['days'] or exo['ver'] or exo['dias'] or exo['comer']
                    c.execute('UPDATE dest SET name=?,region=?,emoji=?,descr=?,tips=?,price=?,ex=? WHERE id=?', (name, st(b.get('region'), 60), st(b.get('emoji'), 8), st(b.get('desc'), 2000), json.dumps(ls(b.get('tips')), ensure_ascii=False), max(0, float(b.get('price') or 0)), json.dumps(exo, ensure_ascii=False) if has else None, m.group(1)))
                else: c.close(); return self.send(404, {'error': 'no'})
            c.commit(); c.close(); self.send(200, {'ok': 1})
        except Exception:
            self.send(400, {'error': 'solicitud'})

if __name__ == '__main__':
    init()
    print('Meridiano listo en http://localhost:%d  (clave del panel: %s)' % (PORT, PASS))
    print('Cierra con Ctrl + C')
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
