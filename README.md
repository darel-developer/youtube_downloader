# 🎥 YouTube Downloader & Summarizer

[![Python CI](https://github.com/darel-developer/youtube_downloader/actions/workflows/ci.yml/badge.svg)](https://github.com/darel-developer/youtube_downloader/actions/workflows/ci.yml)

Un petit service Flask qui permet de :

- Télécharger une vidéo YouTube au format MP4 ou MP3.
- Générer automatiquement un **résumé textuel** de la vidéo (via Whisper + OpenAI).

L’interface est minimale mais fonctionnelle, le tout dans une seule page web.

---

## 🧱 Architecture du projet

```
youtube_downloader/
├── app.py                 # application Flask
├── downloads/             # dossier où sont enregistrés les fichiers téléchargés
└── templates/
    └── index.html         # interface Bootstrap
```

- **app.py** gère les routes, la logique de téléchargement (yt‑dlp), la transcription (Whisper) et l’appel à l’API OpenAI.
- **templates/index.html** fournit un formulaire pour l’URL, le choix de format et le bouton de résumé.
- Un dossier `downloads/` est créé automatiquement pour stocker les fichiers temporaires.

---

## ⚙️ Prérequis

- Python ≥ 3.10 (testé sur Windows).
- Clés/API :
  - `OPENAI_API_KEY` (variable d’environnement) pour l’accès aux modèles GPT.
- Dépendances Python listées ci‑dessous.

---

## 📦 Installation

```bash
# depuis la racine du projet
python -m venv venv
venv\Scripts\activate        # Windows
# ou `source venv/bin/activate` sur Unix

pip install -r requirements.txt  
```

---

## 🚀 Lancement

```bash
set OPENAI_API_KEY=ta_cle
python app.py
```

- L’application démarre en mode debug.
- Ouvre `http://127.0.0.1:5000/` dans ton navigateur.
- Colle un lien YouTube, choisis MP4/MP3 ou clique sur **Résumé de la vidéo**.

Les fichiers sont envoyés en téléchargement et les résumés s’affichent directement.

---

## 🧩 Fonctionnement interne

1. **Téléchargement**  
   Utilisation de `yt_dlp` pour récupérer la vidéo ou l’audio.  
   Le chemin `downloads/` est nettoyé et surveillé pour garantir que les fichiers sont complets.

2. **Transcription**  
   - Si la vidéo contient des sous‑titres, ils sont téléchargés et nettoyés.
   - Sinon, l’audio est extrait et passé au modèle Whisper `base`.

3. **Résumé**  
   Le texte généré est envoyé à l’API OpenAI (`gpt-3.5-turbo`) avec une consigne de résumé.

4. **Interface**  
   Bootstrap simple avec un formulaire et une zone de résumé.

---

## 🔮 Features à venir (idées)

---

## 🛠️ CI/CD

Le projet est équipé d'un pipeline GitHub Actions défini dans `.github/workflows/ci.yml`. Il s'exécute sur chaque `push` ou `pull_request` vers la branche `main` et réalise :

1. Installation de Python 3.11
2. Installation des dépendances (`requirements.txt`) + `flake8` pour le linting
3. Vérification de la syntaxe Python
4. Un test de fumée minimal

Le badge en haut du README indique l'état du pipeline ; remplacez `<owner>/<repo>` par votre dépôt.


- 📁 **Historique / journaux** des vidéos traitées.
- 🧠 Paramètres de résumé (longueur, langue, ton).
- 🗂 Mise en cache des transcriptions / résumés pour réutilisation.
- 🎨 Refonte UI + feedback de progression.
- 📝 Export du résumé au format TXT/PDF.
- 📡 Support d’autres plateformes (Vimeo, TikTok…).
- 🔒 Authentification utilisateur.

---

## ✅ Notes

- Nécessite `ffmpeg` : `imageio-ffmpeg` gère l’exécutable mais vérifie l’existence au démarrage.
- La fonction `wait_for_file_stable` garantit que le téléchargement est terminé avant traitement (utile surtout sous Windows).
- Ajoute un `.gitignore` si tu commites : exclure `downloads/`, `venv/`, `.env`.

---

