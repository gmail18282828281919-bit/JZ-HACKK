# JZ-AI — ton modèle + ta clé d'API

Un serveur d'IA **auto-hébergé** avec une API compatible OpenAI et un système de
clés d'API maison. Comme le modèle tourne sur ta machine, il n'y a **aucun quota
ni facturation de tokens** — c'est ça, les « tokens illimités » (la vraie limite,
c'est la puissance de ta machine, pas un compteur).

> **Sur Android / Termux ?** Suis [TERMUX.md](TERMUX.md) : le serveur
> `ai/server/lite.py` ne dépend que de la bibliothèque standard, donc
> aucun `pip install` n'est nécessaire.

## 1. Installer

```bash
cd ai
pip install -r requirements.txt
```

Sans aucune dépendance (Termux, machine minimale), utilise le serveur *lite* :

```bash
python3 -m ai.server.lite   # memes routes, zero pip
```

## 2. Choisir le modèle

Un script télécharge le bon modèle et affiche la commande de lancement :

```bash
bash ai/scripts/models.sh list        # voir les modèles
bash ai/scripts/models.sh get code    # télécharger
```

| Preset | Taille | Pour quoi |
|---|---|---|
| `general-mini` | 0,4 Go | Le plus léger. Qualité limitée. |
| `general` | 1,0 Go | Conversation. Tourne sur téléphone. |
| `code` | 1,0 Go | **Programmation.** Tourne sur téléphone. |
| `code-pro` | 4,4 Go | Programmation, nettement meilleur. PC requis. |
| `vision` | 4,4 Go | **Lecture d'images.** PC requis. |

Trois backends, du plus capable au plus léger :

| Backend | Ce qu'il faut | Quand l'utiliser |
|---|---|---|
| `llama` | `pip install llama-cpp-python` + un `.gguf` | **Recommandé.** Seul à gérer la vision. |
| `transformers` | `pip install transformers torch accelerate` | Si tu préfères HuggingFace. |
| `echo` | rien | Répondeur de test, aucune vraie génération. |

Sans configuration, `JZAI_BACKEND=auto` essaie `llama`, puis `transformers`, puis
retombe sur `echo` — donc le serveur démarre toujours.

### Profil de réponse

`JZAI_PROFILE=code` donne au modèle des consignes de programmation (code complet
dans un bloc, cas limites signalés, pas de bibliothèque inventée).
`JZAI_PROFILE=general` est le défaut.

## 3. Créer une clé d'API

```bash
python3 ai/scripts/keys.py new "mon apk"
#   jz-3f9c1a...   <- copie-la, seul son hash est stocké
python3 ai/scripts/keys.py list
python3 ai/scripts/keys.py revoke 1
```

## 4. Lancer le serveur

```bash
export JZAI_ADMIN_TOKEN="un-secret-a-toi"   # optionnel, active /admin/keys
./ai/run.sh                                  # http://0.0.0.0:8000
```

## 5. Tester

```bash
curl http://localhost:8000/health

curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer jz-TA-CLE" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Bonjour"}]}'
```

## 6. Brancher l'apk

L'application Android complète est dans [`apk/`](../apk/README.md) — elle se
compile toute seule sur GitHub Actions, pas besoin d'Android Studio.

Dans l'app, ouvre le menu **⋮ → Réglages** et saisis :

- **Adresse du serveur** : `http://127.0.0.1:8000` si Termux tourne sur le même
  téléphone, sinon l'IP du serveur sur ton réseau.
- **Clé d'API** : celle créée à l'étape 3.

La clé est stockée dans les SharedPreferences privées de l'app, jamais compilée
dans l'apk (qui se décompile en quelques minutes).

## Fichiers et images

Le serveur extrait le texte des fichiers joints et l'injecte dans le contexte du
modèle. Deux façons de faire.

**Envoyer le fichier d'abord**, puis le citer par son identifiant :

```bash
curl -X POST http://localhost:8000/v1/files \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"filename\":\"script.py\",\"content_base64\":\"$(base64 -w0 script.py)\"}"
# -> {"id":"file-abc123...", "kind":"text", "chars":842, ...}

curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":[
        {"type":"text","text":"Trouve le bug dans ce script."},
        {"type":"file","file_id":"file-abc123..."}]}]}'
```

**Ou tout envoyer d'un coup**, sans téléversement préalable :

```json
{"type": "file", "filename": "script.py", "content_base64": "..."}
```

Formats lus : texte et code (une soixantaine d'extensions), PDF *(nécessite
`pip install pypdf`)*, DOCX, ODT, PPTX, HTML, JSON, CSV, ZIP (liste du contenu),
et images. Limites : 8 Mio par fichier, 8 fichiers par requête, 200 000
caractères extraits.

### Images

Format OpenAI classique, en base64 uniquement (le serveur ne va jamais chercher
une URL distante) :

```json
{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
```

**Il faut un modèle vision pour que l'image soit réellement lue.** Sans
`JZAI_MMPROJ_PATH`, le serveur prévient le modèle qu'il ne peut pas voir l'image
— il le dira au lieu d'inventer. Pour l'activer :

```bash
bash ai/scripts/models.sh get vision   # affiche les variables à exporter
```

`JZAI_VISION_HANDLER` doit correspondre à la famille du modèle : `llava-1.5`
(défaut), `llava-1.6`, `nanollava`, `moondream`, `llama-3-vision`,
`minicpm-v-2.6`.

## Endpoints

| Méthode | Route | Auth | Rôle |
|---|---|---|---|
| GET | `/health` | — | état, backend actif, nb de clés |
| GET | `/v1/models` | clé | liste le modèle |
| POST | `/v1/chat/completions` | clé | chat (`"stream": true` supporté) |
| POST | `/v1/files` | clé | téléverse un fichier, renvoie un `file_id` |
| POST | `/admin/keys` | `X-Admin-Token` | créer une clé |
| GET | `/admin/keys` | `X-Admin-Token` | lister les clés |
| DELETE | `/admin/keys/{id}` | `X-Admin-Token` | révoquer une clé |

## Réglages (variables d'environnement)

Voir `ai/.env.example`. Les principales : `JZAI_BACKEND`, `JZAI_GGUF_PATH`,
`JZAI_HF_MODEL`, `JZAI_MODEL_NAME`, `JZAI_PORT`, `JZAI_ADMIN_TOKEN`,
`JZAI_RATE_LIMIT` (0 = illimité), `JZAI_SYSTEM_PROMPT`, `JZAI_PROFILE`,
`JZAI_MMPROJ_PATH`, `JZAI_VISION_HANDLER`.

## Sécurité — à ne pas zapper

- La clé d'API ne doit **pas** être compilée en dur dans l'apk : quelqu'un peut
  décompiler le `.apk` et la lire. Passe par `BuildConfig` + un `local.properties`
  non commité, et prévois une clé par utilisateur que tu peux révoquer.
- Le serveur n'a pas de TLS : sur Internet, mets-le derrière un reverse proxy
  (Caddy ou nginx) qui gère le HTTPS.
- `data/jzai.db` contient les hashes des clés — ne le commit pas.
