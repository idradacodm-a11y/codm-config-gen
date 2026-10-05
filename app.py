from flask import Flask, request, render_template_string, redirect, url_for, session, jsonify, send_file
import os
import secrets
import string
import json
import time
import zipfile
import io
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
KEYS_FILE = DATA / "keys.json"
ADMIN_PASS = "XEDRAN"

def load_keys():
    if KEYS_FILE.exists():
        try:
            return json.loads(KEYS_FILE.read_text())
        except:
            return {}
    return {}

def save_keys(keys):
    KEYS_FILE.write_text(json.dumps(keys, indent=2))

def generate_key(prefix="CODM"):
    part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    part2 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    part3 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"{prefix}-{part}-{part2}-{part3}"

def is_key_valid(key):
    keys = load_keys()
    if key not in keys:
        return False, "Invalid key"
    info = keys[key]
    if info.get("revoked"):
        return False, "Key revoked"
    if info.get("type") == "lifetime":
        return True, "Lifetime"
    exp = info.get("expires")
    if exp and time.time() > exp:
        return False, "Key expired"
    return True, "ok"

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ==================== CONFIG GENERATOR ====================
def make_config_zip(mode="MB"):
    """Generate a config zip. mode = MB or RANDOM"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        readme = f"""CODM GARENA CONFIG
==================
Mode: {mode}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

HOW TO APPLY:
1. Use MT Manager / ZArchiver
2. Go to Android/data/com.garena.game.codm/files/
3. Delete contents (backup first)
4. Extract this zip inside files folder
5. Force close CODM and reopen

Mode notes:
- MB = Mid/Brutal tuned (strong mid-long tracking)
- RANDOM = Randomized strength profile
"""
        zf.writestr("README.txt", readme)

        # fake but structured config
        if mode == "MB":
            aim = 1.38
            mid = 1.42
            longr = 1.30
            recoil_v = 0.70
        else:
            aim = round(1.20 + secrets.randbelow(30)/100, 2)
            mid = round(1.25 + secrets.randbelow(30)/100, 2)
            longr = round(1.15 + secrets.randbelow(25)/100, 2)
            recoil_v = round(0.65 + secrets.randbelow(20)/100, 2)

        ini = f"""[UserSettings]
