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

Trois backends, du plus capable au plus léger :

| Backend | Ce qu'il faut | Quand l'utiliser |
|---|---|---|
| `llama` | `pip install llama-cpp-python` + un fichier `.gguf` | **Recommandé**. Rapide sur CPU. |
| `transformers` | `pip install transformers torch accelerate` | Si tu préfères HuggingFace. |
| `echo` | rien | Pour tester l'API et l'apk sans modèle. |

Modèle léger conseillé (~400 Mo, tourne sur un petit PC) :

```bash
# télécharge un .gguf, ex. Qwen2.5-0.5B-Instruct Q4_K_M
export JZAI_GGUF_PATH=/chemin/vers/qwen2.5-0.5b-instruct-q4_k_m.gguf
export JZAI_BACKEND=llama
```

Sans configuration, `JZAI_BACKEND=auto` essaie `llama`, puis `transformers`, puis
retombe sur `echo` — donc le serveur démarre toujours.

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

Copie `ai/android/JZAiClient.kt` dans ton projet Android :

```kotlin
val ai = JZAiClient(
    baseUrl = "http://192.168.1.20:8000",  // IP de ta machine sur le réseau
    apiKey  = BuildConfig.JZ_API_KEY,       // ne code jamais la clé en dur
)

lifecycleScope.launch {
    val reponse = ai.ask("Salut, tu fais quoi ?")
    textView.text = reponse
}
```

Il faut `<uses-permission android:name="android.permission.INTERNET"/>` dans le
manifest, et `android:usesCleartextTraffic="true"` tant que tu es en HTTP simple.

## Endpoints

| Méthode | Route | Auth | Rôle |
|---|---|---|---|
| GET | `/health` | — | état, backend actif, nb de clés |
| GET | `/v1/models` | clé | liste le modèle |
| POST | `/v1/chat/completions` | clé | chat (`"stream": true` supporté) |
| POST | `/admin/keys` | `X-Admin-Token` | créer une clé |
| GET | `/admin/keys` | `X-Admin-Token` | lister les clés |
| DELETE | `/admin/keys/{id}` | `X-Admin-Token` | révoquer une clé |

## Réglages (variables d'environnement)

Voir `ai/.env.example`. Les principales : `JZAI_BACKEND`, `JZAI_GGUF_PATH`,
`JZAI_HF_MODEL`, `JZAI_MODEL_NAME`, `JZAI_PORT`, `JZAI_ADMIN_TOKEN`,
`JZAI_RATE_LIMIT` (0 = illimité), `JZAI_SYSTEM_PROMPT`.

## Sécurité — à ne pas zapper

- La clé d'API ne doit **pas** être compilée en dur dans l'apk : quelqu'un peut
  décompiler le `.apk` et la lire. Passe par `BuildConfig` + un `local.properties`
  non commité, et prévois une clé par utilisateur que tu peux révoquer.
- Le serveur n'a pas de TLS : sur Internet, mets-le derrière un reverse proxy
  (Caddy ou nginx) qui gère le HTTPS.
- `data/jzai.db` contient les hashes des clés — ne le commit pas.
