# ══════════════════════════════════════════════════════════════════════════════
#  API DASHBOARD — à coller dans app.py
#  Emplacement : après les routes /api/guild/<guild_id>/roles existantes,
#  et AVANT le lancement du serveur Flask.
#
#  Dépend de ce qui existe déjà dans app.py :
#    app, bot, session, request, jsonify, json, os
#    require_guild_admin, jload, jsave, FILES
#    get_server_config, save_server_config, get_level_config, save_level_config
#    get_logs_cfg, save_logs_cfg, LOGS_TYPES
#    _load_captcha, _save_captcha
#    _prefix_cache, _save_prefixes, DEFAULT_PREFIX
#    _defaultroles, _starboard_cfg, _showpic_cfg
# ══════════════════════════════════════════════════════════════════════════════

def _i(v, default=None):
    """Convertit en int un ID venant du JSON (le bot attend des int, pas des str)."""
    try:
        if v is None or v == "":
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _b(v, default=False):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "on", "oui", "yes")
    return default


def _s(v, default="", maxlen=2000):
    if v is None:
        return default
    return str(v)[:maxlen]


def _int_list(v):
    out = []
    for x in (v or []):
        n = _i(x)
        if n is not None:
            out.append(n)
    return out


def _guild_config_payload(guild):
    """Assemble la configuration complète du serveur pour le dashboard."""
    gid = str(guild.id)

    tickets = jload(FILES["ticket_select"]).get(gid, {})
    welcome = jload(FILES["welcome"]).get(gid, {})
    depart = jload(FILES["depart"]).get(gid, {})
    antilink = jload(FILES["antilink"]).get(gid, {})
    antibot = jload(FILES["antibot"]).get(gid, {})
    giveaway = jload(FILES["giveaway_cfg"]).get(gid, {})
    captcha = _load_captcha().get(gid, {})
    logs = get_logs_cfg(guild.id)
    srv = get_server_config(gid)
    lvl = get_level_config(gid)

    return {
        "prefix": _prefix_cache.get(guild.id, DEFAULT_PREFIX),
        "tickets": {
            "panel": tickets.get("panel", {}),
            "choix": tickets.get("choix", []),
        },
        "welcome": welcome,
        "depart": depart,
        "logs": {t[0]: logs.get(t[0], {}) for t in LOGS_TYPES},
        "antilink": antilink,
        "antiraid": srv.get("antiraid", {}),
        "captcha": captcha,
        "levels": {
            "xp_channel": lvl.get("xp_channel"),
            "notif_channel": lvl.get("notif_channel"),
            "xp_min": lvl.get("xp_min", 5),
            "xp_max": lvl.get("xp_max", 15),
        },
        "giveaway": giveaway,
        "antibot": {k: v for k, v in antibot.items() if k != "offenders"},
        "starboard": _starboard_cfg.get(gid, {}),
        "showpic": _showpic_cfg.get(gid, {}),
        "defaultroles": _defaultroles.get(gid, []),
    }


