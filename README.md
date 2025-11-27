# 🤖 Bot Telegram - Surveillance des Prix Amazon Canada

Bot Telegram qui surveille les prix des produits Amazon.ca en utilisant l'API Keepa et vous envoie des alertes quand les prix baissent.

## 📋 Fonctionnalités

- ✅ Surveillance automatique des prix Amazon Canada
- ✅ Alertes instantanées quand le prix baisse
- ✅ Ajout de produits via lien ou ASIN
- ✅ Liste de tous vos produits surveillés
- ✅ Suppression de produits
- ✅ Utilise l'API Keepa pour des données précises

## 🚀 Installation

### Prérequis

- Python 3.10 ou supérieur
- Un compte Telegram
- Une clé API Keepa

### 1. Cloner ou télécharger le projet

```bash
cd telegram_amazon_bot
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Créer un bot Telegram

1. Ouvrez Telegram et cherchez **@BotFather**
2. Envoyez la commande `/newbot`
3. Suivez les instructions pour nommer votre bot
4. **Copiez le token** que BotFather vous donne (ex: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 4. Configurer le bot

Ouvrez `config.py` et remplacez le token :

```python
TELEGRAM_TOKEN = "VOTRE_TOKEN_ICI"  # Token de BotFather
CHECK_INTERVAL_MINUTES = 30          # Intervalle de vérification (en minutes)
```

**Note:** Ce bot utilise Playwright (gratuit) pour scraper Amazon.ca directement. Pas besoin de clé API Keepa !

### 5. Installer Playwright

```bash
playwright install chromium
playwright install-deps chromium
```

### 6. Lancer le bot

```bash
python bot.py
```

Le bot devrait démarrer et vous pouvez le tester dans Telegram !

## 📱 Utilisation

### Commandes disponibles

- `/start` - Message d'accueil
- `/add [lien ou ASIN]` - Ajouter un produit à surveiller
- `/list` - Voir tous vos produits surveillés
- `/delete [ASIN]` - Supprimer un produit
- `/help` - Afficher l'aide

### Exemples

```
/add B08N5WRWNW
/add https://www.amazon.ca/dp/B08N5WRWNW
/list
/delete B08N5WRWNW
```

## 🌐 Hébergement gratuit

### Option 1: PythonAnywhere (Recommandé pour débutants)

1. Créez un compte sur [PythonAnywhere](https://www.pythonanywhere.com) (gratuit)
2. Uploadez vos fichiers via l'interface web
3. Créez une tâche planifiée (Scheduled Tasks) pour lancer `bot.py`
4. Le bot tournera 24/7 (limite: 1 tâche sur le plan gratuit)

**Note:** Le plan gratuit de PythonAnywhere limite l'exécution à certaines heures. Pour un bot 24/7, considérez Railway ou un VPS.

### Option 2: Railway (Recommandé pour 24/7)

1. Créez un compte sur [Railway](https://railway.app) (gratuit avec crédits)
2. Créez un nouveau projet
3. Connectez votre repository GitHub ou uploadez les fichiers
4. Railway détectera automatiquement Python et installera les dépendances
5. Ajoutez les variables d'environnement :
   - `TELEGRAM_TOKEN` = votre token
   - `KEEPA_KEY` = votre clé Keepa
6. Le bot démarrera automatiquement

### Option 3: Google Cloud Platform (VM gratuite)

1. Créez une VM `e2-micro` sur GCP (gratuit)
2. Installez Python et les dépendances
3. Utilisez `systemd` pour faire tourner le bot 24/7 (comme votre tracker actuel)

### Option 4: Heroku (Alternative)

1. Créez un compte sur [Heroku](https://www.heroku.com)
2. Installez Heroku CLI
3. Créez un `Procfile` avec : `worker: python bot.py`
4. Déployez avec `git push heroku main`

## 📁 Structure du projet

```
telegram_amazon_bot/
├── bot.py          # Code principal du bot
├── config.py       # Configuration (tokens, clés)
├── data.json       # Base de données locale (produits, utilisateurs)
├── requirements.txt # Dépendances Python
└── README.md       # Ce fichier
```

## ⚙️ Configuration avancée

### Changer l'intervalle de vérification

Dans `config.py` :

```python
CHECK_INTERVAL_MINUTES = 60  # Vérifie toutes les heures
```

### Avantages de Playwright

- ✅ **100% gratuit** - Pas de limite de requêtes
- ✅ **Pas besoin de clé API** - Fonctionne directement
- ✅ **Techniques anti-détection** - User-agent rotation, headers réalistes
- ✅ **Compatible avec votre tracker principal** - Même technologie

**Note:** Le scraping peut être plus lent que Keepa API, mais c'est entièrement gratuit !

## 🐛 Dépannage

### Le bot ne répond pas

1. Vérifiez que le token Telegram est correct
2. Vérifiez que le bot est démarré (`python bot.py`)
3. Vérifiez les logs pour les erreurs

### Erreur API Keepa

1. Vérifiez que votre clé API est correcte
2. Vérifiez que vous n'avez pas dépassé la limite de requêtes
3. Attendez quelques minutes et réessayez

### Le bot ne trouve pas l'ASIN

- Assurez-vous que le lien est bien un lien Amazon.ca
- Vérifiez que l'ASIN est correct (10 caractères)

## 📝 Notes importantes

- Le bot stocke les données localement dans `data.json`
- Les prix Keepa sont en centimes, le bot les convertit automatiquement en dollars
- Le bot vérifie les prix périodiquement et envoie des alertes automatiquement
- Pour un usage en production, considérez utiliser une base de données (SQLite, PostgreSQL)

## 🔒 Sécurité

- **Ne partagez jamais** votre `config.py` ou vos tokens
- Ajoutez `config.py` et `data.json` à `.gitignore` si vous utilisez Git
- Utilisez des variables d'environnement pour les clés en production

## 📞 Support

Pour toute question ou problème, consultez :

- [Documentation python-telegram-bot](https://python-telegram-bot.org/)
- [Documentation Keepa API](https://keepa.com/#!api)

## 📄 Licence

Ce projet est fourni tel quel, sans garantie.
