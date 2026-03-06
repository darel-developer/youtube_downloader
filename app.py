from flask import Flask, render_template, request, send_file
import yt_dlp
import os

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"

@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        url = request.form["url"]

        try:

            ydl_opts = {
                'format': 'best',
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'retries': 10,
                'fragment_retries': 10
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

            return send_file(filename, as_attachment=True)

        except Exception as e:
            return f"Erreur lors du téléchargement : {str(e)}"

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)