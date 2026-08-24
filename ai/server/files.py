"""Extraction de texte a partir de fichiers envoyes par le client.

Tout est fait avec la bibliotheque standard, sauf le PDF qui utilise pypdf
s'il est installe. Les fichiers sont gardes en memoire (pas sur disque) et
le magasin est borne pour eviter de saturer la RAM d'un telephone.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import re
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional

MAX_FILE_BYTES = 8 * 1024 * 1024      # 8 Mio par fichier
MAX_TEXT_CHARS = 200_000              # tronque au-dela
MAX_STORED_FILES = 32                 # magasin circulaire

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}

TEXT_EXTENSIONS = {
    "txt", "md", "markdown", "rst", "log", "csv", "tsv", "json", "jsonl",
    "yaml", "yml", "toml", "ini", "cfg", "conf", "env", "sql", "xml", "svg",
    "py", "js", "mjs", "ts", "tsx", "jsx", "kt", "kts", "java", "c", "h",
    "cpp", "hpp", "cc", "cs", "go", "rs", "rb", "php", "swift", "lua", "sh",
    "bash", "zsh", "bat", "ps1", "gradle", "properties", "dart", "r", "m",
    "pl", "vim", "dockerfile", "makefile", "gitignore", "diff", "patch",
}


class FileError(Exception):
    """Fichier illisible ou format non supporte (message destine a l'utilisateur)."""


@dataclass
class StoredFile:
    id: str
    filename: str
    mime: str
    size: int
    kind: str                          # "text" | "image"
    text: str = ""
    data_url: str = ""                 # pour les images, utilisable par un modele vision
    created_at: float = field(default_factory=time.time)


# --------------------------- utilitaires ---------------------------
def _extension(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].lower()
    if "." not in name:
        return name  # ex: "Makefile", "Dockerfile"
    return name.rsplit(".", 1)[1]


def _decode_text(data: bytes) -> Optional[str]:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def _from_html(data: bytes) -> str:
    text = _decode_text(data) or ""
    parser = _Stripper()
    parser.feed(text)
    return "\n".join(parser.parts)


def _from_zip_xml(data: bytes, members: tuple[str, ...]) -> str:
    """Texte d'un .docx / .odt / .pptx : ce sont des zip contenant du XML."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            targets = [n for n in names if any(n.startswith(m) or n == m for m in members)]
            if not targets:
                raise FileError("Document vide ou format inattendu.")
            chunks = []
            for name in sorted(targets):
                xml = archive.read(name).decode("utf-8", errors="replace")
                xml = re.sub(r"</(w:p|text:p|a:p)>", "\n", xml)
                chunks.append(re.sub(r"<[^>]+>", "", xml))
    except zipfile.BadZipFile:
        raise FileError("Fichier corrompu ou ce n'est pas un document Office.")
    text = "\n".join(chunks)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _from_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise FileError(
            "Lecture PDF indisponible : installe pypdf (pip install pypdf), "
            "ou convertis le PDF en texte avant de l'envoyer."
        )
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 - pypdf leve des erreurs variees
        raise FileError(f"PDF illisible : {exc}")
    text = "\n\n".join(p for p in pages if p)
    if not text.strip():
        raise FileError(
            "Ce PDF ne contient pas de texte (c'est probablement un scan). "
            "Il faudrait de l'OCR, que ce serveur ne fait pas."
        )
    return text


def _from_zip_listing(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            lines = [
                f"{info.filename}  ({info.file_size} octets)"
                for info in archive.infolist()
                if not info.is_dir()
            ]
    except zipfile.BadZipFile:
        raise FileError("Archive zip corrompue.")
    return "Contenu de l'archive :\n" + "\n".join(lines)


# --------------------------- extraction ----------------------------
def extract(filename: str, data: bytes, mime: str = "") -> StoredFile:
    """Transforme un fichier brut en texte exploitable par le modele."""
    if not data:
        raise FileError("Fichier vide.")
    if len(data) > MAX_FILE_BYTES:
        raise FileError(
            f"Fichier trop volumineux ({len(data) // 1024} Kio). "
            f"Maximum : {MAX_FILE_BYTES // 1024 // 1024} Mio."
        )

    ext = _extension(filename)
    file_id = "file-" + uuid.uuid4().hex[:16]

    if ext in IMAGE_EXTENSIONS or mime.startswith("image/"):
        guessed = mime or f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
        return StoredFile(
            id=file_id,
            filename=filename,
            mime=guessed,
            size=len(data),
            kind="image",
            data_url=f"data:{guessed};base64,{base64.b64encode(data).decode('ascii')}",
        )

    if ext == "pdf":
        text = _from_pdf(data)
    elif ext in ("docx", "dotx"):
        text = _from_zip_xml(data, ("word/document.xml",))
    elif ext == "odt":
        text = _from_zip_xml(data, ("content.xml",))
    elif ext in ("pptx", "potx"):
        text = _from_zip_xml(data, ("ppt/slides/slide",))
    elif ext in ("html", "htm"):
        text = _from_html(data)
    elif ext == "zip":
        text = _from_zip_listing(data)
    elif ext == "json":
        raw = _decode_text(data)
        if raw is None:
            raise FileError("JSON illisible (encodage inconnu).")
        try:
            text = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        except ValueError:
            text = raw  # JSON invalide : on passe le brut, le modele s'en sortira
    elif ext in TEXT_EXTENSIONS:
        text = _decode_text(data) or ""
        if not text:
            raise FileError("Fichier texte illisible (encodage inconnu).")
    else:
        decoded = _decode_text(data)
        if decoded is None or "\x00" in decoded[:1024]:
            raise FileError(
                f"Format '.{ext}' non supporte. Formats lisibles : texte et code, "
                "PDF, DOCX, ODT, PPTX, HTML, JSON, CSV, ZIP, images."
            )
        text = decoded

    truncated = False
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
        truncated = True
    if truncated:
        text += f"\n\n[... fichier tronque a {MAX_TEXT_CHARS} caracteres ...]"

    return StoredFile(
        id=file_id,
        filename=filename,
        mime=mime or "text/plain",
        size=len(data),
        kind="text",
        text=text,
    )


def decode_base64(payload: str) -> bytes:
    """Accepte du base64 nu ou une data: URL."""
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise FileError("Contenu base64 invalide.")


# ---------------------------- magasin ------------------------------
_store: dict[str, StoredFile] = {}


def put(stored: StoredFile) -> StoredFile:
    _store[stored.id] = stored
    while len(_store) > MAX_STORED_FILES:
        oldest = min(_store.values(), key=lambda f: f.created_at)
        _store.pop(oldest.id, None)
    return stored


def get(file_id: str) -> Optional[StoredFile]:
    return _store.get(file_id)


def describe(stored: StoredFile) -> dict:
    return {
        "id": stored.id,
        "filename": stored.filename,
        "kind": stored.kind,
        "size": stored.size,
        "chars": len(stored.text),
        "preview": stored.text[:300] if stored.kind == "text" else "",
    }
