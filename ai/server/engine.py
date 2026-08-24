"""Moteurs d'inference. Trois backends, du plus capable au plus leger.

  llama        -> llama-cpp-python + un fichier .gguf (recommande, CPU)
  transformers -> HuggingFace transformers (telecharge le modele au 1er lancement)
  echo         -> repondeur local minimal, zero dependance (pour tester l'API)

Aucun backend ne compte de tokens : la generation tourne en local, donc
"tokens illimites" au sens ou il n'y a aucun quota ni facturation.
"""
from __future__ import annotations

import re
from typing import Iterator, List, Dict

from . import config

Message = Dict[str, str]


def _to_prompt(messages: List[Message]) -> str:
    """Format chat generique pour les backends qui n'ont pas de template."""
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        tag = {"system": "Systeme", "assistant": "JZ-AI", "user": "Utilisateur"}.get(role, role)
        parts.append(f"{tag}: {content}")
    parts.append("JZ-AI:")
    return "\n".join(parts)


class BaseEngine:
    name = "base"
    vision = False  # True si le backend sait lire les images

    def generate(self, messages: List[Message], max_tokens: int, temperature: float) -> Iterator[str]:
        raise NotImplementedError


class LlamaEngine(BaseEngine):
    name = "llama"

    def __init__(self, gguf_path: str, mmproj_path: str = ""):
        from llama_cpp import Llama  # import tardif : dependance optionnelle

        chat_handler = None
        if mmproj_path:
            # Le projecteur (mmproj) transforme l'image en tokens que le modele
            # comprend. Sans lui, un .gguf vision reste aveugle. Chaque famille
            # de modele a son propre format de prompt, d'ou le choix du handler.
            from llama_cpp import llama_chat_format

            handlers = {
                "llava-1.5": "Llava15ChatHandler",
                "llava-1.6": "Llava16ChatHandler",
                "nanollava": "NanoLlavaChatHandler",
                "moondream": "MoondreamChatHandler",
                "llama-3-vision": "Llama3VisionAlphaChatHandler",
                "minicpm-v-2.6": "MiniCPMv26ChatHandler",
            }
            wanted = config.VISION_HANDLER
            if wanted not in handlers:
                raise RuntimeError(
                    f"JZAI_VISION_HANDLER='{wanted}' inconnu. "
                    f"Valeurs possibles : {', '.join(sorted(handlers))}"
                )
            handler_cls = getattr(llama_chat_format, handlers[wanted], None)
            if handler_cls is None:
                raise RuntimeError(
                    f"Ta version de llama-cpp-python ne fournit pas "
                    f"{handlers[wanted]} : mets-la a jour (pip install -U llama-cpp-python)."
                )
            chat_handler = handler_cls(clip_model_path=mmproj_path, verbose=False)
            self.vision = True

        self.llm = Llama(
            model_path=gguf_path,
            n_ctx=config.CONTEXT_SIZE,
            n_threads=config.N_THREADS,
            chat_handler=chat_handler,
            verbose=False,
        )

    def generate(self, messages, max_tokens, temperature):
        stream = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            piece = chunk["choices"][0].get("delta", {}).get("content")
            if piece:
                yield piece


class TransformersEngine(BaseEngine):
    name = "transformers"

    def __init__(self, model_id: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype="auto", device_map="auto"
        )
        self.model.eval()

    def generate(self, messages, max_tokens, temperature):
        from threading import Thread
        from transformers import TextIteratorStreamer

        if self.tokenizer.chat_template:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            text = _to_prompt(messages)

        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        streamer = TextIteratorStreamer(
            self.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        kwargs = dict(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=max(temperature, 1e-4),
            do_sample=temperature > 0,
            streamer=streamer,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        thread = Thread(target=self.model.generate, kwargs=kwargs)
        thread.start()
        for piece in streamer:
            if piece:
                yield piece
        thread.join()


class EchoEngine(BaseEngine):
    """Repondeur de secours : regles simples + calculatrice. Sert a valider
    l'API, l'authentification et l'apk avant de brancher un vrai modele."""

    name = "echo"

    RULES = [
        (r"\b(bonjour|salut|hello|yo|coucou)\b", "Salut ! Je suis JZ-AI. Qu'est-ce que je peux faire pour toi ?"),
        (r"\b(qui es[- ]tu|tu es qui|ton nom)\b", "Je suis JZ-AI, un modele auto-heberge : pas de quota, pas de facturation."),
        (r"\b(merci|thanks)\b", "Avec plaisir."),
        (r"\b(au revoir|bye|ciao)\b", "A plus !"),
    ]

    def _answer(self, messages: List[Message]) -> str:
        user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user = (m.get("content") or "").strip()
                break
        low = user.lower()

        # Les pieces jointes passent en premier : le contenu d'un fichier peut
        # contenir "salut" ou "merci" sans que ce soit une salutation.
        if "--- Fichier joint :" in user:
            noms = re.findall(r"--- Fichier joint : (.+?) \(", user)
            lignes = user.count("\n")
            return (
                f"J'ai bien recu {len(noms)} fichier(s) : {', '.join(noms)} "
                f"({lignes} lignes au total). Le backend 'echo' ne sait pas les analyser : "
                "charge un vrai modele pour ca."
            )

        if "[image jointe" in user:
            return (
                "Une image a ete recue, mais le backend 'echo' ne lit pas les images. "
                "Il faut un modele vision (JZAI_GGUF_PATH + JZAI_MMPROJ_PATH)."
            )

        for pattern, reply in self.RULES:
            if re.search(pattern, low):
                return reply

        calc = re.fullmatch(r"[\d\s\+\-\*/\.\(\)]{3,}", user)
        if calc:
            try:
                return f"= {eval(user, {'__builtins__': {}}, {})}"  # entree restreinte aux chiffres/operateurs
            except Exception:
                pass

        if user.endswith("?"):
            return (
                "Le backend 'echo' ne sait pas repondre a ca : c'est un repondeur de test. "
                "Branche un vrai modele (JZAI_GGUF_PATH ou JZAI_BACKEND=transformers) "
                "pour des reponses generees."
            )
        return f"[echo] Tu as dit : {user}" if user else "[echo] Message vide."

    def generate(self, messages, max_tokens, temperature):
        for word in self._answer(messages).split(" "):
            yield word + " "


_engine: BaseEngine | None = None


def get_engine() -> BaseEngine:
    """Choisit le backend une seule fois, avec repli automatique."""
    global _engine
    if _engine is not None:
        return _engine

    wanted = config.BACKEND
    order = {
        "llama": ["llama"],
        "transformers": ["transformers"],
        "echo": ["echo"],
        "auto": ["llama", "transformers", "echo"],
    }.get(wanted, ["echo"])

    errors = []
    for backend in order:
        try:
            if backend == "llama":
                if not config.GGUF_PATH:
                    raise RuntimeError("JZAI_GGUF_PATH non defini")
                _engine = LlamaEngine(config.GGUF_PATH, config.MMPROJ_PATH)
            elif backend == "transformers":
                _engine = TransformersEngine(config.HF_MODEL)
            else:
                _engine = EchoEngine()
            print(f"[JZ-AI] backend actif : {_engine.name}"
                  f"{' (vision activee)' if _engine.vision else ''}")
            return _engine
        except Exception as exc:  # noqa: BLE001 - on essaie le backend suivant
            errors.append(f"{backend}: {exc}")

    raise RuntimeError("Aucun backend disponible -> " + " | ".join(errors))
