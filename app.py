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
# HTML Template (Playful + Professional)
# --------------------
HTML = """
<!doctype html>
<title>Aly Translator</title>

<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: linear-gradient(135deg, #f6f8ff, #eef1ff);
    margin: 0;
    padding: 0;
  }
  .card {
    background: white;
    max-width: 560px;
    margin: 80px auto;
    padding: 28px;
    border-radius: 14px;
    box-shadow: 0 12px 30px rgba(0,0,0,0.12);
  }
  h2 {
    margin-top: 0;
  }
  input, button {
    width: 100%;
    padding: 12px;
    font-size: 15px;
    margin-top: 8px;
    border-radius: 8px;
    border: 1px solid #ccc;
  }
  button {
    background: #4f46e5;
    color: white;
    font-weight: bold;
    border: none;
    cursor: pointer;
  }
  button:hover {
    background: #4338ca;
  }
  footer {
    text-align: center;
    margin-top: 24px;
    font-size: 13px;
    color: #666;
  }
</style>

<div class="card">
  <h2>🔥 Aly Webpage Translator</h2>
  <p>Paste a webpage URL and translate it into <b>any language</b>.</p>

  <form method="post" onsubmit="this.querySelector('button').innerText='Translating…';">
    <label><b>Webpage URL</b></label>
    <input name="url" placeholder="https://example.com" required>

    <br><br>

    <label><b>Translate to</b></label>
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

<footer>
  Built with ❤️ by <b>Aly</b>
</footer>
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
        # ---- Simple rate limit ----
        now = time.time()
        if now - LAST_REQUEST_TIME < 5:
            error = "Please wait a few seconds before translating again."
            return render_template_string(HTML, result=None, error=error)
        LAST_REQUEST_TIME = now

        url = request.form.get("url", "").strip()
        target_language = request.form.get("language", "").strip()

        if not url or not target_language:
            error = "Please provide both a URL and a target language."
            return render_template_string(HTML, result=None, error=error)

        try:
            # ---- Fetch webpage ----
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove junk elements
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                tag.decompose()

            content = soup.find("article") or soup.find("main")
            text = " ".join(
                content.stripped_strings if content else soup.stripped_strings
            )
            text = text[:MAX_CHARS]

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

        except Exception:
            error = "Unexpected error occurred during translation."

    return render_template_string(HTML, result=result, error=error)


# --------------------
# Run (Docker / Render compatible)
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)