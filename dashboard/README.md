# Dashboard web du bot Discord

Dashboard complet (tickets, anti-raid, anti-lien, vérification, logs, bienvenue,
niveaux, giveaways, divers, import/export) **servi directement par le bot**,
sur **un seul port** : celui de ton allocation Pterodactyl, **30121**.

---

## Pourquoi ça ne marchait pas avant

Trois problèmes, et un seul est un problème de firewall :

| # | Problème | Conséquence |
|---|----------|-------------|
| 1 | L'API Flask du bot n'envoyait **aucun header CORS** | La page hébergée sur `dashboard.moderabot.xyz` ne pouvait pas appeler l'API du bot. Le navigateur bloquait chaque requête. |
| 2 | **Mixed content** : une page en `https://` ne peut pas appeler `http://ip:30121` | Bloqué par le navigateur **quoi que tu fasses au firewall**. Impossible à corriger côté réseau. |
| 3 | `WEB_PORT` retombait sur **5001**, alors que le panel n'expose que **30121** | nginx du panel renvoyait 502 : le bot écoutait sur un port non alloué. |

**La solution : ne pas héberger le HTML ailleurs.** Le bot sert lui-même les pages
sur son port. Même origine → 1 et 2 disparaissent complètement, et il n'y a
qu'**un seul port** à ouvrir. Pas de second port, pas de proxy obligatoire.

---

## Installation (5 minutes)

### 1. Copier le dossier

Dépose le dossier `dashboard/` **à côté** de ton `app.py`, sur le serveur :

```
/home/container/
├── app.py
├── config.json
└── dashboard/
    ├── __init__.py
    ├── server.py
    ├── patch_app.py
    └── static/
        ├── index.html      (connexion)
        ├── servers.html    (choix du serveur)
        ├── dash.html       (configuration)
        └── logo.png        (ton logo, optionnel)
```

### 2. Patcher app.py

```bash
python3 dashboard/patch_app.py app.py
```

Le script crée un `app.py.bak`, vérifie que le résultat compile, et corrige :

