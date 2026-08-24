#!/data/data/com.termux/files/usr/bin/bash
# Installation JZ-AI sur Termux (Android). Aucun pip requis.
#   bash ai/termux.sh
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
MODELS="$ROOT/ai/models"
GGUF="$MODELS/qwen2.5-0.5b-instruct-q4_k_m.gguf"
GGUF_URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "1/4 Paquets Termux"
pkg install -y python git curl

say "2/4 Verification de Python"
python3 -c 'import sqlite3, json, http.server; print("stdlib OK -> aucun pip necessaire")'

say "3/4 Modele"
if [ -f "$GGUF" ]; then
  echo "Deja present : $GGUF"
else
  read -r -p "Telecharger Qwen2.5-0.5B (~400 Mo) ? [o/N] " rep
  if [ "${rep,,}" = "o" ]; then
    mkdir -p "$MODELS"
    curl -L --fail -o "$GGUF.part" "$GGUF_URL"
    mv "$GGUF.part" "$GGUF"
    echo "Telecharge : $GGUF"
    echo
    echo "Pour l'utiliser il faut le moteur llama.cpp :"
    echo "    pkg install -y clang cmake ninja"
    echo "    pip install llama-cpp-python      # long (compilation)"
  else
    echo "Ignore. Le backend 'echo' fonctionnera sans modele."
  fi
fi

say "4/4 Cle d'API"
KEY_OUT="$(python3 "$ROOT/ai/scripts/keys.py" new "termux")"
echo "$KEY_OUT"

# Script de demarrage pret a l'emploi
cat > "$ROOT/ai/start-termux.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$ROOT"
export JZAI_PORT=\${JZAI_PORT:-8000}
[ -f "$GGUF" ] && export JZAI_GGUF_PATH="$GGUF"
export JZAI_BACKEND=\${JZAI_BACKEND:-auto}
command -v termux-wake-lock >/dev/null && termux-wake-lock
exec python3 -m ai.server.lite
EOF
chmod +x "$ROOT/ai/start-termux.sh"

say "Termine"
echo "Demarrer le serveur :   bash ai/start-termux.sh"
echo "Tester :                curl http://127.0.0.1:8000/health"
