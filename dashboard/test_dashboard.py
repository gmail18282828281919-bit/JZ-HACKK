import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask
from dashboard import register_dashboard
import dashboard.server as ds

class G:
    def __init__(s, i, n): s.id=i; s.name=n; s.member_count=120
class Av:  url="https://cdn.discordapp.com/embed/avatars/0.png"
class U:
    display_avatar=Av()
    def __str__(s): return "ModeraBot#0001"
class Bot:
    user=U(); guilds=[G(111,"Serveur A"), G(222,"Serveur B")]
    latency=0.042
    def is_ready(s): return True

# on simule Discord: pas d'appel reseau
ds._verify_token = lambda t: (
    ({"id":"42","username":"jz","global_name":"JZ","avatar":None,"discriminator":"0"},
     [{"id":"111","name":"Serveur A","icon":None,"owner":True,"permissions":"8"},
      {"id":"222","name":"Serveur B","icon":None,"permissions":"32"},
      {"id":"333","name":"Sans perms","icon":None,"permissions":"1024"}])
    if t == "goodtoken" else (None, [])
)

app = Flask(__name__)
register_dashboard(app, Bot(), client_id="123456", port=30121,
                   allowed_origins="https://dashboard.moderabot.xyz")
c = app.test_client()
fail = 0
def check(label, cond, extra=""):
    global fail
    print(("  ✅ " if cond else "  ❌ ")+label+("" if cond else "  <- "+str(extra)))
    if not cond: fail += 1

print("\n[pages]")
for p in ["/", "/index.html", "/servers.html", "/dash.html", "/dashboard", "/servers"]:
    r = c.get(p)
    check(f"GET {p} -> 200 html", r.status_code==200 and b"<!DOCTYPE html>" in r.data, r.status_code)

print("\n[/api/config]")
r = c.get("/api/config"); j = r.get_json()
check("200", r.status_code==200, r.status_code)
check("client_id expose", j["client_id"]=="123456", j)
check("redirect_uri = origine + /servers.html", j["redirect_uri"].endswith("/servers.html"), j)
check("aucun secret dans la reponse", "secret" not in json.dumps(j).lower(), j)
check("etat du bot", j["bot_ready"] is True and j["guild_count"]==2, j)

print("\n[/api/status]")
r = c.get("/api/status"); j = r.get_json()
check("200 sans authentification", r.status_code==200, r.status_code)
check("bot_ready", j["bot_ready"] is True, j)
check("latence gateway en ms", j["ws_latency_ms"]==42, j)
check("nb de serveurs", j["guild_count"]==2, j)
check("nb de membres", j["member_count"]==240, j)
check("uptime present", isinstance(j["uptime_seconds"], int), j)
check("aucun secret", "secret" not in json.dumps(j).lower(), j)

print("\n[/api/me]")
check("sans token -> 401", c.get("/api/me").status_code==401)
check("mauvais token -> 401", c.get("/api/me", headers={"Authorization":"Bearer nope"}).status_code==401)
r = c.get("/api/me", headers={"Authorization":"Bearer goodtoken"}); j = r.get_json()
check("bon token -> 200", r.status_code==200, r.status_code)
ids = [g["id"] for g in j["guilds"]]
check("serveurs sans perms filtres", "333" not in ids, ids)
check("owner + manage_guild gardes", ids==["111","222"], ids)
check("bot_present correct", all(g["bot_present"] for g in j["guilds"]), j["guilds"])

print("\n[CORS]")
r = c.get("/api/config", headers={"Origin":"https://dashboard.moderabot.xyz"})
check("origine autorisee reflechie",
      r.headers.get("Access-Control-Allow-Origin")=="https://dashboard.moderabot.xyz", dict(r.headers))
r = c.get("/api/config", headers={"Origin":"https://evil.example"})
check("origine inconnue refusee", r.headers.get("Access-Control-Allow-Origin") is None, dict(r.headers))
check("pas de allow-credentials", r.headers.get("Access-Control-Allow-Credentials") is None)
r = c.options("/api/config", headers={"Origin":"https://dashboard.moderabot.xyz",
                                      "Access-Control-Request-Method":"GET"})
check("preflight OPTIONS ok", r.status_code < 400 and
      r.headers.get("Access-Control-Allow-Origin")=="https://dashboard.moderabot.xyz", r.status_code)

print("\n[/api/status — bot deconnecte]")
class BotDown:
    user=None; guilds=[]; latency=float("nan")
    def is_ready(s): return False
app2 = Flask(__name__ + "2")
register_dashboard(app2, BotDown(), client_id="123456", port=30121)
j2 = app2.test_client().get("/api/status").get_json()
check("API repond quand meme", j2["api"] is True, j2)
check("bot_ready = false", j2["bot_ready"] is False, j2)
check("latence NaN -> null", j2["ws_latency_ms"] is None, j2)

print("\n[divers]")
check("favicon -> 204", c.get("/favicon.ico").status_code==204)
check("page inconnue -> 404", c.get("/../etc/passwd").status_code in (301,308,404))
print("\n"+("TOUT PASSE ✅" if not fail else f"{fail} ECHEC(S) ❌"))
sys.exit(1 if fail else 0)
