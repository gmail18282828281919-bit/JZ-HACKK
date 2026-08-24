#!/usr/bin/env bash
# Telecharge un modele GGUF pour JZ-AI et affiche la commande de lancement.
#
#   bash ai/scripts/models.sh list
#   bash ai/scripts/models.sh get code
set -euo pipefail

cd "$(dirname "$0")/../.."
DEST="$PWD/ai/models"
HF="https://huggingface.co"

# nom | taille | description | url_modele | url_mmproj (vide si pas de vision)
presets() {
  cat <<'EOF'
general|1.0 Go|Conversation generale, leger|Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf|
general-mini|0.4 Go|Le plus leger, qualite limitee|Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf|
code|1.0 Go|Code, tourne sur telephone|Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf|
code-pro|4.4 Go|Code, nettement meilleur, PC requis|Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf|
vision|4.4 Go|Lecture d'images, PC requis|mys/ggml_llava-v1.5-7b/resolve/main/ggml-model-q4_k.gguf|mys/ggml_llava-v1.5-7b/resolve/main/mmproj-model-f16.gguf
EOF
}

usage() {
  echo "Usage : bash ai/scripts/models.sh {list|get <nom>}"
  echo
  echo "Modeles disponibles :"
  presets | while IFS='|' read -r name size desc _ mmproj; do
    printf "  %-13s %-8s %s%s\n" "$name" "$size" "$desc" \
      "$([ -n "$mmproj" ] && echo ' (+ projecteur vision)')"
  done
}

fetch() {
  local url="$1" out="$2"
  if [ -f "$out" ]; then
    echo "Deja present : $out"
    return
  fi
  echo "Telechargement -> $out"
  # -C - reprend un telechargement interrompu (utile en 4G)
  curl -L --fail -C - -o "$out.part" "$HF/$url"
  mv "$out.part" "$out"
}

case "${1:-}" in
  list|"") usage ;;
  get)
    name="${2:-}"
    line=$(presets | grep "^$name|" || true)
    if [ -z "$line" ]; then
      echo "Modele inconnu : '${name:-(vide)}'" >&2
      echo >&2
      usage >&2
      exit 1
    fi
    IFS='|' read -r _ size desc model_url mmproj_url <<< "$line"

    echo "Modele : $name ($size) — $desc"
    mkdir -p "$DEST"
    model_file="$DEST/$(basename "$model_url")"
    fetch "$model_url" "$model_file"

    mmproj_file=""
    if [ -n "$mmproj_url" ]; then
      mmproj_file="$DEST/$(basename "$mmproj_url")"
      fetch "$mmproj_url" "$mmproj_file"
    fi

    profile=general
    [ "${name#code}" != "$name" ] && profile=code

    echo
    echo "Il faut le moteur llama.cpp :"
    echo "    pip install llama-cpp-python"
    echo
    echo "Puis lance le serveur avec :"
    echo "    export JZAI_BACKEND=llama"
    echo "    export JZAI_GGUF_PATH=\"$model_file\""
    [ -n "$mmproj_file" ] && echo "    export JZAI_MMPROJ_PATH=\"$mmproj_file\""
    [ -n "$mmproj_file" ] && echo "    export JZAI_VISION_HANDLER=llava-1.5"
    echo "    export JZAI_PROFILE=$profile"
    echo "    python3 -m ai.server.lite"
    ;;
  *) usage; exit 1 ;;
esac
