
import os
import re
import time
import uuid
import logging
from pathlib import Path

import requests
import yt_dlp
import imageio_ffmpeg

from flask import (
    Flask,
    render_template,
    request,
    send_file,
    jsonify,
)
from openai import OpenAI
from marketing import marketing_bp


# ==================================================
# INITIALISATION FLASK
# ==================================================

app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "super-secret-dev-key"
)

app.register_blueprint(marketing_bp)


# ==================================================
# CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_FOLDER = BASE_DIR / "downloads"
DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

if not os.path.isfile(FFMPEG_PATH):
    raise RuntimeError(
        f"FFmpeg introuvable : {FFMPEG_PATH}"
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ==================================================
# ROBOTS.TXT
# ==================================================

@app.route("/robots.txt")
def robots():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Sitemap: https://youtube-downloader-z1vn.onrender.com/sitemap.xml",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


# ==================================================
# OUTILS
# ==================================================

def validate_url(url):
    """Accepte uniquement les URL YouTube."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    allowed_hosts = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtube-nocookie.com",
    }

    if parsed.scheme not in ("http", "https"):
        raise ValueError("L'URL doit commencer par http:// ou https://.")

    if hostname not in allowed_hosts:
        raise ValueError("Veuillez fournir une URL YouTube valide.")

    return url


def create_ydl_options():
    """Options communes à yt-dlp."""
    return {
        "ffmpeg_location": FFMPEG_PATH,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
    }


# ==================================================
# WHISPER
# ==================================================

def get_whisper_model():
    import whisper
    return whisper.load_model("tiny")


# ==================================================
# RÉSUMÉ VIDÉO
# ==================================================

def generate_summary(video_url):
    if client is None:
        raise RuntimeError(
            "La clé OPENAI_API_KEY n'est pas configurée."
        )

    validate_url(video_url)

    logging.info("Début du résumé vidéo.")

    text_for_summary = ""
    audio_file = None

    # Première tentative : récupérer les sous-titres
    ydl_opts = create_ydl_options()
    ydl_opts.update({
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    subtitles = info.get("subtitles") or {}
    automatic_subtitles = info.get("automatic_captions") or {}

    # Priorité aux sous-titres français, puis anglais,
    # puis aux autres langues disponibles.
    available = subtitles or automatic_subtitles

    if available:
        lang = (
            "fr" if "fr" in available
            else "en" if "en" in available
            else next(iter(available))
        )

        entries = available.get(lang, [])

        subtitle_entry = next(
            (
                item for item in entries
                if item.get("ext") == "vtt"
            ),
            entries[0] if entries else None,
        )

        if subtitle_entry:
            response = requests.get(
                subtitle_entry["url"],
                timeout=30,
            )
            response.raise_for_status()
            subtitle_text = response.text

            # Supprimer les en-têtes, timestamps et balises VTT.
            subtitle_text = re.sub(
                r"(?m)^\d{2}:\d{2}:\d{2}\.\d+\s+-->.*$",
                " ",
                subtitle_text,
            )
            subtitle_text = re.sub(
                r"(?m)^\d{2}:\d{2}(?:\.\d+)?\s+-->.*$",
                " ",
                subtitle_text,
            )
            subtitle_text = re.sub(
                r"<[^>]+>",
                " ",
                subtitle_text,
            )
            subtitle_text = re.sub(
                r"(?m)^(WEBVTT|Kind:.*|Language:.*|\d+)\s*$",
                " ",
                subtitle_text,
            )
            subtitle_text = re.sub(
                r"\s+",
                " ",
                subtitle_text,
            ).strip()

            text_for_summary = subtitle_text

    # Si aucun sous-titre exploitable, télécharger l'audio
    # puis le transcrire avec Whisper.
    if not text_for_summary:
        audio_file = DOWNLOAD_FOLDER / f"temp_audio_{uuid.uuid4().hex}"

        ydl_opts_audio = create_ydl_options()
        ydl_opts_audio.update({
            "format": "bestaudio/best",
            "outtmpl": str(audio_file) + ".%(ext)s",
            "quiet": True,
            "no_warnings": True,
        })

        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            info = ydl.extract_info(video_url, download=True)
            downloaded_path = Path(ydl.prepare_filename(info))

        if not downloaded_path.exists():
            candidates = list(
                DOWNLOAD_FOLDER.glob(audio_file.name + ".*")
            )
            if not candidates:
                raise FileNotFoundError(
                    "Le fichier audio temporaire est introuvable."
                )
            downloaded_path = candidates[0]

        audio_file = downloaded_path

        try:
            logging.info("Transcription audio avec Whisper.")
            model = get_whisper_model()
            result = model.transcribe(str(audio_file))
            text_for_summary = result.get("text", "").strip()
        finally:
            if audio_file.exists():
                audio_file.unlink()

    if not text_for_summary:
        raise RuntimeError(
            "Impossible de récupérer le texte de cette vidéo."
        )

    # Limiter la taille envoyée au modèle pour éviter
    # une requête excessivement longue.
    text_for_summary = text_for_summary[:50000]

    logging.info("Génération du résumé avec OpenAI.")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un assistant qui résume les vidéos "
                    "clairement, fidèlement et de manière concise."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Résume cette transcription en français, "
                    "en présentant les idées essentielles :\n\n"
                    + text_for_summary
                ),
            },
        ],
        temperature=0.5,
        max_tokens=400,
    )

    return response.choices[0].message.content or ""


# ==================================================
# TÉLÉCHARGEMENT VIDÉO / AUDIO
# ==================================================

def _download_video(url, file_format):
    validate_url(url)

    file_format = file_format.lower().strip()

    if file_format not in ("mp4", "mp3"):
        raise ValueError("Format invalide : choisissez MP4 ou MP3.")

    download_id = uuid.uuid4().hex
    output_template = str(
        DOWNLOAD_FOLDER / f"{download_id}.%(ext)s"
    )

    ydl_opts = create_ydl_options()
    ydl_opts.update({
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
    })

    if file_format == "mp4":
        # Préférer un MP4 avec audio intégré si disponible.
        # Sinon, fusionner la meilleure vidéo et le meilleur audio.
        ydl_opts["format"] = (
            "best[ext=mp4]/bestvideo*+bestaudio/best"
        )
        ydl_opts["merge_output_format"] = "mp4"

    else:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    logging.info(
        "Téléchargement demandé : format=%s",
        file_format,
    )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        prepared_path = Path(ydl.prepare_filename(info))

    # yt-dlp peut changer l'extension après fusion/conversion.
    if file_format == "mp3":
        final_path = prepared_path.with_suffix(".mp3")
    else:
        final_path = prepared_path.with_suffix(".mp4")

    if not final_path.is_file():
        # Recherche le fichier réel associé à cet identifiant.
        candidates = list(
            DOWNLOAD_FOLDER.glob(f"{download_id}.*")
        )

        candidates = [
            path for path in candidates
            if path.is_file()
            and not path.name.endswith((".part", ".ytdl"))
        ]

        if file_format == "mp4":
            mp4_candidates = [
                path for path in candidates
                if path.suffix.lower() == ".mp4"
            ]
            candidates = mp4_candidates or candidates
        else:
            mp3_candidates = [
                path for path in candidates
                if path.suffix.lower() == ".mp3"
            ]
            candidates = mp3_candidates

        if candidates:
            final_path = candidates[0]
        else:
            raise FileNotFoundError(
                "Le téléchargement s'est terminé, "
                "mais le fichier final est introuvable."
            )

    if final_path.stat().st_size == 0:
        raise RuntimeError("Le fichier téléchargé est vide.")

    logging.info("Fichier prêt : %s", final_path)

    return str(final_path)


# ==================================================
# ENVOI DU FICHIER AU NAVIGATEUR
# ==================================================

def send_download(filename, file_format):
    mimetype = (
        "video/mp4"
        if file_format == "mp4"
        else "audio/mpeg"
    )

    return send_file(
        filename,
        as_attachment=True,
        download_name=Path(filename).name,
        mimetype=mimetype,
    )


# ==================================================
# API : RÉSUMÉ
# ==================================================

@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "URL manquante."}), 400

    try:
        summary = generate_summary(url)
        return jsonify({"summary": summary})

    except Exception:
        logging.exception("Erreur pendant le résumé AJAX.")
        return jsonify({
            "error": (
                "Impossible de résumer cette vidéo. "
                "Vérifiez l'URL, les sous-titres et la configuration."
            )
        }), 500


# ==================================================
# API : TÉLÉCHARGEMENT
# ==================================================

@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}

    url = (data.get("url") or "").strip()
    file_format = (data.get("format") or "mp4").strip().lower()

    if not url:
        return jsonify({"error": "URL manquante."}), 400

    if file_format not in ("mp4", "mp3"):
        return jsonify({
            "error": "Format invalide : choisissez MP4 ou MP3."
        }), 400

    try:
        filename = _download_video(url, file_format)
        return send_download(filename, file_format)

    except Exception:
        logging.exception("Erreur téléchargement AJAX.")
        return jsonify({
            "error": (
                "Le téléchargement a échoué. "
                "Consultez les logs du serveur pour le détail."
            )
        }), 500


# ==================================================
# PAGE PRINCIPALE
# ==================================================

@app.route("/", methods=["GET", "POST"])
def index():
    summary = None

    if request.method == "POST":
        url = (request.form.get("url") or "").strip()
        file_format = (
            request.form.get("format") or "mp4"
        ).strip().lower()
        action = request.form.get("action", "download")

        try:
            if not url:
                raise ValueError("Veuillez saisir une URL YouTube.")

            if action == "summarize":
                summary = generate_summary(url)
                return render_template(
                    "index.html",
                    summary=summary,
                )

            filename = _download_video(url, file_format)
            return send_download(filename, file_format)

        except Exception as exc:
            logging.exception("Erreur sur la page principale.")
            summary = f"Erreur : {exc}"

    return render_template("index.html", summary=summary)


# ==================================================
# DÉMARRAGE
# ==================================================

if __name__ == "__main__":
    logging.info("Démarrage du serveur Flask.")
    logging.info("FFmpeg : %s", FFMPEG_PATH)

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False,
    )
