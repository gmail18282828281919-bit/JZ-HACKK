"""API HTTP JZ-AI, compatible avec le format OpenAI /v1/chat/completions."""
from __future__ import annotations

import json
import time
import uuid
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config, db, files
from . import messages as msg
from .auth import require_admin, require_key
from .engine import get_engine
from .files import FileError

app = FastAPI(title="JZ-AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------- schemas -----------------------------
class ChatRequest(BaseModel):
    model: Optional[str] = None
    # `content` accepte une chaine ou une liste de blocs (texte/fichier/image),
    # d'ou le typage libre : la validation se fait dans messages.normalize().
    messages: List[dict]
    temperature: float = 0.7
    max_tokens: int = Field(default=config.MAX_NEW_TOKENS, ge=1, le=8192)
    stream: bool = False


class KeyRequest(BaseModel):
    label: str = "apk"


class FileRequest(BaseModel):
    filename: str
    content_base64: str
    mime: str = ""


# ----------------------------- helpers -----------------------------
def _sse(completion_id: str, created: int, delta: dict, finish: Optional[str] = None) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": config.MODEL_NAME,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ----------------------------- routes ------------------------------
@app.get("/health")
def health():
    engine = get_engine()
    return {
        "status": "ok",
        "model": config.MODEL_NAME,
        "backend": engine.name,
        "profile": config.PROFILE,
        "vision": engine.vision,
        "files": True,
        "active_keys": db.count_active(),
        "token_limit": "unlimited",
    }


@app.get("/v1/models")
def models(_key=Depends(require_key)):
    return {
        "object": "list",
        "data": [
            {
                "id": config.MODEL_NAME,
                "object": "model",
                "created": 0,
                "owned_by": "jz",
            }
        ],
    }


@app.post("/v1/files")
def upload_file(req: FileRequest, _key=Depends(require_key)):
    try:
        raw = files.decode_base64(req.content_base64)
        stored = files.put(files.extract(req.filename, raw, req.mime))
    except FileError as exc:
        raise HTTPException(400, str(exc))
    return files.describe(stored)


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest, _key=Depends(require_key)):
    engine = get_engine()
    try:
        chat = msg.normalize(req.messages)
    except FileError as exc:
        raise HTTPException(400, str(exc))

    messages = chat.multimodal if engine.vision else chat.plain
    system = config.SYSTEM_PROMPT
    if not engine.vision:
        system += msg.note_missing_vision(chat)
    if not any(m.get("role") == "system" for m in messages):
        messages = [{"role": "system", "content": system}] + messages

    completion_id = "chatcmpl-" + uuid.uuid4().hex[:24]
    created = int(time.time())

    if req.stream:
        def event_stream():
            yield _sse(completion_id, created, {"role": "assistant", "content": ""})
            try:
                for piece in engine.generate(messages, req.max_tokens, req.temperature):
                    yield _sse(completion_id, created, {"content": piece})
            except Exception as exc:  # noqa: BLE001 - remonte l'erreur dans le flux
                yield _sse(completion_id, created, {"content": f"\n[erreur: {exc}]"})
            yield _sse(completion_id, created, {}, finish="stop")
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    text = "".join(engine.generate(messages, req.max_tokens, req.temperature)).strip()
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": config.MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        # Compteurs informatifs uniquement : rien n'est facture ni plafonne.
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


# --- endpoints admin (proteges par JZAI_ADMIN_TOKEN) ---
@app.post("/admin/keys")
def create_key(req: KeyRequest, _admin=Depends(require_admin)):
    raw = db.generate_key(req.label)
    return {"api_key": raw, "label": req.label, "note": "Copie-la maintenant, elle ne sera plus affichee."}


@app.get("/admin/keys")
def get_keys(_admin=Depends(require_admin)):
    return {"keys": [dict(r) for r in db.list_keys()]}


@app.delete("/admin/keys/{key_id}")
def delete_key(key_id: int, _admin=Depends(require_admin)):
    if not db.revoke_key(key_id):
        raise HTTPException(404, "Cle introuvable.")
    return {"revoked": key_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
