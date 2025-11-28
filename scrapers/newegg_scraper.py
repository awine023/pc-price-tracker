"""Scraper pour Newegg Canada."""
import asyncio
import logging
import re
import random
import time
import concurrent.futures
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page, Playwright

from utils.constants import USER_AGENTS, CURL_CFFI_AVAILABLE, curl_requests

logger = logging.getLogger(__name__)

class NeweggScraper:
    """Scraper pour Newegg Canada."""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def init_browser(self):
        """Initialise le navigateur Playwright."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
            context = await self.browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                locale='en-CA',
            )
            self.page = await context.new_page()
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du navigateur Newegg: {e}")
    
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
    
    def _search_with_curl_cffi(self, search_query: str, max_results: int = 3) -> List[Dict]:
        """Recherche avec curl-cffi (meilleur pour contourner la protection) - méthode synchrone."""
        if curl_requests is None:
            logger.error("❌ curl_requests est None - curl-cffi n'est pas correctement importé")
            return []
        
        search_url = f"https://www.newegg.ca/p/pl?d={search_query.replace(' ', '+')}"
        
        logger.info(f"🔍 Recherche Newegg avec curl-cffi: {search_query}")
        logger.info(f"🔗 URL: {search_url}")
        
        # Essayer différentes versions de Chrome
        impersonations = ["chrome120", "chrome119", "chrome110", "chrome107", "edge110"]
        response = None
        
        for impersonate in impersonations:
            try:
                logger.debug(f"Tentative avec {impersonate}...")
                
                session = curl_requests.Session()
                
                # Visiter la page d'accueil d'abord
                try:
                    session.get(
                        "https://www.newegg.ca/",
                        impersonate=impersonate,
                        timeout=15,
                        headers={
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-CA,en-US;q=0.9,en;q=0.8,fr-CA;q=0.7,fr;q=0.6',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Sec-Fetch-Dest': 'document',
                            'Sec-Fetch-Mode': 'navigate',
                            'Sec-Fetch-Site': 'none',
                            'Sec-Fetch-User': '?1',
                            'Cache-Control': 'max-age=0',
                            'DNT': '1',
                        }
                    )
                    time.sleep(random.uniform(1, 2))
                except:
                    pass
                
                # Faire la recherche
                response = session.get(
                    search_url,
                    impersonate=impersonate,
                    timeout=30,
                    headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-CA,en-US;q=0.9,en;q=0.8,fr-CA;q=0.7,fr;q=0.6',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'same-origin',
                        'Sec-Fetch-User': '?1',
                        'Referer': 'https://www.newegg.ca/',
                        'Cache-Control': 'max-age=0',
                        'DNT': '1',
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ curl-cffi réussi avec {impersonate} (status 200)")
                    break
                elif response.status_code == 403:
                    logger.debug(f"❌ {impersonate} bloqué (403), essai suivant...")
                    continue
                else:
                    logger.debug(f"Newegg retourné {response.status_code} avec {impersonate}")
                    if response.status_code < 500:
                        continue
                    else:
                        break
            except Exception as e:
                logger.debug(f"Erreur avec {impersonate}: {e}")
                continue
        else:
            logger.warning("❌ Toutes les tentatives curl-cffi ont échoué")
            return []
        
        if not response or response.status_code != 200:
            logger.warning(f"Newegg retourné {response.status_code if response else 'None'}")
            return []
        
        # Sauvegarder le HTML pour debug
        try:
            import os
            os.makedirs('debug_html', exist_ok=True)
            safe_query = search_query.replace(' ', '_').replace('/', '_')[:50]
            debug_file = f"debug_html/newegg_{safe_query}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info(f"💾 HTML sauvegardé dans: {debug_file}")
        except:
            pass
        
        # Parser le HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Titre de la page pour debug
        page_title = soup.find('title')
        if page_title:
            logger.info(f"📄 Titre de la page curl-cffi: {page_title.get_text(strip=True)}")
        logger.info(f"📊 Taille du HTML: {len(response.text)} caractères")
        
        # Chercher les produits avec plusieurs sélecteurs
        product_elems = []
        selectors = [
            'div.item-cell',
            'div.item-container',
            'div[class*="item-cell"]',
            'div[class*="item-container"]',
            'div.item-info',
            'div[data-testid*="item"]',
            'article.item-cell',
            'div.product-item'
        ]
        
        for selector in selectors:
            product_elems = soup.select(selector)
            if product_elems:
                logger.info(f"✅ Trouvé {len(product_elems)} produits avec {selector}")
                break
        
        if not product_elems:
            logger.warning("⚠️ Aucun produit trouvé avec les sélecteurs CSS")
            return []
        
        # Extraire les mots-clés importants de la requête de recherche
        query_lower = search_query.lower()
        # Enlever les mots communs non pertinents
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'don', 'should', 'now'}
        query_words = [w for w in re.findall(r'\b\w+\b', query_lower) if w not in stop_words and len(w) > 2]
        
        # Si pas assez de mots-clés, prendre les mots les plus longs
        if len(query_words) < 2:
            query_words = sorted(re.findall(r'\b\w+\b', query_lower), key=len, reverse=True)[:5]
        
        logger.debug(f"🔍 Mots-clés de recherche: {query_words}")
        
        # Extraire tous les produits avec leur score de pertinence
        products_with_scores = []
        for product_elem in product_elems[:max_results * 3]:  # Prendre plus pour filtrer
            try:
                # Extraire le titre
                title = None
                title_selectors = [
                    'a.item-title',
                    '.item-title',
                    'a[title]',
                    'img[alt]',
                    'h2 a',
                    'h3 a',
                    'a.item-img',
                    '.item-info a'
                ]
                for selector in title_selectors:
                    title_elem = product_elem.select_one(selector)
                    if title_elem:
                        title = (
                            title_elem.get('title') or 
                            title_elem.get('alt') or 
                            title_elem.get_text(strip=True)
                        )
                        if title:
                            break
                
                if not title:
                    continue
                
                # Extraire le prix
                price = None
                price_selectors = [
                    'li.price-current',
                    '.price-current',
                    'ul.price li',
                    '.price',
                    '[class*="price-current"]',
                    'strong.price-current',
                    '.price-box',
                    'span.price',
                    '[class*="price"]'
                ]
                
                for selector in price_selectors:
                    price_elem = product_elem.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price_matches = re.findall(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                        for match in price_matches:
                            try:
                                test_price = float(match)
                                if 1 < test_price < 100000:
                                    price = test_price
                                    break
                            except ValueError:
                                continue
                        if price:
                            break
                
                # Si pas trouvé, chercher dans tout le texte
                if not price:
                    all_text = product_elem.get_text()
                    price_matches = re.findall(r'\$?\s*([\d,]+\.?\d*)', all_text)
                    for match in price_matches:
                        try:
                            test_price = float(match.replace(',', ''))
                            if 1 < test_price < 100000:
                                price = test_price
                                break
                        except ValueError:
                            continue
                
                if not price or price <= 0:
                    continue
                
                # Extraire l'URL
                url = None
                link_selectors = [
                    'a.item-title',
                    'a[href*="/p/"]',
                    'a[href*="/Product"]',
                    'a.item-img',
                    'a[href]'
                ]
                for selector in link_selectors:
                    link_elem = product_elem.select_one(selector)
                    if link_elem:
                        url = link_elem.get('href') or ''
                        if url and not url.startswith('http'):
                            url = f"https://www.newegg.ca{url}"
                        # S'assurer que ce n'est pas une page de recherche
                        if url and 'p/pl' not in url and 'Search' not in url:
                            break
                
                if not url or 'p/pl' in url or 'Search' in url:
                    continue
                
                # Calculer le score de pertinence
                title_lower = title.lower()
                score = 0
                
                # Points pour chaque mot-clé trouvé dans le titre
                for word in query_words:
                    if word in title_lower:
                        score += 2
                        # Bonus si le mot est au début du titre
                        if title_lower.startswith(word):
                            score += 1
                
                # Bonus si plusieurs mots-clés sont trouvés
                matched_words = sum(1 for word in query_words if word in title_lower)
                if matched_words >= len(query_words) * 0.6:  # Au moins 60% des mots-clés
                    score += 5
                
                # Bonus pour les numéros de modèle (ex: 7800X3D, 4000D)
                model_numbers = re.findall(r'\d+[A-Z]?\d*[A-Z]?', query_lower)
                for model in model_numbers:
                    if model in title_lower:
                        score += 10  # Gros bonus pour les numéros de modèle
                
                products_with_scores.append({
                    "title": title,
                    "price": price,
                    "url": url,
                    "score": score
                })
            except Exception as e:
                logger.debug(f"Erreur extraction produit Newegg: {e}")
                continue
        
        # Trier par score de pertinence (décroissant)
        products_with_scores.sort(key=lambda x: x['score'], reverse=True)
        
        # Filtrer: ne garder que les produits avec un score minimum
        min_score = 2  # Au moins 1 mot-clé trouvé
        filtered_products = [p for p in products_with_scores if p['score'] >= min_score]
        
        # Prendre les meilleurs résultats
        products_list = [{"title": p["title"], "price": p["price"], "url": p["url"]} 
                        for p in filtered_products[:max_results]]
        
        if products_list:
            logger.info(f"✅ {len(products_list)} produit(s) Newegg trouvé(s) avec curl-cffi (filtrés par pertinence)")
        else:
            logger.warning(f"⚠️ Aucun produit pertinent trouvé (scores: {[p['score'] for p in products_with_scores[:5]]})")
        
        return products_list
    
    async def search_products(self, search_query: str, max_results: int = 3) -> List[Dict]:
        """Recherche des produits sur Newegg Canada et retourne plusieurs résultats."""
        try:
            # Essayer d'abord avec curl-cffi (meilleur pour contourner la protection)
            if CURL_CFFI_AVAILABLE and curl_requests is not None:
                try:
                    logger.info("🔄 Tentative avec curl-cffi pour contourner la protection...")
                    
                    # curl-cffi est synchrone, donc on l'exécute dans un thread
                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._search_with_curl_cffi, search_query, max_results)
                        result = await loop.run_in_executor(None, lambda: future.result())
                    
                    if result and len(result) > 0:
                        logger.info(f"✅ curl-cffi a réussi, {len(result)} produit(s) trouvé(s)")
                        return result
                    else:
                        logger.warning("⚠️ curl-cffi n'a retourné aucun résultat, fallback sur Playwright")
                except Exception as e:
                    logger.warning(f"❌ curl-cffi échoué, fallback sur Playwright: {e}")
            else:
                logger.warning("⚠️ curl-cffi non disponible, utilisation directe de Playwright")
            
            # Fallback: Playwright (si curl-cffi échoue)
            if not self.page or not self.browser:
                await self.init_browser()
            
            search_url = f"https://www.newegg.ca/p/pl?d={search_query.replace(' ', '+')}"
            
            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(3, 5))
            
            # Extraire avec BeautifulSoup
            html = await self.page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # Chercher les produits
            product_elems = []
            selectors = [
                'div.item-cell',
                'div.item-container',
                'div[class*="item-cell"]',
                'div[class*="item-container"]'
            ]
            
            for selector in selectors:
                product_elems = soup.select(selector)
                if product_elems:
                    break
            
            if not product_elems:
                return []
            
            # Extraire les mots-clés importants de la requête de recherche
            query_lower = search_query.lower()
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'don', 'should', 'now'}
            query_words = [w for w in re.findall(r'\b\w+\b', query_lower) if w not in stop_words and len(w) > 2]
            
            if len(query_words) < 2:
                query_words = sorted(re.findall(r'\b\w+\b', query_lower), key=len, reverse=True)[:5]
            
            # Extraire tous les produits avec leur score de pertinence
            products_with_scores = []
            for product_elem in product_elems[:max_results * 3]:
                try:
                    # Extraire le titre
                    title = None
                    title_selectors = ['a.item-title', '.item-title', 'img[alt]', 'a[title]']
                    for selector in title_selectors:
                        title_elem = product_elem.select_one(selector)
                        if title_elem:
                            title = title_elem.get('title') or title_elem.get('alt') or title_elem.get_text(strip=True)
                            if title:
                                break
                    
                    if not title:
                        continue
                    
                    # Extraire le prix
                    price = None
                    price_selectors = [
                        'li.price-current',
                        '.price-current',
                        'ul.price li',
                        '.price',
                        '[class*="price-current"]',
                        'strong.price-current',
                        '.price-box'
                    ]
                    
                    for selector in price_selectors:
                        price_elem = product_elem.select_one(selector)
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price_matches = re.findall(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                            for match in price_matches:
                                try:
                                    test_price = float(match)
                                    if 1 < test_price < 100000:
                                        price = test_price
                                        break
                                except ValueError:
                                    continue
                            if price:
                                break
                    
                    # Si pas trouvé, chercher dans tout le texte
                    if not price:
                        all_text = product_elem.get_text()
                        price_matches = re.findall(r'\$?\s*([\d,]+\.?\d*)', all_text)
                        for match in price_matches:
                            try:
                                test_price = float(match.replace(',', ''))
                                if 1 < test_price < 100000:
                                    price = test_price
                                    break
                            except ValueError:
                                continue
                    
                    if not price or price <= 0:
                        continue
                    
                    # Extraire l'URL
                    url_elem = product_elem.select_one('a.item-title, a[href*="/p/"]')
                    url = url_elem.get('href') if url_elem else None
                    if url and not url.startswith('http'):
                        url = f"https://www.newegg.ca{url}"
                    
                    # S'assurer que c'est un lien direct
                    if not url or 'p/pl' in url or 'Search' in url:
                        continue
                    
                    # Calculer le score de pertinence
                    title_lower = title.lower()
                    score = 0
                    
                    # Points pour chaque mot-clé trouvé dans le titre
                    for word in query_words:
                        if word in title_lower:
                            score += 2
                            if title_lower.startswith(word):
                                score += 1
                    
                    # Bonus si plusieurs mots-clés sont trouvés
                    matched_words = sum(1 for word in query_words if word in title_lower)
                    if matched_words >= len(query_words) * 0.6:
                        score += 5
                    
                    # Bonus pour les numéros de modèle
                    model_numbers = re.findall(r'\d+[A-Z]?\d*[A-Z]?', query_lower)
                    for model in model_numbers:
                        if model in title_lower:
                            score += 10
                    
                    products_with_scores.append({
                        "title": title,
                        "price": price,
                        "url": url,
                        "score": score
                    })
                except Exception as e:
                    logger.debug(f"Erreur extraction produit Newegg: {e}")
                    continue
            
            # Trier par score de pertinence
            products_with_scores.sort(key=lambda x: x['score'], reverse=True)
            
            # Filtrer: ne garder que les produits avec un score minimum
            min_score = 2
            filtered_products = [p for p in products_with_scores if p['score'] >= min_score]
            
            # Prendre les meilleurs résultats
            products_list = [{"title": p["title"], "price": p["price"], "url": p["url"]} 
                            for p in filtered_products[:max_results]]
            
            return products_list
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Newegg: {e}")
            return []


