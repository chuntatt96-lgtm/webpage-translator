import time
import csv
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string
from openai import OpenAI
from datetime import date, datetime

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()  # Uses OPENAI_API_KEY from environment

MAX_CHARS = 3000
DAILY_LIMIT = 10  # per IP per day

# In-memory daily usage tracking
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
# HTML Template
# --------------------
HTML = """
<!doctype html>
<html>
<head>
  <title>Aly — Friendly AI Translator</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial;
      background: linear-gradient(135deg, #fef6ff, #eef2ff);
      min-height: 100vh;
      margin: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .container {
      width: 100%;
      max-width: 720px;
      background: white;
      padding: 32px;
      border-radius: 18px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.12);
    }
    h1 {
      text-align: center;
      margin-bottom: 6px;
      font-size: 36px;
    }
    .subtitle {
      text-align: center;
      color: #555;
      font-size: 15px;
      margin-bottom: 26px;
    }
    .intro {
      background: #f9fafb;
      padding: 16px;
      border-radius: 12px;
      font-size: 14px;
      color: #444;
      margin-bottom: 26px;
      line-height: 1.6;
    }
    .tabs {
      display: flex;
      gap: 10px;
      margin-bottom: 20px;
    }
    .tab {
      flex: 1;
      padding: 10px;
      text-align: center;
      border-radius: 10px;
      background: #f3f4f6;
      cursor: pointer;
      font-weight: 600;
    }
    .tab.active {
      background: #6366f1;
      color: white;
    }
    label {
      font-weight: 600;
      margin-bottom: 6px;
      display: block;
      font-size: 14px;
    }
    input, textarea {
      width: 100%;
      padding: 12px;
      border-radius: 10px;
      border: 1px solid #d1d5db;
      margin-bottom: 18px;
      font-size: 14px;
    }
    textarea {
      resize: vertical;
      min-height: 120px;
    }
    button {
      width: 100%;
      padding: 14px;
      border-radius: 12px;
      border: none;
      background: #6366f1;
      color: white;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
    }
    .hint {
      font-size: 13px;
      color: #6b7280;
      margin-top: -10px;
      margin-bottom: 14px;
    }
    .error {
      background: #fee2e2;
      color: #991b1b;
      padding: 14px;
      border-radius: 12px;
      margin-top: 18px;
      font-size: 14px;
    }
    .result {
      margin-top: 28px;
    }
    pre {
      background: #f9fafb;
      padding: 16px;
      border-radius: 12px;
      white-space: pre-wrap;
      max-height: 320px;
      overflow-y: auto;
      line-height: 1.55;
      font-size: 14px;
    }
    .result-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 10px;
      font-size: 13px;
      color: #555;
    }
    .copy-btn {
      background: #10b981;
      border: none;
      padding: 8px 14px;
      border-radius: 8px;
      color: white;
      cursor: pointer;
      font-weight: 600;
    }
    footer {
      margin-top: 34px;
      text-align: center;
      font-size: 12px;
      color: #888;
    }
    .hidden { display: none; }
  </style>

  <script>
    function switchMode(mode) {
      document.getElementById("urlBox").classList.toggle("hidden", mode !== "url");
      document.getElementById("textBox").classList.toggle("hidden", mode !== "text");
      document.getElementById("tab-url").classList.toggle("active", mode === "url");
      document.getElementById("tab-text").classList.toggle("active", mode === "text");
    }
    function copyResult() {
      navigator.clipboard.writeText(
        document.getElementById("outputText").innerText
      );
      alert("Copied! ✨");
    }
  </script>
</head>

<body>
<div class="container">
  <h1>✨ Aly</h1>
  <div class="subtitle">Your friendly AI translator for web & text 🌍</div>

  <div class="intro">
    <b>What is Aly?</b><br>
    Aly helps you instantly translate webpages or text into any language.
    Perfect for research, reading foreign articles, or quick understanding.
  </div>

  <div class="tabs">
    <div id="tab-url" class="tab active" onclick="switchMode('url')">🌐 Webpage</div>
    <div id="tab-text" class="tab" onclick="switchMode('text')">✍️ Text</div>
  </div>

  <form method="post" onsubmit="this.querySelector('button').innerText='Aly is thinking… 🧠';">

    <div id="urlBox">
      <label>Webpage URL</label>
      <input name="url" placeholder="https://example.com">
      <div class="hint">Best with blogs, docs, Wikipedia, news</div>
    </div>

    <div id="textBox" class="hidden">
      <label>Paste text</label>
      <textarea name="text" placeholder="Paste anything you want Aly to translate…"></textarea>
    </div>

    <label>Translate to</label>
    <input name="language" placeholder="Chinese, Japanese, French, Thai…" required>

    <button type="submit">Translate ✨</button>
  </form>

  {% if error %}
    <div class="error">⚠️ {{ error }}</div>
  {% endif %}

  {% if result %}
    <div class="result">
      <h3>🎉 Translation ready</h3>
      <pre id="outputText">{{ result }}</pre>
      <div class="result-actions">
        <span>{{ char_count }} characters • {{ remaining }} left today</span>
        <button class="copy-btn" onclick="copyResult()">Copy</button>
      </div>
    </div>
  {% endif %}

  <footer>
    © 2026 Aly • Built thoughtfully ☕
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
    today = date.today().isoformat()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    record = USAGE.get(ip)
    if not record or record["date"] != today:
        USAGE[ip] = {"date": today, "count": 0}

    remaining = DAILY_LIMIT - USAGE[ip]["count"]

    result = None
    error = None
    char_count = 0

    if request.method == "POST":
        if USAGE[ip]["count"] >= DAILY_LIMIT:
            error = "Aly needs a short break 💤 Come back tomorrow!"
            return render_template_string(HTML, error=error, remaining=0)

        url = request.form.get("url", "").strip()
        user_text = request.form.get("text", "").strip()
        target_language = request.form.get("language", "").strip()

        if not url and not user_text:
            error = "Give Aly something to translate — a URL or some text ✨"
            return render_template_string(HTML, error=error, remaining=remaining)

        if url and user_text:
            error = "Pick one please 😄 URL or text, not both."
            return render_template_string(HTML, error=error, remaining=remaining)

        try:
            if user_text:
                text = user_text[:MAX_CHARS]
                mode = "text"
            else:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                    tag.decompose()
                content = soup.find("article") or soup.find("main")
                text = " ".join(
                    content.stripped_strings if content else soup.stripped_strings
                )
                text = text[:MAX_CHARS]
                mode = "url"

            if not text.strip():
                error = "Aly couldn’t find readable text 🤔 Try pasting text instead."
                return render_template_string(HTML, error=error, remaining=remaining)

            char_count = len(text)

            ai_response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {"role": "system", "content": "You are a friendly translation engine. Only output the translated text."},
                    {"role": "user", "content": f"Translate this to {target_language}:\n\n{text}"}
                ]
            )

            result = ai_response.output_text

            # Track usage
            USAGE[ip]["count"] += 1
            remaining -= 1
            log_usage(ip, mode, char_count)

        except requests.exceptions.RequestException:
            error = "That website blocked Aly 🚫 Try pasting the text instead."
        except Exception as e:
            error = f"Aly tripped 😅 ({str(e)})"

    return render_template_string(
        HTML,
        result=result,
        error=error,
        char_count=char_count,
        remaining=remaining
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)