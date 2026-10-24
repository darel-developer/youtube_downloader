# � YouTube Downloader & Marketing AI

Un projet Flask qui combine :

- un téléchargeur YouTube MP4 / MP3
- un résumé IA des vidéos
- une page marketing pour générer des publications sociales avec Groq
- une landing page plus orientée conversion / acquisition

---

## ✅ Ce que contient le projet

- [app.py](app.py) : application Flask principale, logique de téléchargement, validation d’URL, nettoyage des fichiers, résumé IA et routes de l’API
- [marketing.py](marketing.py) : blueprint marketing pour la génération de publications avec Groq
- [templates/index.html](templates/index.html) : landing page principale
- [templates/marketing.html](templates/marketing.html) : page de génération de contenu social
- [static/css](static/css) : styles séparés pour les pages
- [static/js](static/js) : JS pour les interactions
- [downloads/](downloads/) : dossier de stockage temporaire des fichiers générés

---

## ⚙️ Stack technique

- Python 3.10+
- Flask
- yt-dlp
- imageio-ffmpeg
- Groq
- python-dotenv
- gunicorn

---

## 🚀 Installation locale

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Pour Windows PowerShell, tu peux aussi faire :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 🔐 Variables d’environnement

Crée un fichier `.env` à la racine avec le contenu suivant :

```env
GROQ_API_KEY=ta_cle_groq
GROQ_MODEL=openai/gpt-oss-20b
FLASK_SECRET_KEY=change-me-in-production
```

Tu peux copier le modèle depuis [.env.example](.env.example).

---

## ▶️ Lancement

```bash
python app.py
```

Puis ouvre :

- http://127.0.0.1:5000/
- http://127.0.0.1:5000/marketing

---

## 🧩 Fonctionnement principal

### 1. Téléchargement
- Validation de l’URL YouTube
- Normalisation de l’URL
- Téléchargement MP4 ou MP3 via yt-dlp
- Nettoyage des fichiers temporaires dans le dossier downloads

### 2. Résumé IA
- Extraction des sous-titres si disponibles
- Sinon transcription audio via Whisper si installé
- Envoi du texte à Groq pour générer un résumé lisible

### 3. Génération marketing
- Prompt orienté community manager / copywriting
- Génération d’une publication sociale
- Ajout automatique d’un bloc hashtags si le modèle n’en fournit pas

---

## 🏭 Ce qu’il faut ajouter pour passer en production

Voici la checklist la plus importante avant de mettre le projet en ligne :

### Sécurité
- remplacer `FLASK_SECRET_KEY` par une vraie clé forte
- ne jamais committer le fichier `.env`
- activer HTTPS via le hébergeur / reverse proxy
- sécuriser les routes contre les abus (rate limiting, validation stricte, logs)

### Déploiement
- utiliser un serveur WSGI en production : `gunicorn`
- configurer une variable d’environnement pour le mode production
- désactiver le debug (`debug=False`)
- mettre la page derrière un domaine propre avec SSL

### Gestion des fichiers
- limiter la taille des uploads / téléchargements
- nettoyer automatiquement les fichiers anciens dans `downloads/`
- prévoir un quota disque ou un stockage externe si les usages augmentent

### Observabilité
- ajouter des logs structurés
- surveiller les erreurs (Sentry ou équivalent)
- enregistrer les erreurs Groq / yt-dlp / téléchargement

### Robustesse
- ajouter des tests automatisés
- contrôler les erreurs sur les URLs invalides ou bloquées
- prévoir un message propre si le téléchargement échoue
- ajouter une gestion de retry sur les appels API externes

### SEO / acquisition
- ajouter un vrai titre, meta description, Open Graph et robots.txt
- préparer des pages de vente / landing page plus poussées
- distinguer clairement les pages “outil” et “marketing AI” dans la navigation

### Bonnes pratiques business
- spécifier clairement la légalité / usage du service
- ajouter une page mentions légales / CGU si tu le publies public
- vérifier les droits d’utilisation des contenus téléchargés selon le pays et la plateforme

---

## 🚀 Commande de prod recommandée

Pour un déploiement simple avec Gunicorn :

```bash
gunicorn --bind 0.0.0.0:8000 app:app
```

Pour Render / Railway / VPS, tu places simplement :

- `gunicorn app:app`
- la variable `GROQ_API_KEY`
- la variable `FLASK_SECRET_KEY`

---

## 🧪 Conseils utiles

- Garde le dossier `downloads/` hors du dépôt si possible
- Jette un œil au nettoyage des fichiers anciens pour éviter de remplir le disque
- Si le site est public, limite les requêtes par IP pour éviter le spam
- Si tu veux monétiser, ajoute d’abord un système de quota ou une version premium

---

## 📌 À venir

- amélioration de la sécurité upload/download
- gestion des erreurs plus explicites
- UI plus premium et plus conversion-driven
- dashboard d’usage / statistiques
- stockage centralisé des fichiers et génération d’URL de téléchargement
- auth admin / protection contre l’abus

---

## ✅ En résumé

Le projet est déjà utile et fonctionnel localement, mais pour la production il faut surtout :

1. sécuriser les variables et le secret
2. passer en WSGI (Gunicorn)
3. activer HTTPS
4. limiter l’abus et nettoyer le stockage
5. ajouter logs + monitoring
6. préparer la conformité / SEO / landing page

---

