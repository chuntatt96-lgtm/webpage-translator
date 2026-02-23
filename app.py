import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string
from openai import OpenAI

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()  # Uses OPENAI_API_KEY from environment

LAST_REQUEST_TIME = 0
MAX_CHARS = 3000

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
      max-width: 680px;
      background: white;
      padding: 32px;
      border-radius: 18px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.12);
    }

    h1 {
      text-align: center;
      margin-bottom: 6px;
      font-size: 34px;
    }

    .subtitle {
      text-align: center;
      color: #555;
      font-size: 15px;
      margin-bottom: 24px;
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
      transition: all 0.2s ease;
    }

    .tab:hover {
      transform: translateY(-1px);
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
      transition: all 0.2s ease;
    }

    button:hover {
      background: #4f46e5;
      transform: translateY(-1px);
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

    .copy-btn:hover {
      background: #059669;
    }

    footer {
      margin-top: 30px;
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
      alert("Copied! 🎉");
    }
  </script>
</head>

<body>
  <div class="container">
    <h1>✨ Aly</h1>
    <div class="subtitle">
      Your friendly AI that speaks every language 🌍
    </div>

    <div class="tabs">
      <div id="tab-url" class="tab active" onclick="switchMode('url')">
        🌐 Translate a webpage
      </div>
      <div id="tab-text" class="tab" onclick="switchMode('text')">
        ✍️ Translate text
      </div>
    </div>

    <form method="post" onsubmit="this.querySelector('button').innerText='Aly is thinking… 🧠';">

      <div id="urlBox">
        <label>Webpage URL</label>
        <input name="url" placeholder="https://example.com">
        <div class="hint">Tip: Works best with blogs, docs & Wikipedia</div>
      </div>

      <div id="textBox" class="hidden">
        <label>Paste text</label>
        <textarea name="text" placeholder="Paste anything you want Aly to translate…"></textarea>
      </div>

      <label>Translate to</label>
      <input name="language" placeholder="Chinese, Japanese, Thai, French…" required>

      <button type="submit">Translate ✨</button>
    </form>

    {% if error %}
      <div class="error">
        ⚠️ {{ error }}
      </div>
    {% endif %}

    {% if result %}
      <div class="result">
        <h3>🎉 Translation ready</h3>
        <pre id="outputText">{{ result }}</pre>

        <div class="result-actions">
          <span>{{ char_count }} characters processed</span>
          <button class="copy-btn" onclick="copyResult()">Copy</button>
        </div>
      </div>
    {% endif %}

    <footer>
      © 2026 Aly • Made with curiosity & caffeine ☕
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

    result = None
    error = None
    char_count = 0

    if request.method == "POST":
        now = time.time()
        if now - LAST_REQUEST_TIME < 5:
            error = "Slow down a little 😅 Give Aly a few seconds."
            return render_template_string(HTML, error=error)
        LAST_REQUEST_TIME = now

        url = request.form.get("url", "").strip()
        user_text = request.form.get("text", "").strip()
        target_language = request.form.get("language", "").strip()

        if not url and not user_text:
            error = "Give Aly something to translate — a URL or some text ✨"
            return render_template_string(HTML, error=error)

        if url and user_text:
            error = "Pick one please 😄 Either a URL or pasted text."
            return render_template_string(HTML, error=error)

        try:
            if user_text:
                text = user_text[:MAX_CHARS]
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

            if not text.strip():
                error = "Hmm… Aly couldn’t find readable text there 🤔 Try pasting text instead."
                return render_template_string(HTML, error=error)

            char_count = len(text)

            ai_response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "system",
                        "content": "You are a friendly translation engine. Only output the translated text."
                    },
                    {
                        "role": "user",
                        "content": f"Translate the following text to {target_language}:\n\n{text}"
                    }
                ]
            )

            result = ai_response.output_text

        except requests.exceptions.RequestException:
            error = "That website blocked Aly 🚫 Try pasting the text instead."
        except Exception as e:
            error = f"Aly tripped 😅 ({str(e)})"

    return render_template_string(
        HTML,
        result=result,
        error=error,
        char_count=char_count
    )

# --------------------
# Run (Render compatible)
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)