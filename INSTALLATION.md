# Pack Modules Pro — ModeraBot

Ajout **100 % additif** : ton `app.py` et ton `dash_2.html` d'origine ne sont pas modifiés.

## 1. Le bot

Copie `modules_extra.py` à côté de `app.py`, puis ajoute **une seule ligne**
dans `app.py`, juste avant la dernière ligne `bot.run(TOKEN)` :

```python
import modules_extra
modules_extra.setup(bot, app)

bot.run(TOKEN)
```

C'est tout. Au démarrage tu verras :
`[modules_extra] 6 categories et 45+ commandes ajoutees.`

Si un nom de commande existe déjà dans `app.py`, il est automatiquement
préfixé (`+xnom`) au lieu de faire planter le bot — un message le signale.

## 2. Le dashboard

Remplace `dash_2.html` par celui fourni : c'est **ton fichier d'origine, inchangé**,
avec le bloc `dashboard_extras_snippet.html` collé avant `</body>`.
(Si tu préfères, colle toi-même le contenu de `dashboard_extras_snippet.html`
avant `</body>` de ton fichier actuel — même résultat.)

Les nouvelles pages lisent et écrivent sur `GET/POST /api/guild/<id>/extras`,
la route ajoutée par `modules_extra.py`. Les routes existantes ne sont pas touchées.

## 3. Les 11 catégories ajoutées

| Catégorie | Panneau | Commandes |
|---|---|---|
| 💰 Économie | `+economy` | `+balance` `+daily` `+work` `+pay` `+deposit` `+withdraw` `+rob` `+shop` `+buy` `+inventory` `+ecolb` `+addmoney` `+removemoney` `+resetmoney` |
| 🛡️ AutoMod Pro | `+automod` | `+badword` `+antiinvite` `+automodignore` `+automodlogs` `+automodtest` |
| 💡 Suggestions | `+suggestions` | `+suggest` `+approve` `+deny` `+suggestinfo` `+suggestreset` |
| 📊 Sondages | `+pollconfig` | `+pollpro` `+quickpoll` `+endpoll` `+pollresults` |
| 🔒 Protection | `+guard` | `+lock` `+unlock` `+lockall` `+unlockall` `+slowmode` `+panic` `+raidmode` `+agegate` |
| 📋 Candidatures | `+apply` | `+applysend` `+applyadd` `+applydel` `+applylist` |
| 🧨 Anti-nuke | `+antinuke` | `+antinukewl` `+antinukelogs` |
| 📒 Infractions | `+infractions` | `+addinfraction` `+delinfraction` `+clearinfractions` `+topinfractions` |
| 🔁 Messages auto | `+automessage` | `+automessageadd` `+automessagelist` `+automessagedel` |
| 🎂 Anniversaires | `+birthdays` | `+birthday` `+birthdaylist` `+nextbirthdays` `+birthdayremove` |
| ⌨️ Commandes perso | `+customcmd` | `+ccadd` `+ccdel` `+cclist` |

`+modules` affiche le récapitulatif dans Discord.

Chaque panneau fonctionne comme `+ticket` / `+welcome` : embed de statut,
menu déroulant, modals de configuration et boutons on/off.
Les panneaux publics (candidatures, suggestions) utilisent des vues
persistantes : ils continuent de marcher après un redémarrage du bot.

## 4. Fichiers de données créés

- `extras_configs/<guild_id>.json` — configuration des 11 modules
- `extras_bank/<guild_id>.json` — soldes et inventaires de l'économie
- `extras_infractions/<guild_id>.json` — casiers des membres
- `extras_birthdays/<guild_id>.json` — dates d'anniversaire

Rien n'écrase tes fichiers existants.
