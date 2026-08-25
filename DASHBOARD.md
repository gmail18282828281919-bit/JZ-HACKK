# Dashboard ModeraBot — connexion à l'API du bot

## Le problème

Le dashboard affichait :

> **L'API du bot ne répond pas.** Les salons et rôles ne peuvent pas être listés
> (saisie par ID), et tes réglages sont gardés dans ce navigateur en attendant.

Trois causes cumulées :

1. **Mauvaise cible.** `dash.html` et `servers.html` appelaient `/api/...` en
   chemin relatif. La page étant servie par `dashboard.moderabot.xyz` (hébergeur
   statique) et l'API tournant sur le serveur du bot, ces appels partaient vers
   l'hébergeur statique → 404 → `apiAlive = false`.
2. **Pas de CORS.** Même en visant la bonne origine, Flask ne renvoyait aucun
   en-tête `Access-Control-Allow-Origin` : le navigateur bloquait la réponse.
3. **Pas d'authentification cross-origin.** Le cookie de session Flask est en
   `SameSite=Lax`, donc jamais envoyé vers une autre origine. Seul le token
   Discord porté par la page (`Authorization: Bearer …`) peut authentifier.

## Ce qui a été changé

**`app.py`**

- Bloc CORS (`@app.after_request`) : `Access-Control-Allow-Origin` renvoyé pour
  les origines de `DASHBOARD_ORIGINS`, plus `Allow-Credentials`,
  `Allow-Headers: Authorization, Content-Type, Accept` et `Vary: Origin`.
- Route `OPTIONS /api/<path>` pour répondre au pré-vol CORS (204).
- `GET /api/health` : permet de distinguer « API injoignable » de « mauvaise URL ».
- `GET /api/bot-guilds` : renvoie les serveurs de l'utilisateur où le bot est
  présent. Accepte le cookie **ou** le token Bearer, contrairement à
  `/api/my-guilds` qui exigeait la session — c'est cette route que
  `servers.html` interrogeait déjà en premier.
- Secrets sortis du code (voir plus bas).

**`dash.html` / `servers.html`**

- Constante `API_BASE` (surchargée par `window.MB_API_BASE`) préfixant tous les
  appels `/api/...`.
- Envoi systématique de `Authorization: Bearer <token Discord>`, et
  `credentials: 'omit'` en cross-origin (le cookie ne servirait à rien).

## Ce qu'il reste à faire côté hébergement

**L'API doit être servie en HTTPS.** Une page en `https://` ne peut pas appeler
`http://5.178.107.228:2025` : le navigateur bloque le contenu mixte, quels que
soient les en-têtes CORS. Deux options :

1. **Sous-domaine dédié** — faire pointer `api.moderabot.xyz` vers le serveur,
   avec nginx + certificat (Let's Encrypt ou proxy Cloudflare) qui relaie vers
   `127.0.0.1:2025`. C'est la valeur par défaut d'`API_BASE`.

   ```nginx
   server {
       listen 443 ssl;
       server_name api.moderabot.xyz;
       # ssl_certificate ... ;
       location / {
           proxy_pass http://127.0.0.1:2025;
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
   }
   ```

2. **Proxy depuis l'hébergeur du dashboard** — rediriger `/api/*` vers le
   serveur du bot. Dans ce cas, mettre `API_BASE` à `''` (chaîne vide) dans les
   deux fichiers HTML : tout redevient same-origin et le CORS n'est plus requis.

Vérification une fois en place :

```bash
curl -i https://api.moderabot.xyz/api/health \
     -H "Origin: https://dashboard.moderabot.xyz"
# attendu : 200, {"ok":true,"bot_ready":true,...}
#           Access-Control-Allow-Origin: https://dashboard.moderabot.xyz
```

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `DASHBOARD_ORIGINS` | Origines autorisées en CORS, séparées par des virgules |
| `DISCORD_CLIENT_ID` | ID de l'application Discord |
| `DISCORD_CLIENT_SECRET` | Secret client OAuth2 |
| `OAUTH_REDIRECT_URI` | URL de callback déclarée dans le portail Discord |
| `FLASK_SECRET_KEY` | Clé de signature des sessions Flask |
| `BOT_API_TOKEN` | Clé de `/bot/stats?key=…` |
| `DASHBOARD_PORT` | Port d'écoute du serveur web |

Ces valeurs peuvent aussi être placées dans `config.json` (`client_secret`,
`flask_secret_key`, `api_token`, `redirect_uri`), qui est ignoré par git.

## ⚠️ Secrets à révoquer

Le fichier `app.py` d'origine contenait en clair :

- `CLIENT_SECRET = "S1LZeq…"` — **secret client OAuth2 Discord**
- `API_TOKEN` / `SECRET_KEY = "f92Jk…"` — clé d'API et clé de session Flask

Ce dépôt est **public**. Ces valeurs ont donc été retirées du code avant le
commit, mais elles ont circulé : il faut les considérer comme compromises.

1. Portail Discord → *OAuth2* → **Reset Secret**.
2. Générer une nouvelle `FLASK_SECRET_KEY` et un nouveau `BOT_API_TOKEN`
   (`python -c "import os; print(os.urandom(32).hex())"`).
3. Les renseigner en variables d'environnement, jamais dans le code.
