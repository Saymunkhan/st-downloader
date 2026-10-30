"""
ST DOWNLOADER - Facebook / YouTube / TikTok video downloader with Admin Panel
Run:  python app.py   then open  http://localhost:5000
Admin panel:  http://localhost:5000/admin   (password: admin123 -> CHANGE IT)
Change password:  ADMIN_PASSWORD=yourpass python app.py
"""
import os
import secrets
import shutil
import sqlite3
import tempfile
from datetime import datetime
from functools import wraps
from io import BytesIO
from urllib.parse import urlparse

import yt_dlp
from flask import (Flask, Response, redirect, render_template_string, request,
                   send_file, session, url_for)

APP_NAME = "ST DOWNLOADER"
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "st.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)


# ---------------------------------------------------------------- database
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY, ts TEXT, platform TEXT, url TEXT,
            kind TEXT, status TEXT, ip TEXT)""")
        c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT)")
        for k, v in [("youtube", "1"), ("facebook", "1"), ("tiktok", "1"),
                     ("maintenance", "0"), ("notice", "")]:
            c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))


def get_settings():
    with db() as c:
        return {r["k"]: r["v"] for r in c.execute("SELECT k, v FROM settings")}


def set_setting(k, v):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))


def log(platform, url, kind, status):
    with db() as c:
        c.execute("INSERT INTO history(ts,platform,url,kind,status,ip) VALUES(?,?,?,?,?,?)",
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), platform, url, kind,
                   status, request.remote_addr))


# ---------------------------------------------------------------- helpers
def platform_of(url):
    if "://" not in url:
        url = "https://" + url
    host = urlparse(url).netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "facebook.com" in host or "fb.watch" in host:
        return "facebook"
    if "tiktok.com" in host:
        return "tiktok"
    return None


def ydl_options(outdir, audio, hq):
    opts = {
        "outtmpl": os.path.join(outdir, "%(title).80s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "restrictfilenames": True,
    }
    if audio:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                   "preferredcodec": "mp3", "preferredquality": "192"}]
    elif hq:
        opts["format"] = "bv*+ba/b"
        opts["merge_output_format"] = "mp4"
    else:
        opts["format"] = "best[ext=mp4]/best"
    return opts


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*a, **kw)
    return wrapper


# ---------------------------------------------------------------- templates
CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,sans-serif;background:#0b1220;color:#e5e7eb;
     display:flex;justify-content:center;padding:20px}
.wrap{width:100%;max-width:520px}
.card{background:#162036;padding:20px;border-radius:16px;margin-bottom:16px}
h1{margin:0 0 4px;font-size:24px;letter-spacing:1px}
h2{margin:0 0 12px;font-size:17px}
.sub{color:#94a3b8;font-size:13px;margin-bottom:14px}
input[type=text],input[type=password]{width:100%;padding:13px;border-radius:10px;
     border:1px solid #334155;background:#0b1220;color:#e5e7eb;font-size:15px}
label{display:block;margin:10px 0;font-size:14px}
button,.btn{display:inline-block;width:100%;padding:13px;border:0;border-radius:10px;
     background:#2563eb;color:#fff;font-size:16px;cursor:pointer;text-align:center;
     text-decoration:none;margin-top:6px}
.btn-red{background:#b91c1c}.btn-gray{background:#334155}
.err{background:#7f1d1d;padding:10px;border-radius:10px;margin-bottom:12px;font-size:14px}
.notice{background:#1e3a8a;padding:10px;border-radius:10px;margin-bottom:12px;font-size:14px}
.warn{background:#78350f;padding:10px;border-radius:10px;margin-bottom:12px;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.stat{background:#0b1220;border-radius:12px;padding:12px;text-align:center}
.stat b{display:block;font-size:24px}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{padding:6px 4px;border-bottom:1px solid #263248;text-align:left;
      word-break:break-all;vertical-align:top}
.ok{color:#4ade80}.fail{color:#f87171}
small{color:#94a3b8}
"""

HEAD = """
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0b1220">
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon.svg">
<link rel="apple-touch-icon" href="/icon.svg">
<style>""" + CSS + """</style>
"""

