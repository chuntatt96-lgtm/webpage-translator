import time
import os
import tempfile
from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# --------------------
# App setup
# --------------------
app = Flask(__name__)
client = OpenAI()  # uses OPENAI_API_KEY from environment

LAST_REQUEST_TIME = 0
MAX_CHARS = 2000

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
    width: 560px;
    margin: 50px auto;
    padding: 28px;
    border-radius: 14px;
    box-shadow: 0 12px 30px rgba(0,0,0,0.12);
  }
  h2 {
    margin-top: 0;
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
    border-radius: 8px;
    background: #f0f0f0;
    cursor: pointer;
    font-weight: bold;
  }
  .tab.active {
    background: #ff6b6b;
    color: white;
  }
  input, textarea, button {
    width: 100%;
    padding: 10px;
    margin-top: 8px;
    font-size: 14px;
  }
  button {
    margin-top: 16px;
    background: #ff6b6b;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
  }
  button:hover {
    background: #ff5252;
  }
  .hidden {
    display: none;
  }
  .error {
    color: red;
    margin-top: 12px;
  }
  pre {
    white-space: pre-wrap;
    background: #fafafa;
    padding: 14px;
    border-radius: 8px;
  }
  footer {
    text-align: center;
    margin-top: 25px;
    font-size: 12px;
    color: #888;
  }
</style>

<div class="card">
  <h2>✨ Aly Translator ✨</h2>
  <p>Translate webpages, text, or audio — effortlessly.</p>

  <div class="tabs">
    <div class="tab active" onclick="showTab('web')">🌐 Webpage</div>
    <div class="tab" onclick="showTab('text')">✍️ Text</div>
    <div class="tab" onclick="showTab('audio')">🔊 Audio</div>
  </div>

  <form method="post" enctype="multipart/form-data"
        onsubmit="this.querySelector('button').innerText='Working magic… ✨';">

    <input type="hidden" name="mode" id="mode" value="web">

    <!-- Webpage -->
    <div id="web">
      <label>Webpage URL</label>
      <input name="url" placeholder="https://example.com">
    </div>

    <!-- Text -->
    <div id="text" class="hidden">
      <label>Paste text</label>
      <textarea name="text" rows="6"
        placeholder="Paste anything here…"></textarea>
    </div>

    <!-- Audio -->
    <div id="audio" class="hidden">
      <label>Upload audio file (mp3 / wav / m4a)</label>
      <input type="file" name="audio">
    </div>

    <label>Translate to</label>
    <input name="language" placeholder="e.g. Chinese, Japanese, French">

    <button type="submit">Translate 🚀</button>
  </form>

  {% if error %}
    <div class="error"><b>Error:</b> {{ error }}</div>
  {% endif %}

  {% if result %}
    <hr>
    <h3>Result</h3>
    <pre>{{ result }}</pre>
  {% endif %}

  <footer>Made with ❤️ by Aly</footer>
</div>

<script>
function showTab(tab) {
  document.getElementById("web").classList.add("hidden");
  document.getElementById("text").classList.add("hidden");
  document.getElementById("audio").classList.add("hidden");

  document.getElementById(tab).classList.remove("hidden");
  document.getElementById("mode").value = tab;

  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
}
</script>
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
        now = time.time()
        if now - LAST_REQUEST_TIME < 4:
            return render_template_string(HTML, error="Slow down 😉 Try again in a moment.")
        LAST_REQUEST_TIME = now

        mode = request.form.get("mode")
        target_language = request.form.get("language", "").strip()

        if not target_language:
            return render_template_string(HTML, error="Please specify a target language.")

        try:
            # --------------------
            # WEBPAGE MODE
            # --------------------
            if mode == "web":
                url = request.form.get("url", "").strip()
                if not url:
                    raise ValueError("Please enter a webpage URL.")

                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                    tag.decompose()

                content = soup.find("article") or soup.find("main")
                text = " ".join(
                    content.stripped_strings if content else soup.stripped_strings
                )[:MAX_CHARS]

            # --------------------
            # TEXT MODE
            # --------------------
            elif mode == "text":
                text = request.form.get("text", "").strip()
                if not text:
                    raise ValueError("Please paste some text to translate.")
                text = text[:MAX_CHARS]

            # --------------------
            # AUDIO MODE
            # --------------------
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
                    text = transcript.text[:MAX_CHARS]

            # --------------------
            # TRANSLATION
            # --------------------
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=f"Translate the following text to {target_language}:\n\n{text}"
            )

            result = response.output_text

        except Exception as e:
            error = str(e)

    return render_template_string(HTML, result=result, error=error)


# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)