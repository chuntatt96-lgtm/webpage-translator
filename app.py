from flask import Flask, render_template
from server import sock

app = Flask(__name__)
sock.init_app(app)

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)