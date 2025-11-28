"""Commandes Telegram pour le bot."""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from utils.helpers import extract_asin, load_data
from database import db
from config import CHECK_INTERVAL_MINUTES

logger = logging.getLogger(__name__)

# Les scrapers seront passés depuis bot.py
amazon_scraper = None
newegg_scraper = None
memoryexpress_scraper = None
canadacomputers_scraper = None
bestbuy_scraper = None
price_analyzer = None
global_application = None

def set_scrapers(amazon, newegg, memoryexpress, canadacomputers, bestbuy, analyzer):
    """Configure les scrapers depuis bot.py."""
    global amazon_scraper, newegg_scraper, memoryexpress_scraper, canadacomputers_scraper, bestbuy_scraper, price_analyzer
    amazon_scraper = amazon
    newegg_scraper = newegg
    memoryexpress_scraper = memoryexpress
    canadacomputers_scraper = canadacomputers
    bestbuy_scraper = bestbuy
    price_analyzer = analyzer

def set_application(app):
    """Configure l'application Telegram depuis bot.py."""
    global global_application
    global_application = app

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /start - Message d'accueil."""
    welcome_message = """
🤖 **Bot de Surveillance des Prix Amazon Canada**

Bienvenue ! Ce bot surveille les prix des produits Amazon.ca et vous alerte quand ils baissent.

**Commandes disponibles :**
/add - Ajouter un produit à surveiller (lien ou ASIN)
/category - Surveiller une catégorie entière (ex: carte graphique)
/list - Voir tous les produits et catégories surveillés
/delete - Supprimer un produit
/help - Afficher cette aide

**Comment ajouter un produit :**
1. Envoyez un lien Amazon.ca
2. Ou envoyez l'ASIN du produit (10 caractères)

Exemple: /add B08N5WRWNW
ou: /add https://www.amazon.ca/dp/B08N5WRWNW

**Note:** Ce bot utilise Playwright (gratuit) pour scraper Amazon.ca
"""
    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /add - Ajoute un produit à surveiller."""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Inconnu"

    if not context.args:
        await update.message.reply_text(
            "❌ Veuillez fournir un lien Amazon.ca ou un ASIN.\n"
            "Exemple: /add B08N5WRWNW\n"
            "ou: /add https://www.amazon.ca/dp/B08N5WRWNW"
        )
        return

    url_or_asin = " ".join(context.args)
    asin = extract_asin(url_or_asin)

    if not asin:
        await update.message.reply_text(
            "❌ Impossible d'extraire l'ASIN. "
            "Veuillez envoyer un lien Amazon.ca valide ou un ASIN."
        )
        return

    # Ajouter l'utilisateur à la base de données
    db.add_user(user_id, username)

    # Vérifier si le produit existe déjà
    existing_product = db.get_product(asin)
    if existing_product:
        await update.message.reply_text(
            f"⚠️ Ce produit est déjà surveillé:\n"
            f"📦 {existing_product['title']}\n"
            f"💰 Prix actuel: ${existing_product.get('last_price', 0):.2f} CAD"
        )
        return

    # Récupérer les informations du produit
    await update.message.reply_text("⏳ Récupération des informations du produit...")
    
    try:
        product_info = await amazon_scraper.get_product_info(asin)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du produit: {e}")
        product_info = None

    if not product_info:
        await update.message.reply_text(
            "❌ Impossible de récupérer les informations du produit. "
            "Vérifiez que l'ASIN est correct et que le produit existe sur Amazon.ca"
        )
        return

    # Ajouter le produit à la base de données
    db.add_product(
        asin=asin,
        title=product_info["title"],
        url=product_info["url"],
        added_by=user_id,
        current_price=product_info["current_price"],
        amazon_lowest_price=product_info.get("amazon_lowest_price"),
        amazon_lowest_date=product_info.get("amazon_lowest_date")
    )
    
    # Ajouter à l'historique des prix
    if product_info["current_price"]:
        db.update_product_price(
            asin=asin,
            price=product_info["current_price"],
            original_price=product_info.get("original_price"),
            discount_percent=None,
            in_stock=product_info.get("in_stock", True)
        )

    price_text = f"${product_info['current_price']:.2f} CAD" if product_info['current_price'] else "Non disponible"
    stock_text = "✅ En stock" if product_info.get('in_stock') else "❌ Rupture de stock"
    
    discount_text = ""
    if product_info.get('original_price') and product_info['original_price'] > product_info['current_price']:
        discount = ((product_info['original_price'] - product_info['current_price']) / product_info['original_price']) * 100
        discount_text = f"\n🎉 RABAIS: {discount:.1f}% (Prix original: ${product_info['original_price']:.2f} CAD)"

    await update.message.reply_text(
        f"✅ **Produit ajouté avec succès !**\n\n"
        f"📦 {product_info['title']}\n"
        f"💰 Prix actuel: {price_text}\n"
        f"📦 Stock: {stock_text}{discount_text}\n"
        f"🔗 {product_info['url']}\n\n"
        f"Le bot surveillera ce produit toutes les {CHECK_INTERVAL_MINUTES} minutes.",
        parse_mode="Markdown",
    )


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /list - Liste tous les produits, catégories, big deals et erreurs de prix."""
    user_id = str(update.effective_user.id)

    # Obtenir les produits depuis la DB
    user_products = db.get_user_products(user_id)
    
    # Obtenir les catégories depuis JSON (pas encore migré vers DB)
    data = load_data()
    categories = data.get("categories", {})
    user_categories = []
    for category_id, category_data in categories.items():
        if category_data.get("added_by") == user_id:
            user_categories.append({
                "name": category_data.get("name", category_id),
                "product_count": category_data.get("product_count", 0),
                "discounted_count": category_data.get("discounted_count", 0),
            })
    
    # Obtenir les big deals et erreurs de prix
    big_deals = db.get_big_deals(limit=20)  # Limiter à 20 pour éviter les messages trop longs
    price_errors = db.get_price_errors(limit=20)
    
    # Obtenir les comparaisons de prix de l'utilisateur
    user_comparisons = db.get_user_comparisons(user_id)

    if not user_products and not user_categories and not user_comparisons and not big_deals and not price_errors:
        await update.message.reply_text(
            "📭 Vous n'avez aucun produit, catégorie ou comparaison surveillé.\n"
            "Utilisez /add pour ajouter un produit, /category pour surveiller une catégorie, ou /compare pour comparer les prix."
        )
        return

    message = ""
    
    # Afficher les produits surveillés
    if user_products:
        message += "📦 **Vos produits surveillés :**\n\n"
        for product in user_products:
            price_text = f"${product['last_price']:.2f} CAD" if product.get('last_price') else "Non disponible"
            message += f"📦 {product['title'][:50]}...\n"
            message += f"💰 Prix: {price_text}\n"
            message += f"🔗 {product['url']}\n"
            message += f"🆔 ASIN: {product['asin']}\n\n"
    
    # Afficher les catégories surveillées
    if user_categories:
        if message:
            message += "\n"
        message += "📂 **Vos catégories surveillées :**\n\n"
        for category in user_categories:
            message += f"📂 **{category['name']}**\n"
            message += f"📊 {category.get('product_count', 0)} produits\n"
            message += f"🎉 {category.get('discounted_count', 0)} en rabais\n\n"
    
    # Afficher les comparaisons de prix
    if user_comparisons:
        if message:
            message += "\n"
        message += "🛒 **Vos comparaisons de prix :**\n\n"
        for comparison in user_comparisons[:10]:  # Limiter à 10 pour le message
            product_name = comparison.get('product_name', 'Produit inconnu')
            best_price = comparison.get('best_price')
            best_site = comparison.get('best_site', '').title()
            
            message += f"🛒 **{product_name}**\n"
            
            if best_price:
                message += f"💰 Meilleur prix: ${best_price:.2f} CAD ({best_site})\n"
                
                # Afficher les prix de chaque site
                amazon_price = comparison.get('amazon_price')
                newegg_price = comparison.get('newegg_price')
                memoryexpress_price = comparison.get('memoryexpress_price')
                
                prices_info = []
                if amazon_price:
                    prices_info.append(f"Amazon: ${amazon_price:.2f}")
                if newegg_price:
                    prices_info.append(f"Newegg: ${newegg_price:.2f}")
                if memoryexpress_price:
                    prices_info.append(f"Memory Express: ${memoryexpress_price:.2f}")
                
                if prices_info:
                    message += f"📊 {' | '.join(prices_info)}\n"
            else:
                message += f"⏳ En attente de vérification...\n"
            
            message += f"🔍 Recherche: {comparison.get('search_query', 'N/A')}\n\n"
        
        if len(user_comparisons) > 10:
            message += f"📊 ... et {len(user_comparisons) - 10} autres comparaisons.\n\n"
    
    # Afficher les big deals
    if big_deals:
        if message:
            message += "\n"
        message += f"🔥 **Gros rabais détectés ({len(big_deals)} articles) :**\n\n"
        for i, deal in enumerate(big_deals[:10], 1):  # Limiter à 10 pour le message
            discount = deal.get('discount_percent', 0)
            current_price = deal.get('current_price', 0)
            title = deal.get('title', 'Titre inconnu')
            message += f"{i}. 🔥 {title[:45]}...\n"
            message += f"   💰 ${current_price:.2f} CAD (-{discount:.1f}%)\n"
            message += f"   🔗 {deal.get('url', 'N/A')}\n\n"
        
        if len(big_deals) > 10:
            message += f"📊 ... et {len(big_deals) - 10} autres gros rabais.\n"
            message += f"💡 Utilisez /bigdeals pour voir tous les articles.\n\n"
    
    # Afficher les erreurs de prix
    if price_errors:
        if message:
            message += "\n"
        message += f"⚠️ **Erreurs de prix détectées ({len(price_errors)} articles) :**\n\n"
        for i, error in enumerate(price_errors[:10], 1):  # Limiter à 10 pour le message
            price = error.get('price', 0)
            title = error.get('title', 'Titre inconnu')
            error_type = error.get('error_type', 'unknown')
            message += f"{i}. ⚠️ {title[:45]}...\n"
            message += f"   💰 ${price:.2f} CAD\n"
            message += f"   🔗 {error.get('url', 'N/A')}\n\n"
        
        if len(price_errors) > 10:
            message += f"📊 ... et {len(price_errors) - 10} autres erreurs.\n"
            message += f"💡 Utilisez /priceerrors pour voir tous les articles.\n\n"

    # Gérer les messages trop longs (limite Telegram: 4096 caractères)
    if len(message) > 4000:
        # Diviser le message en plusieurs parties
        parts = []
        current_part = ""
        
        sections = message.split("\n\n")
        for section in sections:
            if len(current_part) + len(section) + 2 > 4000:
                if current_part:
                    parts.append(current_part)
                current_part = section + "\n\n"
            else:
                current_part += section + "\n\n"
        
        if current_part:
            parts.append(current_part)
        
        # Envoyer chaque partie
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # Dernière partie
                await update.message.reply_text(part, parse_mode="Markdown")
            else:
                # Parties intermédiaires
                await update.message.reply_text(part + "\n_(suite...)_", parse_mode="Markdown")
    else:
        await update.message.reply_text(message, parse_mode="Markdown")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /delete - Supprime un produit surveillé."""
    user_id = str(update.effective_user.id)

    if not context.args:
        await update.message.reply_text(
            "❌ Veuillez fournir un ASIN.\n"
            "Exemple: /delete B08N5WRWNW"
        )
        return

    asin = context.args[0].upper()

    # Vérifier si le produit existe et appartient à l'utilisateur
    product = db.get_product(asin)
    if not product:
        await update.message.reply_text("❌ Produit non trouvé.")
        return

    if product['added_by'] != user_id:
        await update.message.reply_text(
            "❌ Vous n'avez pas ajouté ce produit."
        )
        return

    # Supprimer le produit
    deleted = db.delete_product(asin, user_id)
    if deleted:
        await update.message.reply_text(
            f"✅ Produit supprimé:\n📦 {product['title']}"
        )
    else:
        await update.message.reply_text("❌ Erreur lors de la suppression.")


async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /compare - Compare les prix d'un produit sur Amazon, Newegg et Memory Express."""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Inconnu"
    
    if not context.args:
        await update.message.reply_text(
            "❌ Veuillez fournir le nom d'un produit à comparer.\n\n"
            "**Exemple :**\n"
            "/compare RTX 4070\n"
            "/compare Ryzen 7 7800X3D\n"
            "/compare Samsung 980 Pro 1TB\n\n"
            "Le bot comparera automatiquement les prix toutes les 60 minutes sur :\n"
            "🛒 Amazon.ca\n"
            "🛒 Newegg.ca\n"
            "🛒 Memory Express\n"
            "🛒 Canada Computers\n"
            "🛒 Best Buy"
        )
        return
    
    product_name = " ".join(context.args)
    search_query = product_name
    
    await update.message.reply_text(
        f"⏳ Recherche de '{product_name}' sur les 5 sites...\n"
        "Cela peut prendre quelques instants."
    )
    
    # Créer une boucle d'événements pour les appels async
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Rechercher sur les 3 sites en parallèle
        amazon_result = None
        newegg_result = None
        
        # Amazon - utiliser la recherche de catégorie pour trouver le produit
        try:
            products = await amazon_scraper.get_category_products(search_query, max_products=1)
            if products:
                amazon_result = {
                    "title": products[0].get("title", product_name),
                    "price": products[0].get("current_price"),
                    "url": products[0].get("url")
                }
        except Exception as e:
            logger.error(f"Erreur recherche Amazon: {e}")
        
        # Newegg - retourne une liste de produits, prendre seulement le premier (produit principal)
        newegg_result = None
        try:
            newegg_results = await newegg_scraper.search_products(search_query, max_results=3)
            if newegg_results:
                # Prendre le premier produit (le plus pertinent)
                newegg_result = newegg_results[0]
        except Exception as e:
            logger.error(f"Erreur recherche Newegg: {e}")
        
        # Memory Express - retourne une liste de produits, prendre seulement le premier (produit principal)
        memoryexpress_result = None
        try:
            memoryexpress_results = await memoryexpress_scraper.search_products(search_query, max_results=3)
            if memoryexpress_results:
                # Prendre le premier produit (le plus pertinent)
                memoryexpress_result = memoryexpress_results[0]
        except Exception as e:
            logger.error(f"Erreur recherche Memory Express: {e}")
        
        # Canada Computers - retourne une liste de produits, prendre seulement le premier (produit principal)
        canadacomputers_result = None
        try:
            canadacomputers_results = await canadacomputers_scraper.search_products(search_query, max_results=3)
            if canadacomputers_results:
                # Prendre le premier produit (le plus pertinent)
                canadacomputers_result = canadacomputers_results[0]
        except Exception as e:
            logger.error(f"Erreur recherche Canada Computers: {e}")
        
        # Best Buy - retourne une liste de produits, prendre seulement le premier (produit principal)
        bestbuy_result = None
        try:
            bestbuy_results = await bestbuy_scraper.search_products(search_query, max_results=3)
            if bestbuy_results:
                # Prendre le premier produit (le plus pertinent)
                bestbuy_result = bestbuy_results[0]
        except Exception as e:
            logger.error(f"Erreur recherche Best Buy: {e}")
        
        # Collecter tous les prix pour trouver le meilleur (un seul par site)
        all_prices = []
        if amazon_result and amazon_result.get("price"):
            all_prices.append(("Amazon.ca", amazon_result["price"], amazon_result.get("url", ""), amazon_result.get("title", product_name)))
        
        if newegg_result and newegg_result.get("price"):
            all_prices.append(("Newegg.ca", newegg_result["price"], newegg_result.get("url", ""), newegg_result.get("title", product_name)))
        
        if memoryexpress_result and memoryexpress_result.get("price"):
            all_prices.append(("Memory Express", memoryexpress_result["price"], memoryexpress_result.get("url", ""), memoryexpress_result.get("title", product_name)))
        
        if canadacomputers_result and canadacomputers_result.get("price"):
            all_prices.append(("Canada Computers", canadacomputers_result["price"], canadacomputers_result.get("url", ""), canadacomputers_result.get("title", product_name)))
        
        if bestbuy_result and bestbuy_result.get("price"):
            all_prices.append(("Best Buy", bestbuy_result["price"], bestbuy_result.get("url", ""), bestbuy_result.get("title", product_name)))
        
        if not all_prices:
            await update.message.reply_text(
                f"❌ Aucun produit trouvé pour '{product_name}' sur les 5 sites.\n\n"
                "**Suggestions :**\n"
                "• Vérifiez l'orthographe\n"
                "• Essayez un terme plus spécifique\n"
                "• Exemple: /compare RTX 4070 au lieu de /compare carte graphique"
            )
            return
        
        # Trier par prix
        all_prices.sort(key=lambda x: x[1])
        best_site, best_price, best_url, best_title = all_prices[0]
        
        # Sauvegarder dans la base de données (garder le produit principal de chaque site)
        db.add_user(user_id, username)
        comparison_id = db.add_price_comparison(user_id, product_name, search_query)
        
        # Utiliser les résultats principaux (premier produit de chaque site)
        db.update_price_comparison(
            comparison_id,
            amazon_price=amazon_result.get("price") if amazon_result else None,
            amazon_url=amazon_result.get("url") if amazon_result else None,
            canadacomputers_price=canadacomputers_result.get("price") if canadacomputers_result else None,
            canadacomputers_url=canadacomputers_result.get("url") if canadacomputers_result else None,
            newegg_price=newegg_result.get("price") if newegg_result else None,
            newegg_url=newegg_result.get("url") if newegg_result else None,
            memoryexpress_price=memoryexpress_result.get("price") if memoryexpress_result else None,
            memoryexpress_url=memoryexpress_result.get("url") if memoryexpress_result else None,
            bestbuy_price=bestbuy_result.get("price") if bestbuy_result else None,
            bestbuy_url=bestbuy_result.get("url") if bestbuy_result else None
        )
        
        # Construire le message de comparaison avec le produit principal de chaque site
        message = f"📊 **Comparaison de prix pour : {product_name}**\n\n"
        message += f"🏆 **Meilleur prix : {best_site} - ${best_price:.2f} CAD**\n"
        message += f"🔗 {best_url}\n\n"
        
        # Afficher Amazon (produit principal)
        if amazon_result and amazon_result.get("price"):
            message += f"**🛒 Amazon.ca**\n"
            message += f"💰 ${amazon_result['price']:.2f} CAD\n"
            message += f"📦 {amazon_result.get('title', product_name)}\n"
            message += f"🔗 {amazon_result.get('url', '')}\n\n"
        else:
            message += f"**🛒 Amazon.ca**\n"
            message += f"❌ Aucun produit trouvé\n\n"
        
        # Afficher Newegg (produit principal uniquement)
        if newegg_result and newegg_result.get("price"):
            message += f"**🛒 Newegg.ca**\n"
            message += f"💰 ${newegg_result['price']:.2f} CAD\n"
            message += f"📦 {newegg_result.get('title', product_name)}\n"
            message += f"🔗 {newegg_result.get('url', '')}\n\n"
        else:
            message += f"**🛒 Newegg.ca**\n"
            message += f"❌ Aucun produit trouvé\n\n"
        
        # Afficher Memory Express (produit principal uniquement)
        if memoryexpress_result and memoryexpress_result.get("price"):
            message += f"**🛒 Memory Express**\n"
            message += f"💰 ${memoryexpress_result['price']:.2f} CAD\n"
            message += f"📦 {memoryexpress_result.get('title', product_name)}\n"
            message += f"🔗 {memoryexpress_result.get('url', '')}\n\n"
        else:
            message += f"**🛒 Memory Express**\n"
            message += f"❌ Aucun produit trouvé ou erreur de connexion\n\n"
        
        # Afficher Canada Computers (produit principal uniquement)
        if canadacomputers_result and canadacomputers_result.get("price"):
            message += f"**🛒 Canada Computers**\n"
            message += f"💰 ${canadacomputers_result['price']:.2f} CAD\n"
            message += f"📦 {canadacomputers_result.get('title', product_name)}\n"
            message += f"🔗 {canadacomputers_result.get('url', '')}\n\n"
        else:
            message += f"**🛒 Canada Computers**\n"
            message += f"❌ Aucun produit trouvé ou erreur de connexion\n\n"
        
        # Afficher Best Buy (produit principal uniquement)
        if bestbuy_result and bestbuy_result.get("price"):
            message += f"**🛒 Best Buy**\n"
            message += f"💰 ${bestbuy_result['price']:.2f} CAD\n"
            message += f"📦 {bestbuy_result.get('title', product_name)}\n"
            message += f"🔗 {bestbuy_result.get('url', '')}\n\n"
        else:
            message += f"**🛒 Best Buy**\n"
            message += f"❌ Aucun produit trouvé ou erreur de connexion\n\n"
        
        message += f"✅ Comparaison sauvegardée. Mise à jour automatique toutes les 60 minutes."
        message += f"Vous recevrez une alerte si un meilleur prix est trouvé."
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Erreur lors de la comparaison: {e}")
        await update.message.reply_text(
            f"❌ Erreur lors de la comparaison: {str(e)}"
        )
    finally:
        loop.close()


