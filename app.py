import os
import time
import csv
import uuid
import subprocess
from datetime import date
from io import BytesIO

from flask import Flask, request, render_template_string, send_file
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

USAGE_LOG = "usage_log.csv"
MAX_CHARS = 3000
RATE_LIMIT_SECONDS = 5
LAST_REQUEST_TIME = 0
LAST_TRANSLATION = ""
LAST_SRT_FILE = None

DAILY_LIMITS = {
    "text": 5,
    "web": 5,
    "audio": 2,
    "video": 1,
}

# --------------------
# Usage tracking
# --------------------
def log_usage(feature, chars, language, ip):
    exists = os.path.exists(USAGE_LOG)
    with open(USAGE_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["timestamp", "feature", "characters", "language", "ip"])
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            feature,
            chars,
            language,
            ip
        ])

def check_daily_limit(ip, feature):
    today = date.today().isoformat()
    count = 0
    if not os.path.exists(USAGE_LOG):
        return True
    with open(USAGE_LOG, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["ip"] == ip and row["feature"] == feature and row["timestamp"].startswith(today):
                count += 1
    return count < DAILY_LIMITS.get(feature, 0)

# --------------------
# AI helpers
# --------------------
def translate_text(text, language, feature, ip):
    global LAST_TRANSLATION
    text = text[:MAX_CHARS]
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"Translate the following text to {language}:\n\n{text}"
    )
    LAST_TRANSLATION = response.output_text
    log_usage(feature, len(text), language, ip)
    return LAST_TRANSLATION

def transcribe_audio(path):
    response = client.audio.transcriptions.create(
        file=open(path, "rb"),
        model="gpt-4o-mini-transcribe"
    )
    return response.text

# --------------------
# UI (BOLD)
# --------------------
HTML = """
<!doctype html>
<title>Aly — Built for Creators</title>

<style>
:root {
  --bg: #0b0d10;
  --card: #12151b;
  --accent: #ff4d4d;
  --text: #ffffff;
  --muted: #9aa4b2;
  --border: #1f2937;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: Inter, system-ui, Arial;
  background: radial-gradient(circle at top, #141821, #080a0f);
  color: var(--text);
}

.container {
  max-width: 860px;
  margin: 60px auto;
  padding: 24px;
}

.card {
  background: linear-gradient(180deg, #12151b, #0f1218);
  border-radius: 18px;
  padding: 36px;
  box-shadow: 0 40px 80px rgba(0,0,0,.6);
  border: 1px solid var(--border);
}

header h1 {
  margin: 0;
  font-size: 36px;
  font-weight: 900;
  letter-spacing: -1px;
}

header p {
  margin-top: 8px;
  color: var(--muted);
  font-size: 16px;
}

.tabs {
  display: flex;
  gap: 10px;
  margin: 32px 0;
}

.tab-btn {
  padding: 10px 18px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-weight: 600;
}

.tab-btn.active {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

input, textarea {
  width: 100%;
  padding: 14px;
  margin-top: 10px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: #0b0e14;
  color: var(--text);
  font-size: 14px;
}

textarea { min-height: 120px; }

.primary {
  margin-top: 22px;
  padding: 14px;
  border-radius: 14px;
  background: var(--accent);
  border: none;
  color: #000;
  font-size: 16px;
  font-weight: 800;
  cursor: pointer;
}

.result {
  margin-top: 30px;
  padding: 20px;
  border-radius: 14px;
  background: #0b0e14;
  white-space: pre-wrap;
}

.actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

.actions button {
  padding: 10px 16px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  cursor: pointer;
}

.error {
  margin-top: 20px;
  padding: 14px;
  border-radius: 12px;
  background: #2a1212;
  color: #ffb4b4;
}

.hidden { display: none; }

footer {
  margin-top: 40px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
}
</style>

<div class="container">
  <div class="card">

    <header>
      <h1>Aly</h1>
      <p>Translate text, audio & video into publish-ready content.</p>
    </header>

    <div class="tabs">
      <button class="tab-btn active" onclick="openTab('text', this)">Text</button>
      <button class="tab-btn" onclick="openTab('web', this)">Web</button>
      <button class="tab-btn" onclick="openTab('audio', this)">Audio</button>
      <button class="tab-btn" onclick="openTab('video', this)">Video</button>
    </div>

    <form method="post" enctype="multipart/form-data">
      <input type="hidden" name="mode" id="mode" value="text">

      <div id="text" class="tab">
        <textarea name="text" placeholder="Paste script, caption, or post"></textarea>
      </div>

      <div id="web" class="tab hidden">
        <input name="url" placeholder="https://example.com">
      </div>

      <div id="audio" class="tab hidden">
        <input type="file" name="audio">
      </div>

      <div id="video" class="tab hidden">
        <input type="file" name="video">
      </div>

      <input name="language" placeholder="Translate to (e.g. Japanese, Spanish)" required>

      <button class="primary">Translate</button>
    </form>

    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}

    {% if result %}
      <div class="result" id="resultText">{{ result }}</div>
      <div class="actions">
        <button onclick="copyText()">Copy</button>
        <a href="/download"><button type="button">Download</button></a>
        {% if srt %}
        <a href="/download_srt"><button type="button">Subtitles (.srt)</button></a>
        {% endif %}
      </div>
    {% endif %}

  </div>

  <footer>© Aly • Built for creators who move fast</footer>
</div>

<script>
function openTab(name, btn) {
  document.querySelectorAll('.tab').forEach(t => t.classList.add('hidden'));
  document.getElementById(name).classList.remove('hidden');
  document.getElementById('mode').value = name;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

function copyText() {
  navigator.clipboard.writeText(
    document.getElementById("resultText").innerText
  );
  alert("Copied");
}
</script>
"""

