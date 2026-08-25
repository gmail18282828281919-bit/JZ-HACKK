# ⭐ Système Premium — Fondateurs

## Commandes

| Commande | Qui | Rôle |
|---|---|---|
| `+premium` | tout le monde | Voir son statut, activer un code (bouton), lien support |
| `+premium <code>` | tout le monde | Activation directe d'un code |
| `+premium @membre` | fondateurs | Fiche premium d'un membre |
| `+premiumpanel` | **fondateurs** | Panel complet de gestion (alias : `+pp`, `+ppanel`, `+panelpremium`, `+premiumadmin`, `+gestionpremium`) |

Les fondateurs sont les IDs de `OWNER_IDS` (`MAIN_OWNER_ID` + `FOUNDER_IDS`).

## Le panel `+premiumpanel`

Stats en direct : membres actifs, premiums à vie, expirations < 7 jours, codes disponibles / épuisés, total d'activations, et les 6 prochaines expirations.

**Boutons**

| Ligne | Bouton | Action |
|---|---|---|
| 1 | 🔑 Générer codes | Durée, quantité (1-20), utilisations par code (0 = illimité), code personnalisé, note interne |
| 1 | 📜 Liste des codes | Liste paginée (🟢 dispo / 🔴 épuisé) + bouton 📋 Copier (texte ou fichier `.txt`) |
| 1 | 🗑️ Supprimer code | Supprime un code précis |
| 2 | ➕ Ajouter premium | Donne le premium à un ID/mention pour une durée donnée |
| 2 | ⏱️ Modifier durée | `+7d` (ajoute), `-3d` (retire), `=30d` (fixe), `perm` (à vie) |
| 2 | ❌ Retirer premium | Retire l'accès + le rôle, MP au membre |
| 3 | 👥 Membres premium | Liste paginée avec expiration et source |
| 3 | 📊 Historique | Toutes les actions (activation, génération, ajout, édition, retrait, purge, expiration) |
| 3 | 🧹 Nettoyer | Supprime codes épuisés + accès expirés (avec confirmation) |
| 4 | 🔄 Actualiser · 🔒 Fermer | |

## Formats de durée

`30` = 30 jours · `45m` · `12h` · `7d`/`7j` · `2w` · `6mo` · `1y` · `perm` (à vie, `expires_at = 0`).

## Codes

Format auto : `JZ-XXXX-XXXX-XXXX` (alphabet sans I/O/0/1). Multi-usage possible (`uses_max`), `0` = illimité.
Activer un code alors qu'on est déjà premium **prolonge** l'abonnement au lieu de le remettre à zéro.

## Automatismes

- Rôle premium (`PREMIUM_ROLE_ID`) ajouté/retiré automatiquement sur le serveur principal.
- Vérification toutes les 60 s : MP de rappel 24 h avant l'expiration, MP + retrait du rôle à l'expiration.
- Logs envoyés dans `LOG_CHANNEL_ID` + historique persistant dans `premium_logs.json`.

## Fonctionnalités premium

`+antibot` (salon honeypot anti-bot), `+captcha`, `+ticket` mode menu déroulant, `+backup` (20 sauvegardes),
`+joinmp`, `+depart`.

`+antibot` est débloqué si l'auteur est fondateur, premium, ou si l'owner du serveur est premium.

## Stockage

`premium.json` :

```json
{
  "codes": { "JZ-XXXX-XXXX-XXXX": { "duration": 2592000, "uses_max": 1, "uses": 0,
                                     "used": false, "used_by": [], "created_by": "id",
                                     "created_at": 0, "note": "" } },
  "users": { "id": { "expires_at": 0, "granted_by": "id", "granted_at": 0,
                     "source": "code|fondateur|manuel", "code": "…", "warned": false,
                     "history": [] } }
}
```

`expires_at = 0` signifie **premium à vie**.
