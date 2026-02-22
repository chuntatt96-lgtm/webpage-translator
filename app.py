import time

LAST_REQUEST_TIME = 0

from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()

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
  button {
    padding: 8px 18px;
    font-size: 14px;
    cursor: pointer;
  }
</style>

<div class="card">
  <h2>🔥 Webpage Translator (Updated) 🔥</h2>
  <p>Paste a webpage URL and choose a target language.</p>

  <form method="post" onsubmit="this.querySelector('button').innerText='Translating…';">
    <input name="url"
           style="width:100%; padding:8px;"
           placeholder="https://example.com"
           required>

    <br><br>

    <label><b>Translate to:</b></label><br>
    <input name="language"
       style="width:100%; padding:8px;"
       placeholder="e.g. Chinese, Japanese, French, German"
       required>

    <br><br>

    <button type="submit">Translate</button>
  </form>

  {% if error %}
    <p style="color:red; margin-top:15px;">
      <b>Error:</b> {{ error }}
    </p>
  {% endif %}

  {% if result %}
    <hr>
    <h3>Translation Result</h3>
    <pre style="white-space: pre-wrap;">{{ result }}</pre>
  {% endif %}
</div>
"""




@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    error = None

    if request.method == "POST":
        global LAST_REQUEST_TIME
        now = time.time()

        if now - LAST_REQUEST_TIME < 5:
            error = "Please wait a few seconds before translating again."
            return render_template_string(HTML, result=None, error=error)

        LAST_REQUEST_TIME = now

        url = request.form["url"]
        target_language = request.form["language"]

        try:
            headers = {
                "User-Agent": "Mozilla/5.0"
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                tag.decompose()

            content = soup.find("article") or soup.find("main")

            if content:
                text = " ".join(content.stripped_strings)
            else:
                text = " ".join(soup.stripped_strings)

            MAX_CHARS = 2000
            text = text[:MAX_CHARS]


            ai_response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "system",
                        "content": "You are a translation engine. Only translate the provided text into the target language. Do not add explanations."
                    },
                    {
                        "role": "user",
                        "content": f"Target language: {target_language}\n\nText:\n{text}"
                    }
    ]
)


            result = ai_response.output_text

        except requests.exceptions.RequestException:
            error = "Unable to access the webpage. It may block automated access."

        except Exception:
            error = "Unexpected error occurred during translation."

    return render_template_string(HTML, result=result, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