# --------------------
# Routes
# --------------------
@app.route("/", methods=["GET", "POST"])
def home():
    global LAST_REQUEST_TIME, LAST_SRT_FILE

    result = None
    error = None
    srt = False

    if request.method == "POST":
        if time.time() - LAST_REQUEST_TIME < RATE_LIMIT_SECONDS:
            return render_template_string(HTML, error="Slow down. Try again in a second.")

        LAST_REQUEST_TIME = time.time()
        mode = request.form.get("mode")
        language = request.form.get("language")
        ip = request.remote_addr

        if not check_daily_limit(ip, mode):
            return render_template_string(HTML, error="Daily limit reached. Upgrade coming soon.")

        try:
            if mode == "text":
                result = translate_text(request.form.get("text",""), language, "text", ip)

            elif mode == "web":
                r = requests.get(request.form.get("url"), timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for t in soup(["script","style","header","footer","nav"]):
                    t.decompose()
                result = translate_text(" ".join(soup.stripped_strings), language, "web", ip)

            elif mode == "audio":
                f = request.files["audio"]
                path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.wav")
                f.save(path)
                result = translate_text(transcribe_audio(path), language, "audio", ip)

            elif mode == "video":
                f = request.files["video"]
                vpath = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.mp4")
                apath = vpath.replace(".mp4",".wav")
                f.save(vpath)
                subprocess.run(["ffmpeg","-y","-i",vpath,apath],check=True)
                text = transcribe_audio(apath)
                result = translate_text(text, language, "video", ip)

                LAST_SRT_FILE = vpath.replace(".mp4",".srt")
                with open(LAST_SRT_FILE,"w",encoding="utf-8") as f:
                    f.write("1\n00:00:00,000 --> 99:59:59,000\n"+result)
                srt = True

        except Exception:
            error = "Processing failed."

    return render_template_string(HTML, result=result, error=error, srt=srt)

@app.route("/download")
def download():
    buffer = BytesIO()
    buffer.write(LAST_TRANSLATION.encode("utf-8"))
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="aly_translation.txt")

@app.route("/download_srt")
def download_srt():
    if LAST_SRT_FILE and os.path.exists(LAST_SRT_FILE):
        return send_file(LAST_SRT_FILE, as_attachment=True)
    return "No subtitles available."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)