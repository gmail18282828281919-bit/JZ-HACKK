# Héberger JZ-AI sur Termux (Android)

Le serveur `ai/server/lite.py` n'utilise **que la bibliothèque standard de
Python** : pas de `pip install`, donc pas de compilation Rust/C interminable
sur Android.

## Version rapide (script)

```bash
pkg update -y && pkg install -y git python curl
git clone https://github.com/gmail18282828281919-bit/JZ-HACKK.git
cd JZ-HACKK
git checkout claude/ai-model-api-key-7fsf3p
bash ai/termux.sh
```

Le script installe les paquets, propose de télécharger le modèle, **crée ta clé
d'API** et génère `ai/start-termux.sh`.

## Version manuelle (étape par étape)

### 1. Paquets

```bash
pkg update -y && pkg upgrade -y
pkg install -y git python curl
```

### 2. Récupérer le projet

```bash
git clone https://github.com/gmail18282828281919-bit/JZ-HACKK.git
cd JZ-HACKK
git checkout claude/ai-model-api-key-7fsf3p
```

### 3. Créer la clé d'API

```bash
python3 ai/scripts/keys.py new "mon apk"
```

Sortie :

```
Cle creee (mon apk) :

    jz-3f9c1a7b2e...        <-- COPIE-LA MAINTENANT

Garde-la : seul son hash est stocke, elle ne sera plus affichee.
```

Autres commandes : `python3 ai/scripts/keys.py list` et
`python3 ai/scripts/keys.py revoke 1`.

### 4. Lancer le serveur

```bash
python3 -m ai.server.lite
```

Il démarre sur `http://0.0.0.0:8000` avec le backend `echo` (réponses de test).

### 5. Vérifier

Ouvre une **deuxième session Termux** (glisse depuis le bord gauche → NEW SESSION) :

```bash
curl http://127.0.0.1:8000/health

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer jz-TA-CLE" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Bonjour"}]}'
```

## Passer à un vrai modèle

Le backend `echo` sert à valider l'API. Pour de vraies réponses il faut
llama.cpp — la compilation prend **20 à 40 minutes** sur téléphone :

```bash
pkg install -y clang cmake ninja
pip install llama-cpp-python
```

Puis choisis un modèle :

```bash
bash ai/scripts/models.sh list
bash ai/scripts/models.sh get code     # 1 Go, spécialisé programmation
```

Le script affiche les variables à exporter, puis :

```bash
python3 -m ai.server.lite
```

Compte ~1,5 Go de RAM libre et **10 à 60 secondes par réponse** sur téléphone.
Si la compilation échoue ou que le modèle se fait tuer par manque de mémoire,
reste sur `echo` et héberge le vrai modèle sur un PC.

**La vision (lecture d'images) est hors de portée d'un téléphone** : le plus
petit couple modèle + projecteur fiable pèse 4,4 Go. Fais-le tourner sur un PC
et pointe l'app vers son adresse.

## Lire des fichiers

Ça marche quel que soit le modèle — l'extraction du texte est faite par le
serveur, pas par l'IA :

```bash
curl -X POST http://127.0.0.1:8000/v1/files \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"filename\":\"note.txt\",\"content_base64\":\"$(base64 -w0 note.txt)\"}"
```

Formats : texte et code, PDF (`pip install pypdf`), DOCX, ODT, PPTX, HTML, JSON,
CSV, ZIP, images. Détails dans [README.md](README.md#fichiers-et-images).

## Éviter que Android tue le serveur

```bash
pkg install -y termux-api
termux-wake-lock
```

Et dans les réglages Android : **Batterie → Termux → Sans restriction**.

## Connecter l'apk

**Même téléphone** (apk et Termux ensemble) — le plus simple :

```kotlin
val ai = JZAiClient(baseUrl = "http://127.0.0.1:8000", apiKey = "jz-...")
```

**Depuis un autre appareil du même Wi-Fi** — récupère l'IP du téléphone :

```bash
pkg install -y iproute2
ip addr show wlan0 | grep 'inet '
# ex: inet 192.168.1.42/24  ->  baseUrl = "http://192.168.1.42:8000"
```

Dans les deux cas, ajoute au `AndroidManifest.xml` :

```xml
<uses-permission android:name="android.permission.INTERNET"/>
<application android:usesCleartextTraffic="true" ... >
```

(`usesCleartextTraffic` est nécessaire même pour `127.0.0.1` depuis Android 9.)

## Problèmes courants

| Symptôme | Cause / solution |
|---|---|
| `Address already in use` | Serveur déjà lancé : `pkill -f ai.server.lite` |
| `python3: command not found` | `pkg install python` |
| L'apk n'atteint pas le serveur | `usesCleartextTraffic` manquant, ou mauvaise IP |
| Le serveur meurt en arrière-plan | `termux-wake-lock` + batterie sans restriction |
| `Killed` au chargement du modèle | Pas assez de RAM : reste sur `echo` |
| Clé perdue | Elle est irrécupérable (hashée) : `keys.py revoke <id>` puis `keys.py new` |
