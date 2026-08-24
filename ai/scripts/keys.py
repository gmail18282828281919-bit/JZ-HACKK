#!/usr/bin/env python3
"""Gestion des cles d'API en ligne de commande.

  python3 -m ai.scripts.keys new "mon apk"
  python3 -m ai.scripts.keys list
  python3 -m ai.scripts.keys revoke 3
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.server import db  # noqa: E402


def _fmt(ts):
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    cmd = argv[0]
    if cmd == "new":
        label = argv[1] if len(argv) > 1 else "default"
        raw = db.generate_key(label)
        print(f"Cle creee ({label}) :\n\n    {raw}\n")
        print("Garde-la : seul son hash est stocke, elle ne sera plus affichee.")
    elif cmd == "list":
        rows = db.list_keys()
        if not rows:
            print("Aucune cle. Cree-en une avec : keys.py new \"mon apk\"")
            return 0
        print(f"{'id':>3}  {'label':<16} {'cle':<10} {'creee':<17} {'derniere':<17} {'appels':>6}  etat")
        for r in rows:
            state = "revoquee" if r["revoked"] else "active"
            print(
                f"{r['id']:>3}  {r['label']:<16} ...{r['key_hint']:<7} "
                f"{_fmt(r['created_at']):<17} {_fmt(r['last_used']):<17} {r['calls']:>6}  {state}"
            )
    elif cmd == "revoke":
        if len(argv) < 2:
            print("Usage: keys.py revoke <id>")
            return 1
        ok = db.revoke_key(int(argv[1]))
        print("Cle revoquee." if ok else "Cle introuvable.")
        return 0 if ok else 1
    else:
        print(f"Commande inconnue : {cmd}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
