from flask import Flask, request, jsonify
from parser import parse_wb_card

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "WB Parser API is running."

@app.route("/parse", methods=["POST"])
def parse():
    data = request.json
    links = data.get("links", [])
    results = []
    for url in links:
        result = parse_wb_card(url)
        result["url"] = url
        results.append(result)
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)