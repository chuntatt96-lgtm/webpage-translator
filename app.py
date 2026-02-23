import os, time, csv, tempfile, subprocess
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string, send_file
from openai import OpenAI

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()

MAX_CHARS = 3000
DAILY_LIMIT = 10
RATE_LIMIT_SECONDS = 4

LAST_REQUEST_TIME = 0
USAGE = {}

# --------------------
# Usage logging
# --------------------
def log_usage(ip, mode, chars):
    with open("usage_log.csv", "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.utcnow().isoformat(), ip, mode, chars
        ])

# --------------------
# HTML (Professional SaaS)
# --------------------
HTML = """
<!doctype html>
<html>
<head>
<title>Aly — AI Translator</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Inter,system-ui;background:#f8fafc;margin:0}
.container{max-width:900px;margin:50px auto;padding:20px}
.card{background:#fff;border-radius:14px;border:1px solid #e5e7eb;padding:32px}
h1{margin:0}
.tabs{display:flex;gap:10px;border-bottom:1px solid #e5e7eb;margin:20px 0}
.tab{padding:10px 14px;cursor:pointer;color:#64748b}
.tab.active{color:#2563eb;border-bottom:2px solid #2563eb}
input,textarea{width:100%;padding:12px;border:1px solid #e5e7eb;border-radius:8px}
textarea{min-height:120px}
button{margin-top:20px;padding:12px 18px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-weight:600}
pre{background:#f9fafb;border-radius:8px;padding:16px;white-space:pre-wrap}
.hidden{display:none}
.meta{font-size:12px;color:#64748b;margin-top:8px}
.error{background:#fee2e2;color:#991b1b;padding:12px;border-radius:8px;margin-top:16px}
footer{text-align:center;margin-top:30px;font-size:12px;color:#64748b}
</style>
<script>
function tab(id,el){
  ["web","text","audio","video"].forEach(x=>document.getElementById(x).classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
  document.getElementById("mode").value=id;
  document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
  el.classList.add("active");
}
</script>
</head>

<body>
<div class="container">
<div class="card">
<h1>Aly</h1>
<p>Translate text, websites, audio & video into any language.</p>

<div class="tabs">
<div class="tab active" onclick="tab('web',this)">Web</div>
<div class="tab" onclick="tab('text',this)">Text</div>
<div class="tab" onclick="tab('audio',this)">Audio</div>
<div class="tab" onclick="tab('video',this)">Video</div>
</div>

<form method="post" enctype="multipart/form-data">
<input type="hidden" name="mode" id="mode" value="web">

<div id="web">
<input name="url" placeholder="https://example.com">
</div>

<div id="text" class="hidden">
<textarea name="text" placeholder="Paste text"></textarea>
</div>

<div id="audio" class="hidden">
<input type="file" name="audio" accept=".mp3,.wav,.m4a">
</div>

<div id="video" class="hidden">
<input type="file" name="video" accept=".mp4,.mov,.mkv">
</div>

<input name="language" placeholder="Target language (e.g. Japanese)">
<button>Translate</button>
</form>

{% if error %}<div class="error">{{ error }}</div>{% endif %}

{% if result %}
<hr>
<pre>{{ result }}</pre>
<div class="meta">{{ chars }} chars • {{ remaining }} left today</div>
{% endif %}

{% if srt %}
<hr>
<a href="/download/{{ srt }}">⬇ Download subtitles (.srt)</a>
{% endif %}
</div>
<footer>© Aly • MVP v3</footer>
</div>
</body>
</html>
"""

# --------------------
# Route
# --------------------
@app.route("/", methods=["GET","POST"])
def home():
    global LAST_REQUEST_TIME
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    today = date.today().isoformat()

    if ip not in USAGE or USAGE[ip]["date"]!=today:
        USAGE[ip]={"date":today,"count":0}

    remaining = DAILY_LIMIT - USAGE[ip]["count"]
    error=result=srt=None
    chars=0

    if request.method=="POST":
        if time.time()-LAST_REQUEST_TIME<RATE_LIMIT_SECONDS:
            return render_template_string(HTML,error="Please wait a moment.",remaining=remaining)
        LAST_REQUEST_TIME=time.time()

        if remaining<=0:
            return render_template_string(HTML,error="Daily limit reached.",remaining=0)

        mode=request.form.get("mode")
        lang=request.form.get("language","").strip()
        if not lang:
            return render_template_string(HTML,error="Target language required.",remaining=remaining)

        try:
            # WEB
            if mode=="web":
                r=requests.get(request.form["url"],timeout=10)
                soup=BeautifulSoup(r.text,"html.parser")
                for t in soup(["script","style"]): t.decompose()
                text=" ".join(soup.stripped_strings)

            # TEXT
            elif mode=="text":
                text=request.form["text"]

            # AUDIO
            elif mode=="audio":
                f=request.files["audio"]
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    f.save(tmp.name)
                    text=client.audio.transcriptions.create(
                        file=open(tmp.name,"rb"),
                        model="gpt-4o-transcribe"
                    ).text

            # VIDEO → SRT
            elif mode=="video":
                v=request.files["video"]
                tmpdir=tempfile.mkdtemp()
                vpath=os.path.join(tmpdir,"v.mp4")
                apath=os.path.join(tmpdir,"a.wav")
                v.save(vpath)
                subprocess.run(["ffmpeg","-i",vpath,"-ar","16000","-ac","1",apath],check=True)
                transcript=client.audio.transcriptions.create(
                    file=open(apath,"rb"),
                    model="gpt-4o-transcribe"
                ).text
                text=transcript
                srt=f"srt_{int(time.time())}.srt"
                with open(srt,"w",encoding="utf-8") as f:
                    f.write("1\n00:00:00,000 --> 99:59:59,000\n"+text)

            text=text[:MAX_CHARS]
            chars=len(text)

            result=client.responses.create(
                model="gpt-4.1-mini",
                input=f"Translate to {lang}:\n\n{text}"
            ).output_text

            USAGE[ip]["count"]+=1
            remaining-=1
            log_usage(ip,mode,chars)

        except Exception as e:
            error=str(e)

    return render_template_string(
        HTML,result=result,error=error,chars=chars,remaining=remaining,srt=srt
    )

@app.route("/download/<path:f>")
def dl(f):
    return send_file(f,as_attachment=True)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)