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

### 1. Uploader les fichiers

**5 fichiers**, à déposer à côté de ton `app.py` (dans `/home/container/` sur
Pterodactyl, via l'onglet *Gestionnaire de fichiers*) :

```
/home/container/
├── app.py              (déjà là)
├── config.json         (déjà là)
├── dashboard.py        ← 1. le module
├── patch_app.py        ← 2. lance le patch puis le bot
└── web/                ← dossier à créer
    ├── index.html      ← 3. connexion
    ├── servers.html    ← 4. choix du serveur
    └── dash.html       ← 5. configuration
```

Ajoute aussi ton `logo.png` dans `web/` si tu en as un — les pages le
référencent, mais elles fonctionnent sans.

> Le dossier peut aussi s'appeler `static/` ou `public/`, et les pages peuvent
> même être posées directement à côté de `dashboard.py` : le module cherche
> `index.html` à ces différents endroits tout seul.

### 2. Patcher app.py

Le patch corrige `app.py` (voir la liste plus bas). Deux façons de le lancer,
selon ce que ton hébergeur t'autorise.

**Sur Pterodactyl** — la commande de démarrage est verrouillée par l'egg, mais
la variable **APP PY FILE** est modifiable. Onglet **Startup** → champ
*APP PY FILE* : remplace `app.py` par :

```
patch_app.py
```

C'est tout. À chaque démarrage, le patch se rejoue (sans rien refaire s'il est
déjà appliqué) puis passe la main au bot, dans le même processus — la console
du panel et le bouton Stop continuent de fonctionner normalement.

Si ton fichier principal ne s'appelle pas `app.py`, ajoute une variable
d'environnement `BOT_FILE` avec son nom.

**Avec un accès shell** — patch seul, sans lancer le bot :

```bash
python3 patch_app.py app.py
```

Le script crée un `app.py.bak`, vérifie que le résultat compile avant d'écrire,
et corrige :

- `WEB_PORT` → `SERVER_PORT` (l'allocation du panel) devient prioritaire, défaut **30121** ;
- le `print` qui affichait « port 30121 » en dur alors que le bot écoutait ailleurs ;
- `SESSION_COOKIE_SECURE = True`, qui empêchait toute session en `http://` simple ;
- `require_guild_admin`, qui n'acceptait que le cookie : les routes
  `/overview`, `/members`, `/settings`, `/security/*` répondaient **toujours 403**
  depuis le dashboard. Elles acceptent maintenant aussi le token `Bearer` ;
- `client_id` / `client_secret` / `secret_key` : lus depuis `config.json` ou les
  variables d'environnement au lieu d'être écrits en dur dans le code ;
- l'appel à `register_dashboard(...)` avant le démarrage du serveur web.

Relancer le script est sans risque : il détecte ce qui est déjà fait. Si le
résultat ne compilait pas, rien n'est écrit et le bot démarre quand même, sans
le dashboard.

### 3. Compléter config.json

Ajoute ces clés à ton `config.json` existant :

```json
{
  "client_id":     "L_APPLICATION_ID_DE_TON_BOT",
  "client_secret": "LE_CLIENT_SECRET_DU_PORTAIL_DISCORD",
  "secret_key":    "une-longue-chaine-aleatoire-a-toi",
  "dashboard_port": 30121
}
```

Deux clés facultatives, seulement si tu passes par un nom de domaine ou si tu
héberges le HTML ailleurs (voir plus bas) :

```json
  "dashboard_public_url":      "",
  "dashboard_allowed_origins": ""
```

> `client_secret` était écrit en clair dans `app.py`. **Régénère-le** sur le
> portail Discord (*OAuth2 → Reset Secret*) et mets le nouveau dans
> `config.json`, qui ne doit jamais partir sur GitHub.

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

## Si le port du bot est bloqué : le tunnel inverse

Beaucoup d'hébergeurs de bots bloquent les connexions **entrantes** sur les
allocations. Le bot écoute bien, mais personne ne peut le joindre. Aucun
réglage du panel n'y change quoi que ce soit.

Le tunnel retourne le problème : **c'est le bot qui appelle ton VPS**, en
sortant. Les connexions sortantes ne sont jamais bloquées — c'est comme ça
que le bot parle à Discord.

```
Bot (Pterodactyl)                          Ton VPS
      │                                        │
      │ ── connexion SSH sortante ───────────► │  sshd
      │                                        │
      │                          127.0.0.1:8099 ◄── nginx
      │                                        │
      ◄──── le trafic redescend par le tunnel ─┘
```

Le port distant est lié à `127.0.0.1` : **seul nginx, sur ton VPS, peut
l'atteindre**. Rien n'est exposé à Internet, et tout le trajet est chiffré
par SSH.

### Côté VPS

Crée un utilisateur dédié au tunnel — pas root :

```bash
sudo adduser --disabled-password --gecos "" bottunnel
sudo -u bottunnel mkdir -p /home/bottunnel/.ssh
sudo -u bottunnel touch /home/bottunnel/.ssh/authorized_keys
sudo -u bottunnel chmod 700 /home/bottunnel/.ssh
sudo -u bottunnel chmod 600 /home/bottunnel/.ssh/authorized_keys
```

La clé publique à y coller sera affichée par le bot à son premier démarrage.

### Côté bot

Onglet **Startup** → **ADDITIONAL PYTHON PACKAGES** → ajoute :

```
paramiko
```

Puis dans `config.json` :

```json
"tunnel": {
  "host": "195.95.144.228",
  "port": 22,
  "user": "bottunnel",
  "remote_port": 8099
}
```

Au premier démarrage, le bot crée sa clé et l'affiche dans la console. Tu la
copies dans `/home/bottunnel/.ssh/authorized_keys` sur le VPS, tu redémarres,
et la console affiche :

```
🔒 Tunnel ouvert : bottunnel@195.95.144.228:22 → 127.0.0.1:8099 → bot:30121
```

### Côté nginx

Dans la config, remplace le `proxy_pass` par l'extrémité du tunnel :

```nginx
proxy_pass http://127.0.0.1:8099;
```

### Comportement

Le tunnel se reconnecte tout seul si la connexion tombe, avec un délai qui
double à chaque échec (5 s, 10 s, 20 s… plafonné à 2 minutes). Son état
apparaît dans `/api/status` et donc dans l'indicateur du dashboard.

Si `paramiko` n'est pas installé, le tunnel est simplement désactivé et le
bot démarre normalement — il ne plante jamais pour ça.

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
python3 test_dashboard.py
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
