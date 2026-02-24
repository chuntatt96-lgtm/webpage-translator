import time
import tempfile
from datetime import date

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string, send_file
from openai import OpenAI
from io import BytesIO

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()  # Uses OPENAI_API_KEY from environment

MAX_CHARS = 2000
RATE_LIMIT_SECONDS = 4
LAST_REQUEST_TIME = 0

# Store last result for download (MVP-safe)
LAST_TRANSLATION = ""

# --------------------
# HTML — Professional Creator UI
# --------------------
HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Aly — Creator Translator</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
:root {
  --bg: #f8fafc;
  --card: #ffffff;
  --text: #0f172a;
  --muted: #64748b;
  --border: #e5e7eb;
  --primary: #2563eb;
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
.header h1 {
  margin: 0;
  font-size: 28px;
}
.header p {
  margin-top: 6px;
  color: var(--muted);
}
.tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  margin: 24px 0;
}
.tab {
  padding: 10px 14px;
  font-size: 14px;
  cursor: pointer;
  color: var(--muted);
}
.tab.active {
  color: var(--primary);
  border-bottom: 2px solid var(--primary);
}
.label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}
input, textarea {
  width: 100%;
  padding: 12px;
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
  font-weight: 600;
  cursor: pointer;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.secondary {
  background: white;
  color: var(--primary);
  border: 1px solid var(--border);
}
.hidden { display: none; }
.error {
  margin-top: 20px;
  padding: 12px;
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
}
pre {
  background: #f9fafb;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  white-space: pre-wrap;
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
  ["web","text","audio"].forEach(t =>
    document.getElementById(t).classList.add("hidden")
  );
  document.getElementById(tab).classList.remove("hidden");
  document.getElementById("mode").value = tab;
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.remove("active")
  );
  el.classList.add("active");
}

function copyResult() {
  const text = document.getElementById("resultText").innerText;
  navigator.clipboard.writeText(text);
  alert("Copied to clipboard");
}
</script>
</head>

<body>
<div class="container">
  <div class="card">

    <div class="header">
      <h1>Aly</h1>
      <p>Translation tools built for content creators.</p>
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
      </div>

      <div id="text" class="hidden">
        <div class="label">Text</div>
        <textarea name="text" placeholder="Paste text to translate"></textarea>
      </div>

      <div id="audio" class="hidden">
        <div class="label">Audio file</div>
        <input type="file" name="audio" accept=".mp3,.wav,.m4a">
      </div>

      <div class="label">Target language</div>
      <input name="language" placeholder="e.g. Japanese, French, Chinese">

      <button type="submit">Translate</button>
    </form>

    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}

    {% if result %}
      <div style="margin-top:24px;">
        <pre id="resultText">{{ result }}</pre>
        <div class="actions">
          <button class="secondary" onclick="copyResult()">Copy</button>
          <a href="/download">
            <button type="button" class="secondary">Download .txt</button>
          </a>
        </div>
      </div>
    {% endif %}

  </div>

  <footer>
    © {{ year }} Aly • Creator Translation Tools
  </footer>
</div>
</body>
</html>
"""

# --------------------
# Routes
# --------------------
@app.route("/", methods=["GET", "POST"])
def home():
    global LAST_REQUEST_TIME, LAST_TRANSLATION
    result = None
    error = None

    if request.method == "POST":
        if time.time() - LAST_REQUEST_TIME < RATE_LIMIT_SECONDS:
            error = "Please wait a moment before submitting again."
            return render_template_string(HTML, error=error, year=date.today().year)
        LAST_REQUEST_TIME = time.time()

        mode = request.form.get("mode")
        target_language = request.form.get("language", "").strip()

        if not target_language:
            return render_template_string(
                HTML, error="Please specify a target language.", year=date.today().year
            )

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

            response = client.responses.create(
                model="gpt-4.1-mini",
                input=f"Translate the following text to {target_language}:\n\n{text}"
            )

            result = response.output_text
            LAST_TRANSLATION = result

        except Exception as e:
            error = str(e)

    return render_template_string(
        HTML,
        result=result,
        error=error,
        year=date.today().year
    )

@app.route("/download")
def download():
    if not LAST_TRANSLATION:
        return "Nothing to download."
    buffer = BytesIO()
    buffer.write(LAST_TRANSLATION.encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="aly_translation.txt",
        mimetype="text/plain"
    )

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)