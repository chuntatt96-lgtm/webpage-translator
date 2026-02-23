import time
import csv
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
USAGE = {}  # { ip: {date, count} }

# --------------------
# Usage logging
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
# HTML — Professional SaaS UI
# --------------------
HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Aly — AI Translator</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
:root {
  --bg: #f8fafc;
  --card: #ffffff;
  --text: #0f172a;
  --muted: #64748b;
  --border: #e5e7eb;
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
  background: var(--bg);
  color: var(--text);
}

.container {
  max-width: 760px;
  margin: 64px auto;
  padding: 0 20px;
}

.card {
  background: var(--card);
  border-radius: 12px;
  border: 1px solid var(--border);
  padding: 32px;
}

.header {
  margin-bottom: 28px;
}

.header h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
}

.header p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 15px;
}

.tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}

.tab {
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 500;
  color: var(--muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.tab.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

.label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.hint {
  font-size: 12px;
  color: var(--muted);
  margin-top: -6px;
  margin-bottom: 14px;
}

input, textarea {
  width: 100%;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  font-size: 14px;
}

textarea {
  resize: vertical;
  min-height: 120px;
}

button {
  margin-top: 20px;
  padding: 12px 18px;
  border-radius: 8px;
  border: none;
  background: var(--primary);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

button:hover {
  background: var(--primary-hover);
}

.hidden { display: none; }

.error {
  margin-top: 20px;
  padding: 12px;
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
  font-size: 14px;
}

.result {
  margin-top: 28px;
}

pre {
  background: #f9fafb;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.55;
}

.meta {
  margin-top: 10px;
  font-size: 12px;
  color: var(--muted);
}

footer {
  text-align: center;
  margin-top: 36px;
  font-size: 12px;
  color: var(--muted);
}
</style>

<script>
function showTab(tab, el) {
  ["web","text","audio"].forEach(t => {
    document.getElementById(t).classList.add("hidden");
  });
  document.getElementById(tab).classList.remove("hidden");
  document.getElementById("mode").value = tab;

  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
}
</script>
</head>

<body>
<div class="container">
  <div class="card">

    <div class="header">
      <h1>Aly</h1>
      <p>Translate webpages, text, and audio into any language.</p>
    </div>

    <div class="tabs">
      <div class="tab active" onclick="showTab('web', this)">Webpage</div>
      <div class="tab" onclick="showTab('text', this)">Text</div>
      <div class="tab" onclick="showTab('audio', this)">Audio</div>
    </div>

    <form method="post" enctype="multipart/form-data">
      <input type="hidden" name="mode" id="mode" value="web">

      <div id="web">
        <div class="label">Webpage URL</div>
        <input name="url" placeholder="https://example.com">
        <div class="hint">Best for articles, blogs, documentation</div>
      </div>

      <div id="text" class="hidden">
        <div class="label">Text</div>
        <textarea name="text" placeholder="Paste text to translate"></textarea>
      </div>

      <div id="audio" class="hidden">
        <div class="label">Audio file</div>
        <input type="file" name="audio" accept=".mp3,.wav,.m4a">
        <div class="hint">Speech audio works best</div>
      </div>

      <div class="label">Target language</div>
      <input name="language" placeholder="e.g. Japanese, French, Chinese">

      <button type="submit">Translate</button>
    </form>

    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}

    {% if result %}
      <div class="result">
        <pre>{{ result }}</pre>
        <div class="meta">
          {{ char_count }} characters • {{ remaining }} requests left today
        </div>
      </div>
    {% endif %}

  </div>

  <footer>
    © 2026 Aly • Built for real-world translation
  </footer>
</div>
</body>
</html>
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
            error = "Please wait a moment before submitting again."
            return render_template_string(HTML, error=error, remaining=remaining)

        LAST_REQUEST_TIME = now

        if remaining <= 0:
            error = "Daily limit reached. Please come back tomorrow."
            return render_template_string(HTML, error=error, remaining=0)

        mode = request.form.get("mode")
        target_language = request.form.get("language", "").strip()

        if not target_language:
            error = "Please specify a target language."
            return render_template_string(HTML, error=error, remaining=remaining)

        try:
            if mode == "web":
                url = request.form.get("url", "").strip()
                if not url:
                    raise ValueError("Webpage URL is required.")

                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                r.raise_for_status()

                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script","style","noscript","header","footer","nav"]):
                    tag.decompose()

                content = soup.find("article") or soup.find("main")
                text = " ".join(
                    content.stripped_strings if content else soup.stripped_strings
                )

            elif mode == "text":
                text = request.form.get("text", "").strip()
                if not text:
                    raise ValueError("Please provide text to translate.")

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
                raise ValueError("Invalid mode.")

            text = text[:MAX_CHARS]
            char_count = len(text)

            ai = client.responses.create(
                model="gpt-4.1-mini",
                input=f"Translate the following text to {target_language}:\n\n{text}"
            )

            result = ai.output_text

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)