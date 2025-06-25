from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "WB Parser API is running."

@app.route("/parse", methods=["POST"])
def parse():
    data = request.json
    links = data.get("links", [])
    # Здесь можно вставить реальный парсинг
    results = [{"url": url, "title": "Название", "price": "1234", "description": "Описание", "chars": "Характеристики"} for url in links]
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
