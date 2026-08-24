"""Serveur JZ-AI sans aucune dependance (bibliotheque standard uniquement).

Memes routes que main.py (FastAPI), mais utilisable sur Termux / Android ou
partout ou installer pydantic + uvicorn est trop lourd.

    python3 -m ai.server.lite
"""
from __future__ import annotations

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from . import config, db, files, messages
from .engine import get_engine
from .files import FileError

MAX_BODY = 24 << 20  # 24 Mio (assez pour un fichier joint en base64)


def _extract_key(headers) -> str:
    auth = headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (headers.get("X-API-Key") or "").strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "JZ-AI/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------- utilitaires -------------------------
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str) -> None:
        self._send_json(code, {"error": {"message": message, "code": code}})

    def _read_body(self) -> Optional[dict]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            self._error(413, "Corps de requete trop volumineux.")
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._error(400, "JSON invalide.")
            return None

    def _auth(self):
        """Renvoie la ligne de la cle, ou None (reponse d'erreur deja envoyee)."""
        raw = _extract_key(self.headers)
        if not raw:
            self._error(401, "Cle d'API manquante (header Authorization: Bearer <cle>).")
            return None
        row = db.verify_key(raw)
        if row is None:
            self._error(401, "Cle d'API invalide ou revoquee.")
            return None
        db.touch_key(row["id"])
        return row

    def _auth_admin(self) -> bool:
        expected = db.admin_token()
        if not expected:
            self._error(503, "JZAI_ADMIN_TOKEN n'est pas defini : endpoints admin desactives.")
            return False
        if self.headers.get("X-Admin-Token", "") != expected:
            self._error(403, "Token admin invalide.")
            return False
        return True

    def log_message(self, fmt, *args):  # journal compact
        print(f"[JZ-AI] {self.address_string()} {fmt % args}")

    # --------------------------- routes ----------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key, X-Admin-Token")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/health":
            engine = get_engine()
            self._send_json(200, {
                "status": "ok",
                "model": config.MODEL_NAME,
                "backend": engine.name,
                "profile": config.PROFILE,
                "vision": engine.vision,
                "files": True,
                "active_keys": db.count_active(),
                "token_limit": "unlimited",
                "server": "lite",
            })
        elif path == "/v1/models":
            if self._auth() is None:
                return
            self._send_json(200, {
                "object": "list",
                "data": [{"id": config.MODEL_NAME, "object": "model", "created": 0, "owned_by": "jz"}],
            })
        elif path == "/admin/keys":
            if not self._auth_admin():
                return
            self._send_json(200, {"keys": [dict(r) for r in db.list_keys()]})
        else:
            self._error(404, f"Route inconnue : {path}")

    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if path == "/v1/chat/completions":
            if self._auth() is None:
                return
            body = self._read_body()
            if body is None:
                return
            self._chat(body)
        elif path == "/v1/files":
            if self._auth() is None:
                return
            body = self._read_body()
            if body is None:
                return
            self._upload(body)
        elif path == "/admin/keys":
            if not self._auth_admin():
                return
            body = self._read_body()
            if body is None:
                return
            label = str(body.get("label") or "default")
            self._send_json(200, {
                "api_key": db.generate_key(label),
                "label": label,
                "note": "Copie-la maintenant, elle ne sera plus affichee.",
            })
        else:
            self._error(404, f"Route inconnue : {path}")

    def do_DELETE(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/admin/keys/"):
            if not self._auth_admin():
                return
            try:
                key_id = int(path.rsplit("/", 1)[1])
            except ValueError:
                self._error(400, "Identifiant de cle invalide.")
                return
            if db.revoke_key(key_id):
                self._send_json(200, {"revoked": key_id})
            else:
                self._error(404, "Cle introuvable.")
        else:
            self._error(404, f"Route inconnue : {path}")

    # -------------------------- fichiers ---------------------------
    def _upload(self, body: dict) -> None:
        filename = str(body.get("filename") or "").strip()
        payload = body.get("content_base64") or body.get("data")
        if not filename:
            self._error(400, "Champ 'filename' manquant.")
            return
        if not payload:
            self._error(400, "Champ 'content_base64' manquant.")
            return
        try:
            raw = files.decode_base64(str(payload))
            stored = files.put(files.extract(filename, raw, str(body.get("mime") or "")))
        except FileError as exc:
            self._error(400, str(exc))
            return
        self._send_json(200, files.describe(stored))

    # --------------------------- chat ------------------------------
    def _chat(self, body: dict) -> None:
        try:
            chat = messages.normalize(body.get("messages"))
        except FileError as exc:
            self._error(400, str(exc))
            return

        engine_ = get_engine()
        clean = chat.multimodal if engine_.vision else chat.plain
        system = config.SYSTEM_PROMPT
        if not engine_.vision:
            system += messages.note_missing_vision(chat)
        if not any(m.get("role") == "system" for m in clean):
            clean = [{"role": "system", "content": system}] + clean

        try:
            max_tokens = max(1, min(int(body.get("max_tokens") or config.MAX_NEW_TOKENS), 8192))
            temperature = float(body.get("temperature", 0.7))
        except (TypeError, ValueError):
            self._error(400, "'max_tokens' ou 'temperature' invalide.")
            return

        engine = engine_
        completion_id = "chatcmpl-" + uuid.uuid4().hex[:24]
        created = int(time.time())

        if body.get("stream"):
            self._chat_stream(engine, clean, max_tokens, temperature, completion_id, created)
            return

        try:
            text = "".join(engine.generate(clean, max_tokens, temperature)).strip()
        except Exception as exc:  # noqa: BLE001
            self._error(500, f"Erreur de generation : {exc}")
            return

        self._send_json(200, {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": config.MODEL_NAME,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    def _chat_stream(self, engine, chat_messages, max_tokens, temperature, completion_id, created) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def chunk(delta: dict, finish=None) -> None:
            payload = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": config.MODEL_NAME,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            raw = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(b"%x\r\n%s\r\n" % (len(raw), raw))
            self.wfile.flush()

        try:
            chunk({"role": "assistant", "content": ""})
            try:
                for piece in engine.generate(chat_messages, max_tokens, temperature):
                    chunk({"content": piece})
            except Exception as exc:  # noqa: BLE001
                chunk({"content": f"\n[erreur: {exc}]"})
            chunk({}, finish="stop")
            done = b"data: [DONE]\n\n"
            self.wfile.write(b"%x\r\n%s\r\n" % (len(done), done))
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # le client a ferme la connexion


def main() -> None:
    get_engine()  # charge le modele avant d'accepter du trafic
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    server.daemon_threads = True
    print(f"[JZ-AI] serveur lite sur http://{config.HOST}:{config.PORT}  (modele: {config.MODEL_NAME})")
    print(f"[JZ-AI] cles actives : {db.count_active()}   Ctrl+C pour arreter")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[JZ-AI] arret.")
        server.shutdown()


if __name__ == "__main__":
    main()
