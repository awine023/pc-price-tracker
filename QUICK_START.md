# 🚀 Démarrage Rapide - Bot Telegram Amazon (Playwright)

## ✅ Avantages

- **100% GRATUIT** - Pas besoin de Keepa API
- **Pas de limite** - Scrape directement Amazon.ca
- **Même technologie** que votre tracker principal

## 📦 Installation

### 1. Installer les dépendances

```bash
cd telegram_amazon_bot
pip install -r requirements.txt
```

### 2. Installer Playwright

```bash
playwright install chromium
playwright install-deps chromium
```

### 3. Configurer le bot

Le token Telegram est déjà configuré dans `config.py`. Si vous voulez le changer :

```python
TELEGRAM_TOKEN = "VOTRE_TOKEN_ICI"
CHECK_INTERVAL_MINUTES = 30  # Vérification toutes les 30 minutes
```

## 🚀 Lancer le bot

```bash
python bot.py
```

Le bot devrait démarrer et afficher :
```
🤖 Bot démarré !
⏰ Vérification des prix programmée toutes les 30 minutes
```

## 📱 Utilisation dans Telegram

1. Ouvrez Telegram et cherchez votre bot (nom que vous avez donné à BotFather)
2. Envoyez `/start` pour commencer
3. Ajoutez un produit avec `/add` :
   ```
   /add B08N5WRWNW
   ```
   ou
   ```
   /add https://www.amazon.ca/dp/B08N5WRWNW
   ```

## 🔔 Commandes disponibles

- `/start` - Message d'accueil
- `/add [lien ou ASIN]` - Ajouter un produit
- `/list` - Voir tous vos produits
- `/delete [ASIN]` - Supprimer un produit
- `/help` - Aide

## ⚠️ Notes importantes

1. **Première vérification** : Le bot peut prendre quelques secondes pour scraper chaque produit
2. **Alertes automatiques** : Vous recevrez une notification Telegram quand le prix baisse
3. **Stock** : Le bot vérifie aussi la disponibilité du produit
4. **Gratuit** : Pas de limite de requêtes, contrairement à Keepa API

## 🐛 Dépannage

### Erreur "Playwright not installed"
```bash
playwright install chromium
```

### Erreur "Token invalide"
Vérifiez que `TELEGRAM_TOKEN` dans `config.py` est correct.

### Le bot ne répond pas
Vérifiez que le bot est bien démarré et que vous avez envoyé `/start` dans Telegram.

## 📊 Comparaison avec Keepa API

| Fonctionnalité | Keepa API | Playwright (ce bot) |
|----------------|-----------|---------------------|
| Coût | ~19€/mois | **GRATUIT** |
| Limite | 100 req/jour (gratuit) | **Illimité** |
| Historique des prix | ✅ Oui | ❌ Non (prix actuel seulement) |
| Vitesse | Rapide | Plus lent (scraping) |
| Installation | Simple | Nécessite Playwright |

**Conclusion** : Ce bot est parfait si vous voulez surveiller quelques produits gratuitement !

