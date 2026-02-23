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
MAX_CHARS = 2000

# --------------------
# HTML Template
# --------------------
HTML = """
<!doctype html>
<html>
<head>
  <title>Webpage Translator</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <style>
    * { box-sizing: border-box; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial;
      background: linear-gradient(135deg, #f5f7fa, #e4e7eb);
      min-height: 100vh;
      margin: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .container {
      width: 100%;
      max-width: 560px;
      background: white;
      padding: 32px;
      border-radius: 14px;
      box-shadow: 0 12px 30px rgba(0,0,0,0.12);
    }

    h1 {
      text-align: center;
      margin-bottom: 6px;
    }

    .subtitle {
      text-align: center;
      color: #666;
      font-size: 14px;
      margin-bottom: 24px;
    }

    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 20px;
    }

    .tab {
      flex: 1;
      padding: 10px;
      text-align: center;
      border-radius: 8px;
      background: #f1f1f1;
      cursor: pointer;
      font-weight: 600;
    }

    .tab.active {
      background: #4f46e5;
      color: white;
    }

    label {
      font-weight: 600;
      margin-bottom: 6px;
      display: block;
    }

    input, textarea {
      width: 100%;
      padding: 12px;
      border-radius: 8px;
      border: 1px solid #ccc;
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
      border-radius: 10px;
      border: none;
      background: #4f46e5;
      color: white;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
    }

    .error {
      background: #fee2e2;
      color: #991b1b;
      padding: 12px;
      border-radius: 8px;
      margin-top: 18px;
    }

    pre {
      background: #f9fafb;
      padding: 14px;
      border-radius: 8px;
      white-space: pre-wrap;
      margin-top: 12px;
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
  </script>
</head>

<body>
  <div class="container">
    <h1>🔥 Webpage Translator</h1>
    <div class="subtitle">Translate a webpage OR paste text directly</div>

    <div class="tabs">
      <div id="tab-url" class="tab active" onclick="switchMode('url')">🌐 URL</div>
      <div id="tab-text" class="tab" onclick="switchMode('text')">✍️ Text</div>
    </div>

    <form method="post" onsubmit="this.querySelector('button').innerText='Translating…';">

      <div id="urlBox">
        <label>Webpage URL</label>
        <input name="url" placeholder="https://example.com">
      </div>

      <div id="textBox" class="hidden">
        <label>Paste text</label>
        <textarea name="text" placeholder="Paste text here..."></textarea>
      </div>

      <label>Translate to</label>
      <input name="language" placeholder="e.g. Chinese, Japanese, French" required>

      <button type="submit">Translate</button>
    </form>

    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}

    {% if result %}
      <h3>Result</h3>
      <pre>{{ result }}</pre>
    {% endif %}
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

    if request.method == "POST":
        # ---- Rate limit ----
        now = time.time()
        if now - LAST_REQUEST_TIME < 5:
            error = "Please wait a few seconds before translating again."
            return render_template_string(HTML, result=None, error=error)
        LAST_REQUEST_TIME = now

        # ---- Inputs ----
        url = request.form.get("url", "").strip()
        user_text = request.form.get("text", "").strip()
        target_language = request.form.get("language", "").strip()

        if not url and not user_text:
            error = "Please enter a URL or paste text."
            return render_template_string(HTML, result=None, error=error)

        if url and user_text:
            error = "Please use only one input method."
            return render_template_string(HTML, result=None, error=error)

        try:
            # ---- Get text ----
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

            # ---- OpenAI ----
            ai_response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "system",
                        "content": "You are a translation engine. Only translate the text."
                    },
                    {
                        "role": "user",
                        "content": f"Translate the following text to {target_language}:\n\n{text}"
                    }
                ]
            )

            result = ai_response.output_text

        except requests.exceptions.RequestException:
            error = "Unable to access the webpage. It may block automated access."
        except Exception:
            error = "Unexpected error occurred during translation."

    return render_template_string(HTML, result=result, error=error)

# --------------------
# Run (Render-compatible)
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)