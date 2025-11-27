# 🚀 Déploiement 24/7 du Bot Telegram sur Google Cloud Platform

## Étape 1: Créer la VM (5 minutes)

1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créez un projet (ou utilisez un existant)
3. **Compute Engine** → **VM instances** → **CREATE INSTANCE**
4. Configuration:
   - **Nom**: `telegram-amazon-bot`
   - **Machine type**: `e2-micro` (GRATUIT dans le free tier)
   - **OS**: Ubuntu 22.04 LTS
   - **Disque**: 20 GB
   - **Firewall**: ✅ HTTP, ✅ HTTPS (optionnel, pour monitoring)
5. Cliquez sur **CREATE**

## Étape 2: Se connecter (1 minute)

1. Cliquez sur **SSH** à côté de votre VM
2. Une fenêtre SSH s'ouvre automatiquement

## Étape 3: Cloner le repository (1 minute)

**IMPORTANT:** Utilisez HTTPS, pas SSH!

### Option A: Si le dossier n'existe pas encore

```bash
# Cloner avec HTTPS
git clone https://github.com/awine023/pc-price-tracker.git
cd pc-price-tracker/telegram_amazon_bot
```

### Option B: Si le dossier existe déjà (comme dans votre cas)

```bash
# Supprimer l'ancien dossier (si vous n'avez pas de données importantes)
rm -rf pc-price-tracker

# Puis cloner
git clone https://github.com/awine023/pc-price-tracker.git
cd pc-price-tracker/telegram_amazon_bot
```

### Option C: Si vous voulez garder les fichiers existants

```bash
# Aller dans le dossier
cd pc-price-tracker

# Si git pull échoue avec des conflits, sauvegarder les changements locaux
git stash
# ou git stash save "Sauvegarde avant pull"

# Puis faire le pull
git pull origin main
# ou git pull origin master (selon votre branche principale)

# Aller dans le dossier du bot (vous êtes déjà dans pc-price-tracker)
cd telegram_amazon_bot
```

Si le repository est privé, vous devrez entrer votre nom d'utilisateur et un token GitHub.

## Étape 4: Configuration automatique (5 minutes)

```bash
# Rendre le script exécutable
chmod +x setup_gcp.sh

# Exécuter le script
./setup_gcp.sh
```

Le script va:

- ✅ Installer Python 3.11
- ✅ Installer toutes les dépendances
- ✅ Installer Playwright et les navigateurs
- ✅ Créer l'environnement virtuel
- ✅ Installer le service systemd pour 24/7

## Étape 5: Configurer le bot (2 minutes)

### Si le fichier config.py n'existe pas encore

```bash
# Créer le fichier config.py
nano config.py
```

Puis collez ce contenu (remplacez VOTRE_TOKEN par votre vrai token) :

```python
"""
Configuration file for Telegram Amazon Price Tracker Bot
Utilise Playwright (gratuit) au lieu de Keepa API
"""

# Telegram Bot Token (obtenu via @BotFather)
TELEGRAM_TOKEN = "VOTRE_TOKEN_ICI"

# Intervalle de vérification des prix (en minutes)
CHECK_INTERVAL_MINUTES = 30
```

### Si le fichier existe déjà

```bash
# Éditer le fichier de configuration
nano config.py
```

Modifiez `TELEGRAM_TOKEN` avec votre token du bot (obtenu via @BotFather).

**IMPORTANT:** Ne partagez jamais votre token publiquement!

## Étape 6: Démarrer le bot (1 minute)

```bash
# Démarrer le service
sudo systemctl start telegram-amazon-bot

# Vérifier le statut
sudo systemctl status telegram-amazon-bot

# Voir les logs
sudo journalctl -u telegram-amazon-bot -f
```

## ✅ C'est fait !

Le bot tourne maintenant 24/7 sur Google Cloud !

### Commandes utiles

```bash
# Démarrer le bot
sudo systemctl start telegram-amazon-bot

# Arrêter le bot
sudo systemctl stop telegram-amazon-bot

# Redémarrer le bot
sudo systemctl restart telegram-amazon-bot

# Voir le statut
sudo systemctl status telegram-amazon-bot

# Voir les logs en temps réel
sudo journalctl -u telegram-amazon-bot -f

# Voir les dernières 100 lignes de logs
sudo journalctl -u telegram-amazon-bot -n 100
```