@app.route("/api/guild/<guild_id>/dashboard", methods=["GET", "POST"])
def api_guild_dashboard(guild_id):
    guild, member = require_guild_admin(guild_id)
    if not guild:
        return jsonify({"error": "forbidden"}), 403

    gid = str(guild.id)

    # ─────────────────────────── LECTURE ───────────────────────────
    if request.method == "GET":
        categories = [{"id": str(c.id), "name": c.name} for c in guild.categories]
        channels = [{"id": str(c.id), "name": c.name,
                     "category": str(c.category.id) if c.category else None}
                    for c in guild.text_channels]
        voice = [{"id": str(c.id), "name": c.name} for c in guild.voice_channels]
        roles = [{"id": str(r.id), "name": r.name, "color": str(r.color)}
                 for r in guild.roles if r.name != "@everyone" and not r.managed]
        roles.reverse()
        channels.sort(key=lambda c: c["name"].lower())
        categories.sort(key=lambda c: c["name"].lower())

        return jsonify({
            "guild": {
                "id": gid,
                "name": guild.name,
                "icon": str(guild.icon.url) if guild.icon else None,
                "members": guild.member_count,
                "online": sum(1 for m in guild.members if str(m.status) != "offline"),
                "channels": len(guild.channels),
                "roles": len(guild.roles),
            },
            "channels": channels,
            "voice_channels": voice,
            "categories": categories,
            "roles": roles,
            "log_types": [{"key": t[0], "label": t[1], "emoji": t[2]} for t in LOGS_TYPES],
            "config": _guild_config_payload(guild),
        })

    # ─────────────────────────── ÉCRITURE ───────────────────────────
    body = request.get_json(silent=True) or {}
    saved = []

    # ---- Préfixe ----
    if "prefix" in body:
        p = _s(body.get("prefix"), maxlen=5).strip()
        if p:
            _prefix_cache[guild.id] = p
            _save_prefixes()
            saved.append("prefix")

    # ---- Tickets (ticket_select.json) ----
    if "tickets" in body:
        t = body["tickets"] or {}
        data = jload(FILES["ticket_select"])
        entry = data.setdefault(gid, {})

        if "panel" in t:
            p = t["panel"] or {}
            mode = _s(p.get("mode"), "select", 20)
            if mode not in ("select", "bouton", "container_v2"):
                mode = "select"
            entry["panel"] = {
                "titre": _s(p.get("titre"), "Support", 100),
                "description": _s(p.get("description"), "", 500),
                "image": _s(p.get("image"), "", 300) or None,
                "logs": _i(p.get("logs")),
                "couleur": _s(p.get("couleur"), "#5865F2", 10) or "#5865F2",
                "mode": mode,
            }

        if "choix" in t:
            choix = []
            for c in (t["choix"] or [])[:25]:
                nom = _s(c.get("nom"), "", 25).strip()
                if not nom:
                    continue
                btn = _s(c.get("btn_color"), "bleu", 10)
                if btn not in ("bleu", "vert", "rouge", "gris"):
                    btn = "bleu"
                choix.append({
                    "nom": nom,
                    "description": _s(c.get("description"), "", 97),
                    "emoji": _s(c.get("emoji"), "🎫", 5) or "🎫",
                    "categorie": _i(c.get("categorie")),
                    "roles": _int_list(c.get("roles")),
                    "titre": _s(c.get("titre"), f"Ticket — {nom}", 100),
                    "message": _s(c.get("message"), "Bienvenue {user} ! Explique ton problème.", 500),
                    "btn_color": btn,
                    "salon_name": _s(c.get("salon_name"), "ticket-{username}", 50) or "ticket-{username}",
                    "ia_enabled": _b(c.get("ia_enabled")),
                })
            entry["choix"] = choix

        jsave(FILES["ticket_select"], data)
        saved.append("tickets")

    # ---- Bienvenue (welcome.json) ----
    if "welcome" in body:
        w = body["welcome"] or {}
        data = jload(FILES["welcome"])
        emb = w.get("embed") or {}
        mode = _s(w.get("mode"), "texte", 10)
        data[gid] = {
            "enabled": _b(w.get("enabled"), True),
            "channel_id": _i(w.get("channel_id")),
            "mode": "embed" if mode == "embed" else "texte",
            "message": _s(w.get("message"), "", 2000),
            "auto_delete": max(0, _i(w.get("auto_delete"), 0) or 0),
            "mp_enabled": _b(w.get("mp_enabled")),
            "mp_message": _s(w.get("mp_message"), "", 2000),
            "embed": {
                "titre": _s(emb.get("titre"), "", 256),
                "desc": _s(emb.get("desc"), "", 2000),
                "color": _s(emb.get("color"), "#5865F2", 10) or "#5865F2",
                "thumb": _s(emb.get("thumb"), "", 300),
                "image": _s(emb.get("image"), "", 300),
            },
        }
        jsave(FILES["welcome"], data)
        saved.append("welcome")

    # ---- Départ (depart.json) ----
    if "depart" in body:
        d = body["depart"] or {}
        data = jload(FILES["depart"])
        data[gid] = {
            "channel_id": _i(d.get("channel_id")),
            "title": _s(d.get("title"), "", 256),
            "description": _s(d.get("description"), "", 2000),
        }
        jsave(FILES["depart"], data)
        saved.append("depart")

    # ---- Logs (logs_config.json) ----
    if "logs" in body:
        cfg = get_logs_cfg(guild.id)
        valid = {t[0] for t in LOGS_TYPES}
        for key, val in (body["logs"] or {}).items():
            if key not in valid:
                continue
            cfg[key] = {
                "enabled": _b((val or {}).get("enabled")),
                "channel": _i((val or {}).get("channel"), 0) or 0,
            }
        save_logs_cfg(guild.id, cfg)
        saved.append("logs")

    # ---- Anti-lien (antilink_config.json) ----
    if "antilink" in body:
        a = body["antilink"] or {}
        data = jload(FILES["antilink"])
        action = _s(a.get("action"), "delete", 20)
        data[gid] = {
            "enabled": _b(a.get("enabled")),
            "action": action,
            "whitelist": [_s(x, "", 120) for x in (a.get("whitelist") or [])][:100],
        }
        jsave(FILES["antilink"], data)
        saved.append("antilink")

    # ---- Anti-raid (server_configs/<gid>.json) ----
    if "antiraid" in body:
        a = body["antiraid"] or {}
        srv = get_server_config(gid)
        ar = srv.get("antiraid", {})
        ar["enabled"] = _b(a.get("enabled"))
        ar["modlog"] = _i(a.get("modlog"))
        for sub, fields in (
            ("join", ("join_action", "join_interval", "join_threshold")),
            ("spam", ("spam_action", "spam_interval", "spam_threshold")),
            ("mention", ("mention_action", "mention_limit")),
            ("caps", ("caps_percent", "caps_min_length")),
            ("emoji_spam", ("max_emojis",)),
        ):
            if sub in a:
                ar[sub] = _b((a.get(sub) or {}).get("enabled"))
            for f in fields:
                if f in a:
                    ar[f] = _s(a[f], "", 20) if f.endswith("action") else _i(a[f], 0)
        srv["antiraid"] = ar
        save_server_config(gid, srv)
        saved.append("antiraid")

    # ---- Captcha / vérification (captcha_config.json) ----
    if "captcha" in body:
        c = body["captcha"] or {}
        data = _load_captcha()
        data[gid] = {
            "enabled": _b(c.get("enabled")),
            "channel_id": _i(c.get("channel_id")),
            "verified_role": _i(c.get("verified_role")),
            "unverified_role": _i(c.get("unverified_role")),
            "code_length": min(10, max(4, _i(c.get("code_length"), 6) or 6)),
            "max_tries": min(10, max(1, _i(c.get("max_tries"), 3) or 3)),
            "kick_on_fail": _b(c.get("kick_on_fail")),
            "style": _s(c.get("style"), "code", 20),
            "welcome_message": _s(c.get("welcome_message"), "", 1000),
        }
        _save_captcha(data)
        saved.append("captcha")

    # ---- Niveaux (level_configs/<gid>.json — on préserve "members") ----
    if "levels" in body:
        l = body["levels"] or {}
        cfg = get_level_config(gid)
        cfg["xp_channel"] = _i(l.get("xp_channel"))
        cfg["notif_channel"] = _i(l.get("notif_channel"))
        cfg["xp_min"] = max(0, _i(l.get("xp_min"), 5) or 0)
        cfg["xp_max"] = max(cfg["xp_min"], _i(l.get("xp_max"), 15) or 0)
        cfg.setdefault("members", {})
        save_level_config(gid, cfg)
        saved.append("levels")

    # ---- Giveaway (giveaway_config.json) ----
    if "giveaway" in body:
        g = body["giveaway"] or {}
        data = jload(FILES["giveaway_cfg"])
        cur = data.get(gid, {})
        cur.update({
            "salon_id": _i(g.get("salon_id")),
            "emoji": _s(g.get("emoji"), "🎉", 8) or "🎉",
            "btn_text": _s(g.get("btn_text"), "Participer", 40),
            "btn_color": _s(g.get("btn_color"), "bleu", 10),
            "duree": _s(g.get("duree"), "", 20),
            "gagnants": max(1, _i(g.get("gagnants"), 1) or 1),
            "required_roles": _int_list(g.get("required_roles")),
            "blacklist_roles": _int_list(g.get("blacklist_roles")),
            "vocal_required": _b(g.get("vocal_required")),
        })
        data[gid] = cur
        jsave(FILES["giveaway_cfg"], data)
        saved.append("giveaway")

    # ---- Anti-bot (antibot_config.json — on préserve "offenders") ----
    if "antibot" in body:
        a = body["antibot"] or {}
        data = jload(FILES["antibot"])
        cur = data.get(gid, {})
        cur["enabled"] = _b(a.get("enabled"))
        cur["channel_id"] = _i(a.get("channel_id"))
        data[gid] = cur
        jsave(FILES["antibot"], data)
        saved.append("antibot")

    # ---- Starboard / ShowPic / Rôles par défaut (mémoire vive) ----
    if "starboard" in body:
        s = body["starboard"] or {}
        ch = _i(s.get("channel_id"))
        if ch:
            _starboard_cfg[gid] = {
                "channel_id": ch,
                "seuil": max(1, _i(s.get("seuil"), 3) or 3),
                "emoji": _s(s.get("emoji"), "⭐", 8) or "⭐",
            }
        else:
            _starboard_cfg.pop(gid, None)
        saved.append("starboard")

    if "showpic" in body:
        s = body["showpic"] or {}
        _showpic_cfg[gid] = {"enabled": _b(s.get("enabled")), "channel_id": _i(s.get("channel_id"))}
        saved.append("showpic")

    if "defaultroles" in body:
        _defaultroles[gid] = _int_list(body.get("defaultroles"))[:10]
        saved.append("defaultroles")

    return jsonify({"ok": True, "saved": saved})


@app.route("/api/guild/<guild_id>/stats")
def api_guild_stats(guild_id):
    """Statistiques affichées sur la page Vue d'ensemble du dashboard."""
    guild, member = require_guild_admin(guild_id)
    if not guild:
        return jsonify({"error": "forbidden"}), 403

    lvl = get_level_config(str(guild.id))
    top = sorted(
        ((uid, d) for uid, d in (lvl.get("members") or {}).items()),
        key=lambda kv: (kv[1].get("level", 0), kv[1].get("xp", 0)),
        reverse=True,
    )[:5]

    recent = []
    for uid, d in top:
        m = guild.get_member(_i(uid, 0) or 0)
        recent.append({
            "title": (m.display_name if m else f"Membre {uid}"),
            "detail": f"Niveau {d.get('level', 0)} · {d.get('xp', 0)} XP",
        })

    return jsonify({
        "members": guild.member_count,
        "online": sum(1 for m in guild.members if str(m.status) != "offline"),
        "infractions": len((jload(FILES["antibot"]).get(str(guild.id), {}) or {}).get("offenders", [])),
        "recent": recent,
    })
