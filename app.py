
import logging
import os
import re
import time
import uuid
from pathlib import Path

import imageio_ffmpeg
import yt_dlp
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
from groq import Groq
from werkzeug.utils import secure_filename

from marketing import marketing_bp


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent


def get_download_dir():
    """Choisir un dossier de stockage fiable en local et en production."""
    if os.getenv("VERCEL"):
        candidate = Path("/tmp/downloads")
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    candidates = [
        Path.home() / "Downloads",
        Path.home() / "downloads",
        Path("/tmp/downloads"),
        BASE_DIR / "downloads",
    ]

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if candidate.exists() and os.access(candidate, os.W_OK):
                return candidate
        except OSError:
            continue

    return BASE_DIR / "downloads"


DOWNLOAD_FOLDER = get_download_dir()
DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = not app.debug
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000

app.register_blueprint(marketing_bp)


@app.after_request
def add_security_and_cache_headers(response):
    """Ajouter des en-têtes de sécurité et de cache en production."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self';"
    )

    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

    return response

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# VALIDATION DES URLS YOUTUBE
# =========================================================

def validate_url(url):
    """Vérifier que l'URL correspond à YouTube."""
    if not isinstance(url, str):
        return False

    url = url.strip()

    pattern = (
        r"^(https?://)?"
        r"(www\.|m\.)?"
        r"(youtube\.com|youtu\.be|youtube-nocookie\.com)"
        r"(/|$)"
    )

    return bool(re.match(pattern, url, re.IGNORECASE))


def normalize_url(url):
    """Ajouter https:// si le protocole est absent."""
    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


# =========================================================
# OPTIONS YT-DLP
# =========================================================

def create_ydl_options(output_path=None, audio_only=False):
    """Préparer les options de téléchargement."""
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ffmpeg_location": FFMPEG_PATH,
        "socket_timeout": 30,
        "retries": 3,
    }

    if output_path:
        options["outtmpl"] = str(output_path)

    if audio_only:
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        options["format"] = "bestvideo*+bestaudio/best"
        options["merge_output_format"] = "mp4"

    return options


# =========================================================
# EXTRACTION ET NETTOYAGE DES SOUS-TITRES
# =========================================================

