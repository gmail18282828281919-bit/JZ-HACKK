# ModeraBot — bot Discord + dashboard web

Bot Discord (`discord.py`, asynchrone) et dashboard Flask (synchrone, dans un
thread séparé) dans le **même programme**, qui communiquent par une **base
SQLite partagée**. Connexion des utilisateurs en **OAuth2 Discord** : chacun ne
voit et ne configure que les serveurs où il a la permission « Gérer le serveur ».

```
                    ┌──────────────────────────────┐
   Discord  ◄──────►│  bot/  (asyncio, tasks)      │
                    │   cogs : tickets, antiraid,  │
                    │   automod, welcome, logs,    │
                    │   levels, bridge             │
                    └──────────┬───────────────────┘
                               │  lecture / écriture
                    ┌──────────▼───────────────────┐
                    │  data/jz.db  (SQLite WAL)    │
                    │  config · stats · tickets    │
                    │  action_queue · audit_log    │
                    └──────────▲───────────────────┘
                               │  lecture / écriture
   Navigateur ◄─── nginx ─────►│  web/  (Flask, thread)
        (HTTPS)     (site      │   OAuth2 + API + Jinja2
                     seulement)└──────────────────────────┘
```

## Le point clé : le site *commande* le bot

Le dashboard n'a **jamais** le token du bot. Quand tu cliques sur « Bannir » ou
« Verrouiller le serveur », Flask écrit une ligne dans la table `action_queue`.
La task `consume_queue` du cog `bridge` (toutes les 2 s) :

1. réserve les ordres en attente (transaction `BEGIN IMMEDIATE`) ;
2. **revérifie côté bot** que le demandeur est toujours membre et a bien
   « Gérer le serveur » — la vérification du site ne suffit pas ;
3. contrôle la hiérarchie des rôles (impossible de frapper plus haut que soi) ;
4. exécute, écrit le résultat, journalise dans `audit_log` et dans le salon de logs.

Le navigateur suit l'état de son ordre via `/api/guild/<id>/action/<id>` et
affiche le résultat renvoyé par le bot.

## Les tasks du bot

| Cog | Task | Fréquence | Rôle |
|---|---|---|---|
| `client` | `heartbeat` | 30 s | écrit latence/uptime, alimente le badge « Bot en ligne » |
| `bridge` | `consume_queue` | 2 s | exécute les ordres du dashboard |
| `bridge` | `refresh_cache` | 5 min | pousse salons + rôles en base pour les menus du site |
| `tickets` | `auto_close` | 10 min | ferme les tickets inactifs, archive le transcript |
| `antiraid` | `decay` | 30 s | purge les compteurs d'arrivées hors fenêtre |
| `antiraid` | `unlock` | 30 s | lève le lockdown à la fin du délai |
| `automod` | `expire_sanctions` | 1 min | débannit / clôt les sanctions temporaires |

## Modules configurables

`tickets`, `antiraid`, `automod`, `welcome`, `logs`, `levels`.

Le schéma de chaque module vit dans **`core/defaults.py`** — une seule source de
vérité : le bot lit les mêmes clés que le formulaire du dashboard, qui est
**généré automatiquement** à partir de ce fichier. Ajouter un réglage =
ajouter une entrée dans `MODULES`, rien d'autre à toucher côté site.

Toute config reçue passe par `sanitize()` : bornes des entiers, listes blanches
des `select`, tailles maximales. On ne fait jamais confiance au navigateur.

## Installation

```bash
git clone <ce dépôt> /opt/moderabot && cd /opt/moderabot
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env      # token, client id/secret, secret Flask
./venv/bin/python main.py
```

Sur le [portail développeur Discord](https://discord.com/developers/applications) :

- **Bot → Privileged Gateway Intents** : activer `SERVER MEMBERS` et `MESSAGE CONTENT` ;
- **OAuth2 → Redirects** : ajouter exactement la valeur de `OAUTH_REDIRECT_URI`
  (par défaut `https://dashboard.moderabot.xyz/servers.html`).

## Production

Deux services séparés, c'est plus propre (redémarrer le site ne coupe pas le bot) :

```bash
cp deploy/moderabot-*.service /etc/systemd/system/
systemctl enable --now moderabot-bot moderabot-web
cp deploy/nginx.conf /etc/nginx/sites-available/moderabot
ln -s /etc/nginx/sites-available/moderabot /etc/nginx/sites-enabled/
certbot --nginx -d dashboard.moderabot.xyz && nginx -t && systemctl reload nginx
```

**nginx ne proxifie que le site.** Le bot n'écoute sur aucun port : il ouvre une
connexion sortante vers Discord. L'exposer derrière un proxy, c'est offrir une
porte d'entrée vers ton token — à ne jamais faire.

## Sécurité en place

- Flask écoute sur `127.0.0.1` uniquement ; nginx termine le TLS.
- Session signée, cookie `HttpOnly` + `SameSite=Lax` + `Secure`.
- `state` anti-CSRF sur le flux OAuth2, jeton CSRF sur chaque POST.
- Le `CLIENT_SECRET` et les tokens OAuth ne quittent jamais le serveur.
- Liste blanche stricte des actions (`ALLOWED_ACTIONS`) + revalidation côté bot.
- Limite de 20 actions/min par utilisateur, en plus du `limit_req` nginx.
- CSP sans `unsafe-inline` sur les scripts, `frame-ancestors 'none'`.

## Structure

```
main.py               bot + web dans un seul processus
wsgi.py               entrée gunicorn (site seul)
core/config.py        variables d'environnement
core/defaults.py      schéma des modules (source unique)
core/database.py      SQLite partagé, sync + wrapper async
bot/client.py         client Discord, heartbeat, cache serveurs
bot/cogs/bridge.py    file d'actions dashboard → bot
bot/cogs/*.py         modules fonctionnels
web/app.py            Flask : pages, OAuth2, API
web/oauth.py          client OAuth2 Discord
web/templates/        index · servers · dash (Jinja2)
web/static/           css/js du dashboard
deploy/               nginx + units systemd
```
