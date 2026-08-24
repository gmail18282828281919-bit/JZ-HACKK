"""Configuration du serveur JZ-AI (tout se regle par variables d'environnement)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("JZAI_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("JZAI_DB", DATA_DIR / "jzai.db"))

# Nom public du modele (celui que l'apk demandera)
MODEL_NAME = os.getenv("JZAI_MODEL_NAME", "jz-mini-1")

# Backend d'inference : "llama" (GGUF via llama-cpp-python),
# "transformers" (HuggingFace) ou "echo" (aucune dependance, pour tester).
BACKEND = os.getenv("JZAI_BACKEND", "auto").lower()

# Chemin d'un fichier .gguf pour le backend llama.cpp
GGUF_PATH = os.getenv("JZAI_GGUF_PATH", "")

# Projecteur multimodal (mmproj-*.gguf) : active la lecture d'images.
# Doit correspondre au meme modele vision que GGUF_PATH.
MMPROJ_PATH = os.getenv("JZAI_MMPROJ_PATH", "")

# Format de prompt du modele vision : llava-1.5, llava-1.6, nanollava,
# moondream, llama-3-vision, minicpm-v-2.6
VISION_HANDLER = os.getenv("JZAI_VISION_HANDLER", "llava-1.5").lower()

# Modele HuggingFace pour le backend transformers (petit = rapide)
HF_MODEL = os.getenv("JZAI_HF_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")

# Generation
MAX_NEW_TOKENS = int(os.getenv("JZAI_MAX_NEW_TOKENS", "512"))
CONTEXT_SIZE = int(os.getenv("JZAI_CTX", "4096"))
N_THREADS = int(os.getenv("JZAI_THREADS", "0")) or None

# Reseau
HOST = os.getenv("JZAI_HOST", "0.0.0.0")
PORT = int(os.getenv("JZAI_PORT", "8000"))

# Limite de requetes par minute et par cle (0 = illimite).
# Les *tokens* sont toujours illimites : le modele tourne sur ta machine,
# il n'y a aucun compteur de facturation.
RATE_LIMIT_PER_MIN = int(os.getenv("JZAI_RATE_LIMIT", "0"))

# Profil du prompt systeme : "general" ou "code"
PROFILE = os.getenv("JZAI_PROFILE", "general").lower()

_PROMPTS = {
    "general": (
        "Tu es JZ-AI, un assistant francais concis, direct et utile. "
        "Si tu ne sais pas, dis-le au lieu d'inventer."
    ),
    "code": (
        "Tu es JZ-AI, un assistant de programmation francais. Reponds avec du code "
        "complet et fonctionnel dans un bloc ``` avec le bon langage. Explique "
        "brievement les choix importants, pas ligne par ligne. Signale les cas "
        "limites et les erreurs a gerer. Si l'enonce est ambigu, pose la question "
        "au lieu de deviner. N'invente jamais une fonction ou une bibliotheque : "
        "si tu n'es pas sur qu'elle existe, dis-le."
    ),
}

SYSTEM_PROMPT = os.getenv("JZAI_SYSTEM_PROMPT", _PROMPTS.get(PROFILE, _PROMPTS["general"]))