- `WEB_PORT` → `SERVER_PORT` (l'allocation du panel) devient prioritaire, défaut **30121** ;
- le `print` qui affichait « port 30121 » en dur alors que le bot écoutait ailleurs ;
- `SESSION_COOKIE_SECURE = True`, qui empêchait toute session en `http://` simple ;
- `require_guild_admin`, qui n'acceptait que le cookie : les routes
  `/overview`, `/members`, `/settings`, `/security/*` répondaient **toujours 403**
  depuis le dashboard. Elles acceptent maintenant aussi le token `Bearer` ;
- `client_id` / `client_secret` / `secret_key` : lus depuis `config.json` ou les
  variables d'environnement au lieu d'être écrits en dur dans le code ;
- l'appel à `register_dashboard(...)` avant le démarrage du serveur web.

Relancer le script est sans risque : il détecte ce qui est déjà fait.

### 3. Compléter config.json

Voir `dashboard/config.example.json`. Le minimum :

```json
{
  "client_id": "L_APPLICATION_ID_DE_TON_BOT",
  "client_secret": "...",
  "secret_key": "une-longue-chaine-aleatoire",
  "dashboard_port": 30121
}
```

> `client_secret` était écrit en clair dans `app.py`. **Régénère-le** sur le portail
> Discord (*OAuth2 → Reset Secret*) et mets le nouveau dans `config.json`, qui ne
> doit jamais partir sur GitHub.

### 4. Déclarer la Redirect URI sur Discord

[Portail développeur](https://discord.com/developers/applications) → ton
application → **OAuth2** → *Redirects* → **Add Redirect** :

```
http://IP_PUBLIQUE_DU_PANEL:30121/servers.html
```

L'IP publique est celle affichée à côté de l'allocation dans Pterodactyl.
**Elle doit correspondre au caractère près** (pas de `/` final), sinon Discord
répond « Invalid OAuth2 redirect_uri ».

Si tu utilises un nom de domaine (voir plus bas), mets plutôt
`https://ton-domaine.fr/servers.html`.

### 5. Dépendances

```bash
pip install flask requests waitress
```

`waitress` est optionnel mais recommandé : sans lui le bot tombe sur le serveur
de développement de Flask, qui n'est pas fait pour être exposé.

### 6. Redémarrer et vérifier

Au démarrage, la console doit afficher :

```
🔌 Port web retenu : 30121  (source : SERVER_PORT (allocation du panel))
🖥️  Dashboard web branche sur l'API du bot
🌐 Serveur web (waitress) sur 0.0.0.0:30121
```

Puis ouvre `http://IP_PUBLIQUE:30121/`.

---

## L'indicateur d'état

En haut à droite de `dash.html`, une pastille répond à la question « est-ce que
ça marche ? ». Elle se met à jour **toutes les 15 secondes** et distingue trois
états :

| Pastille | Signification |
|---|---|
| 🟢 **Nom du bot en ligne** | l'API répond **et** le bot est connecté à Discord — tout fonctionne |
| 🟠 **Bot hors ligne** | le serveur web répond, mais la connexion Discord est coupée (token invalide, intents manquants, bot en cours de démarrage) |
| 🔴 **API injoignable** | aucune réponse : bot arrêté, ou port fermé |

Un clic dessus ouvre le détail :

- **API du bot** — le serveur web reçoit-il les requêtes ;
- **Connexion Discord** — la gateway est-elle établie (`bot.is_ready()`) ;
- **Latence API** — aller-retour navigateur → bot, mesuré côté navigateur ;
- **Latence Discord** — latence de la gateway (`bot.latency`) ;
- **Serveurs** — nombre de guildes et de membres vus par le bot ;
- **En ligne depuis** — uptime ;
- **Dernière vérification** — heure du dernier échange réussi.

La distinction 🟠/🔴 est le vrai diagnostic : **orange = problème Discord**
(token, intents), **rouge = problème réseau** (port, firewall, bot arrêté).

Le pied de page de `index.html` et `servers.html` affiche le même état
(avant, « Bot en ligne » y était écrit en dur, même bot éteint).

## Ports et firewall

**Un seul port : 30121/tcp.** Rien d'autre à ouvrir.

### Côté Pterodactyl

1. Panel → ton serveur → **Network** : l'allocation `IP:30121` doit exister et
   être **assignée** (marquée « Primary »).
2. Le bot doit écouter sur `0.0.0.0` et non `127.0.0.1` — c'est déjà le cas
   (`serve(app, host="0.0.0.0", port=WEB_PORT, ...)`).
3. Ne force pas `dashboard_port` sur une autre valeur que l'allocation : un port
   non alloué n'est **pas** routé jusqu'au conteneur.

### Côté machine hôte (si tu as un accès root)

Si le port n'est toujours pas joignable de l'extérieur :

```bash
# ufw (Debian / Ubuntu)
sudo ufw allow 30121/tcp
sudo ufw reload

# firewalld (CentOS / Rocky / AlmaLinux)
sudo firewall-cmd --permanent --add-port=30121/tcp
sudo firewall-cmd --reload
```

Chez un hébergeur cloud (OVH, Hetzner, Oracle, AWS…), pense aussi au
**pare-feu réseau du panel de l'hébergeur** : c'est souvent lui qui bloque,
pas la machine.

### Vérifier

```bash
# depuis le serveur : le bot écoute-t-il ?
ss -ltnp | grep 30121
curl -s http://127.0.0.1:30121/api/health      # -> {"bot_ready":true,"ok":true}

# depuis chez toi : le port passe-t-il le firewall ?
curl -s http://IP_PUBLIQUE:30121/api/health
```

| Résultat depuis l'extérieur | Diagnostic |
|---|---|
| Réponse JSON | tout est bon |
| `Connection refused` | le bot n'écoute pas / mauvais port |
| Timeout | firewall (hôte ou hébergeur) |
| Fonctionne en local mais pas dehors | allocation Pterodactyl manquante |

---

## Optionnel : nom de domaine en https

Utile si tu veux `https://dashboard.mondomaine.fr` au lieu d'une IP. Le port
30121 peut alors rester **fermé à l'extérieur** : seul nginx y accède en local.

```nginx
server {
    listen 443 ssl;
    server_name dashboard.mondomaine.fr;

    ssl_certificate     /etc/letsencrypt/live/dashboard.mondomaine.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dashboard.mondomaine.fr/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:30121;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Puis dans `config.json` :

```json
"dashboard_public_url": "https://dashboard.mondomaine.fr"
```

et ajoute `https://dashboard.mondomaine.fr/servers.html` dans les Redirects Discord.

---

## Optionnel : garder le HTML sur un hébergeur séparé

Déconseillé (c'est ce qui cassait tout), mais possible. Deux conditions
**obligatoires** :

1. L'API du bot doit être joignable **en https** — sinon la page https ne pourra
   jamais l'appeler. Il faut donc le reverse proxy ci-dessus de toute façon.
2. Déclarer l'origine du site dans `config.json` :

```json
"dashboard_allowed_origins": "https://dashboard.moderabot.xyz"
```

Puis, dans le `<head>` de tes pages :

```html
<script>window.MB_API_BASE='https://api.mondomaine.fr';</script>
```

L'authentification passe par un header `Bearer`, jamais par cookie : aucun
`Access-Control-Allow-Credentials` n'est envoyé, donc l'origine autorisée ne peut
pas être détournée pour agir au nom d'un utilisateur connecté.

---

## Comment ça marche

```
Navigateur                        Bot (0.0.0.0:30121)
   │
   │  GET /                       → index.html   (page de connexion)
   │  GET /api/config             → client_id + redirect_uri
   │
   │  ── OAuth2 implicite ──►  discord.com
   │  ◄── #access_token=… ──   redirection vers /servers.html
   │
   │  GET /api/me      Bearer …   → serveurs où tu es admin + bot présent ou non
   │  GET /dashboard.html?guild=… → la page de configuration
   │  GET /api/guild/<id>/dashboard  Bearer …  → salons, rôles, config actuelle
   │  POST /api/guild/<id>/dashboard Bearer …  → enregistre dans les .json du bot
   │  GET /api/guild/<id>/stats      Bearer …  → membres, en ligne, top niveaux
  │
  │  GET /api/status  (toutes les 15 s)  → alimente l'indicateur d'état
```

Le token Discord n'est jamais stocké côté serveur : le bot le vérifie auprès de
Discord (avec un cache de 2 minutes) et contrôle à chaque requête que
l'utilisateur possède bien **Administrateur** ou **Gérer le serveur** sur la
guilde demandée.

### Routes ajoutées par ce module

| Route | Rôle |
|---|---|
| `GET /` `/index.html` `/servers.html` `/dash.html` | les pages du dashboard |
| `GET /dashboard` `/servers` | alias sans `.html` |
| `GET /api/config` | `client_id`, `redirect_uri` — **aucun secret** |
| `GET /api/status` | état temps réel : bot connecté, latences, serveurs, uptime |
| `GET /api/me` | utilisateur + ses serveurs administrables, bot présent ou non |

Les routes `/api/guild/...` existantes du bot ne sont pas modifiées.

---

## Tests

```bash
python3 dashboard/test_dashboard.py
```

Vérifie sans réseau ni bot réel : les pages répondent, `/api/config` ne fuite
aucun secret, `/api/me` rejette les tokens invalides et filtre les serveurs sans
permission, le CORS ne reflète que les origines déclarées.

---

## Problèmes courants

| Symptôme | Cause | Correctif |
|---|---|---|
| « L'API du bot ne répond pas » | port fermé ou bot arrêté | `curl http://127.0.0.1:30121/api/health` sur le serveur |
| « Invalid OAuth2 redirect_uri » | Redirect URI absente ou différente | recopier **exactement** l'URL affichée au démarrage |
| Retour en boucle sur Discord | `client_id` faux dans `config.json` | vérifier l'Application ID du portail |
| Boucle après avoir cliqué « Se connecter » | ton `index.html` utilisait `response_type=code` alors que `servers.html` attend un token | corrigé : les deux pages utilisent `response_type=token` |
| `403 forbidden` sur `/api/guild/...` | pas admin sur ce serveur, ou bot absent | `+invite`, et vérifier tes permissions |
| Le bot n'apparaît pas dans la liste | cache des membres | activer **Server Members Intent** sur le portail |
| Page blanche en https | mixed content | tout servir par le bot, ou passer par nginx |
| 502 via le domaine du panel | bot sur un port non alloué | `dashboard_port` = allocation Pterodactyl |
