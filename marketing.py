from flask import Blueprint, request, jsonify, render_template
from openai import OpenAI
import os

# Initialisation client OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Blueprint
marketing_bp = Blueprint("marketing", __name__)


# ===== PAGE HTML =====
@marketing_bp.route("/marketing")
def marketing_page():
    return render_template("marketing.html")


# ===== API IA =====
@marketing_bp.route("/api/marketing/generate", methods=["POST"])
def generate_post():
    data = request.get_json()
    prompt = data.get("prompt", "")

    if not prompt:
        return jsonify({"error": "Prompt vide"}), 400

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en community management et marketing digital. Tu rédiges des publications engageantes avec des hashtags performants."
                },
                {
                    "role": "user",
                    "content": f"Rédige un texte de publication optimisé avec des hashtags : {prompt}"
                }
            ],
            temperature=0.7,
            max_tokens=300
        )

        result = response.choices[0].message.content

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500