#!/bin/bash

# ===================================================
# Script de configuration pour Google Cloud Platform
# Bot Telegram Amazon Price Tracker
# ===================================================

set -e  # Arrêter en cas d'erreur

echo "==================================================="
echo "  Configuration du Bot Telegram sur GCP"
echo "==================================================="
echo ""

# Couleurs pour les messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "bot.py" ]; then
    echo -e "${RED}❌ Erreur: Ce script doit être exécuté depuis le dossier telegram_amazon_bot${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Étape 1/6: Mise à jour du système...${NC}"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

echo -e "${YELLOW}📦 Étape 2/6: Installation de Python 3.11 et dépendances...${NC}"
sudo apt-get install -y -qq python3.11 python3.11-venv python3.11-dev python3-pip
sudo apt-get install -y -qq build-essential curl git

echo -e "${YELLOW}📦 Étape 3/6: Installation de Node.js (requis pour Playwright)...${NC}"
# Installer Node.js pour Playwright
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y -qq nodejs

echo -e "${YELLOW}📦 Étape 4/6: Création de l'environnement virtuel...${NC}"
python3.11 -m venv venv
source venv/bin/activate

echo -e "${YELLOW}📦 Étape 5/6: Installation des dépendances Python...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo -e "${YELLOW}📦 Installation de Playwright et navigateurs...${NC}"
# Installer les dépendances système pour Playwright
sudo apt-get install -y -qq \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxshmfence1

# Installer Playwright et les navigateurs
playwright install chromium
playwright install-deps chromium

echo -e "${YELLOW}📦 Étape 6/6: Configuration du service systemd...${NC}"

# Obtenir le chemin absolu du répertoire
BOT_DIR=$(pwd)
USER=$(whoami)
PYTHON_PATH="$BOT_DIR/venv/bin/python"
BOT_SCRIPT="$BOT_DIR/bot.py"

# Créer le fichier de service systemd
sudo tee /etc/systemd/system/telegram-amazon-bot.service > /dev/null <<EOF
[Unit]
Description=Telegram Amazon Price Tracker Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$BOT_DIR/venv/bin"
ExecStart=$PYTHON_PATH $BOT_SCRIPT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Recharger systemd
sudo systemctl daemon-reload

# Activer le service (démarrage automatique au boot)
sudo systemctl enable telegram-amazon-bot.service

echo ""
echo -e "${GREEN}===================================================${NC}"
echo -e "${GREEN}✅ Configuration terminée avec succès !${NC}"
echo -e "${GREEN}===================================================${NC}"
echo ""
echo "📝 Prochaines étapes:"
echo ""
echo "1. Configurez votre token Telegram dans config.py:"
echo "   nano config.py"
echo ""
echo "2. Démarrer le bot:"
echo "   sudo systemctl start telegram-amazon-bot"
echo ""
echo "3. Vérifier le statut:"
echo "   sudo systemctl status telegram-amazon-bot"
echo ""
echo "4. Voir les logs:"
echo "   sudo journalctl -u telegram-amazon-bot -f"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Configurez votre TELEGRAM_TOKEN avant de démarrer le bot !${NC}"
echo ""