def clean_subtitles(text):
    """Nettoyer un fichier VTT ou SRT."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(
        r"\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*"
        r"\d{2}:\d{2}:\d{2}[.,]\d{3}.*",
        " ",
        text,
    )
    text = re.sub(
        r"\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}[.,]\d{3}.*",
        " ",
        text,
    )
    text = re.sub(r"^\s*\d+\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"WEBVTT.*", " ", text)
    text = re.sub(r"NOTE.*", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_subtitles(video_url, work_id):
    """Télécharger les sous-titres disponibles et extraire leur texte."""
    output_template = str(DOWNLOAD_FOLDER / f"{work_id}.%(ext)s")

    options = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["fr", "fr-FR", "en", "en-US"],
        "subtitlesformat": "vtt/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([video_url])

        subtitle_files = list(DOWNLOAD_FOLDER.glob(f"{work_id}*.vtt"))
        subtitle_files += list(DOWNLOAD_FOLDER.glob(f"{work_id}*.srt"))

        for subtitle_file in subtitle_files:
            try:
                content = subtitle_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
                cleaned = clean_subtitles(content)

                if cleaned:
                    logger.info("Sous-titres récupérés.")
                    return cleaned
            finally:
                try:
                    subtitle_file.unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "Impossible de supprimer %s",
                        subtitle_file,
                    )

    except Exception:
        logger.exception("Impossible de récupérer les sous-titres.")

    return None


# =========================================================
# TRANSCRIPTION AVEC WHISPER (OPTIONNEL)
# =========================================================

def transcribe_with_whisper(video_url, work_id):
    """
    Télécharger temporairement l'audio puis le transcrire avec Whisper.
    Whisper doit être installé dans le même environnement Python.
    """
    try:
        import whisper
    except ImportError:
        logger.warning(
            "Whisper n'est pas installé. "
            "La transcription locale ne sera pas disponible."
        )
        return None

    audio_template = str(DOWNLOAD_FOLDER / f"{work_id}_audio.%(ext)s")

    options = {
        "format": "bestaudio/best",
        "outtmpl": audio_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ffmpeg_location": FFMPEG_PATH,
        "socket_timeout": 30,
        "retries": 3,
    }

    audio_file = None

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(video_url, download=True)
            audio_file = Path(ydl.prepare_filename(info))

        # yt-dlp peut changer l'extension selon le format audio.
        if not audio_file.exists():
            candidates = list(
                DOWNLOAD_FOLDER.glob(f"{work_id}_audio.*")
            )
            audio_file = candidates[0] if candidates else None

        if not audio_file or not audio_file.exists():
            logger.error("Fichier audio introuvable après téléchargement.")
            return None

        logger.info("Chargement du modèle Whisper.")
        model = whisper.load_model("base")

        logger.info("Transcription audio en cours.")
        result = model.transcribe(
            str(audio_file),
            fp16=False,
        )

        transcription = (result.get("text") or "").strip()
        return transcription or None

    except Exception:
        logger.exception("Erreur pendant la transcription Whisper.")
        return None

    finally:
        for file_path in DOWNLOAD_FOLDER.glob(f"{work_id}_audio.*"):
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Impossible de supprimer %s", file_path)


# =========================================================
# GÉNÉRATION DU RÉSUMÉ AVEC GROQ
# =========================================================

def generate_summary(video_url):
    """Résumer une vidéo YouTube à partir de ses sous-titres ou de Whisper."""
    if client is None:
        raise RuntimeError(
            "La clé GROQ_API_KEY n'est pas configurée dans le fichier .env."
        )

    if not validate_url(video_url):
        raise ValueError("L'URL fournie ne semble pas être une URL YouTube valide.")

    video_url = normalize_url(video_url)
    work_id = uuid.uuid4().hex

    # 1. Essayer de récupérer les sous-titres.
    transcript = extract_subtitles(video_url, work_id)

    # 2. Si les sous-titres sont indisponibles, essayer Whisper.
    if not transcript:
        logger.info("Sous-titres indisponibles : tentative avec Whisper.")
        transcript = transcribe_with_whisper(video_url, work_id)

    if not transcript:
        raise RuntimeError(
            "Impossible d'obtenir le texte de la vidéo. "
            "Vérifiez la disponibilité des sous-titres ou installez Whisper."
        )

    # Limiter la longueur du texte envoyé au modèle.
    # Cette limite évite d'envoyer une transcription excessivement longue.
    max_characters = 60000
    if len(transcript) > max_characters:
        transcript = transcript[:max_characters]
        logger.warning("Transcription tronquée avant l'envoi à Groq.")

    logger.info("Génération du résumé avec Groq.")

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un assistant spécialisé dans le résumé de vidéos. "
                    "Résume fidèlement le contenu fourni en français. "
                    "Présente les idées principales dans un langage clair, "
                    "simple et concis. N'invente aucun fait et indique les "
                    "points essentiels lorsque c'est pertinent."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Résume cette transcription en français. "
                    "Présente les idées essentielles de manière structurée.\n\n"
                    f"Transcription :\n{transcript}"
                ),
            },
        ],
        temperature=0.5,
        max_tokens=700,
    )

    summary = response.choices[0].message.content or ""

    if not summary.strip():
        raise RuntimeError("Groq n'a retourné aucun résumé.")

    return summary.strip()


# =========================================================
# TÉLÉCHARGEMENT DES VIDÉOS
# =========================================================

def download_video(video_url, file_format="mp4"):
    """Télécharger une vidéo YouTube au format MP4 ou MP3."""
    if not validate_url(video_url):
        raise ValueError("Veuillez fournir une URL YouTube valide.")

    video_url = normalize_url(video_url)
    work_id = uuid.uuid4().hex
    output_template = str(DOWNLOAD_FOLDER / f"{work_id}.%(ext)s")

    audio_only = file_format == "mp3"
    options = create_ydl_options(
        output_path=output_template,
        audio_only=audio_only,
    )

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(video_url, download=True)
        downloaded_path = Path(ydl.prepare_filename(info))

    if audio_only:
        downloaded_path = downloaded_path.with_suffix(".mp3")

    if not downloaded_path.exists():
        # Selon le format choisi, yt-dlp peut produire une extension différente.
        candidates = list(DOWNLOAD_FOLDER.glob(f"{work_id}.*"))
        candidates = [
            path for path in candidates
            if path.suffix.lower() in {".mp4", ".mp3", ".mkv", ".webm", ".m4a"}
        ]

        if not candidates:
            raise FileNotFoundError(
                "Le téléchargement est terminé, mais le fichier est introuvable."
            )

        downloaded_path = candidates[0]

    return downloaded_path


# =========================================================
# ROUTES FLASK
# =========================================================

@app.route("/", methods=["GET"])
def index():
    """Afficher la page d'accueil."""
    return render_template("index.html")