async def category_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /category - Surveille une catégorie entière."""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Inconnu"
    
    if not context.args:
        await update.message.reply_text(
            "❌ Veuillez fournir le nom d'une catégorie.\n\n"
            "**Exemples :**\n"
            "/category carte graphique\n"
            "/category processeur AMD\n"
            "/category SSD NVMe\n"
            "/category RAM DDR5\n\n"
            "**Filtres automatiques :**\n"
            "⭐ Note: 4+ étoiles\n"
            "🏷️ Marques connues uniquement\n"
            "🔧 Processeurs: Ryzen 7 et 9 uniquement (pas de Ryzen 5)\n\n"
            "Le bot surveillera tous les produits en rabais dans cette catégorie !"
        )
        return
    
    category_name = " ".join(context.args)
    
    # Vérifier si la catégorie existe déjà
    data = load_data()
    if "categories" not in data:
        data["categories"] = {}
    
    category_id = category_name.lower().replace(" ", "_")
    
    if category_id in data["categories"]:
        category = data["categories"][category_id]
        await update.message.reply_text(
            f"⚠️ Cette catégorie est déjà surveillée:\n"
            f"📂 {category['name']}\n"
            f"📊 {category.get('product_count', 0)} produits trouvés"
        )
        return
    
    # Scraper la catégorie
    await update.message.reply_text(f"⏳ Recherche des produits dans la catégorie '{category_name}'...")
    
    try:
        products = await amazon_scraper.get_category_products(category_name, max_products=30)
    except Exception as e:
        logger.error(f"Erreur lors du scraping de catégorie: {e}")
        products = []
    
    if not products:
        # Vérifier si c'est un problème de blocage Amazon
        error_msg = (
            f"❌ Aucun produit trouvé pour '{category_name}'.\n\n"
        )
        
        # Vérifier si Amazon a bloqué
        try:
            page_title = await amazon_scraper.page.title() if amazon_scraper.page else None
            if page_title and 'something went wrong' in page_title.lower():
                error_msg += (
                    "⚠️ **Amazon a détecté le bot**\n\n"
                    "Amazon.ca bloque parfois le scraping automatique.\n\n"
                    "**Solutions :**\n"
                    "1. Attendez quelques minutes et réessayez\n"
                    "2. Utilisez des termes de recherche plus spécifiques\n"
                    "3. Essayez avec un terme différent\n\n"
                    "**Exemples :**\n"
                    "/category RTX 4070\n"
                    "/category GeForce RTX\n"
                    "/category carte graphique NVIDIA\n"
                )
            else:
                error_msg += (
                    "**Filtres appliqués :**\n"
                    "⭐ Note: 4+ étoiles\n"
                    "🏷️ Marques connues uniquement\n"
                    "🔧 Processeurs: Ryzen 7 et 9 uniquement\n\n"
                    "**Suggestions :**\n"
                    "• Vérifiez l'orthographe\n"
                    "• Essayez un terme plus spécifique\n"
                    "• Exemple: /category RTX 4070 au lieu de /category nvidia\n"
                )
        except:
            error_msg += (
                "**Filtres appliqués :**\n"
                "⭐ Note: 4+ étoiles\n"
                "🏷️ Marques connues uniquement\n\n"
                "Vérifiez l'orthographe ou essayez un autre terme de recherche."
            )
        
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return
    
    # Filtrer seulement les produits en rabais
    discounted_products = [p for p in products if p.get('discount_percent') and p['discount_percent'] > 0]
    
    # Sauvegarder la catégorie
    data["categories"][category_id] = {
        "name": category_name,
        "search_query": category_name,
        "added_by": user_id,
        "added_at": datetime.now().isoformat(),
        "last_check": datetime.now().isoformat(),
        "product_count": len(products),
        "discounted_count": len(discounted_products),
        "products": {p["asin"]: {
            "title": p["title"],
            "current_price": p["current_price"],
            "original_price": p.get("original_price"),
            "discount_percent": p.get("discount_percent"),
            "url": p["url"],
            "last_seen": datetime.now().isoformat(),
        } for p in products}
    }
    
    # Ajouter la catégorie à l'utilisateur
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "username": username,
            "products": [],
            "categories": [],
        }
    if "categories" not in data["users"][user_id]:
        data["users"][user_id]["categories"] = []
    if category_id not in data["users"][user_id]["categories"]:
        data["users"][user_id]["categories"].append(category_id)
    
    save_data(data)
    
    # Message de confirmation
    message = (
        f"✅ **Catégorie ajoutée avec succès !**\n\n"
        f"📂 **{category_name}**\n"
        f"📊 {len(products)} produits trouvés\n"
        f"🎉 {len(discounted_products)} produits en rabais\n\n"
    )
    
    if discounted_products:
        # Trier par rabais décroissant
        sorted_discounts = sorted(discounted_products, key=lambda x: x.get('discount_percent', 0), reverse=True)
        
        message += f"**🎉 Tous les articles en rabais ({len(sorted_discounts)} produits) :**\n\n"
        
        # Construire la liste de tous les produits
        products_list = ""
        for i, product in enumerate(sorted_discounts, 1):
            rating_text = f"⭐ {product.get('rating', 'N/A')}" if product.get('rating') else "⭐ N/A"
            original_text = f" (Prix original: ${product.get('original_price', 0):.2f} CAD)" if product.get('original_price') else ""
            products_list += f"{i}. **{product['title'][:60]}...**\n"
            products_list += f"   💰 ${product['current_price']:.2f} CAD (-{product['discount_percent']:.1f}%){original_text}\n"
            products_list += f"   {rating_text} | 🔗 [Voir]({product['url']})\n\n"
        
        # Vérifier la longueur du message (limite Telegram: 4096 caractères)
        full_message = message + products_list + f"\n**Filtres appliqués :**\n⭐ Note: 4+ étoiles\n🏷️ Marques connues uniquement\n🔧 Processeurs: Ryzen 7 et 9 uniquement\n\n"
        full_message += f"Le bot surveillera cette catégorie toutes les {CHECK_INTERVAL_MINUTES} minutes et vous alertera pour tous les nouveaux rabais !"
        
        # Si le message est trop long, diviser en plusieurs messages
        if len(full_message) > 4000:
            # Envoyer le message principal
            await update.message.reply_text(message + f"\n**{len(sorted_discounts)} produits en rabais trouvés !**", parse_mode="Markdown")
            
            # Envoyer les produits par groupes
            current_batch = ""
            batch_num = 1
            
            for i, product in enumerate(sorted_discounts, 1):
                rating_text = f"⭐ {product.get('rating', 'N/A')}" if product.get('rating') else "⭐ N/A"
                original_text = f" (Prix original: ${product.get('original_price', 0):.2f} CAD)" if product.get('original_price') else ""
                product_line = f"{i}. **{product['title'][:60]}...**\n"
                product_line += f"   💰 ${product['current_price']:.2f} CAD (-{product['discount_percent']:.1f}%){original_text}\n"
                product_line += f"   {rating_text} | 🔗 [Voir]({product['url']})\n\n"
                
                # Si ajouter ce produit dépasse la limite, envoyer le batch actuel
                if len(current_batch) + len(product_line) > 3500:
                    await update.message.reply_text(
                        f"**📦 Rabais (suite {batch_num}) :**\n\n{current_batch}",
                        parse_mode="Markdown"
                    )
                    current_batch = product_line
                    batch_num += 1
                else:
                    current_batch += product_line
            
            # Envoyer le dernier batch
            if current_batch:
                await update.message.reply_text(
                    f"**📦 Rabais (suite {batch_num}) :**\n\n{current_batch}",
                    parse_mode="Markdown"
                )
            
            # Message final
            await update.message.reply_text(
                f"**Filtres appliqués :**\n"
                f"⭐ Note: 4+ étoiles\n"
                f"🏷️ Marques connues uniquement\n"
                f"🔧 Processeurs: Ryzen 7 et 9 uniquement\n\n"
                f"Le bot surveillera cette catégorie toutes les {CHECK_INTERVAL_MINUTES} minutes !",
                parse_mode="Markdown"
            )
        else:
            # Message assez court, tout envoyer en un seul message
            await update.message.reply_text(full_message, parse_mode="Markdown")
            return
    
    # Si pas de produits en rabais, afficher quand même le message de confirmation
    if not discounted_products:
        message += f"**Filtres appliqués :**\n"
        message += f"⭐ Note: 4+ étoiles\n"
        message += f"🏷️ Marques connues uniquement\n"
        message += f"🔧 Processeurs: Ryzen 7 et 9 uniquement\n\n"
        message += f"Le bot surveillera cette catégorie toutes les {CHECK_INTERVAL_MINUTES} minutes et vous alertera pour tous les nouveaux rabais !"
        await update.message.reply_text(message, parse_mode="Markdown")


async def scannow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /scannow - Force un scan immédiat d'Amazon.ca pour trouver des gros rabais."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    await update.message.reply_text(
        "⏳ Démarrage d'un scan immédiat d'Amazon.ca...\n"
        "Cela peut prendre quelques minutes. Je vous enverrai un message quand c'est terminé !"
    )
    
    # Lancer le scan en arrière-plan
    try:
        # Utiliser l'application globale
        if global_application is None:
            await update.message.reply_text(
                "❌ Erreur: Application non initialisée. Veuillez redémarrer le bot."
            )
            return
        
        # Lancer le scan dans un thread séparé pour ne pas bloquer
        import threading
        def run_scan():
            try:
                scan_amazon_globally(global_application, notify_chat_id=chat_id)
            except Exception as e:
                logger.error(f"Erreur lors du scan: {e}")
                # Envoyer un message d'erreur à l'utilisateur
                try:
                    global_application.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Erreur lors du scan: {str(e)}"
                    )
                except:
                    pass
        
        scan_thread = threading.Thread(target=run_scan, daemon=True)
        scan_thread.start()
        
        await update.message.reply_text(
            "✅ Scan lancé en arrière-plan ! Vous recevrez une notification à la fin du scan."
        )
    except Exception as e:
        logger.error(f"Erreur lors du scan immédiat: {e}")
        await update.message.reply_text(
            f"❌ Erreur lors du scan: {str(e)}"
        )


async def bigdeals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /bigdeals - Affiche les gros rabais détectés."""
    big_deals = db.get_all_big_deals()
    
    if not big_deals:
        await update.message.reply_text(
            f"📭 Aucun gros rabais détecté pour le moment.\n\n"
            f"Le bot scanne automatiquement Amazon.ca toutes les {GLOBAL_SCAN_INTERVAL_MINUTES} minutes "
            f"pour trouver des rabais >{BIG_DISCOUNT_THRESHOLD}%.\n\n"
            f"💡 **Astuce:** Utilisez /scannow pour forcer un scan immédiat !\n\n"
            f"Les gros rabais seront affichés ici automatiquement !"
        )
        return
    
    # Trier par pourcentage de rabais décroissant
    sorted_deals = sorted(
        big_deals,
        key=lambda x: x.get("discount_percent", 0),
        reverse=True
    )
    
    # Diviser en plusieurs messages si nécessaire (limite Telegram: 4096 caractères)
    MAX_MESSAGE_LENGTH = 4000  # Laisser une marge
    current_message = f"🔥 **Gros rabais détectés ({len(sorted_deals)}) :**\n\n"
    batch_num = 1
    item_num = 1
    
    for deal in sorted_deals:
        deal_text = (
            f"{item_num}. **{deal['title'][:50]}...**\n"
            f"   💰 ${deal['current_price']:.2f} CAD "
            f"(-{deal['discount_percent']:.1f}%)\n"
            f"   💵 Prix original: ${deal['original_price']:.2f} CAD\n"
            f"   🔗 [Voir]({deal['url']})\n\n"
        )
        
        # Si ajouter ce deal dépasse la limite, envoyer le message actuel et commencer un nouveau
        if len(current_message) + len(deal_text) > MAX_MESSAGE_LENGTH:
            if batch_num == 1:
                # Premier message - enlever le titre pour le remettre dans le nouveau message
                current_message = current_message.replace(f"🔥 **Gros rabais détectés ({len(sorted_deals)}) :**\n\n", "")
                await update.message.reply_text(
                    f"🔥 **Gros rabais détectés ({len(sorted_deals)}) - Partie {batch_num} :**\n\n{current_message}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"**📦 Gros rabais (suite {batch_num}) :**\n\n{current_message}",
                    parse_mode="Markdown"
                )
            current_message = deal_text
            batch_num += 1
        else:
            current_message += deal_text
        
        item_num += 1
    
    # Envoyer le dernier message
    if current_message:
        if batch_num == 1:
            await update.message.reply_text(current_message, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"**📦 Gros rabais (suite {batch_num}) :**\n\n{current_message}",
                parse_mode="Markdown"
            )


