"""Authentification par cle d'API + limitation de debit optionnelle."""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Header, HTTPException, status

from . import config, db

_hits: Dict[int, Deque[float]] = defaultdict(deque)


def _check_rate(key_id: int) -> None:
    limit = config.RATE_LIMIT_PER_MIN
    if limit <= 0:  # 0 = aucune limite
        return
    now = time.time()
    window = _hits[key_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite de {limit} requetes/minute atteinte pour cette cle.",
        )
    window.append(now)


def require_key(authorization: str = Header(default=""), x_api_key: str = Header(default="")):
    """Accepte 'Authorization: Bearer jz-...' ou 'X-API-Key: jz-...'."""
    raw = ""
    if authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
    elif x_api_key:
        raw = x_api_key.strip()

    if not raw:
        raise HTTPException(401, "Cle d'API manquante (header Authorization: Bearer <cle>).")

    row = db.verify_key(raw)
    if row is None:
        raise HTTPException(401, "Cle d'API invalide ou revoquee.")

    _check_rate(row["id"])
    db.touch_key(row["id"])
    return row


def require_admin(x_admin_token: str = Header(default="")):
    expected = db.admin_token()
    if not expected:
        raise HTTPException(503, "JZAI_ADMIN_TOKEN n'est pas defini : endpoints admin desactives.")
    if x_admin_token != expected:
        raise HTTPException(403, "Token admin invalide.")
    return True
