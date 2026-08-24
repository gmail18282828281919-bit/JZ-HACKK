"""Entree WSGI pour gunicorn quand le site tourne dans son propre processus.

  gunicorn -w 2 -b 127.0.0.1:5000 wsgi:app

A n'utiliser que si tu separes le bot et le site en deux services (recommande
en production : voir deploy/). Le bot se lance alors avec `python main.py --bot-only`.
"""
from core import database as db

db.setup()

from web.app import app  # noqa: E402

__all__ = ["app"]
