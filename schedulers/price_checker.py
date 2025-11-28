"""Vérification périodique des prix des produits surveillés."""
import asyncio
import logging
from datetime import datetime
from telegram.ext import Application

from utils.helpers import load_data, send_message_sync
from database import db
from scrapers import AmazonScraper
from price_analyzer import PriceAnalyzer

logger = logging.getLogger(__name__)

# Les scrapers seront passés depuis bot.py
amazon_scraper = None
price_analyzer = None

def set_scrapers(amazon, analyzer):
    """Configure les scrapers depuis bot.py."""
    global amazon_scraper, price_analyzer
    amazon_scraper = amazon
    price_analyzer = analyzer

def check_prices(app: Application) -> None:
    """Vérifie les prix de tous les produits et catégories et envoie des alertes."""
    data = load_data()
    products = data.get("products", {})
    categories = data.get("categories", {})

    if not products and not categories:
        return

    logger.info(f"Vérification de {len(products)} produits et {len(categories)} catégories...")

    # Créer une nouvelle boucle d'événements pour les appels async
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        for asin, product_data in products.items():
            try:
                # Récupérer les nouvelles informations
                product_info = loop.run_until_complete(amazon_scraper.get_product_info(asin))
                if not product_info:
                    continue

                current_price = product_info.get("current_price")
                last_price = product_data.get("last_price")
                
                # Mettre à jour le prix historique Amazon si disponible
                if product_info.get("amazon_lowest_price"):
                    db.update_product_amazon_lowest(
                        asin=asin,
                        amazon_lowest_price=product_info["amazon_lowest_price"],
                        amazon_lowest_date=product_info.get("amazon_lowest_date")
                    )

                # Mettre à jour le dernier prix
                product_data["last_price"] = current_price
                product_data["last_check"] = datetime.now().isoformat()

                # Analyser le prix pour détecter gros rabais et erreurs
                expected_range = price_analyzer.get_expected_price_range(
                    product_info['title'],
                    category=None
                )
                
                analysis = price_analyzer.analyze_price(
                    current_price=current_price,
                    original_price=product_info.get('original_price'),
                    last_price=last_price,
                    expected_price_range=expected_range,
                    product_title=product_info['title'],
                )

                # Détecter les erreurs de prix (priorité haute)
                if analysis['is_price_error']:
                    error_type = analysis['error_type']
                    error_message = (
                        f"⚠️ **ERREUR DE PRIX DÉTECTÉE !**\n\n"
                        f"📦 {product_info['title']}\n"
                        f"💰 Prix actuel: ${current_price:.2f} CAD\n"
                    )
                    
                    if error_type == 'price_too_low':
                        error_message += f"⚠️ Prix anormalement bas (${current_price:.2f} CAD)\n"
                    elif error_type == 'price_below_expected':
                        error_message += f"⚠️ Prix bien en dessous de la fourchette attendue\n"
                    elif error_type == 'suspicious_drop':
                        error_message += f"⚠️ Chute de prix suspecte détectée\n"
                    
                    error_message += f"🔗 {product_info['url']}\n\n"
                    error_message += f"💡 Vérifiez si c'est une vraie erreur ou un rabais exceptionnel !"
                    
                    # Enregistrer l'erreur
                    data["price_errors"][asin] = {
                        "title": product_info['title'],
                        "price": current_price,
                        "error_type": error_type,
                        "confidence": analysis['confidence'],
                        "detected_at": datetime.now().isoformat(),
                        "url": product_info['url'],
                    }
                    
                    # Envoyer l'alerte à tous les utilisateurs
                    for user_id, user_data in data["users"].items():
                        if asin in user_data.get("products", []):
                            send_message_sync(app, int(user_id), error_message, loop)
                            logger.info(f"⚠️ Alerte erreur de prix envoyée à {user_id} pour {asin}")

                # Détecter les gros rabais
                elif analysis['is_big_discount']:
                    discount_percent = analysis['discount_percent']
                    original_price = product_info.get('original_price')
                    
                    big_deal_message = (
                        f"🔥 **GROS RABAIS DÉTECTÉ !**\n\n"
                        f"📦 {product_info['title']}\n"
                        f"💰 Prix original: ${original_price:.2f} CAD\n"
                        f"💰 Prix actuel: ${current_price:.2f} CAD\n"
                        f"🎯 **RABAIS: -{discount_percent:.1f}%**\n"
                        f"💵 Économie: ${original_price - current_price:.2f} CAD\n"
                    )
                    
                    stock_text = "✅ En stock" if product_info.get('in_stock') else "❌ Rupture de stock"
                    big_deal_message += f"📦 Stock: {stock_text}\n"
                    big_deal_message += f"🔗 {product_info['url']}"
                    
                    # Enregistrer le gros rabais
                    data["big_deals"][asin] = {
                        "title": product_info['title'],
                        "original_price": original_price,
                        "current_price": current_price,
                        "discount_percent": discount_percent,
                        "detected_at": datetime.now().isoformat(),
                        "url": product_info['url'],
                    }
                    
                    # Envoyer l'alerte à tous les utilisateurs
                    for user_id, user_data in data["users"].items():
                        if asin in user_data.get("products", []):
                            send_message_sync(app, int(user_id), big_deal_message, loop)
                            logger.info(f"🔥 Alerte gros rabais envoyée à {user_id} pour {asin}")

                # Vérifier si le prix a baissé (alerte normale)
                elif current_price and last_price and current_price < last_price:
                    price_drop = last_price - current_price
                    percent_drop = (price_drop / last_price) * 100

                    # Trouver tous les utilisateurs qui surveillent ce produit
                    stock_text = "✅ En stock" if product_info.get('in_stock') else "❌ Rupture de stock"
                    alert_message = (
                        f"🔔 **Alerte de baisse de prix !**\n\n"
                        f"📦 {product_info['title']}\n"
                        f"💰 Prix précédent: ${last_price:.2f} CAD\n"
                        f"💰 Prix actuel: ${current_price:.2f} CAD\n"
                        f"📉 Baisse: ${price_drop:.2f} CAD ({percent_drop:.1f}%)\n"
                        f"📦 Stock: {stock_text}\n"
                        f"🔗 {product_info['url']}"
                    )

                    # Envoyer l'alerte à tous les utilisateurs
                    for user_id, user_data in data["users"].items():
                        if asin in user_data.get("products", []):
                            send_message_sync(app, int(user_id), alert_message, loop)
                            logger.info(f"Alerte envoyée à l'utilisateur {user_id} pour {asin}")

                save_data(data)
                time.sleep(2)  # Pause entre les requêtes

            except Exception as e:
                logger.error(f"Erreur lors de la vérification du produit {asin}: {e}")
        
        # Vérifier les catégories
        for category_id, category_data in categories.items():
            try:
                logger.info(f"Vérification de la catégorie: {category_data['name']}")
                
                # Scraper la catégorie
                products = loop.run_until_complete(
                    amazon_scraper.get_category_products(category_data['search_query'], max_products=30)
                )
                
                if not products:
                    continue
                
                # Filtrer les produits en rabais
                discounted_products = [p for p in products if p.get('discount_percent') and p['discount_percent'] > 0]
                
                # Comparer avec les produits déjà connus
                known_products = category_data.get("products", {})
                new_discounts = []
                
                for product in discounted_products:
                    asin = product["asin"]
                    
                    # Si nouveau produit ou nouveau rabais
                    if asin not in known_products:
                        new_discounts.append(product)
                    else:
                        # Vérifier si le rabais a augmenté
                        known_product = known_products[asin]
                        known_discount = known_product.get("discount_percent", 0)
                        new_discount = product.get("discount_percent", 0)
                        
                        if new_discount > known_discount:
                            new_discounts.append(product)
                
                # Mettre à jour les produits connus
                for product in products:
                    asin = product["asin"]
                    category_data["products"][asin] = {
                        "title": product["title"],
                        "current_price": product["current_price"],
                        "original_price": product.get("original_price"),
                        "discount_percent": product.get("discount_percent"),
                        "url": product["url"],
                        "last_seen": datetime.now().isoformat(),
                    }
                
                category_data["product_count"] = len(products)
                category_data["discounted_count"] = len(discounted_products)
                category_data["last_check"] = datetime.now().isoformat()
                
                # Envoyer des alertes pour les nouveaux rabais
                if new_discounts:
                    for product in new_discounts:
                        rating_text = f"⭐ {product.get('rating', 'N/A')}" if product.get('rating') else ""
                        alert_message = (
                            f"🎉 **Nouveau rabais dans '{category_data['name']}' !**\n\n"
                            f"📦 {product['title']}\n"
                            f"💰 Prix: ${product['current_price']:.2f} CAD\n"
                        )
                        
                        if product.get('original_price'):
                            alert_message += f"💵 Prix original: ${product['original_price']:.2f} CAD\n"
                        
                        if product.get('discount_percent'):
                            alert_message += f"🎯 Rabais: -{product['discount_percent']:.1f}%\n"
                        
                        if rating_text:
                            alert_message += f"{rating_text}\n"
                        
                        alert_message += f"🔗 {product['url']}"
                        
                        # Envoyer à tous les utilisateurs qui surveillent cette catégorie
                        for user_id, user_data in data["users"].items():
                            if category_id in user_data.get("categories", []):
                                send_message_sync(app, int(user_id), alert_message, loop)
                                logger.info(f"Alerte catégorie envoyée à {user_id} pour {product['asin']}")
                
                save_data(data)
                time.sleep(3)  # Pause entre les catégories
                
            except Exception as e:
                logger.error(f"Erreur lors de la vérification de la catégorie {category_id}: {e}")
    
    finally:
        loop.close()