HOME = """<!doctype html><html><head><title>ST DOWNLOADER</title>""" + HEAD + """</head><body>
<div class="wrap"><div class="card">
  <h1>ST DOWNLOADER</h1>
  <div class="sub">Facebook &bull; YouTube &bull; TikTok</div>
  {% if s.notice %}<div class="notice">{{ s.notice }}</div>{% endif %}
  {% if s.maintenance == '1' %}<div class="warn">Ekhon maintenance cholche. Pore chesta korun.</div>{% endif %}
  <form method="post" onsubmit="document.getElementById('b').textContent='Downloading... opekkha korun'">
    <input type="text" name="url" placeholder="Video-r link ekhane paste korun" required>
    <label><input type="checkbox" name="hq"> Best quality <small>(ffmpeg lagbe)</small></label>
    <label><input type="checkbox" name="audio"> Shudhu audio MP3 <small>(ffmpeg lagbe)</small></label>
    <button id="b" type="submit">Download</button>
  </form>
  {% if error %}<div class="err" style="margin-top:12px">{{ error }}</div>{% endif %}
</div>
<small>Shudhu nijer video ba jeta download korar anumoti ache, setar jonno use korun.</small>
</div>
<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js');}</script>
</body></html>"""

LOGIN = """<!doctype html><html><head><title>Admin Login</title>""" + HEAD + """</head><body>
<div class="wrap"><div class="card">
  <h1>Admin Login</h1><div class="sub">ST DOWNLOADER</div>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="post">
    <input type="password" name="password" placeholder="Password" required>
    <button type="submit">Login</button>
  </form>
  <a class="btn btn-gray" href="/">Back</a>
</div></div></body></html>"""

ADMIN = """<!doctype html><html><head><title>Admin - ST DOWNLOADER</title>""" + HEAD + """</head><body>
<div class="wrap">
  <div class="card">
    <h1>Admin Panel</h1><div class="sub">ST DOWNLOADER</div>
    {% if default_pw %}<div class="warn">Apni default password (admin123) use korchen. Bodle nin:
      <code>ADMIN_PASSWORD=notunpass python app.py</code></div>{% endif %}
    <div class="grid">
      <div class="stat"><b>{{ total }}</b>Total</div>
      <div class="stat"><b>{{ today }}</b>Aj</div>
      <div class="stat"><b>{{ ok }}</b>Successful</div>
      <div class="stat"><b>{{ failed }}</b>Failed</div>
    </div>
    <p><small>YouTube: {{ plat.get('youtube',0) }} &nbsp; Facebook: {{ plat.get('facebook',0) }}
       &nbsp; TikTok: {{ plat.get('tiktok',0) }}</small></p>
  </div>

  <div class="card">
    <h2>Settings</h2>
    <form method="post" action="/admin/settings">
      <label><input type="checkbox" name="youtube" {{ 'checked' if s.youtube=='1' }}> YouTube chalu</label>
      <label><input type="checkbox" name="facebook" {{ 'checked' if s.facebook=='1' }}> Facebook chalu</label>
      <label><input type="checkbox" name="tiktok" {{ 'checked' if s.tiktok=='1' }}> TikTok chalu</label>
      <label><input type="checkbox" name="maintenance" {{ 'checked' if s.maintenance=='1' }}> Maintenance mode (download bondho)</label>
      <label>Home page notice <small>(khali rakhle dekhabe na)</small></label>
      <input type="text" name="notice" value="{{ s.notice }}">
      <button type="submit">Save</button>
    </form>
  </div>

  <div class="card">
    <h2>Recent downloads</h2>
    <table>
      <tr><th>Time</th><th>Site</th><th>Status</th></tr>
      {% for r in rows %}
      <tr><td>{{ r.ts[5:16] }}</td>
          <td>{{ r.platform }}<br><small>{{ r.kind }}</small></td>
          <td class="{{ 'ok' if r.status=='ok' else 'fail' }}">{{ r.status[:40] }}</td></tr>
      <tr><td colspan="3"><small>{{ r.url }} &middot; {{ r.ip }}</small></td></tr>
      {% else %}<tr><td colspan="3"><small>Ekhono kono download nai.</small></td></tr>
      {% endfor %}
    </table>
    <form method="post" action="/admin/clear" onsubmit="return confirm('Shob history muche felben?')">
      <button class="btn-red" type="submit">History clear korun</button>
    </form>
  </div>
  <a class="btn btn-gray" href="/">Home</a>
  <a class="btn btn-gray" href="/admin/logout">Logout</a>
</div></body></html>"""


