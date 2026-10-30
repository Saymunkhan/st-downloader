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
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{background:#070b16}
body{margin:0;min-height:100vh;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
     color:#e5e7eb;display:flex;justify-content:center;padding:20px 16px 40px;
     background:radial-gradient(900px 500px at 0% -5%,rgba(37,99,235,.55),transparent 60%),
                radial-gradient(800px 500px at 100% 5%,rgba(139,92,246,.45),transparent 55%),#070b16;
     background-attachment:fixed}
.wrap{width:100%;max-width:520px}
.brand{display:flex;align-items:center;gap:14px;margin:6px 4px 22px}
.logo{width:50px;height:50px;border-radius:15px;display:flex;align-items:center;justify-content:center;
      font-weight:800;font-size:19px;color:#fff;letter-spacing:.5px;
      background:linear-gradient(135deg,#3b82f6,#8b5cf6);box-shadow:0 10px 28px rgba(59,130,246,.45)}
.brand h1{font-size:23px;margin:0;letter-spacing:1.2px}
.brand .tag{color:#94a3b8;font-size:13px;margin-top:2px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}
.chip{font-size:12px;padding:6px 12px;border-radius:999px;font-weight:600;
      background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12)}
.chip.yt{color:#fca5a5}.chip.fb{color:#93c5fd}.chip.tt{color:#5eead4}
.card{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.11);
      backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
      padding:20px;border-radius:22px;margin-bottom:16px;box-shadow:0 22px 50px rgba(0,0,0,.4)}
h1{margin:0 0 4px;font-size:24px;letter-spacing:1px}
h2{margin:0 0 14px;font-size:17px}
.sub{color:#94a3b8;font-size:13px;margin-bottom:14px}
.field{display:flex;gap:8px}
.field input{flex:1;min-width:0}
input[type=text],input[type=password]{width:100%;padding:15px 16px;border-radius:14px;
     border:1px solid rgba(255,255,255,.14);background:rgba(7,11,22,.7);color:#f1f5f9;
     font-size:15px;outline:none;transition:border .15s,box-shadow .15s}
input[type=text]:focus,input[type=password]:focus{border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.3)}
.paste{flex:none;width:auto;margin:0;padding:0 16px;border-radius:14px;font-size:14px;
       background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.14)}
.opts{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 4px}
.opt{position:relative;cursor:pointer}
.opt input{position:absolute;opacity:0}
.opt span{display:inline-block;padding:9px 14px;border-radius:999px;font-size:13px;
          background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);color:#cbd5e1}
.opt input:checked + span{background:linear-gradient(135deg,#2563eb,#7c3aed);border-color:transparent;color:#fff}
label{display:block;margin:12px 0;font-size:14px}
button,.btn{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;
     padding:15px;border:0;border-radius:14px;color:#fff;font-size:16px;font-weight:600;
     cursor:pointer;text-align:center;text-decoration:none;margin-top:10px;
     background:linear-gradient(135deg,#2563eb,#7c3aed);box-shadow:0 10px 24px rgba(79,70,229,.4)}
button:active,.btn:active{transform:scale(.98)}
.btn-red{background:linear-gradient(135deg,#dc2626,#b91c1c);box-shadow:none}
.btn-gray{background:rgba(255,255,255,.1);box-shadow:none;border:1px solid rgba(255,255,255,.12)}
.spin{width:18px;height:18px;border:3px solid rgba(255,255,255,.35);border-top-color:#fff;
      border-radius:50%;animation:sp .8s linear infinite;display:none}
button.busy .spin{display:inline-block}
@keyframes sp{to{transform:rotate(360deg)}}
.err{background:rgba(220,38,38,.18);border:1px solid rgba(248,113,113,.4);color:#fecaca;
     padding:12px 14px;border-radius:14px;margin-bottom:12px;font-size:14px}
.notice{background:rgba(37,99,235,.2);border:1px solid rgba(96,165,250,.4);color:#bfdbfe;
        padding:12px 14px;border-radius:14px;margin-bottom:12px;font-size:14px}
.warn{background:rgba(217,119,6,.2);border:1px solid rgba(251,191,36,.4);color:#fde68a;
      padding:12px 14px;border-radius:14px;margin-bottom:12px;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.stat{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
      border-radius:16px;padding:14px;text-align:center;font-size:13px;color:#94a3b8}
.stat b{display:block;font-size:28px;color:#fff}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{padding:7px 4px;border-bottom:1px solid rgba(255,255,255,.08);text-align:left;
      word-break:break-all;vertical-align:top}
.ok{color:#4ade80}.fail{color:#f87171}
code{background:rgba(255,255,255,.1);padding:2px 6px;border-radius:6px}
small{color:#94a3b8}
.foot{text-align:center;color:#64748b;font-size:12px;margin-top:6px}

.tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}
button.tab{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
     width:auto;margin:0;padding:14px 6px;border-radius:16px;font-size:13px;font-weight:600;
     color:#cbd5e1;background:rgba(255,255,255,.06);border:1.5px solid rgba(255,255,255,.12);
     box-shadow:none;transition:all .15s}
button.tab svg{width:30px;height:30px}
button.tab[data-p=youtube]{--a:#ef4444}
button.tab[data-p=facebook]{--a:#3b82f6}
button.tab[data-p=tiktok]{--a:#14b8a6}
button.tab .ic{width:46px;height:46px;border-radius:14px;display:flex;align-items:center;
     justify-content:center;background:var(--a);color:#fff}
button.tab.active{border-color:var(--a);background:rgba(255,255,255,.12);color:#fff;
     box-shadow:0 0 0 3px rgba(255,255,255,.06),0 10px 26px rgba(0,0,0,.35)}
.wrap[data-p=youtube]{--a:#ef4444;--a2:#f97316}
.wrap[data-p=facebook]{--a:#2563eb;--a2:#6366f1}
.wrap[data-p=tiktok]{--a:#0d9488;--a2:#06b6d4}
button.go{background:linear-gradient(135deg,var(--a),var(--a2));box-shadow:0 10px 24px rgba(0,0,0,.4)}
button.go .ic{width:26px;height:26px;display:flex}
button.go .ic svg{width:26px;height:26px}
.opt input:checked + span{background:var(--a);border-color:transparent;color:#fff}
.field input:focus{border-color:var(--a);box-shadow:none}
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
<div class="wrap" id="w" data-p="youtube">
  <div class="brand">
    <div class="logo">ST</div>
    <div><h1>ST DOWNLOADER</h1><div class="tag">Fast &amp; simple video downloader</div></div>
  </div>
  <div class="card">
    {% if s.notice %}<div class="notice">{{ s.notice }}</div>{% endif %}
    {% if s.maintenance == '1' %}<div class="warn">Ekhon maintenance cholche. Pore chesta korun.</div>{% endif %}
    <form method="post" id="f">
      <input type="hidden" name="platform" id="pf" value="youtube">
      <div class="tabs">
        <button type="button" class="tab active" data-p="youtube"><span class="ic"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg></span>YouTube</button>
        <button type="button" class="tab" data-p="facebook"><span class="ic"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="8" r="3.2"/><circle cx="17" cy="9" r="2.5"/><path d="M3 19c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5z"/><path d="M16 14c2.9 0 5 1.8 5 4.5V19h-4.2c0-1.8-.5-3.4-1.6-4.6.2-.2.5-.4.8-.4z"/></svg></span>Facebook</button>
        <button type="button" class="tab" data-p="tiktok"><span class="ic"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 4v10.2A3.5 3.5 0 1 0 12 17.4V8h4V4z"/></svg></span>TikTok</button>
      </div>
      <div class="field">
        <input type="text" id="url" name="url" placeholder="YouTube video-r link paste korun" required autocomplete="off">
        <button type="button" class="paste" id="pb">Paste</button>
      </div>
      <div class="opts">
        <label class="opt"><input type="checkbox" name="hq"><span>Best quality</span></label>
        <label class="opt"><input type="checkbox" name="audio"><span>Audio MP3</span></label>
      </div>
      <small>Best quality ar MP3 kaj na-o korte pare (ffmpeg lagbe).</small>
      <button id="b" class="go" type="submit"><span class="spin"></span><span class="ic" id="gi"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg></span><span id="bt">YouTube Download</span></button>
    </form>
    {% if error %}<div class="err" style="margin-top:14px">{{ error }}</div>{% endif %}
  </div>
  <div class="foot">Shudhu nijer video ba jeta download korar anumoti ache, setar jonno use korun.</div>
</div>
<script>
var ICONS={youtube:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg>',facebook:'<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="8" r="3.2"/><circle cx="17" cy="9" r="2.5"/><path d="M3 19c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5z"/><path d="M16 14c2.9 0 5 1.8 5 4.5V19h-4.2c0-1.8-.5-3.4-1.6-4.6.2-.2.5-.4.8-.4z"/></svg>',tiktok:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 4v10.2A3.5 3.5 0 1 0 12 17.4V8h4V4z"/></svg>'};
var NAMES={youtube:'YouTube',facebook:'Facebook',tiktok:'TikTok'};
var cur='youtube';
var w=document.getElementById('w'),pf=document.getElementById('pf'),url=document.getElementById('url');
var f=document.getElementById('f'),b=document.getElementById('b'),bt=document.getElementById('bt'),gi=document.getElementById('gi');
function pick(p){
  cur=p;w.setAttribute('data-p',p);pf.value=p;
  var tabs=document.querySelectorAll('button.tab');
  for(var i=0;i<tabs.length;i++){tabs[i].classList.toggle('active',tabs[i].getAttribute('data-p')===p);}
  url.placeholder=NAMES[p]+' video-r link paste korun';
  gi.innerHTML=ICONS[p];bt.textContent=NAMES[p]+' Download';
}
var tabs=document.querySelectorAll('button.tab');
for(var i=0;i<tabs.length;i++){
  tabs[i].addEventListener('click',function(){pick(this.getAttribute('data-p'));});
}
f.addEventListener('submit',function(){
  b.classList.add('busy');bt.textContent='Downloading... opekkha korun';
  setTimeout(function(){b.classList.remove('busy');bt.textContent=NAMES[cur]+' Download';},60000);
});
document.getElementById('pb').addEventListener('click',function(){
  if(navigator.clipboard&&navigator.clipboard.readText){
    navigator.clipboard.readText().then(function(t){url.value=t;}).catch(function(){});
  }
});
if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js');}
</script>
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
    chosen = request.form.get("platform", "")
    if chosen in ("youtube", "facebook", "tiktok") and chosen != plat:
        return render_template_string(
            HOME, s=s, error="Eta " + plat.title() + "-er link. Upor theke " + plat.title() + " button chapun.")
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
