from flask import Flask, request, jsonify
import requests
import time

app = Flask(__name__)

@app.route('/parse', methods=['POST'])
def parse_all_cards():
    try:
        token = request.json.get("token")
        if not token:
            return jsonify({"error": "Token not provided"}), 400

        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }

        all_cards = []
        limit = 100
        offset = 0
        start_time = time.time()
        max_time = 300  # ~5 минут лимит на выполнение

        while True:
            if time.time() - start_time > max_time - 5:
                break

            payload = {
                "limit": limit,
                "offset": offset,
                "withPhoto": True
            }

            response = requests.post(
                "https://suppliers-api.wildberries.ru/content/v1/cards/cursor/list",
                headers=headers,
                json=payload,
                timeout=20
            )

            if response.status_code != 200:
                return jsonify({
                    "error": f"WB API error: {response.status_code}",
                    "details": response.text
                }), 500

            data = response.json().get("data", [])
            if not data:
                break

            all_cards.extend(data)
            offset += limit

        return jsonify({"cards": all_cards}), 200

    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)