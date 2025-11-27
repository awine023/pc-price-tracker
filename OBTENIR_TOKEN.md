# 🔑 Comment obtenir un token Telegram valide

## ❌ Problème actuel
Le token dans `config.py` est invalide ou expiré.

## ✅ Solution : Obtenir un nouveau token

### Méthode 1 : Si vous avez déjà un bot

1. **Ouvrez Telegram** sur votre téléphone ou ordinateur
2. **Cherchez @BotFather** dans Telegram
3. **Envoyez la commande** : `/mybots`
4. **Sélectionnez votre bot** dans la liste
5. **Cliquez sur "API Token"** ou envoyez `/token`
6. **Copiez le token** affiché (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Méthode 2 : Créer un nouveau bot

1. **Ouvrez Telegram** et cherchez **@BotFather**
2. **Envoyez** : `/newbot`
3. **Donnez un nom** à votre bot (ex: "Mon Bot Amazon")
4. **Donnez un username** (doit finir par `bot`, ex: `mon_bot_amazon_bot`)
5. **Copiez le token** que BotFather vous donne

## 📝 Mettre à jour le token

1. **Ouvrez** `config.py`
2. **Remplacez** la ligne :
   ```python
   TELEGRAM_TOKEN = "8038081238:AAG3j0sMSizXLbDl3A3ZCE7U2nD2iNWFWSO"
   ```
   par :
   ```python
   TELEGRAM_TOKEN = "VOTRE_NOUVEAU_TOKEN_ICI"
   ```

3. **Sauvegardez** le fichier
4. **Relancez** le bot avec `python bot.py`

## ✅ Vérifier que le token fonctionne

Après avoir mis à jour le token, le bot devrait démarrer sans erreur et afficher :
```
🤖 Bot démarré !
⏰ Vérification des prix programmée toutes les 30 minutes
```

Sans l'erreur `InvalidToken` !

## 🔒 Sécurité

⚠️ **NE PARTAGEZ JAMAIS** votre token Telegram publiquement !
- Ne le commitez pas sur GitHub (il est déjà dans `.gitignore`)
- Ne le partagez pas avec d'autres personnes
- Si le token est compromis, régénérez-le via BotFather avec `/revoke`

