"""Schema de configuration de chaque module du dashboard.

Chaque module declare ses champs : le dashboard genere le formulaire a partir
d'ici, et le bot lit les memes cles. Une seule source de verite.
"""
from __future__ import annotations

from typing import Any

# type de champ : bool | int | text | textarea | channel | role | multirole | select
MODULES: dict[str, dict[str, Any]] = {
    "tickets": {
        "label": "Tickets",
        "icon": "ticket",
        "description": "Panneau de tickets, categories, transcripts et fermeture auto.",
        "fields": {
            "enabled": {"type": "bool", "label": "Module active", "default": False},
            "panel_channel_id": {"type": "channel", "label": "Salon du panneau", "default": 0},
            "category_id": {"type": "channel", "label": "Categorie des tickets", "default": 0,
                            "channel_type": "category"},
            "staff_role_ids": {"type": "multirole", "label": "Roles staff", "default": []},
            "log_channel_id": {"type": "channel", "label": "Salon des transcripts", "default": 0},
            "panel_title": {"type": "text", "label": "Titre du panneau", "default": "Support"},
            "panel_message": {"type": "textarea", "label": "Message du panneau",
                              "default": "Clique sur le bouton pour ouvrir un ticket."},
            "open_message": {"type": "textarea", "label": "Message a l'ouverture",
                             "default": "Merci d'expliquer ton probleme, le staff arrive."},
            "max_per_user": {"type": "int", "label": "Tickets max par membre", "default": 1,
                             "min": 1, "max": 10},
            "auto_close_hours": {"type": "int", "label": "Fermeture auto (h, 0 = off)",
                                 "default": 48, "min": 0, "max": 720},
            "transcript": {"type": "bool", "label": "Sauvegarder un transcript", "default": True},
        },
    },
    "antiraid": {
        "label": "Anti-Raid",
        "icon": "shield",
        "description": "Detection de vagues d'arrivees, comptes recents et lockdown auto.",
        "fields": {
            "enabled": {"type": "bool", "label": "Module active", "default": False},
            "join_threshold": {"type": "int", "label": "Arrivees avant alerte", "default": 8,
                               "min": 2, "max": 100},
            "join_window": {"type": "int", "label": "Fenetre de detection (s)", "default": 10,
                            "min": 3, "max": 300},
            "action": {"type": "select", "label": "Action sur raid", "default": "lockdown",
                       "options": [
                           ["alert", "Alerter seulement"],
                           ["lockdown", "Verrouiller le serveur"],
                           ["kick", "Expulser les arrivants"],
                           ["ban", "Bannir les arrivants"],
                       ]},
            "lockdown_minutes": {"type": "int", "label": "Duree du lockdown (min)", "default": 10,
                                 "min": 1, "max": 1440},
            "min_account_age": {"type": "int", "label": "Age min du compte (jours, 0 = off)",
                                "default": 7, "min": 0, "max": 365},
            "young_account_action": {"type": "select", "label": "Action compte trop recent",
                                     "default": "alert",
                                     "options": [["alert", "Alerter"], ["kick", "Expulser"],
                                                 ["ban", "Bannir"]]},
            "alert_channel_id": {"type": "channel", "label": "Salon des alertes", "default": 0},
            "verified_role_id": {"type": "role", "label": "Role donne apres verification",
                                 "default": 0},
            "quarantine_role_id": {"type": "role", "label": "Role de quarantaine", "default": 0},
        },
    },
    "automod": {
        "label": "AutoMod",
        "icon": "filter",
        "description": "Anti-spam, anti-lien, anti-mention, filtre de mots et sanctions.",
        "fields": {
            "enabled": {"type": "bool", "label": "Module active", "default": False},
            "anti_spam": {"type": "bool", "label": "Anti-spam", "default": True},
            "spam_messages": {"type": "int", "label": "Messages avant sanction", "default": 5,
                              "min": 3, "max": 30},
            "spam_window": {"type": "int", "label": "Fenetre anti-spam (s)", "default": 5,
                            "min": 2, "max": 60},
            "anti_invite": {"type": "bool", "label": "Bloquer les invitations Discord",
                            "default": True},
            "anti_link": {"type": "bool", "label": "Bloquer tous les liens", "default": False},
            "max_mentions": {"type": "int", "label": "Mentions max par message (0 = off)",
                             "default": 5, "min": 0, "max": 50},
            "banned_words": {"type": "textarea", "label": "Mots interdits (un par ligne)",
                             "default": ""},
            "sanction": {"type": "select", "label": "Sanction", "default": "timeout",
                         "options": [["delete", "Supprimer seulement"], ["warn", "Avertir"],
                                     ["timeout", "Exclusion temporaire"], ["kick", "Expulser"],
                                     ["ban", "Bannir"]]},
            "timeout_minutes": {"type": "int", "label": "Duree du timeout (min)", "default": 10,
                                "min": 1, "max": 40320},
            "warn_limit": {"type": "int", "label": "Avertissements avant ban (0 = off)",
                           "default": 3, "min": 0, "max": 20},
            "ignored_channel_ids": {"type": "multichannel", "label": "Salons ignores",
                                    "default": []},
            "ignored_role_ids": {"type": "multirole", "label": "Roles ignores", "default": []},
        },
    },
    "welcome": {
        "label": "Bienvenue",
        "icon": "wave",
        "description": "Messages d'arrivee et de depart, roles automatiques.",
        "fields": {
            "enabled": {"type": "bool", "label": "Module active", "default": False},
            "channel_id": {"type": "channel", "label": "Salon de bienvenue", "default": 0},
            "message": {"type": "textarea", "label": "Message d'arrivee",
                        "default": "Bienvenue {mention} sur **{server}** ! Tu es le membre #{count}."},
            "leave_enabled": {"type": "bool", "label": "Message de depart", "default": False},
            "leave_channel_id": {"type": "channel", "label": "Salon de depart", "default": 0},
            "leave_message": {"type": "textarea", "label": "Message de depart",
                              "default": "**{user}** a quitte le serveur."},
            "autorole_ids": {"type": "multirole", "label": "Roles automatiques", "default": []},
            "dm_enabled": {"type": "bool", "label": "Envoyer un MP", "default": False},
            "dm_message": {"type": "textarea", "label": "Contenu du MP",
                           "default": "Bienvenue sur {server} !"},
        },
    },
    "logs": {
        "label": "Logs",
        "icon": "list",
        "description": "Journalisation des messages, membres, salons et sanctions.",
        "fields": {
            "enabled": {"type": "bool", "label": "Module active", "default": False},
            "channel_id": {"type": "channel", "label": "Salon des logs", "default": 0},
            "message_delete": {"type": "bool", "label": "Messages supprimes", "default": True},
            "message_edit": {"type": "bool", "label": "Messages modifies", "default": True},
            "member_join": {"type": "bool", "label": "Arrivees", "default": True},
            "member_leave": {"type": "bool", "label": "Departs", "default": True},
            "member_update": {"type": "bool", "label": "Roles / pseudos", "default": False},
            "moderation": {"type": "bool", "label": "Actions de moderation", "default": True},
            "dashboard": {"type": "bool", "label": "Actions du dashboard", "default": True},
        },
    },
    "levels": {
        "label": "Niveaux",
        "icon": "chart",
        "description": "XP par message, annonces de niveau et roles de recompense.",
        "fields": {
            "enabled": {"type": "bool", "label": "Module active", "default": False},
            "xp_min": {"type": "int", "label": "XP min par message", "default": 15, "min": 1,
                       "max": 200},
            "xp_max": {"type": "int", "label": "XP max par message", "default": 25, "min": 1,
                       "max": 500},
            "cooldown": {"type": "int", "label": "Cooldown XP (s)", "default": 60, "min": 0,
                         "max": 3600},
            "announce": {"type": "bool", "label": "Annoncer les montees de niveau",
                         "default": True},
            "announce_channel_id": {"type": "channel", "label": "Salon des annonces (0 = sur place)",
                                    "default": 0},
            "announce_message": {"type": "textarea", "label": "Message de niveau",
                                 "default": "GG {mention}, tu passes niveau **{level}** !"},
            "ignored_channel_ids": {"type": "multichannel", "label": "Salons sans XP",
                                    "default": []},
        },
    },
}


