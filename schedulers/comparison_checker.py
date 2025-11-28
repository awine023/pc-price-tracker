"""Vérification périodique des comparaisons de prix entre sites."""
import asyncio
import logging
from datetime import datetime
from telegram.ext import Application

from utils.helpers import send_message_sync
from database import db
from scrapers import AmazonScraper, NeweggScraper, MemoryExpressScraper, CanadaComputersScraper, BestBuyScraper

logger = logging.getLogger(__name__)

# Les scrapers seront passés depuis bot.py
amazon_scraper = None
newegg_scraper = None
memoryexpress_scraper = None
canadacomputers_scraper = None
bestbuy_scraper = None

def set_scrapers(amazon, newegg, memoryexpress, canadacomputers, bestbuy):
    """Configure les scrapers depuis bot.py."""
    global amazon_scraper, newegg_scraper, memoryexpress_scraper, canadacomputers_scraper, bestbuy_scraper
    amazon_scraper = amazon
    newegg_scraper = newegg
    memoryexpress_scraper = memoryexpress
    canadacomputers_scraper = canadacomputers
    bestbuy_scraper = bestbuy

def check_price_comparisons(app: Application) -> None:
    """Vérifie les prix des produits à comparer sur les 3 sites toutes les 60 minutes."""
    comparisons = db.get_all_comparisons()
    
    if not comparisons:
        return
    
    logger.info(f"🔍 Vérification de {len(comparisons)} comparaisons de prix...")
    
    # Créer une nouvelle boucle d'événements
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        for comparison in comparisons:
            try:
                search_query = comparison['search_query']
                comparison_id = comparison['id']
                user_id = comparison['user_id']
                product_name = comparison['product_name']
                previous_best_price = comparison.get('best_price')
                previous_best_site = comparison.get('best_site')
                
                logger.info(f"Comparaison de '{product_name}' (ID: {comparison_id})")
                
                # Rechercher sur les 3 sites
                amazon_result = None
                newegg_results = []
                
                # Amazon
                try:
                    products = loop.run_until_complete(
                        amazon_scraper.get_category_products(search_query, max_products=1)
                    )
                    if products:
                        amazon_result = {
                            "title": products[0].get("title", product_name),
                            "price": products[0].get("current_price"),
                            "url": products[0].get("url")
                        }
                except Exception as e:
                    logger.error(f"Erreur recherche Amazon pour '{product_name}': {e}")
                
                # Newegg - récupérer plusieurs produits et prendre le meilleur
                try:
                    newegg_results = loop.run_until_complete(
                        newegg_scraper.search_products(search_query, max_results=3)
                    )
                    newegg_result = min(newegg_results, key=lambda x: x.get("price", float('inf'))) if newegg_results else None
                except Exception as e:
                    logger.error(f"Erreur recherche Newegg pour '{product_name}': {e}")
                    newegg_result = None
                
                # Memory Express - récupérer plusieurs produits et prendre le meilleur
                try:
                    memoryexpress_results = loop.run_until_complete(
                        memoryexpress_scraper.search_products(search_query, max_results=3)
                    )
                    memoryexpress_result = min(memoryexpress_results, key=lambda x: x.get("price", float('inf'))) if memoryexpress_results else None
                except Exception as e:
                    logger.error(f"Erreur recherche Memory Express pour '{product_name}': {e}")
                    memoryexpress_result = None
                
                # Canada Computers - récupérer plusieurs produits et prendre le meilleur
                canadacomputers_result = None
                try:
                    canadacomputers_results = loop.run_until_complete(
                        canadacomputers_scraper.search_products(search_query, max_results=3)
                    )
                    canadacomputers_result = min(canadacomputers_results, key=lambda x: x.get("price", float('inf'))) if canadacomputers_results else None
                except Exception as e:
                    logger.error(f"Erreur recherche Canada Computers pour '{product_name}': {e}")
                    canadacomputers_result = None
                
                # Best Buy - récupérer plusieurs produits et prendre le meilleur
                bestbuy_result = None
                try:
                    bestbuy_results = loop.run_until_complete(
                        bestbuy_scraper.search_products(search_query, max_results=3)
                    )
                    bestbuy_result = min(bestbuy_results, key=lambda x: x.get("price", float('inf'))) if bestbuy_results else None
                except Exception as e:
                    logger.error(f"Erreur recherche Best Buy pour '{product_name}': {e}")
                    bestbuy_result = None
                
                # Mettre à jour la base de données
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
                
                # Récupérer les prix mis à jour
                current_comparison = db.get_comparison_by_id(comparison_id)
                
                if not current_comparison:
                    continue
                
                current_best_price = current_comparison.get('best_price')
                current_best_site = current_comparison.get('best_site')
                
                # Vérifier si le meilleur prix a changé
                if current_best_price and previous_best_price:
                    if current_best_price < previous_best_price:
                        # Nouveau meilleur prix trouvé !
                        savings = previous_best_price - current_best_price
                        message = (
                            f"🎉 **NOUVEAU MEILLEUR PRIX TROUVÉ !**\n\n"
                            f"📦 {product_name}\n\n"
                            f"💰 **Ancien meilleur prix:** ${previous_best_price:.2f} CAD ({previous_best_site})\n"
                            f"🏆 **Nouveau meilleur prix:** ${current_best_price:.2f} CAD ({current_best_site})\n"
                            f"💵 **Économie:** ${savings:.2f} CAD\n\n"
                        )
                        
                        # Ajouter les prix de tous les sites
                        if current_comparison.get('amazon_price'):
                            message += f"🛒 Amazon.ca: ${current_comparison['amazon_price']:.2f} CAD\n"
                            if current_comparison.get('amazon_url'):
                                message += f"   🔗 {current_comparison['amazon_url']}\n"
                        if current_comparison.get('newegg_price'):
                            message += f"🛒 Newegg.ca: ${current_comparison['newegg_price']:.2f} CAD\n"
                            if current_comparison.get('newegg_url'):
                                message += f"   🔗 {current_comparison['newegg_url']}\n"
                        if current_comparison.get('memoryexpress_price'):
                            message += f"🛒 Memory Express: ${current_comparison['memoryexpress_price']:.2f} CAD\n"
                            if current_comparison.get('memoryexpress_url'):
                                message += f"   🔗 {current_comparison['memoryexpress_url']}\n"
                        
                        send_message_sync(app, int(user_id), message, loop)
                        logger.info(f"✅ Alerte meilleur prix envoyée à {user_id} pour '{product_name}'")
                
                # Pause entre les comparaisons
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Erreur lors de la vérification de la comparaison {comparison.get('id')}: {e}")
                continue
    
    finally:
        loop.close()


