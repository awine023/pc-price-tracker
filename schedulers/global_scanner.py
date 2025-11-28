"""Scanner global d'Amazon.ca pour détecter gros rabais et erreurs de prix."""
import asyncio
import logging
import time
from typing import Optional
from telegram.ext import Application

from utils.helpers import load_data, send_message_sync
from database import db
from config import POPULAR_CATEGORIES, BIG_DISCOUNT_THRESHOLD, PRICE_ERROR_THRESHOLD, MIN_PRICE_FOR_ERROR
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

def scan_amazon_globally(app: Application, notify_chat_id: Optional[int] = None) -> None:
    """Scanne Amazon.ca globalement pour détecter gros rabais et erreurs de prix."""
    logger.info("🌍 Démarrage du scan global d'Amazon.ca...")
    
    data = load_data()
    
    # Créer une nouvelle boucle d'événements pour les appels async
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    big_deals_count = 0
    price_errors_count = 0
    
    try:
        for category_name in POPULAR_CATEGORIES:
            try:
                logger.info(f"🔍 Scan de la catégorie: {category_name}")
                
                # Réinitialiser le navigateur avant chaque catégorie pour éviter les problèmes
                try:
                    loop.run_until_complete(amazon_scraper.close_browser())
                except Exception as e:
                    logger.debug(f"Erreur lors de la fermeture du navigateur (non critique): {e}")
                time.sleep(1)  # Petite pause
                
                # Scraper la catégorie
                products = loop.run_until_complete(
                    amazon_scraper.get_category_products(category_name, max_products=50)
                )
                
                if not products:
                    logger.warning(f"Aucun produit trouvé pour {category_name}")
                    continue
                
                logger.info(f"✅ {len(products)} produits trouvés dans {category_name}")
                
                # Analyser chaque produit
                for product in products:
                    try:
                        asin = product.get("asin")
                        if not asin:
                            continue
                        
                        current_price = product.get("current_price")
                        original_price = product.get("original_price")
                        
                        if not current_price:
                            continue
                        
                        # Analyser le prix
                        expected_range = price_analyzer.get_expected_price_range(
                            product['title'],
                            category=category_name
                        )
                        
                        analysis = price_analyzer.analyze_price(
                            current_price=current_price,
                            original_price=original_price,
                            last_price=None,  # Pas de prix précédent pour scan global
                            expected_price_range=expected_range,
                            product_title=product['title'],
                        )
                        
                        # Détecter les erreurs de prix
                        if analysis['is_price_error']:
                            error_type = analysis['error_type']
                            
                            # Vérifier si on a déjà détecté cette erreur récemment (24h)
                            existing_error = db.get_price_errors(limit=1)
                            existing_asin = None
                            for err in existing_error:
                                if err.get('asin') == asin:
                                    existing_asin = err
                                    break
                            
                            if existing_asin:
                                detected_at = datetime.fromisoformat(existing_asin.get('detected_at', datetime.now().isoformat()))
                                if (datetime.now() - detected_at).total_seconds() < 86400:
                                    continue
                            
                            # Enregistrer l'erreur dans la DB
                            db.add_price_error(
                                asin=asin,
                                title=product['title'],
                                price=current_price,
                                error_type=error_type,
                                confidence=analysis['confidence'],
                                url=product['url'],
                                category=category_name
                            )
                            
                            logger.info(f"⚠️ Erreur de prix détectée: {product['title'][:50]}... (${current_price:.2f})")
                            price_errors_count += 1
                        
                        # Détecter les gros rabais
                        # Vérifier aussi directement le discount_percent du produit (plus fiable)
                        product_discount = product.get('discount_percent')
                        if product_discount and product_discount >= BIG_DISCOUNT_THRESHOLD:
                            # Utiliser le rabais du produit directement
                            discount_percent = product_discount
                            
                            # Vérifier si on a déjà détecté ce rabais récemment (24h)
                            existing_deals = db.get_all_big_deals()
                            existing_deal = None
                            for deal in existing_deals:
                                if deal.get('asin') == asin:
                                    existing_deal = deal
                                    break
                            
                            if existing_deal:
                                detected_at = datetime.fromisoformat(existing_deal.get('detected_at', datetime.now().isoformat()))
                                if (datetime.now() - detected_at).total_seconds() < 86400:
                                    continue
                            
                            # Enregistrer le gros rabais dans la DB
                            db.add_big_deal(
                                asin=asin,
                                title=product['title'],
                                original_price=original_price or current_price / (1 - discount_percent / 100),
                                current_price=current_price,
                                discount_percent=discount_percent,
                                url=product['url'],
                                category=category_name
                            )
                            
                            logger.info(f"🔥 Gros rabais détecté: {product['title'][:50]}... (-{discount_percent:.1f}%)")
                            big_deals_count += 1
                        
                        # Aussi vérifier via l'analyseur (fallback)
                        elif analysis['is_big_discount']:
                            discount_percent = analysis['discount_percent']
                            
                            # Vérifier si on a déjà détecté ce rabais récemment (24h)
                            existing_deals = db.get_all_big_deals()
                            existing_deal = None
                            for deal in existing_deals:
                                if deal.get('asin') == asin:
                                    existing_deal = deal
                                    break
                            
                            if existing_deal:
                                detected_at = datetime.fromisoformat(existing_deal.get('detected_at', datetime.now().isoformat()))
                                if (datetime.now() - detected_at).total_seconds() < 86400:
                                    continue
                            
                            # Enregistrer le gros rabais dans la DB
                            db.add_big_deal(
                                asin=asin,
                                title=product['title'],
                                original_price=original_price,
                                current_price=current_price,
                                discount_percent=discount_percent,
                                url=product['url'],
                                category=category_name
                            )
                            
                            logger.info(f"🔥 Gros rabais détecté (via analyseur): {product['title'][:50]}... (-{discount_percent:.1f}%)")
                            big_deals_count += 1
                    
                    except Exception as e:
                        logger.error(f"Erreur lors de l'analyse du produit {product.get('asin', 'unknown')}: {e}")
                        continue
                
                # Pause entre les catégories pour éviter le rate limiting
                time.sleep(5)
            
            except Exception as e:
                logger.error(f"Erreur lors du scan de la catégorie {category_name}: {e}")
                continue
        
        logger.info("✅ Scan global terminé")
        
        # Envoyer une notification à l'utilisateur si demandé
        if notify_chat_id is not None:
            try:
                message = (
                    f"✅ **Scan terminé !**\n\n"
                    f"🔍 Scan de {len(POPULAR_CATEGORIES)} catégories complété.\n\n"
                )
                
                if big_deals_count > 0 or price_errors_count > 0:
                    message += (
                        f"📊 **Résultats :**\n"
                        f"🔥 Gros rabais détectés: {big_deals_count}\n"
                        f"⚠️ Erreurs de prix détectées: {price_errors_count}\n\n"
                    )
                
                message += (
                    f"💡 **Commandes disponibles :**\n"
                    f"• `/bigdeals` - Voir tous les gros rabais détectés\n"
                    f"• `/priceerrors` - Voir toutes les erreurs de prix détectées\n\n"
                    f"Utilisez ces commandes pour voir les détails !"
                )
                
                send_message_sync(app, notify_chat_id, message, loop)
                logger.info(f"✅ Notification envoyée à {notify_chat_id} après le scan")
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi de la notification: {e}")
    
    finally:
        loop.close()


