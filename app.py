import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string
from openai import OpenAI

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()  # Uses OPENAI_API_KEY from environment (Render / local)

LAST_REQUEST_TIME = 0
MAX_CHARS = 2000

# --------------------
# HTML Template
# --------------------
HTML = """
<!doctype html>
<title>Webpage Translator</title>

<style>
  body {
    font-family: Arial, sans-serif;
    background: #f2f2f2;
  }
  .card {
    background: white;
    width: 520px;
    margin: 60px auto;
    padding: 24px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }
  input, button {
    width: 100%;
    padding: 10px;
    font-size: 14px;
    margin-top: 6px;
  }
  button {
    cursor: pointer;
  }
</style>

<div class="card">
  <h2>🔥 Webpage Translator 🔥</h2>
  <p>Paste a webpage URL and enter any target language.</p>

  <form method="post" onsubmit="this.querySelector('button').innerText='Translating…';">
    <label>Webpage URL</label>
    <input name="url" placeholder="https://example.com" required>

    <br><br>

    <label>Translate to</label>
    <input name="language" placeholder="e.g. Chinese, Japanese, French, Thai" required>

    <br><br>
    <button type="submit">Translate</button>
  </form>

  {% if error %}
    <p style="color:red; margin-top:15px;"><b>Error:</b> {{ error }}</p>
  {% endif %}

  {% if result %}
    <hr>
    <h3>Translation Result</h3>
    <pre style="white-space: pre-wrap;">{{ result }}</pre>
  {% endif %}
</div>
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

        # ---- Get inputs ----
        url = request.form.get("url", "").strip()
        target_language = request.form.get("language", "").strip()

        if not url:
            error = "Please enter a webpage URL."
            return render_template_string(HTML, result=None, error=error)

        if not target_language:
            error = "Please specify a target language."
            return render_template_string(HTML, result=None, error=error)

        try:
            # ---- Fetch webpage ----
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove junk tags
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                tag.decompose()

            content = soup.find("article") or soup.find("main")
            text = " ".join(
                content.stripped_strings if content else soup.stripped_strings
            )

            text = text[:MAX_CHARS]

            if not text.strip():
                error = "No readable text found on this webpage."
                return render_template_string(HTML, result=None, error=error)

            # ---- OpenAI Translation ----
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

        except Exception as e:
            error = f"Unexpected error: {str(e)}"

    return render_template_string(HTML, result=result, error=error)

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)