class Obj(dict):
    __getattr__ = dict.get


# ---------------------------------------------------------------- public routes
@app.route("/", methods=["GET", "POST"])
def home():
    s = Obj(get_settings())
    if request.method == "GET":
        return render_template_string(HOME, s=s, error=None)

    url = request.form.get("url", "").strip()
    audio = "audio" in request.form
    hq = "hq" in request.form
    kind = "audio" if audio else ("hq" if hq else "video")

    if s.maintenance == "1":
        return render_template_string(HOME, s=s, error="Maintenance cholche.")
    plat = platform_of(url)
    if not plat:
        return render_template_string(
            HOME, s=s, error="Shudhu Facebook, YouTube ba TikTok-er link din.")
    if s.get(plat) != "1":
        return render_template_string(
            HOME, s=s, error=f"{plat.title()} download ekhon bondho ache.")

    tmp = tempfile.mkdtemp()
    try:
        with yt_dlp.YoutubeDL(ydl_options(tmp, audio, hq)) as ydl:
            ydl.download([url])
        files = os.listdir(tmp)
        if not files:
            raise RuntimeError("Kono file paoa jayni.")
        name = files[0]
        with open(os.path.join(tmp, name), "rb") as f:
            data = f.read()
        shutil.rmtree(tmp, ignore_errors=True)
        log(plat, url, kind, "ok")
        return send_file(BytesIO(data), as_attachment=True, download_name=name)
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        msg = str(e).replace("ERROR: ", "")[:200]
        log(plat, url, kind, "failed: " + msg)
        return render_template_string(HOME, s=s, error="Download hoyni: " + msg)


@app.route("/manifest.json")
def manifest():
    return Response("""{
  "name": "ST DOWNLOADER", "short_name": "ST DOWNLOADER",
  "start_url": "/", "display": "standalone",
  "background_color": "#0b1220", "theme_color": "#0b1220",
  "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}]
}""", mimetype="application/manifest+json")


@app.route("/icon.svg")
def icon():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" rx="110" fill="#2563eb"/>
<text x="256" y="215" font-family="Arial,sans-serif" font-size="150" font-weight="bold"
      fill="#fff" text-anchor="middle">ST</text>
<path d="M256 270v110M206 335l50 50 50-50" stroke="#fff" stroke-width="30"
      fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<rect x="150" y="410" width="212" height="26" rx="13" fill="#fff"/></svg>"""
    return Response(svg, mimetype="image/svg+xml")


@app.route("/sw.js")
def sw():
    return Response("self.addEventListener('fetch',function(){});",
                    mimetype="application/javascript")


# ---------------------------------------------------------------- admin routes
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template_string(LOGIN, error="Password vul.")
    return render_template_string(LOGIN, error=None)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin():
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        ok = c.execute("SELECT COUNT(*) FROM history WHERE status='ok'").fetchone()[0]
        today = c.execute("SELECT COUNT(*) FROM history WHERE ts LIKE ?",
                          (datetime.now().strftime("%Y-%m-%d") + "%",)).fetchone()[0]
        plat = {r[0]: r[1] for r in c.execute(
            "SELECT platform, COUNT(*) FROM history WHERE status='ok' GROUP BY platform")}
        rows = [Obj(r) for r in c.execute(
            "SELECT * FROM history ORDER BY id DESC LIMIT 30")]
    return render_template_string(
        ADMIN, total=total, ok=ok, failed=total - ok, today=today, plat=plat,
        rows=rows, s=Obj(get_settings()), default_pw=(ADMIN_PASSWORD == "admin123"))


@app.route("/admin/settings", methods=["POST"])
@admin_required
def admin_settings():
    for k in ("youtube", "facebook", "tiktok", "maintenance"):
        set_setting(k, "1" if k in request.form else "0")
    set_setting("notice", request.form.get("notice", "").strip()[:200])
    return redirect(url_for("admin"))


@app.route("/admin/clear", methods=["POST"])
@admin_required
def admin_clear():
    with db() as c:
        c.execute("DELETE FROM history")
    return redirect(url_for("admin"))


init_db()  # runs under gunicorn too

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
