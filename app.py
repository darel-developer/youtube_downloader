from flask import Flask, render_template, request, send_file
import yt_dlp
import os
import imageio_ffmpeg

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"

# créer le dossier downloads s'il n'existe pas
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# chemin automatique de ffmpeg
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        url = request.form["url"]
        file_format = request.form["format"]

        try:

            # OPTION MP4
            if file_format == "mp4":

                ydl_opts = {
                    'format': 'best',
                    'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                    'retries': 10,
                    'fragment_retries': 10
                }

            # OPTION MP3
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

                # corriger le nom si conversion mp3
                if file_format == "mp3":
                    filename = os.path.splitext(filename)[0] + ".mp3"

            return send_file(filename, as_attachment=True)

        except Exception as e:
            return f"Erreur lors du téléchargement : {str(e)}"

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)