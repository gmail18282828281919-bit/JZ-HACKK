"""Normalisation des messages entrants.

Accepte le format simple ({"role","content": "texte"}) et le format enrichi
compatible OpenAI, ou `content` est une liste de blocs :

    {"type": "text",      "text": "resume ce fichier"}
    {"type": "file",      "file_id": "file-abc"}                  # deja televerse
    {"type": "file",      "filename": "a.py", "content_base64": "..."}
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}

Produit deux vues des memes messages :
  - `plain`      : tout aplati en texte (pour les modeles sans vision)
  - `multimodal` : blocs conserves (pour un modele vision llama.cpp)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import files
from .files import FileError

MAX_FILES_PER_REQUEST = 8


@dataclass
class NormalizedChat:
    plain: list[dict] = field(default_factory=list)
    multimodal: list[dict] = field(default_factory=list)
    has_images: bool = False
    attachments: list[str] = field(default_factory=list)  # noms de fichiers joints


def _fence(stored: files.StoredFile) -> str:
    """Encadre le contenu d'un fichier pour que le modele voie ou il commence."""
    ext = stored.filename.rsplit(".", 1)[-1].lower() if "." in stored.filename else ""
    lang = ext if ext and len(ext) <= 12 else ""
    return (
        f"\n\n--- Fichier joint : {stored.filename} "
        f"({stored.size} octets) ---\n"
        f"```{lang}\n{stored.text}\n```\n"
        f"--- fin de {stored.filename} ---\n"
    )


def _resolve_file(block: dict) -> files.StoredFile:
    """Recupere un fichier deja televerse, ou en cree un depuis du base64."""
    file_id = block.get("file_id")
    if file_id:
        stored = files.get(str(file_id))
        if stored is None:
            raise FileError(
                f"Fichier '{file_id}' inconnu ou expire. Reenvoie-le via POST /v1/files."
            )
        return stored

    payload = block.get("content_base64") or block.get("data")
    if not payload:
        raise FileError("Bloc 'file' sans 'file_id' ni 'content_base64'.")
    filename = str(block.get("filename") or "fichier.txt")
    stored = files.extract(filename, files.decode_base64(str(payload)), str(block.get("mime") or ""))
    return files.put(stored)


def _image_url(block: dict) -> str:
    raw = block.get("image_url")
    if isinstance(raw, dict):
        url = raw.get("url", "")
    else:
        url = raw or ""
    url = str(url)
    if not url:
        raise FileError("Bloc 'image_url' sans URL.")
    if not url.startswith("data:"):
        raise FileError(
            "Seules les images en data: URL (base64) sont acceptees — "
            "le serveur ne va pas chercher d'URL distante."
        )
    return url


def normalize(raw_messages: Any) -> NormalizedChat:
    """Valide et convertit les messages. Leve FileError si une piece est illisible."""
    if not isinstance(raw_messages, list) or not raw_messages:
        raise FileError("Le champ 'messages' est vide ou invalide.")

    chat = NormalizedChat()
    file_count = 0

    for message in raw_messages:
        if not isinstance(message, dict):
            raise FileError("Chaque message doit etre un objet {role, content}.")
        role = str(message.get("role", "user"))
        content = message.get("content", "")

        if isinstance(content, str):
            chat.plain.append({"role": role, "content": content})
            chat.multimodal.append({"role": role, "content": content})
            continue

        if not isinstance(content, list):
            raise FileError("'content' doit etre une chaine ou une liste de blocs.")

        text_parts: list[str] = []
        blocks: list[dict] = []

        for block in content:
            if not isinstance(block, dict):
                raise FileError("Chaque bloc de 'content' doit etre un objet.")
            btype = str(block.get("type", "text"))

            if btype == "text":
                piece = str(block.get("text", ""))
                text_parts.append(piece)
                blocks.append({"type": "text", "text": piece})

            elif btype == "file":
                file_count += 1
                if file_count > MAX_FILES_PER_REQUEST:
                    raise FileError(f"Trop de fichiers joints (max {MAX_FILES_PER_REQUEST}).")
                stored = _resolve_file(block)
                chat.attachments.append(stored.filename)
                if stored.kind == "image":
                    chat.has_images = True
                    blocks.append({"type": "image_url", "image_url": {"url": stored.data_url}})
                    text_parts.append(f"[image jointe : {stored.filename}]")
                else:
                    fenced = _fence(stored)
                    text_parts.append(fenced)
                    blocks.append({"type": "text", "text": fenced})

            elif btype == "image_url":
                chat.has_images = True
                url = _image_url(block)
                blocks.append({"type": "image_url", "image_url": {"url": url}})
                text_parts.append("[image jointe]")

            else:
                raise FileError(f"Type de bloc inconnu : '{btype}'.")

        chat.plain.append({"role": role, "content": "\n".join(p for p in text_parts if p)})
        chat.multimodal.append({"role": role, "content": blocks})

    return chat


def note_missing_vision(chat: NormalizedChat) -> str:
    """Message a ajouter quand des images arrivent sur un modele sans vision."""
    if not chat.has_images:
        return ""
    return (
        "\n\n[Note systeme : une ou plusieurs images ont ete jointes, mais le modele "
        "charge ne sait pas lire les images. Dis-le clairement a l'utilisateur au lieu "
        "d'inventer leur contenu. Pour activer la vision, il faut lancer le serveur avec "
        "JZAI_MMPROJ_PATH pointant sur le projecteur d'un modele vision.]"
    )
