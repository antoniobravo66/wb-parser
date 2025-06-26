from flask import Flask, request, jsonify
from parser import parse_card

app = Flask(__name__)

@app.route("/")
def home():
    return "WB Parser API is running."

@app.route("/parse", methods=["POST"])
def parse():
    data = request.get_json()
    links = data.get("links", [])
    results = [parse_card(url) for url in links]
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)