@app.route("/robots.txt", methods=["GET"])
def robots_txt():
    """Fournir un fichier robots.txt minimal."""
    return (
        "User-agent: *\n"
        "Allow: /\n",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


@app.route("/api/summarize", methods=["POST"])
def summarize_route():
    """API de génération de résumé."""
    data = request.get_json(silent=True) or {}
    video_url = (
        data.get("url")
        or data.get("video_url")
        or ""
    ).strip()

    if not video_url:
        return jsonify({
            "error": "Veuillez fournir l'URL de la vidéo."
        }), 400

    try:
        summary = generate_summary(video_url)
        return jsonify({"summary": summary, "result": summary}), 200

    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        logger.exception("Erreur lors de la génération du résumé.")
        return jsonify({
            "error": (
                "Impossible de générer le résumé. Vérifiez la configuration "
                "Groq, les sous-titres de la vidéo et les journaux du serveur."
            )
        }), 500


@app.route("/api/download", methods=["POST"])
def download_route():
    """API de téléchargement MP4 ou MP3."""
    data = request.get_json(silent=True) or {}

    video_url = (
        data.get("url")
        or data.get("video_url")
        or ""
    ).strip()

    file_format = (
        data.get("format")
        or data.get("type")
        or "mp4"
    ).strip().lower()

    if not video_url:
        return jsonify({
            "error": "Veuillez fournir l'URL de la vidéo."
        }), 400

    if file_format not in {"mp4", "mp3"}:
        return jsonify({
            "error": "Format non pris en charge. Choisissez MP4 ou MP3."
        }), 400

    try:
        file_path = download_video(video_url, file_format)

        mimetype = (
            "audio/mpeg" if file_format == "mp3"
            else "video/mp4"
        )

        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=secure_filename(file_path.name),
        )

    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        logger.exception("Erreur lors du téléchargement.")
        return jsonify({
            "error": (
                "Le téléchargement a échoué. Vérifiez l'URL, la connexion "
                "et la disponibilité de la vidéo."
            )
        }), 500


# =========================================================
# NETTOYAGE DES ANCIENS FICHIERS
# =========================================================

def cleanup_old_files(max_age_hours=24):
    """Supprimer les fichiers temporaires trop anciens."""
    cutoff = time.time() - (max_age_hours * 60 * 60)

    for file_path in DOWNLOAD_FOLDER.iterdir():
        if not file_path.is_file():
            continue

        try:
            if file_path.stat().st_mtime < cutoff:
                file_path.unlink(missing_ok=True)
                logger.info("Fichier temporaire supprimé : %s", file_path.name)
        except OSError:
            logger.warning(
                "Impossible de supprimer le fichier %s",
                file_path,
            )


# =========================================================
# DÉMARRAGE
# =========================================================

if __name__ == "__main__":
    cleanup_old_files()

    logger.info("Dossier de téléchargement : %s", DOWNLOAD_FOLDER)
    logger.info("FFmpeg utilisé : %s", FFMPEG_PATH)
    logger.info(
        "Clé Groq configurée : %s",
        "oui" if GROQ_API_KEY else "non",
    )

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000")),
        debug=False,
    )
