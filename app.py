import os
import time
import csv
import subprocess
import uuid

from flask import Flask, request, render_template_string, send_file
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()  # uses OPENAI_API_KEY

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

USAGE_LOG = "usage_log.csv"
MAX_CHARS = 3000
RATE_LIMIT_SECONDS = 5
LAST_REQUEST_TIME = 0

# --------------------
# Usage logging
# --------------------
def log_usage(feature, chars, language):
    exists = os.path.exists(USAGE_LOG)
    with open(USAGE_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["timestamp", "feature", "characters", "language"])
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), feature, chars, language])

# --------------------
# HTML UI
# --------------------
HTML = """
<!doctype html>
<title>Aly – Creator Translator</title>
<style>
body {
  font-family: Inter, Arial, sans-serif;
  background: #f5f6f8;
}
.container {
  width: 720px;
  margin: 50px auto;
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.1);
}
h1 { margin-bottom: 10px; }
.tabs button {
  margin-right: 8px;
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.tab { display: none; margin-top: 20px; }
input, textarea, select, button {
  width: 100%;
  margin-top: 8px;
  padding: 10px;
}
.result {
  margin-top: 20px;
  background: #f2f2f2;
  padding: 15px;
  border-radius: 6px;
  white-space: pre-wrap;
}
.error { color: red; }
</style>

<div class="container">
<h1>🔥 Aly Translator 🔥</h1>
<p>Translate text, webpages, audio, and video — built for creators.</p>

<div class="tabs">
<button onclick="openTab('text')">Text</button>
<button onclick="openTab('web')">Webpage</button>
<button onclick="openTab('audio')">Audio</button>
<button onclick="openTab('video')">Video</button>
</div>

<form method="post" enctype="multipart/form-data">
<input type="hidden" name="mode" id="mode">

<div id="text" class="tab">
<textarea name="text" rows="6" placeholder="Paste text here"></textarea>
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

<input name="language" placeholder="Target language (e.g. Japanese, French)" required>

<button type="submit">Translate</button>
</form>

{% if error %}
<p class="error">{{ error }}</p>
{% endif %}

{% if result %}
<div class="result">{{ result }}</div>
{% endif %}
</div>

<script>
function openTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.style.display='none');
  document.getElementById(name).style.display='block';
  document.getElementById('mode').value = name;
}
openTab('text');
</script>
"""

# --------------------
# Translation helpers
# --------------------
def translate_text(text, language, feature):
    text = text[:MAX_CHARS]
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"Translate the following text to {language}:\n\n{text}"
    )
    result = response.output_text
    log_usage(feature, len(text), language)
    return result

def transcribe_audio(path):
    response = client.audio.transcriptions.create(
        file=open(path, "rb"),
        model="gpt-4o-mini-transcribe"
    )
    return response.text

# --------------------
# Routes
# --------------------
@app.route("/", methods=["GET", "POST"])
def home():
    global LAST_REQUEST_TIME

    result = None
    error = None

    if request.method == "POST":
        if time.time() - LAST_REQUEST_TIME < RATE_LIMIT_SECONDS:
            return render_template_string(HTML, error="Please wait a moment.")

        LAST_REQUEST_TIME = time.time()

        mode = request.form.get("mode")
        language = request.form.get("language")

        try:
            if mode == "text":
                result = translate_text(request.form.get("text", ""), language, "text")

            elif mode == "web":
                r = requests.get(request.form.get("url"), timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for t in soup(["script","style","noscript","header","footer","nav"]):
                    t.decompose()
                text = " ".join(soup.stripped_strings)
                result = translate_text(text, language, "web")

            elif mode == "audio":
                f = request.files["audio"]
                path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.wav")
                f.save(path)
                text = transcribe_audio(path)
                result = translate_text(text, language, "audio")

            elif mode == "video":
                f = request.files["video"]
                video_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.mp4")
                audio_path = video_path.replace(".mp4", ".wav")
                f.save(video_path)
                subprocess.run(["ffmpeg", "-y", "-i", video_path, audio_path], check=True)
                text = transcribe_audio(audio_path)
                result = translate_text(text, language, "video")

        except Exception as e:
            error = "Processing failed."

    return render_template_string(HTML, result=result, error=error)

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)