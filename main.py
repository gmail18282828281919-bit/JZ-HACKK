"""Point d'entree unique : le bot Discord et le dashboard dans le meme processus.

  - discord.py est asynchrone  -> il occupe la boucle asyncio du thread principal
  - Flask est synchrone        -> il tourne dans un thread demon separe
  - les deux communiquent uniquement par la base SQLite partagee (core/database)

Lancement :  python main.py
Options   :  python main.py --bot-only | --web-only
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading

from core import config, database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)-16s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("modera")


def start_web_thread() -> threading.Thread:
    """Demarre Flask dans un thread demon (serveur de dev, derriere nginx en prod)."""
    from web.app import run_web

    thread = threading.Thread(target=run_web, name="flask", daemon=True)
    thread.start()
    log.info("dashboard sur http://%s:%s", config.WEB_HOST, config.WEB_PORT)
    return thread


async def start_bot() -> None:
    from bot.client import ModeraBot

    bot = ModeraBot()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.close()))
        except NotImplementedError:      # Windows
            pass

    async with bot:
        await bot.start(config.TOKEN)


def main() -> int:
    args = set(sys.argv[1:])
    db.setup()
    log.info("base de donnees : %s", config.DATABASE_PATH)

    missing = config.missing_config()
    if missing and "--web-only" not in args:
        log.error("variables manquantes dans .env : %s", ", ".join(missing))
        return 1

    if "--bot-only" not in args:
        start_web_thread()

    if "--web-only" in args:
        log.info("mode web seul, Ctrl+C pour quitter")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        return 0

    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        log.info("arret demande")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