def default_config(module: str) -> dict[str, Any]:
    """Config par defaut d'un module."""
    fields = MODULES[module]["fields"]
    return {key: (list(spec["default"]) if isinstance(spec["default"], list)
                  else spec["default"])
            for key, spec in fields.items()}


def sanitize(module: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Valide/normalise une config recue du dashboard (jamais faire confiance au client)."""
    fields = MODULES[module]["fields"]
    clean = default_config(module)

    for key, spec in fields.items():
        if key not in raw:
            continue
        value = raw[key]
        kind = spec["type"]
        try:
            if kind == "bool":
                clean[key] = bool(value)
            elif kind == "int":
                number = int(value)
                clean[key] = max(spec.get("min", 0), min(spec.get("max", 10**9), number))
            elif kind in ("text", "textarea"):
                clean[key] = str(value)[:4000]
            elif kind in ("channel", "role"):
                clean[key] = int(value or 0)
            elif kind in ("multirole", "multichannel"):
                if not isinstance(value, list):
                    value = []
                clean[key] = [int(x) for x in value if str(x).isdigit()][:50]
            elif kind == "select":
                allowed = [option[0] for option in spec["options"]]
                clean[key] = value if value in allowed else spec["default"]
        except (TypeError, ValueError):
            continue

    return clean
