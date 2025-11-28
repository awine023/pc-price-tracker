"""Scraper pour Best Buy Canada."""
import asyncio
import logging
import random
from typing import Dict, List, Optional
import aiohttp
from playwright.async_api import async_playwright, Browser, Page, Playwright

from utils.constants import USER_AGENTS

logger = logging.getLogger(__name__)

class BestBuyScraper:
    """Scraper pour Best Buy Canada."""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def init_browser(self):
        """Initialise le navigateur Playwright (fallback si l'API échoue)."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                ]
            )
            context = await self.browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                locale='fr-CA',
                timezone_id='America/Toronto',
            )
            self.page = await context.new_page()
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du navigateur Best Buy: {e}")
    
    async def close_browser(self):
        """Ferme le navigateur."""
        try:
            if self.page:
                await self.page.close()
        except:
            pass
        try:
            if self.browser:
                await self.browser.close()
        except:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
        self.page = None
        self.browser = None
        self.playwright = None
    
    async def _search_with_api(self, search_query: str, max_results: int = 3) -> List[Dict]:
        """Recherche avec l'API Best Buy (plus fiable que le scraping DOM)."""
        # Simplifier la requête de recherche (enlever les détails superflus)
        # Ex: "corsair frame 4000D ARGB mid-tower ATX computer case - black" -> "corsair 4000D"
        simplified_query = search_query
        # Garder seulement les mots-clés importants (marque + modèle principal)
        words = search_query.split()
        if len(words) > 5:
            # Prendre les premiers mots (marque) + chercher un numéro de modèle
            simplified_query = ' '.join(words[:3])  # Prendre les 3 premiers mots
            # Chercher un numéro de modèle (ex: 4000D, 7800X3D)
            import re
            model_match = re.search(r'\d+[A-Z]?\d*[A-Z]?', search_query)
            if model_match:
                simplified_query += ' ' + model_match.group()
        
        # Essayer d'abord avec la requête simplifiée, puis avec la requête complète
        queries_to_try = [simplified_query]
        if simplified_query != search_query:
            queries_to_try.append(search_query)
        
        api_url = "https://www.bestbuy.ca/api/v2/json/search"
        
        headers = {
            'Accept': 'application/json',
            'Accept-Language': 'en-CA,en;q=0.9,fr-CA;q=0.8,fr;q=0.7',
            'User-Agent': random.choice(USER_AGENTS),
            'Referer': 'https://www.bestbuy.ca/',
        }
        
        for query in queries_to_try:
            try:
                params = {
                    "query": query,
                    "page": 1,
                    "pageSize": max_results * 2,  # Prendre plus pour filtrer
                    "lang": "en-CA"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Debug: logger la structure de la réponse
                            logger.debug(f"📊 Structure réponse Best Buy: {list(data.keys())}")
                            
                            products_list = []
                            # La structure de la réponse peut varier, on essaie plusieurs chemins
                            products = data.get('products', [])
                            if not products:
                                products = data.get('results', [])
                            if not products:
                                products = data.get('data', {}).get('products', [])
                            if not products and isinstance(data, list):
                                products = data
                            
                            logger.debug(f"📦 Nombre de produits trouvés dans la réponse: {len(products) if products else 0}")
                            
                            for product in products[:max_results * 2]:
                                try:
                                    # Extraire le titre
                                    title = product.get('name') or product.get('title') or product.get('productName') or "Produit Best Buy"
                                    
                                    # Extraire le prix
                                    price = None
                                    # Essayer plusieurs chemins pour le prix
                                    price = (
                                        product.get('salePrice') or 
                                        product.get('regularPrice') or 
                                        product.get('price') or 
                                        product.get('currentPrice') or
                                        product.get('customerPrice') or
                                        product.get('pricing', {}).get('current')
                                    )
                                    
                                    # Si c'est un dictionnaire, chercher dans les sous-éléments
                                    if isinstance(price, dict):
                                        price = price.get('value') or price.get('amount') or price.get('price') or price.get('current')
                                    
                                    # Convertir en float
                                    if price:
                                        try:
                                            price = float(price)
                                        except (ValueError, TypeError):
                                            price = None
                                    
                                    if not price or price <= 0:
                                        continue
                                    
                                    # Extraire l'URL
                                    url = None
                                    sku = product.get('sku') or product.get('productId') or product.get('id')
                                    if sku:
                                        url = f"https://www.bestbuy.ca/fr-ca/produit/{sku}"
                                    else:
                                        url = product.get('url') or product.get('productUrl')
                                        if url and not url.startswith('http'):
                                            url = f"https://www.bestbuy.ca{url}"
                                    
                                    if not url:
                                        continue
                                    
                                    products_list.append({
                                        "title": title,
                                        "price": price,
                                        "url": url
                                    })
                                    
                                    if len(products_list) >= max_results:
                                        break
                                except Exception as e:
                                    logger.debug(f"Erreur parsing produit Best Buy: {e}")
                                    continue
                            
                            if products_list:
                                logger.info(f"✅ {len(products_list)} produit(s) Best Buy trouvé(s) via API (requête: '{query}')")
                                return products_list
                        else:
                            logger.debug(f"API Best Buy retourné {response.status} pour '{query}'")
            except Exception as e:
                logger.debug(f"Erreur API Best Buy avec '{query}': {e}")
                continue
        
        logger.warning(f"⚠️ API Best Buy n'a pas retourné de résultats pour '{search_query}'")
        return []
    
    async def search_products(self, search_query: str, max_results: int = 3) -> List[Dict]:
        """Recherche des produits sur Best Buy et retourne plusieurs résultats."""
        try:
            # Utiliser l'API Best Buy (plus fiable et rapide)
            logger.info(f"🔄 Recherche Best Buy via API: {search_query}")
            api_result = await self._search_with_api(search_query, max_results)
            
            if api_result and len(api_result) > 0:
                return api_result
            
            # Si l'API échoue, retourner une liste vide (pas de fallback Playwright car Best Buy est une SPA React)
            logger.warning("⚠️ API Best Buy n'a pas retourné de résultats")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Best Buy: {e}")
            return []
