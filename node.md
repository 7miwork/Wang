# Prüfen ob Node installiert ist
if ! command -v node >/dev/null 2>&1; then
    echo "Node.js wurde nicht gefunden."

    # Homebrew prüfen
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew ist nicht installiert."
        echo ""
        echo "Bitte zuerst Homebrew installieren:"
        echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        exit 1
    fi

    echo "Installiere Node.js..."
    brew install node
fi

echo "Node Version: $(node -v)"
echo "npm Version: $(npm -v)"
