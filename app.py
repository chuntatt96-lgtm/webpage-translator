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
# App Setup
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

# --------------------
# Limits
# --------------------
DAILY_LIMITS = {
    "text": 5,
    "web": 5,
    "audio": 2,
    "video": 1,
}

# --------------------
# Usage Logging
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
            if (
                row["ip"] == ip
                and row["feature"] == feature
                and row["timestamp"].startswith(today)
            ):
                count += 1

    return count < DAILY_LIMITS.get(feature, 0)

# --------------------
# Translation
# --------------------
def translate_text(text, language, feature, ip):
    global LAST_TRANSLATION
    text = text[:MAX_CHARS]

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"Translate the following text to {language}:\n\n{text}"
    )

    result = response.output_text
    LAST_TRANSLATION = result
    log_usage(feature, len(text), language, ip)
    return result

def transcribe_audio(path):
    response = client.audio.transcriptions.create(
        file=open(path, "rb"),
        model="gpt-4o-mini-transcribe"
    )
    return response.text

# --------------------
# UI
# --------------------
HTML = """
<!doctype html>
<title>Aly – Creator Translator</title>
<style>
body { font-family: Inter, Arial; background:#f5f6f8; }
.container { width:750px; margin:40px auto; background:white; padding:30px; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.1);}
.tabs button { margin-right:8px; padding:8px 14px; border:none; border-radius:6px; cursor:pointer;}
.tab { display:none; margin-top:20px;}
input, textarea { width:100%; margin-top:8px; padding:10px;}
.result { margin-top:20px; background:#f2f2f2; padding:15px; border-radius:6px; white-space:pre-wrap;}
.error { color:red; margin-top:10px;}
.actions button { margin-right:10px; margin-top:10px;}
</style>

<div class="container">
<h2>Aly – Translation for Creators</h2>

<div class="tabs">
<button onclick="openTab('text')">Text</button>
<button onclick="openTab('web')">Webpage</button>
<button onclick="openTab('audio')">Audio</button>
<button onclick="openTab('video')">Video</button>
</div>

<form method="post" enctype="multipart/form-data">
<input type="hidden" name="mode" id="mode">

<div id="text" class="tab">
<textarea name="text" rows="5" placeholder="Paste text"></textarea>
</div>

<div id="web" class="tab">
<input name="url" placeholder="https://example.com">
</div>

<div id="audio" class="tab">
<input type="file" name="audio">
</div>

<div id="video" class="tab">
<input type="file" name="video">
</div>

<input name="language" placeholder="Target language (e.g. Japanese)" required>
<button type="submit">Translate</button>
</form>

{% if error %}
<p class="error">{{ error }}</p>
{% endif %}

{% if result %}
<div class="result" id="resultText">{{ result }}</div>

<div class="actions">
<button onclick="copyText()">Copy</button>
<a href="/download"><button type="button">Download .txt</button></a>
{% if srt %}
<a href="/download_srt"><button type="button">Download .srt</button></a>
{% endif %}
</div>
{% endif %}

</div>

<script>
function openTab(name){
document.querySelectorAll('.tab').forEach(t=>t.style.display='none');
document.getElementById(name).style.display='block';
document.getElementById('mode').value=name;
}
openTab('text');

function copyText(){
const text=document.getElementById("resultText").innerText;
navigator.clipboard.writeText(text);
alert("Copied!");
}
</script>
"""

# --------------------
# Routes
# --------------------
@app.route("/", methods=["GET","POST"])
def home():
    global LAST_REQUEST_TIME, LAST_SRT_FILE

    result = None
    error = None
    srt = False

    if request.method == "POST":
        if time.time() - LAST_REQUEST_TIME < RATE_LIMIT_SECONDS:
            return render_template_string(HTML, error="Please wait a moment.")

        LAST_REQUEST_TIME = time.time()

        mode = request.form.get("mode")
        language = request.form.get("language")
        ip = request.remote_addr

        if not check_daily_limit(ip, mode):
            return render_template_string(
                HTML,
                error="Daily limit reached for this feature."
            )

        try:
            if mode == "text":
                result = translate_text(request.form.get("text",""), language, "text", ip)

            elif mode == "web":
                r = requests.get(request.form.get("url"), timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for t in soup(["script","style","header","footer","nav"]):
                    t.decompose()
                text = " ".join(soup.stripped_strings)
                result = translate_text(text, language, "web", ip)

            elif mode == "audio":
                f = request.files["audio"]
                path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.wav")
                f.save(path)
                text = transcribe_audio(path)
                result = translate_text(text, language, "audio", ip)

            elif mode == "video":
                f = request.files["video"]
                video_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.mp4")
                audio_path = video_path.replace(".mp4",".wav")
                f.save(video_path)

                subprocess.run(["ffmpeg","-y","-i",video_path,audio_path],check=True)
                text = transcribe_audio(audio_path)
                result = translate_text(text, language, "video", ip)

                srt_name = f"srt_{uuid.uuid4()}.srt"
                LAST_SRT_FILE = os.path.join(UPLOAD_DIR, srt_name)
                with open(LAST_SRT_FILE,"w",encoding="utf-8") as f:
                    f.write("1\n00:00:00,000 --> 99:59:59,000\n"+result)
                srt = True

        except Exception as e:
            error = "Processing failed."

    return render_template_string(HTML, result=result, error=error, srt=srt)

@app.route("/download")
def download():
    global LAST_TRANSLATION
    buffer = BytesIO()
    buffer.write(LAST_TRANSLATION.encode("utf-8"))
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name="aly_translation.txt",
                     mimetype="text/plain")

@app.route("/download_srt")
def download_srt():
    global LAST_SRT_FILE
    if LAST_SRT_FILE and os.path.exists(LAST_SRT_FILE):
        return send_file(LAST_SRT_FILE, as_attachment=True)
    return "No subtitle file available."

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)