## 🔧 Dépannage

### Erreur "Conflict: terminated by other getUpdates request"

Cette erreur signifie que **plusieurs instances du bot tournent en même temps**. Telegram n'autorise qu'une seule instance par bot.

**Solution :**

1. **Arrêter le bot sur votre PC local** (si vous l'avez lancé) :

   ```bash
   # Sur Windows, arrêtez le bot avec :
   stop_bot.bat
   # ou fermez la fenêtre où le bot tourne
   ```

2. **Vérifier les processus sur la VM GCP** :

   ```bash
   # Vérifier si plusieurs instances tournent
   ps aux | grep bot.py

   # Arrêter toutes les instances manuelles
   pkill -f bot.py

   # Redémarrer le service systemd
   sudo systemctl restart telegram-amazon-bot
   ```

3. **Vérifier qu'une seule instance tourne** :

   ```bash
   # Vérifier le statut
   sudo systemctl status telegram-amazon-bot

   # Vérifier les processus
   ps aux | grep bot.py
   # Il ne devrait y avoir qu'un seul processus
   ```

### Le bot ne démarre pas

```bash
# Vérifier les logs
sudo journalctl -u telegram-amazon-bot -n 50

# Vérifier que le token est configuré
cat config.py | grep TELEGRAM_TOKEN
```

### Erreur "Connection closed while reading from the driver" ou "node: not found"

Cette erreur signifie que **Playwright ne trouve pas Node.js** dans le PATH.

**Solution :**

```bash
# Aller dans le dossier du bot
cd ~/pc-price-tracker/telegram_amazon_bot

# Activer l'environnement virtuel
source venv/bin/activate

# Vérifier que Node.js est installé et accessible
which node
node --version

# Si node n'est pas trouvé, vérifier le PATH
echo $PATH

# Installer Node.js si pas déjà fait
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Installer les dépendances système pour Playwright
sudo apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libatspi2.0-0 libxshmfence1

# IMPORTANT: Réinstaller Playwright pour qu'il trouve Node.js
pip uninstall -y playwright
pip install playwright

# Installer les navigateurs
playwright install chromium
playwright install-deps chromium

# Vérifier que Playwright peut trouver Node.js
python -c "from playwright.sync_api import sync_playwright; print('OK')"

# Mettre à jour le service systemd pour inclure /usr/bin dans le PATH
sudo systemctl edit telegram-amazon-bot.service
```

Dans l'éditeur qui s'ouvre, ajoutez :

```ini
[Service]
Environment="PATH=/usr/bin:/usr/local/bin:/home/annabimi904/pc-price-tracker/telegram_amazon_bot/venv/bin"
```

Puis :

```bash
# Recharger systemd
sudo systemctl daemon-reload

# Redémarrer le bot
sudo systemctl restart telegram-amazon-bot
```

### Le bot s'arrête

Le service systemd redémarre automatiquement le bot en cas d'erreur. Vérifiez les logs pour voir l'erreur:

```bash
sudo journalctl -u telegram-amazon-bot -f
```

### Mettre à jour le bot

```bash
cd ~/pc-price-tracker/telegram_amazon_bot
git pull
sudo systemctl restart telegram-amazon-bot
```

## 💰 Coût

- **e2-micro**: GRATUIT dans le free tier (jusqu'à 1 instance par mois)
- **Disque 20 GB**: ~$2-3/mois
- **Total**: ~$2-3/mois (ou GRATUIT si vous restez dans le free tier)

## 📝 Notes importantes

1. **Token Telegram**: Gardez-le secret ! Ne le commitez jamais dans Git.
2. **Données**: Le fichier `data.json` est sauvegardé localement sur la VM.
3. **Backup**: Pensez à faire des backups réguliers de `data.json` si vous avez beaucoup de produits surveillés.
4. **Monitoring**: Vous pouvez surveiller le bot via les logs systemd.
