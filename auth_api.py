from flask import Flask, request, jsonify
from jwt_token import create_jwt

app = Flask(__name__)


@app.route("/generate-token", methods=["POST"])
def generate_token():

    data = request.json

    # Example payload (customize as needed)
    user_id = data.get("user_id")
    role = data.get("role", "User")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    payload = {
        "user_id": user_id,
        "role": role
    }

    token = create_jwt(payload)

    return jsonify({
        "access_token": token,
        "token_type": "Bearer"
    })


if __name__ == "__main__":
    app.run(debug=True)