AimAssistStrength={aim}
AimAssistRangeMid={mid}
AimAssistRangeLong={longr}
RecoilVerticalScale={recoil_v}
RecoilHorizontalScale=0.85
ADSSpeedMultiplier=1.18
TrackingSpeed=1.22
CrosshairStickiness=1.25
HighFPSMode=1
ConfigMode={mode}
GeneratedAt={int(time.time())}
"""
        zf.writestr("files/Saved/Config/UserSettings.ini", ini)
        zf.writestr("files/Saved/Config/GameUserSettings.ini",
"""[/Script/Engine.GameUserSettings]
bUseVSync=False
FrameRateLimit=120.000000
""")
        # dummy binary blobs
        zf.writestr("files/Saved/SaveGames/PlayerData.sav", secrets.token_bytes(2048))
        zf.writestr("files/Saved/Config/DeviceProfile.dat", secrets.token_bytes(512))
    buf.seek(0)
    return buf

# ==================== ROUTES ====================
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CODM CONFIG // GENERATOR</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
:root{--bg:#000;--panel:#0a0f0a;--border:#00ff41;--text:#00ff41;--muted:#00aa2a;--red:#ff003c}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Share Tech Mono',monospace;background:#000;color:var(--text);min-height:100vh;padding:20px;
background-image:linear-gradient(rgba(0,255,65,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,65,0.03) 1px,transparent 1px);background-size:22px 22px}
.wrap{max-width:520px;margin:0 auto}
.logo{font-size:1.5rem;letter-spacing:3px;text-shadow:0 0 12px #00ff41;margin-bottom:8px;text-align:center}
.logo span{color:#fff}
.sub{text-align:center;color:var(--muted);font-size:.8rem;margin-bottom:24px}
.card{background:var(--panel);border:1px solid var(--border);padding:20px;margin-bottom:16px;box-shadow:0 0 18px rgba(0,255,65,0.12)}
h2{font-size:.75rem;color:var(--muted);letter-spacing:.15em;margin-bottom:14px}
input,select{width:100%;background:#000;border:1px solid var(--border);color:var(--text);padding:12px;font-family:inherit;margin-bottom:12px}
button{width:100%;border:1px solid var(--border);background:#003300;color:#00ff41;padding:14px;font-family:inherit;font-weight:700;cursor:pointer;letter-spacing:1px}
button:hover{box-shadow:0 0 14px rgba(0,255,65,0.4)}
.msg{text-align:center;margin-top:12px;font-size:.85rem}
.err{color:var(--red)}
.ok{color:var(--text)}
a{color:var(--muted);font-size:.8rem}
.footer{text-align:center;margin-top:20px}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo">CODM <span>CONFIG</span></div>
  <div class="sub">// GENERATOR PANEL</div>
  <div class="card">
    <h2>// ENTER KEY</h2>
    <form method="POST" action="/generate">
      <input name="key" placeholder="CODM-XXXX-XXXX-XXXX" required autocomplete="off">
      <select name="mode">
        <option value="MB">MB (Mid/Brutal)</option>
        <option value="RANDOM">RANDOM</option>
      </select>
      <button type="submit">GENERATE CONFIG</button>
    </form>
    {% if error %}<div class="msg err">{{ error }}</div>{% endif %}
    {% if success %}<div class="msg ok">{{ success }}</div>{% endif %}
  </div>
  <div class="footer"><a href="/admin">admin</a></div>
</div>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADMIN // LOGIN</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
body{font-family:'Share Tech Mono',monospace;background:#000;color:#00ff41;min-height:100vh;display:flex;align-items:center;justify-content:center;
background-image:linear-gradient(rgba(0,255,65,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,65,0.03) 1px,transparent 1px);background-size:22px 22px}
.card{background:#0a0f0a;border:1px solid #00ff41;padding:28px;width:100%;max-width:360px;box-shadow:0 0 20px rgba(0,255,65,0.15)}
h1{font-size:1.1rem;letter-spacing:2px;margin-bottom:18px;text-align:center}
input{width:100%;background:#000;border:1px solid #00ff41;color:#00ff41;padding:12px;font-family:inherit;margin-bottom:12px}
button{width:100%;border:1px solid #00ff41;background:#003300;color:#00ff41;padding:12px;font-family:inherit;font-weight:700;cursor:pointer}
.err{color:#ff003c;text-align:center;margin-top:10px;font-size:.85rem}
</style>
</head>
<body>
<div class="card">
  <h1>ADMIN ACCESS</h1>
  <form method="POST">
    <input type="password" name="password" placeholder="PASSWORD" required autofocus>
    <button type="submit">ENTER</button>
  </form>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
</div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ADMIN // PANEL</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
:root{--border:#00ff41;--text:#00ff41;--muted:#00aa2a;--red:#ff003c}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Share Tech Mono',monospace;background:#000;color:var(--text);min-height:100vh;padding:16px;
background-image:linear-gradient(rgba(0,255,65,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,65,0.03) 1px,transparent 1px);background-size:22px 22px}
.wrap{max-width:800px;margin:0 auto}
.logo{font-size:1.2rem;letter-spacing:2px;margin-bottom:16px}
.card{background:#0a0f0a;border:1px solid var(--border);padding:16px;margin-bottom:14px}
h2{font-size:.75rem;color:var(--muted);letter-spacing:.12em;margin-bottom:12px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
input,select{background:#000;border:1px solid var(--border);color:var(--text);padding:10px;font-family:inherit}
button{border:1px solid var(--border);background:#003300;color:#00ff41;padding:10px 14px;font-family:inherit;cursor:pointer}
button.danger{background:#1a0000;color:var(--red);border-color:var(--red)}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th,td{border:1px solid #003300;padding:8px;text-align:left}
th{color:var(--muted)}
.badge{padding:2px 6px;border:1px solid;font-size:.7rem}
.live{border-color:#00ff41;color:#00ff41}
.dead{border-color:#ff003c;color:#ff003c}
a{color:var(--muted)}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo">ADMIN <span style="color:#fff">//</span> KEY PANEL &nbsp; <a href="/logout" style="font-size:.8rem">logout</a></div>

  <div class="card">
    <h2>// GENERATE KEY</h2>
    <form method="POST" action="/admin/generate">
      <div class="row">
        <select name="duration">
          <option value="1">1 Day</option>
          <option value="7">7 Days</option>
          <option value="30">30 Days (1 Month)</option>
          <option value="90">90 Days (3 Months)</option>
          <option value="365">1 Year</option>
          <option value="lifetime">LIFETIME</option>
        </select>
        <input name="note" placeholder="note (optional)" style="flex:1;min-width:140px">
        <button type="submit">GENERATE</button>
      </div>
    </form>
    {% if new_key %}
    <div style="margin-top:10px;padding:10px;border:1px solid #00ff41;background:#001a00">
      NEW KEY: <strong>{{ new_key }}</strong>
    </div>
    {% endif %}
  </div>

  <div class="card">
    <h2>// ALL KEYS ({{ keys|length }})</h2>
    <table>
      <tr><th>KEY</th><th>TYPE</th><th>EXPIRES</th><th>NOTE</th><th>ACTION</th></tr>
      {% for k,v in keys.items() %}
      <tr>
        <td style="font-size:.75rem">{{ k }}</td>
        <td>{{ v.type }}</td>
        <td>{% if v.type=='lifetime' %}NEVER{% else %}{{ v.expires_human }}{% endif %}</td>
        <td>{{ v.note or '-' }}</td>
        <td>
          {% if not v.revoked %}
          <form method="POST" action="/admin/revoke" style="display:inline">
            <input type="hidden" name="key" value="{{ k }}">
            <button class="danger" type="submit">REVOKED</button>
          </form>
          {% else %}
          <span class="badge dead">REVOKED</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </table>
  </div>
</div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML, error=None, success=None)

@app.route("/generate", methods=["POST"])
def generate():
    key = request.form.get("key", "").strip().upper()
    mode = request.form.get("mode", "MB")
    ok, msg = is_key_valid(key)
    if not ok:
        return render_template_string(INDEX_HTML, error=msg, success=None)
    buf = make_config_zip(mode)
    filename = f"CODM_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=filename)

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_panel"))
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        error = "WRONG PASSWORD"
    return render_template_string(ADMIN_LOGIN_HTML, error=error)

@app.route("/admin/panel")
@admin_required
def admin_panel():
    keys = load_keys()
    # human dates
    for k,v in keys.items():
        if v.get("expires"):
            v["expires_human"] = datetime.fromtimestamp(v["expires"]).strftime("%Y-%m-%d %H:%M")
        else:
            v["expires_human"] = "NEVER"
    new_key = session.pop("new_key", None)
    return render_template_string(ADMIN_HTML, keys=keys, new_key=new_key)

@app.route("/admin/generate", methods=["POST"])
@admin_required
def admin_generate():
    duration = request.form.get("duration", "1")
    note = request.form.get("note", "").strip()
    key = generate_key()
    keys = load_keys()
    if duration == "lifetime":
        keys[key] = {"type": "lifetime", "created": time.time(), "note": note, "revoked": False}
    else:
        days = int(duration)
        keys[key] = {
            "type": f"{days}d",
            "created": time.time(),
            "expires": time.time() + days * 86400,
            "note": note,
            "revoked": False
        }
    save_keys(keys)
    session["new_key"] = key
    return redirect(url_for("admin_panel"))

@app.route("/admin/revoke", methods=["POST"])
@admin_required
def admin_revoke():
    key = request.form.get("key", "")
    keys = load_keys()
    if key in keys:
        keys[key]["revoked"] = True
        save_keys(keys)
    return redirect(url_for("admin_panel"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