async def priceerrors_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /priceerrors - Affiche les erreurs de prix détectées sur tout Amazon.ca."""
    # Récupérer les erreurs récentes (dernières 48h)
    price_errors = db.get_price_errors(days=2)
    
    if not price_errors:
        await update.message.reply_text(
            f"✅ Aucune erreur de prix détectée.\n\n"
            f"Le bot scanne automatiquement Amazon.ca toutes les {GLOBAL_SCAN_INTERVAL_MINUTES} minutes "
            f"pour détecter les prix suspects.\n\n"
            f"Les erreurs de prix seront affichées ici automatiquement !"
        )
        return
    
    # Trier par confiance décroissante
    sorted_errors = sorted(
        price_errors,
        key=lambda x: x.get("confidence", 0),
        reverse=True
    )
    
    # Diviser en plusieurs messages si nécessaire (limite Telegram: 4096 caractères)
    MAX_MESSAGE_LENGTH = 4000  # Laisser une marge
    current_message = f"⚠️ **Erreurs de prix détectées sur Amazon.ca ({len(sorted_errors)} récentes) :**\n\n"
    batch_num = 1
    item_num = 1
    
    for error in sorted_errors:
        error_type_text = {
            'price_too_low': 'Prix trop bas',
            'price_below_expected': 'Sous la fourchette attendue',
            'suspicious_drop': 'Chute suspecte',
            'price_too_high': 'Prix trop élevé',
        }.get(error.get('error_type', ''), 'Erreur inconnue')
        
        confidence = error.get('confidence', 0) * 100
        category_text = f"📂 {error.get('category', 'N/A')}" if error.get('category') else ""
        
        error_text = (
            f"{item_num}. **{error['title'][:45]}...**\n"
            f"   💰 Prix: ${error['price']:.2f} CAD\n"
            f"   ⚠️ Type: {error_type_text} ({confidence:.0f}% confiance)\n"
        )
        if category_text:
            error_text += f"   {category_text}\n"
        error_text += f"   🔗 [Vérifier]({error['url']})\n\n"
        
        # Si ajouter cette erreur dépasse la limite, envoyer le message actuel et commencer un nouveau
        if len(current_message) + len(error_text) > MAX_MESSAGE_LENGTH:
            if batch_num == 1:
                # Premier message - enlever le titre pour le remettre dans le nouveau message
                current_message = current_message.replace(f"⚠️ **Erreurs de prix détectées sur Amazon.ca ({len(sorted_errors)} récentes) :**\n\n", "")
                await update.message.reply_text(
                    f"⚠️ **Erreurs de prix détectées ({len(sorted_errors)} récentes) - Partie {batch_num} :**\n\n{current_message}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"**⚠️ Erreurs de prix (suite {batch_num}) :**\n\n{current_message}",
                    parse_mode="Markdown"
                )
            current_message = error_text
            batch_num += 1
        else:
            current_message += error_text
        
        item_num += 1
    
    # Envoyer le dernier message
    if current_message:
        if batch_num == 1:
            # Ajouter les messages finaux seulement au dernier message
            current_message += f"\n💡 Vérifiez si ce sont de vraies erreurs ou des rabais exceptionnels !"
            current_message += f"\n⏰ Prochain scan dans ~{GLOBAL_SCAN_INTERVAL_MINUTES} minutes"
            await update.message.reply_text(current_message, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"**⚠️ Erreurs de prix (suite {batch_num}) :**\n\n{current_message}",
                parse_mode="Markdown"
            )
            # Envoyer les messages finaux séparément
            await update.message.reply_text(
                f"💡 Vérifiez si ce sont de vraies erreurs ou des rabais exceptionnels !\n"
                f"⏰ Prochain scan dans ~{GLOBAL_SCAN_INTERVAL_MINUTES} minutes"
            )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /settings - Configure les seuils de détection."""
    user_id = str(update.effective_user.id)
    
    # Récupérer les paramètres depuis la DB
    user_settings = db.get_user_settings(user_id)
    
    # Valeurs par défaut si pas de paramètres
    big_discount_threshold = user_settings.get('big_discount_threshold') or BIG_DISCOUNT_THRESHOLD
    price_error_threshold = user_settings.get('price_error_threshold') or PRICE_ERROR_THRESHOLD
    
    if not context.args:
        # Afficher les paramètres actuels
        message = (
            f"⚙️ **Vos paramètres de détection :**\n\n"
            f"🔥 Seuil gros rabais: {big_discount_threshold}%\n"
            f"⚠️ Seuil erreur de prix: {price_error_threshold * 100:.0f}%\n\n"
            f"**Pour modifier :**\n"
            f"/settings bigdiscount [pourcentage]\n"
            f"Exemple: /settings bigdiscount 40\n\n"
            f"/settings errorthreshold [pourcentage]\n"
            f"Exemple: /settings errorthreshold 30"
        )
        await update.message.reply_text(message, parse_mode="Markdown")
        return
    
    # Modifier les paramètres
    if len(context.args) >= 2:
        setting_type = context.args[0].lower()
        try:
            value = float(context.args[1])
            
            if setting_type == "bigdiscount":
                db.update_user_settings(user_id, big_discount_threshold=value)
                await update.message.reply_text(
                    f"✅ Seuil gros rabais modifié à {value}%"
                )
            elif setting_type == "errorthreshold":
                db.update_user_settings(user_id, price_error_threshold=value / 100)
                await update.message.reply_text(
                    f"✅ Seuil erreur de prix modifié à {value}%"
                )
            else:
                await update.message.reply_text(
                    "❌ Paramètre inconnu. Utilisez 'bigdiscount' ou 'errorthreshold'"
                )
        except ValueError:
            await update.message.reply_text("❌ Valeur invalide. Utilisez un nombre.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /stats - Affiche les statistiques du bot."""
    stats = db.get_stats()
    
    message = (
        f"📊 **Statistiques du Bot**\n\n"
        f"👥 Utilisateurs: {stats['total_users']}\n"
        f"📦 Produits surveillés: {stats['total_products']}\n"
        f"📂 Catégories surveillées: {stats['total_categories']}\n"
        f"🔥 Gros rabais (7j): {stats['big_deals_7d']}\n"
        f"⚠️ Erreurs de prix (7j): {stats['price_errors_7d']}\n"
        f"📈 Enregistrements de prix: {stats['total_price_records']}\n"
        f"💰 Prix moyen: ${stats['avg_price']:.2f} CAD\n\n"
        f"💡 Le bot surveille automatiquement les prix et détecte les meilleures offres !"
    )
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /history [ASIN ou numéro] - Affiche l'historique des prix d'un produit."""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        # Afficher la liste des produits surveillés par l'utilisateur
        user_products = db.get_user_products(user_id)
        
        if not user_products:
            await update.message.reply_text(
                "❌ Vous n'avez aucun produit surveillé.\n\n"
                "**Utilisation :**\n"
                "• `/history [ASIN]` - Voir l'historique d'un produit par ASIN\n"
                "• `/history [numéro]` - Voir l'historique d'un produit de votre liste\n"
                "• `/history` - Afficher cette liste\n\n"
                "**Exemple :**\n"
                "`/history B08N5WRWNW`\n"
                "ou `/history 1` pour le premier produit de votre liste"
            )
            return
        
        # Construire la liste des produits
        message = "📦 **Vos produits surveillés :**\n\n"
        message += "Envoyez `/history [numéro]` pour voir l'historique d'un produit,\n"
        message += "ou `/history [ASIN]` pour un produit spécifique.\n\n"
        
        for i, product in enumerate(user_products, 1):
            price_text = f"${product['last_price']:.2f} CAD" if product.get('last_price') else "Non disponible"
            message += f"{i}. **{product['title'][:50]}...**\n"
            message += f"   💰 Prix actuel: {price_text}\n"
            message += f"   🆔 ASIN: `{product['asin']}`\n"
            message += f"   📊 `/history {i}` ou `/history {product['asin']}`\n\n"
        
        message += "**Exemples :**\n"
        message += f"• `/history 1` - Historique du premier produit\n"
        message += f"• `/history {user_products[0]['asin']}` - Par ASIN"
        
        await update.message.reply_text(message, parse_mode="Markdown")
        return
    
    # Récupérer l'argument (peut être un numéro ou un ASIN)
    arg = context.args[0].strip()
    
    # Vérifier si c'est un numéro (choix depuis la liste)
    if arg.isdigit():
        user_products = db.get_user_products(user_id)
        product_index = int(arg) - 1  # Convertir en index (0-based)
        
        if product_index < 0 or product_index >= len(user_products):
            await update.message.reply_text(
                f"❌ Numéro invalide. Veuillez choisir un numéro entre 1 et {len(user_products)}.\n\n"
                f"Utilisez `/history` pour voir la liste de vos produits."
            )
            return
        
        product = user_products[product_index]
        asin = product['asin']
    else:
        # C'est un ASIN
        asin = arg.upper()
        product = db.get_product(asin)
        
        if not product:
            await update.message.reply_text(
                f"❌ Produit non trouvé pour l'ASIN: {asin}\n\n"
                "**Options :**\n"
                "• Utilisez `/history` pour voir vos produits surveillés\n"
                "• Utilisez `/add {asin}` pour ajouter ce produit à surveiller"
            )
            return
    
    # Récupérer l'historique (30 derniers jours par défaut)
    days = 30
    if len(context.args) > 1:
        try:
            days = int(context.args[1])
            days = min(days, 90)  # Limiter à 90 jours max
        except ValueError:
            pass
    
    history = db.get_price_history(asin, days=days)
    
    if not history:
        await update.message.reply_text(
            f"📭 Aucun historique de prix disponible pour ce produit.\n\n"
            f"📦 {product['title']}\n"
            f"💰 Prix actuel: ${product.get('last_price', 0):.2f} CAD"
        )
        return
    
    # Construire le message
    message = (
        f"📈 **Historique des prix**\n\n"
        f"📦 {product['title']}\n"
        f"🆔 ASIN: {asin}\n\n"
        f"**Prix ({len(history)} enregistrements, {days} derniers jours) :**\n\n"
    )
    
    # Afficher les 10 derniers prix (ou moins si le message est trop long)
    for i, record in enumerate(history[:10], 1):
        date = datetime.fromisoformat(record['recorded_at']).strftime("%Y-%m-%d %H:%M")
        price_text = f"${record['price']:.2f} CAD"
        
        if record.get('original_price'):
            discount = ((record['original_price'] - record['price']) / record['original_price']) * 100
            price_text += f" (rabais: -{discount:.1f}%)"
        
        stock_text = "✅" if record.get('in_stock') else "❌"
        message += f"{i}. {date}: {price_text} {stock_text}\n"
    
    if len(history) > 10:
        message += f"\n... et {len(history) - 10} autres enregistrements"
    
    # Ajouter les statistiques
    prices = [r['price'] for r in history]
    if prices:
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        current_price = product.get('last_price', 0)
        
        # Trouver le prix le plus bas enregistré par le bot
        bot_lowest_price = min_price
        bot_lowest_records = [r for r in history if r['price'] == min_price]
        bot_lowest_date = None
        if bot_lowest_records:
            bot_lowest_date = datetime.fromisoformat(bot_lowest_records[0]['recorded_at']).strftime("%Y-%m-%d")
        
        # Trouver les périodes de rabais (quand original_price existe et est supérieur au prix actuel)
        discount_periods = []
        for record in history:
            if record.get('original_price') and record['original_price'] > record['price']:
                date = datetime.fromisoformat(record['recorded_at']).strftime("%Y-%m-%d %H:%M")
                discount = ((record['original_price'] - record['price']) / record['original_price']) * 100
                discount_periods.append({
                    'date': date,
                    'price': record['price'],
                    'original_price': record['original_price'],
                    'discount': discount
                })
        
        # Trier les rabais par date (plus récent en premier)
        # Convertir la date pour le tri
        for period in discount_periods:
            try:
                period['sort_date'] = datetime.strptime(period['date'], "%Y-%m-%d %H:%M")
            except:
                period['sort_date'] = datetime.now()
        discount_periods.sort(key=lambda x: x['sort_date'], reverse=True)
        
        # Trouver le prix le plus bas enregistré par le bot
        bot_lowest_price = min_price
        bot_lowest_records = [r for r in history if r['price'] == min_price]
        bot_lowest_date = None
        if bot_lowest_records:
            bot_lowest_date = datetime.fromisoformat(bot_lowest_records[0]['recorded_at']).strftime("%Y-%m-%d")
        
        # Afficher les statistiques (seulement Bot)
        message += (
            f"\n\n**Statistiques :**\n"
            f"💰 Prix actuel: ${current_price:.2f} CAD\n"
        )
        
        # Afficher le prix le plus bas enregistré par le bot
        if bot_lowest_price:
            message += f"🤖 Prix le plus bas (Bot): ${bot_lowest_price:.2f} CAD"
            if bot_lowest_date:
                try:
                    date_obj = datetime.strptime(bot_lowest_date, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%b %d, %Y")
                    message += f" ({formatted_date})"
                except:
                    message += f" ({bot_lowest_date})"
            message += "\n"
        
        message += (
            f"📈 Prix maximum: ${max_price:.2f} CAD\n"
            f"📊 Prix moyen: ${avg_price:.2f} CAD"
        )
        
        # Ajouter les périodes de rabais
        if discount_periods:
            message += f"\n\n**🎉 Périodes de rabais détectées ({len(discount_periods)} enregistrements) :**\n"
            
            # Afficher les 5 rabais les plus récents
            for i, period in enumerate(discount_periods[:5], 1):
                message += (
                    f"{i}. 📅 {period['date']}\n"
                    f"   💰 ${period['price']:.2f} CAD "
                    f"(rabais: -{period['discount']:.1f}%)\n"
                    f"   💵 Prix original: ${period['original_price']:.2f} CAD\n"
                )
            
            if len(discount_periods) > 5:
                message += f"\n   ... et {len(discount_periods) - 5} autres périodes de rabais"
            
            # Trouver le meilleur rabais
            best_discount = max(discount_periods, key=lambda x: x['discount'])
            message += (
                f"\n\n**🔥 Meilleur rabais :**\n"
                f"📅 {best_discount['date']}\n"
                f"💰 ${best_discount['price']:.2f} CAD "
                f"(-{best_discount['discount']:.1f}%)\n"
                f"💵 Prix original: ${best_discount['original_price']:.2f} CAD"
            )
    
    message += f"\n\n🔗 {product['url']}"
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Commande /help - Affiche l'aide."""
    help_text = f"""
📖 **Aide - Commandes disponibles**

/start - Message d'accueil
/add [lien ou ASIN] - Ajouter un produit à surveiller
/category [nom] - Surveiller une catégorie entière
/compare [produit] - Comparer les prix sur Amazon et Newegg
/list - Voir tous vos produits et catégories surveillés
/delete [ASIN] - Supprimer un produit
/history [numéro ou ASIN] - Voir l'historique des prix (choisir depuis votre liste ou ASIN)
/stats - Voir les statistiques du bot
/bigdeals - Voir les gros rabais détectés
/priceerrors - Voir les erreurs de prix détectées
/settings - Configurer les seuils de détection
/help - Afficher cette aide

**Exemples :**
/add B08N5WRWNW
/add https://www.amazon.ca/dp/B08N5WRWNW
/category carte graphique
/category processeur AMD
/compare RTX 4070
/compare Ryzen 7 7800X3D
/delete B08N5WRWNW
/settings bigdiscount 40

**Surveillance de catégories :**
Le bot surveille tous les produits en rabais dans la catégorie et vous alerte pour chaque nouveau rabais trouvé !

**Filtres automatiques :**
⭐ Note: 4+ étoiles uniquement
🏷️ Marques connues uniquement (NVIDIA, AMD, ASUS, MSI, Corsair, Samsung, etc.)
🔧 Processeurs: Ryzen 7 et 9 uniquement (pas de Ryzen 5)

**Comparaison de prix multi-sites :**
🛒 /compare - Compare automatiquement les prix sur Amazon.ca, Newegg.ca et Memory Express
⏰ Vérification automatique toutes les 60 minutes
🎉 Alerte si un meilleur prix est trouvé

**Détection intelligente :**
🔥 Gros rabais: Alerte automatique pour rabais >{BIG_DISCOUNT_THRESHOLD}%
⚠️ Erreurs de prix: Détection des prix anormalement bas/élevés

Le bot vérifie automatiquement les prix toutes les {CHECK_INTERVAL_MINUTES} minutes.

**Note:** Ce bot utilise Playwright (gratuit) pour scraper Amazon.ca directement.
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


