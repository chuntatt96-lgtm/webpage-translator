import time
import csv
import os
import tempfile
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string
from openai import OpenAI

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()  # uses OPENAI_API_KEY from environment

MAX_CHARS = 2000
DAILY_LIMIT = 10
RATE_LIMIT_SECONDS = 4

LAST_REQUEST_TIME = 0
USAGE = {}  # { ip: { "date": yyyy-mm-dd, "count": int } }

# --------------------
# Usage logging (CSV)
# --------------------
def log_usage(ip, mode, char_count):
    with open("usage_log.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.utcnow().isoformat(),
            ip,
            mode,
            char_count
        ])

# --------------------
# HTML (Playful Aly UI)
# --------------------
HTML = """
<!doctype html>
<title>Aly Translator</title>

<style>
body {
  font-family: "Segoe UI", Arial, sans-serif;
  background: linear-gradient(135deg, #fdfbfb, #ebedee);
}
.card {
  background: white;
  width: 620px;
  margin: 40px auto;
  padding: 28px;
  border-radius: 16px;
  box-shadow: 0 14px 36px rgba(0,0,0,0.15);
}
h2 { margin-top: 0; }
.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
}
.tab {
  flex: 1;
  padding: 10px;
  text-align: center;
  border-radius: 10px;
  background: #f0f0f0;
  cursor: pointer;
  font-weight: 600;
}
.tab.active {
  background: #ff6b6b;
  color: white;
}
input, textarea, button {
  width: 100%;
  padding: 12px;
  margin-top: 8px;
  font-size: 14px;
}
textarea { resize: vertical; }
button {
  margin-top: 16px;
  background: #ff6b6b;
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 16px;
  font-weight: bold;
}
button:hover { background: #ff5252; }
.hidden { display: none; }
.error {
  color: #b00020;
  margin-top: 14px;
}
pre {
  white-space: pre-wrap;
  background: #fafafa;
  padding: 16px;
  border-radius: 10px;
}
.meta {
  font-size: 13px;
  color: #666;
  margin-top: 8px;
}
footer {
  text-align: center;
  margin-top: 26px;
  font-size: 12px;
  color: #888;
}
</style>

<div class="card">
  <h2>✨ Aly</h2>
  <p>Your friendly AI for translating <b>websites, text & audio</b> 🌍</p>

  <div class="tabs">
    <div class="tab active" onclick="showTab('web', this)">🌐 Web</div>
    <div class="tab" onclick="showTab('text', this)">✍️ Text</div>
    <div class="tab" onclick="showTab('audio', this)">🔊 Audio</div>
  </div>

  <form method="post" enctype="multipart/form-data"
        onsubmit="this.querySelector('button').innerText='Aly is thinking… 🧠';">

    <input type="hidden" name="mode" id="mode" value="web">

    <div id="web">
      <input name="url" placeholder="https://example.com">
    </div>

    <div id="text" class="hidden">
      <textarea name="text" rows="6" placeholder="Paste text here…"></textarea>
    </div>

    <div id="audio" class="hidden">
      <input type="file" name="audio" accept=".mp3,.wav,.m4a">
      <div class="meta">Short audio works best (speech, podcasts, notes)</div>
    </div>

    <input name="language" placeholder="Translate to (e.g. Chinese, Japanese, French)">

    <button type="submit">Translate 🚀</button>
  </form>

  {% if error %}
    <div class="error">⚠️ {{ error }}</div>
  {% endif %}

  {% if result %}
    <hr>
    <h3>🎉 Result</h3>
    <pre>{{ result }}</pre>
    <div class="meta">
      {{ char_count }} characters • {{ remaining }} uses left today
    </div>
  {% endif %}

  <footer>© 2026 Aly • Built with curiosity ☕</footer>
</div>

<script>
function showTab(tab, el) {
  document.getElementById("web").classList.add("hidden");
  document.getElementById("text").classList.add("hidden");
  document.getElementById("audio").classList.add("hidden");

  document.getElementById(tab).classList.remove("hidden");
  document.getElementById("mode").value = tab;

  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
}
</script>
"""

# --------------------
# Route
# --------------------
@app.route("/", methods=["GET", "POST"])
def home():
    global LAST_REQUEST_TIME

    today = date.today().isoformat()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if ip not in USAGE or USAGE[ip]["date"] != today:
        USAGE[ip] = {"date": today, "count": 0}

    remaining = DAILY_LIMIT - USAGE[ip]["count"]
    result = None
    error = None
    char_count = 0

    if request.method == "POST":
        now = time.time()
        if now - LAST_REQUEST_TIME < RATE_LIMIT_SECONDS:
            return render_template_string(
                HTML, error="Slow down 😅 Give Aly a second.", remaining=remaining
            )
        LAST_REQUEST_TIME = now

        if remaining <= 0:
            return render_template_string(
                HTML, error="Aly needs a rest 💤 Come back tomorrow!", remaining=0
            )

        mode = request.form.get("mode")
        target_language = request.form.get("language", "").strip()

        if not target_language:
            return render_template_string(
                HTML, error="Tell Aly which language you want 😊", remaining=remaining
            )

        try:
            # -------- WEB --------
            if mode == "web":
                url = request.form.get("url", "").strip()
                if not url:
                    raise ValueError("Please enter a webpage URL.")

                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                r.raise_for_status()

                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                    tag.decompose()

                content = soup.find("article") or soup.find("main")
                text = " ".join(
                    content.stripped_strings if content else soup.stripped_strings
                )

            # -------- TEXT --------
            elif mode == "text":
                text = request.form.get("text", "").strip()
                if not text:
                    raise ValueError("Please paste some text.")

            # -------- AUDIO --------
            elif mode == "audio":
                audio = request.files.get("audio")
                if not audio:
                    raise ValueError("Please upload an audio file.")

                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    audio.save(tmp.name)
                    transcript = client.audio.transcriptions.create(
                        file=open(tmp.name, "rb"),
                        model="gpt-4o-transcribe"
                    )
                    text = transcript.text

            else:
                raise ValueError("Unknown mode.")

            text = text[:MAX_CHARS]
            char_count = len(text)

            ai = client.responses.create(
                model="gpt-4.1-mini",
                input=f"Translate the following text to {target_language}:\n\n{text}"
            )

            result = ai.output_text

            # ---- Track usage ----
            USAGE[ip]["count"] += 1
            remaining -= 1
            log_usage(ip, mode, char_count)

        except Exception as e:
            error = str(e)

    return render_template_string(
        HTML,
        result=result,
        error=error,
        char_count=char_count,
        remaining=remaining
    )

# --------------------
# Run (Docker / Render)
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)