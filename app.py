import os
import time
import csv
from datetime import date

from flask import Flask, request, render_template_string, jsonify
from openai import OpenAI

# --------------------
# App setup
# --------------------
app = Flask(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

USAGE_LOG = "usage_log.csv"
MAX_CHARS = 3000
RATE_LIMIT_SECONDS = 5
LAST_REQUEST_TIME = {}

DAILY_LIMITS = {
    "text": 5,
    "extension": 20
}

# --------------------
# CORS (for Chrome extension)
# --------------------
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# --------------------
# Usage tracking
# --------------------
def log_usage(feature, chars, language, ip):
    exists = os.path.exists(USAGE_LOG)
    with open(USAGE_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["timestamp", "feature", "characters", "language", "ip"])
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            feature,
            chars,
            language,
            ip
        ])


def check_daily_limit(ip, feature):
    today = date.today().isoformat()
    count = 0

    if not os.path.exists(USAGE_LOG):
        return True

    with open(USAGE_LOG, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                row["ip"] == ip
                and row["feature"] == feature
                and row["timestamp"].startswith(today)
            ):
                count += 1

    return count < DAILY_LIMITS.get(feature, 0)


# --------------------
# AI helper
# --------------------
def translate_text(text, language, feature, ip):
    text = text[:MAX_CHARS]

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"Translate the following text to {language}:\n\n{text}"
    )

    result = response.output_text
    log_usage(feature, len(text), language, ip)
    return result


# --------------------
# Chrome Extension Endpoint
# --------------------
@app.route("/extension", methods=["POST"])
def extension_translate():
    data = request.json
    text = data.get("text", "")
    language = data.get("language", "English")
    ip = request.remote_addr

    if not check_daily_limit(ip, "extension"):
        return jsonify({"error": "Daily extension limit reached"}), 403

    result = translate_text(text, language, "extension", ip)
    return jsonify({"result": result})


# --------------------
# Main UI
# --------------------
HTML = """
<!doctype html>
<title>Aly — Built for Creators</title>
<style>
body { font-family: Arial; background:#0b0d10; color:white; margin:0;}
.container { max-width:860px; margin:60px auto; padding:24px;}
.card { background:#12151b; border-radius:18px; padding:36px;}
h1 { font-size:36px; font-weight:900;}
input, textarea { width:100%; padding:14px; margin-top:10px; border-radius:12px; background:#0b0e14; border:1px solid #1f2937; color:white;}
button { margin-top:20px; padding:14px; border-radius:14px; background:#ff4d4d; border:none; font-weight:800; cursor:pointer;}
.result { margin-top:30px; padding:20px; border-radius:14px; background:#0b0e14; white-space:pre-wrap;}
.error { margin-top:20px; padding:14px; border-radius:12px; background:#2a1212; color:#ffb4b4;}
</style>

<div class="container">
<div class="card">
<h1>Aly</h1>
<p>Translate text into publish-ready content.</p>

<form method="post">
<textarea name="text" placeholder="Paste text here"></textarea>
<input name="language" placeholder="Translate to (e.g. Japanese)" required>
<button>Translate</button>
</form>

{% if error %}
<div class="error">{{ error }}</div>
{% endif %}

{% if result %}
<div class="result">{{ result }}</div>
{% endif %}

</div>
</div>
"""


# --------------------
# Web App Route
# --------------------
@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    error = None

    if request.method == "POST":
        ip = request.remote_addr
        language = request.form.get("language")
        text = request.form.get("text", "")

        last_time = LAST_REQUEST_TIME.get(ip, 0)
        if time.time() - last_time < RATE_LIMIT_SECONDS:
            error = "Please wait a moment."
        elif not check_daily_limit(ip, "text"):
            error = "Daily limit reached."
        else:
            LAST_REQUEST_TIME[ip] = time.time()
            try:
                result = translate_text(text, language, "text", ip)
            except Exception as e:
                print(e)
                error = "Processing failed."

    return render_template_string(HTML, result=result, error=error)


# --------------------
# Run (Render compatible)
# --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)