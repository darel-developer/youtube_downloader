from flask import Flask, render_template, request, send_file, jsonify, session
import yt_dlp
import os
import imageio_ffmpeg
import openai
import uuid
import time
import re
import requests
import logging

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'super-secret-dev-key')

# ====== CONFIGURATION ======
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
assert os.path.exists(ffmpeg_path), "FFmpeg introuvable ! Vérifie imageio-ffmpeg"

def get_whisper_model():
    import whisper
    return whisper.load_model("tiny")


openai.api_key = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ====== FONCTION D'ATTENTE DE FICHIER STABLE ======
def wait_for_file_stable(filepath, timeout=15):
    """Attendre que le fichier existe, n'a pas de .part et soit stable en taille"""
    total_wait = 0
    last_size = -1
    stable_counter = 0
    filepath = os.path.abspath(filepath)  # chemin absolu
    while total_wait < timeout:
        # Vérifier existence et absence de .part
        if os.path.exists(filepath) and not any(f.endswith(".part") for f in os.listdir(DOWNLOAD_FOLDER)):
            size = os.path.getsize(filepath)
            if size == last_size and size > 0:
                stable_counter += 1
                if stable_counter >= 2:  # stable 1s
                    return True
            else:
                stable_counter = 0
                last_size = size
        time.sleep(0.5)
        total_wait += 0.5
        logging.info(f"Attente active... {total_wait}s écoulées")
    return False

# ====== FONCTION DE RÉSUMÉ ======
def generate_summary(video_url):
    logging.info(f"Début du résumé pour la vidéo : {video_url}")

    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'subtitleslangs': ['all'],
        'subtitlesformat': 'vtt',
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        subtitles = info.get("subtitles")
        logging.info(f"Sous-titres trouvés : {bool(subtitles)}")

        if subtitles:
            lang = list(subtitles.keys())[0]
            sub_url = subtitles[lang][0]['url']
            subtitle_text = requests.get(sub_url).text
            subtitle_text = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}", "", subtitle_text)
            subtitle_text = re.sub(r"\n+", " ", subtitle_text)
            text_for_summary = subtitle_text
        else:
            audio_file = os.path.join(DOWNLOAD_FOLDER, f"temp_audio_{int(time.time()*1000)}.mp3")
            audio_file = os.path.abspath(audio_file)
            logging.info(f"Téléchargement de l'audio dans {audio_file}")

            ydl_opts_audio = {
                'format': 'bestaudio/best',
                'outtmpl': audio_file,
                'ffmpeg_location': ffmpeg_path,
                'noplaylist': True,
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl2:
                ydl2.download([video_url])

            logging.info("Vérification que le fichier audio est prêt et stable...")
            if not wait_for_file_stable(audio_file, timeout=15):
                raise FileNotFoundError(f"Le fichier audio n'a pas été trouvé ou n'est pas stable après 15 secondes : {audio_file}")

            logging.info("Petit délai pour Windows avant la transcription...")
            time.sleep(0.5)

            logging.info("Transcription de l'audio avec Whisper...")
            if not os.path.exists(audio_file):
                raise FileNotFoundError(f"Fichier audio introuvable juste avant Whisper : {audio_file}")
            model = get_whisper_model()
            result = model.transcribe(audio_file)
            text_for_summary = result['text']
            os.remove(audio_file)
            logging.info("Fichier audio temporaire supprimé")

    logging.info("Envoi du texte à OpenAI pour générer le résumé...")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Tu es un assistant qui résume les vidéos de manière concise."},
            {"role": "user", "content": f"Fais un résumé clair de ce texte : {text_for_summary}"}
        ],
        temperature=0.5,
        max_tokens=250
    )

    summary = response['choices'][0]['message']['content']
    logging.info("Résumé généré avec succès")
    return summary

def _download_video(url, file_format):
    # Reuse the same logic as in index() for downloads
    if file_format == "mp4":
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
            'retries': 10,
            'fragment_retries': 10
        }
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
            'ffmpeg_location': ffmpeg_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if file_format == "mp3":
            filename = os.path.splitext(filename)[0] + ".mp3"
        return filename


# ====== ROUTE PRINCIPALE ======
@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL manquante"}), 400

    try:
        summary = generate_summary(url)
        return jsonify({"summary": summary})
    except Exception as e:
        logging.error(f"Erreur résumé AJAX : {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    file_format = (data.get("format") or "mp4").strip()
    if not url:
        return jsonify({"error": "URL manquante"}), 400

    try:
        filename = _download_video(url, file_format)
        return send_file(filename, as_attachment=True)
    except Exception as e:
        logging.error(f"Erreur téléchargement AJAX : {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET", "POST"])
def index():
    summary = None

    if request.method == "POST":
        url = request.form["url"]
        file_format = request.form["format"]
        action = request.form.get("action", "download")
        logging.info(f"Action demandée : {action}, format : {file_format}, URL : {url}")

        try:
            if action == "summarize":
                summary = generate_summary(url)
                return render_template("index.html", summary=summary)

            # CAS TÉLÉCHARGEMENT
            if file_format == "mp4":
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                    'retries': 10,
                    'fragment_retries': 10
                }
            else:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                    'ffmpeg_location': ffmpeg_path,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if file_format == "mp3":
                    filename = os.path.splitext(filename)[0] + ".mp3"
                logging.info(f"Fichier téléchargé : {filename}")

            return send_file(filename, as_attachment=True)

        except Exception as e:
            logging.error(f"Erreur rencontrée : {str(e)}")
            summary = f"Erreur : {str(e)}"

    return render_template("index.html", summary=summary)

if __name__ == "__main__":
    logging.info("Démarrage du serveur Flask...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))