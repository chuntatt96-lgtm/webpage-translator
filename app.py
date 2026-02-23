import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()

LAST_REQUEST_TIME = 0
MAX_CHARS = 3000
HISTORY = []

HTML = """
<!doctype html>
<html>
<head>
  <title>AI Webpage Translator</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
      background: linear-gradient(135deg,#eef2f7,#dce3ec);
      margin:0;
      min-height:100vh;
      display:flex;
      justify-content:center;
      align-items:center;
    }
    .container {
      width:100%;
      max-width:700px;
      background:white;
      padding:30px;
      border-radius:14px;
      box-shadow:0 15px 35px rgba(0,0,0,0.1);
    }
    h1 { text-align:center; margin-bottom:6px; }
    .subtitle {
      text-align:center;
      color:#666;
      margin-bottom:20px;
      font-size:14px;
    }
    .tabs { display:flex; gap:10px; margin-bottom:20px; }
    .tab {
      flex:1;
      padding:10px;
      text-align:center;
      border-radius:8px;
      background:#f1f1f1;
      cursor:pointer;
      font-weight:600;
    }
    .tab.active {
      background:#4f46e5;
      color:white;
    }
    input, textarea {
      width:100%;
      padding:12px;
      border-radius:8px;
      border:1px solid #ccc;
      margin-bottom:15px;
      font-size:14px;
    }
    textarea { min-height:120px; resize:vertical; }
    button {
      width:100%;
      padding:14px;
      border:none;
      border-radius:10px;
      background:#4f46e5;
      color:white;
      font-weight:600;
      cursor:pointer;
    }
    .spinner {
      display:none;
      text-align:center;
      margin-top:10px;
    }
    .error {
      background:#fee2e2;
      color:#991b1b;
      padding:12px;
      border-radius:8px;
      margin-top:15px;
    }
    .result {
      margin-top:25px;
    }
    pre {
      background:#f9fafb;
      padding:15px;
      border-radius:8px;
      white-space:pre-wrap;
      max-height:300px;
      overflow:auto;
    }
    .copy-btn {
      margin-top:10px;
      background:#10b981;
    }
    .history {
      margin-top:30px;
      font-size:13px;
      color:#444;
    }
    .history-item {
      background:#f3f4f6;
      padding:8px;
      border-radius:6px;
      margin-top:5px;
    }
    .hidden { display:none; }
  </style>

  <script>
    function switchMode(mode){
      document.getElementById("urlBox").classList.toggle("hidden",mode!=="url");
      document.getElementById("textBox").classList.toggle("hidden",mode!=="text");
      document.getElementById("tab-url").classList.toggle("active",mode==="url");
      document.getElementById("tab-text").classList.toggle("active",mode==="text");
    }

    function showSpinner(){
      document.getElementById("spinner").style.display="block";
    }

    function copyText(){
      navigator.clipboard.writeText(document.getElementById("outputText").innerText);
      alert("Copied!");
    }
  </script>
</head>

<body>
<div class="container">
  <h1>🚀 AI Webpage Translator</h1>
  <div class="subtitle">Translate webpages or pasted text instantly</div>

  <div class="tabs">
    <div id="tab-url" class="tab active" onclick="switchMode('url')">🌐 URL</div>
    <div id="tab-text" class="tab" onclick="switchMode('text')">✍️ Text</div>
  </div>

  <form method="post" onsubmit="showSpinner()">
    <div id="urlBox">
      <input name="url" placeholder="https://example.com">
    </div>
    <div id="textBox" class="hidden">
      <textarea name="text" placeholder="Paste text here..."></textarea>
    </div>

    <input name="language" placeholder="Target language (e.g. Japanese)" required>

    <button type="submit">Translate</button>
  </form>

  <div id="spinner" class="spinner">⏳ Translating...</div>

  {% if error %}
    <div class="error">{{ error }}</div>
  {% endif %}

  {% if result %}
    <div class="result">
      <h3>Result</h3>
      <pre id="outputText">{{ result }}</pre>
      <button class="copy-btn" onclick="copyText()">Copy</button>
      <div style="font-size:12px;color:#666;margin-top:5px;">
        Characters used: {{ char_count }} / 3000
      </div>
    </div>
  {% endif %}

  {% if history %}
    <div class="history">
      <h4>Recent Translations</h4>
      {% for item in history %}
        <div class="history-item">{{ item }}</div>
      {% endfor %}
    </div>
  {% endif %}
</div>
</body>
</html>
"""

@app.route("/", methods=["GET","POST"])
def home():
    global LAST_REQUEST_TIME, HISTORY
    result = None
    error = None
    char_count = 0

    if request.method=="POST":
        now = time.time()
        if now - LAST_REQUEST_TIME < 5:
            error="Please wait before translating again."
            return render_template_string(HTML,error=error)
        LAST_REQUEST_TIME=now

        url=request.form.get("url","").strip()
        user_text=request.form.get("text","").strip()
        target=request.form.get("language","").strip()

        if not url and not user_text:
            error="Enter a URL or paste text."
            return render_template_string(HTML,error=error)

        if url and user_text:
            error="Use either URL or text, not both."
            return render_template_string(HTML,error=error)

        try:
            if user_text:
                text=user_text[:MAX_CHARS]
            else:
                headers={"User-Agent":"Mozilla/5.0"}
                r=requests.get(url,headers=headers,timeout=10)
                r.raise_for_status()
                soup=BeautifulSoup(r.text,"html.parser")
                for tag in soup(["script","style","noscript","header","footer","nav"]):
                    tag.decompose()
                content=soup.find("article") or soup.find("main")
                text=" ".join(content.stripped_strings if content else soup.stripped_strings)
                text=text[:MAX_CHARS]

            char_count=len(text)

            ai_response=client.responses.create(
                model="gpt-4.1-mini",
                input=f"Detect the source language and translate this into {target}. Only output translation:\n\n{text}"
            )

            result=ai_response.output_text

            HISTORY.insert(0,f"{target} • {char_count} chars")
            HISTORY=HISTORY[:5]

        except requests.exceptions.RequestException:
            error="Website blocked automated access. Try pasting text."
        except Exception as e:
            error=f"Error: {str(e)}"

    return render_template_string(HTML,result=result,error=error,
                                  char_count=char_count,
                                  history=HISTORY)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)