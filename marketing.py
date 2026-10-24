
import logging
import os
import re

from dotenv import load_dotenv
from flask import Blueprint, jsonify, render_template, request
from groq import Groq

# Charger les variables du fichier .env
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "openai/gpt-oss-20b"

# Créer le client uniquement si la clé existe
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

marketing_bp = Blueprint("marketing", __name__)


def build_hashtags(prompt: str, limit: int = 6) -> str:
    """Construire une liste de hashtags simple et exploitable à partir d'un prompt."""
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", prompt.lower())
    stop_words = {
        "avec", "pour", "dans", "sur", "sans", "entre", "comme", "cette", "cette",
        "cest", "comment", "une", "des", "les", "aux", "plus", "tous", "toutes",
        "très", "votre", "votre", "notre", "cela", "deja", "pourquoi", "quoi", "quel",
        "quels", "quelle", "quelles", "plusieurs", "toujours", "avoir", "faire", "faire",
        "vous", "nous", "tu", "je", "est", "sont", "etc", "avoir", "apres", "avant",
        "alors", "donc", "mieux", "avoir", "besoin", "bien", "cette", "ceci", "leur",
        "leurs", "vraiment", "peut", "peuvent", "faire", "mettre", "montrer", "gagner"
    }
    selected = []
    seen = set()

    for word in words:
        if len(word) <= 3 or word in stop_words:
            continue
        tag = "#" + word.strip()
        if tag not in seen:
            seen.add(tag)
            selected.append(tag)
        if len(selected) >= limit:
            break

    if len(selected) < 4:
        selected.extend(["#marketingdigital", "#communitymanager", "#copywriting", "#socialmedia"])

    return " ".join(selected[:limit])


@marketing_bp.route("/marketing", methods=["GET"])
def marketing_page():
    """Afficher la page de génération marketing."""
    return render_template("marketing.html")


@marketing_bp.route("/api/marketing/generate", methods=["POST"])
def generate_post():
    """Générer une publication marketing avec Groq."""
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({
            "error": "Veuillez saisir une demande pour générer la publication."
        }), 400

    if client is None:
        return jsonify({
            "error": "La clé GROQ_API_KEY est absente. Vérifiez votre fichier .env."
        }), 503

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un expert senior en community management, copywriting et marketing digital. "
                        "Ta mission est de créer des publications qui attirent l’attention, suscitent l’intérêt, "
                        "donnent envie d’agir et maximisent le taux d’engagement. "
                        "Rédige des textes naturels, percutants et crédibles, avec une vraie logique de storytelling. "
                        "L’objectif est toujours de créer une émotion, un besoin, ou une curiosité immédiate. "
                        "Adapte le ton selon la plateforme, le public et la promesse, sans être trop générique. "
                        "Tu dois inclure une accroche forte, un message clair, une valeur utile et un appel à l’action pertinent. "
                        "Ajoute obligatoirement 3 à 8 hashtags bien ciblés, sur une ligne séparée à la fin. "
                        "Format de sortie impératif : texte de publication, puis une ligne vide, puis 'Hashtags: ' suivi des hashtags. "
                        "Ne donne jamais de faux faits, ne gonfle pas les promesses et reste crédible. "
                        "Optimise le texte pour les réseaux sociaux : simple, impactant, mémorable, orienté conversion."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Rédige une publication sociale performante basée sur cette demande. "
                        "Structure le texte comme un vrai community manager : intro captivante, valeur utile, émotion / bénéfice, puis CTA fort. "
                        "Le texte doit être prêt à publier, fluide et convaincant. "
                        "Respecte strictement le format demandé : texte, ligne vide, puis Hashtags: ...\n\n"
                        f"Demande : {prompt}"
                    ),
                },
            ],
            temperature=0.7,
            max_completion_tokens=500,
        )

        result = (response.choices[0].message.content or "").strip()

        if not result:
            return jsonify({
                "error": "Le modèle n'a retourné aucun texte."
            }), 502

        if "#" not in result:
            result = f"{result.rstrip()}\n\nHashtags: {build_hashtags(prompt)}"

        return jsonify({"result": result}), 200

    except Exception:
        logging.exception("Erreur lors de la génération de la publication marketing.")
        return jsonify({
            "error": (
                "Impossible de générer la publication. Vérifiez votre clé Groq, "
                "le modèle utilisé et les journaux de l'application."
            )
        }), 502
