#!/bin/bash

# Skript: start_openclaw.sh
# Beschreibung: Startet OpenClaw mit API-Keys aus api_keys.json

# Pfade
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_KEYS_FILE="$SCRIPT_DIR/api_keys.json"
OPENCLAW_ENV="$SCRIPT_DIR/.env"
OPENCLAW_CONFIG="$SCRIPT_DIR/openclaw_config.json"

# Farben für Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funktion für Fehlermeldungen
error_exit() {
    echo -e "${RED}Fehler: $1${NC}" >&2
    exit 1
}

# 1. Prüfe ob api_keys.json existiert
if [ ! -f "$API_KEYS_FILE" ]; then
    error_exit "api_keys.json nicht gefunden in $SCRIPT_DIR"
fi

# 2. Prüfe ob jq installiert ist (für JSON-Verarbeitung)
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}jq wird installiert...${NC}"
    if command -v brew &> /dev/null; then
        brew install jq
    else
        error_exit "jq ist erforderlich. Installiere es mit: brew install jq"
    fi
fi

# 3. Prüfe ob Node.js installiert ist
if ! command -v node &> /dev/null; then
    error_exit "Node.js ist erforderlich. Installiere es von https://nodejs.org/"
fi

# 4. Prüfe ob OpenClaw installiert ist
if ! command -v openclaw &> /dev/null; then
    echo -e "${YELLOW}OpenClaw wird installiert...${NC}"
    npm install -g @openclaw/core || error_exit "OpenClaw Installation fehlgeschlagen"
fi

# 5. .env-Datei für OpenClaw erstellen
echo -e "${GREEN}Erstelle OpenClaw Konfiguration...${NC}"

# Lese API-Keys aus api_keys.json
OPENROUTER_KEY=$(jq -r '.providers.openrouter.api_key // empty' "$API_KEYS_FILE")
GROQ_KEY=$(jq -r '.providers.groq.api_key // empty' "$API_KEYS_FILE")
MISTRAL_KEY=$(jq -r '.providers.mistral.api_key // empty' "$API_KEYS_FILE")

# Erstelle .env-Datei
cat > "$OPENCLAW_ENV" << EOF
# OpenClaw API Keys - Automatisch aus api_keys.json generiert
# Bearbeite api_keys.json, um Keys zu ändern

# OpenRouter
OPENROUTER_API_KEY=$OPENROUTER_KEY

# Groq
GROQ_API_KEY=$GROQ_KEY

# Mistral
MISTRAL_API_KEY=$MISTRAL_KEY

# Standardmodell (kostenlos)
DEFAULT_MODEL=google/gemini-flash-1.5
EOF

# 6. OpenClaw Konfiguration erstellen
cat > "$OPENCLAW_CONFIG" << 'EOF'
{
  "providers": {
    "openrouter": {
      "apiKey": "$OPENROUTER_API_KEY",
      "models": ["google/gemini-flash-1.5", "deepseek/deepseek-chat", "mistralai/mistral-7b-instruct"]
    },
    "groq": {
      "apiKey": "$GROQ_API_KEY",
      "models": ["llama3-8b-instant", "mixtral-8x7b-instruct-v0.1"]
    },
    "mistral": {
      "apiKey": "$MISTRAL_API_KEY",
      "models": ["mistral-tiny"]
    }
  },
  "defaultProvider": "openrouter",
  "defaultModel": "google/gemini-flash-1.5"
}
EOF

# 7. Ersetze Platzhalter in der Konfiguration
if [ -n "$OPENROUTER_KEY" ]; then
    sed -i '' "s|\$OPENROUTER_API_KEY|$OPENROUTER_KEY|g" "$OPENCLAW_CONFIG"
fi
if [ -n "$GROQ_KEY" ]; then
    sed -i '' "s|\$GROQ_API_KEY|$GROQ_KEY|g" "$OPENCLAW_CONFIG"
fi
if [ -n "$MISTRAL_KEY" ]; then
    sed -i '' "s|\$MISTRAL_API_KEY|$MISTRAL_KEY|g" "$OPENCLAW_CONFIG"
fi

# 8. OpenClaw starten
echo -e "${GREEN}Starte OpenClaw...${NC}"
echo -e "${YELLOW}Hinweis: Verwende kostenlose Modelle aus api_keys.json${NC}"
echo ""

# Starte OpenClaw mit der Konfiguration
export $(grep -v '^#' "$OPENCLAW_ENV" | xargs)
openclaw start --config "$OPENCLAW_CONFIG"
