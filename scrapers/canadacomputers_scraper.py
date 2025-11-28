"""Scraper pour Canada Computers."""
import asyncio
import logging
import re
import random
import time
import os
import concurrent.futures
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page, Playwright

from utils.constants import USER_AGENTS, CURL_CFFI_AVAILABLE, curl_requests

logger = logging.getLogger(__name__)

class CanadaComputersScraper:
    """Scraper pour Canada Computers."""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def init_browser(self):
        """Initialise le navigateur Playwright (fallback si curl-cffi échoue)."""
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
                locale='en-CA',
                timezone_id='America/Toronto',
            )
            self.page = await context.new_page()
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du navigateur Canada Computers: {e}")
    
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
        # Vérifier que curl_requests est disponible
        if curl_requests is None:
            logger.error("❌ curl_requests est None - curl-cffi n'est pas correctement importé")
            return []
        
        # Canada Computers utilise le format: /en/search?s=query&hot=1
        search_url = f"https://www.canadacomputers.com/en/search?s={search_query.replace(' ', '+')}&hot=1"
        
        logger.info(f"🔍 Recherche Canada Computers avec curl-cffi: {search_query}")
        logger.info(f"🔗 URL: {search_url}")
        
        # Essayer différentes versions de Chrome et stratégies
        impersonations = ["chrome120", "chrome119", "chrome110", "chrome107", "edge110", "safari15_5"]
        response = None
        
        for impersonate in impersonations:
            try:
                logger.debug(f"Tentative avec {impersonate}...")
                
                # Créer une session pour maintenir les cookies
                session = curl_requests.Session()
                
                # D'abord visiter la page d'accueil pour établir une session
                try:
                    session.get(
                        "https://www.canadacomputers.com/",
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
                    # Petite pause pour simuler un comportement humain
                    time.sleep(random.uniform(1, 2))
                except:
                    pass
                
                # Maintenant faire la recherche avec la session établie
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
                        'Referer': 'https://www.canadacomputers.com/',
                        'Cache-Control': 'max-age=0',
                        'DNT': '1',
                    }
                )
                
                if response.status_code == 200:
                    # Vérifier si ce n'est pas une page 404
                    if '404' not in response.text[:500] and 'Not Found' not in response.text[:500]:
                        logger.info(f"✅ curl-cffi réussi avec {impersonate} (status 200)")
                        break  # Sortir de la boucle impersonate
                    else:
                        logger.debug(f"⚠️ {impersonate} retourne 404, essai suivant...")
                        continue
                elif response.status_code == 403:
                    logger.debug(f"❌ {impersonate} bloqué (403), essai suivant...")
                    continue
                else:
                    logger.debug(f"Canada Computers retourné {response.status_code} avec {impersonate}")
                    if response.status_code < 500:  # Erreur client, pas serveur
                        continue
                    else:
                        break  # Erreur serveur, on peut essayer de parser
            except Exception as e:
                logger.debug(f"Erreur avec {impersonate}: {e}")
                continue
        else:
            # Toutes les tentatives ont échoué
            logger.warning("❌ Toutes les tentatives curl-cffi ont échoué")
            return []
        
        if not response or response.status_code != 200:
            logger.warning(f"Canada Computers retourné {response.status_code if response else 'None'} après toutes les tentatives")
            return []
        
        # Sauvegarder le HTML pour analyse
        try:
            debug_dir = "debug_html"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            # Nettoyer le nom de fichier
            safe_query = "".join(c for c in search_query if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_query = safe_query.replace(' ', '_')
            html_file = os.path.join(debug_dir, f"canadacomputers_{safe_query}.html")
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            logger.info(f"💾 HTML sauvegardé dans: {html_file}")
        except Exception as e:
            logger.debug(f"Erreur sauvegarde HTML: {e}")
        
        # Parser le HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Debug: vérifier le contenu de la page
        page_title = soup.title.string if soup.title else "Pas de titre"
        logger.info(f"📄 Titre de la page curl-cffi: {page_title}")
        logger.info(f"📊 Taille du HTML: {len(response.text)} caractères")
        
        # Chercher les produits avec plusieurs stratégies
        products_list = []
        product_elems = []
        
        # Sélecteurs pour Canada Computers - basés sur la structure HTML réelle
        # Les produits sont dans div.js-product ou div.product avec col-sm-6 col-xl-3
        selectors = [
            'div.js-product.product',  # Structure principale des produits
            'div.js-product',
            'article.product-miniature',
            'div.product.col-sm-6',
            'div[class*="js-product"]',
            'div[class*="product-miniature"]',
        ]
        
        for selector in selectors:
            product_elems = soup.select(selector)
            if product_elems:
                logger.info(f"✅ Trouvé {len(product_elems)} produits avec {selector}")
                break
        
        # Si aucun produit trouvé, essayer de chercher dans tout le HTML
        if not product_elems:
            # Chercher tous les liens qui pourraient être des produits
            all_links = soup.select('a[href*="/product/"], a[href*="/Product/"], a[href*="/products/"]')
            if all_links:
                logger.debug(f"Trouvé {len(all_links)} liens produits potentiels")
                # Créer des éléments factices pour chaque lien
                for link in all_links[:max_results]:
                    parent = link.find_parent(['div', 'article', 'li'])
                    if parent:
                        product_elems.append(parent)
                    else:
                        # Créer un élément factice avec le lien
                        fake_elem = soup.new_tag('div')
                        fake_elem.append(link)
                        product_elems.append(fake_elem)
        
        if not product_elems:
            logger.warning("Aucun produit trouvé avec curl-cffi - sélecteurs CSS")
            logger.info(f"🔍 Extrait du HTML (premiers 1000 caractères): {response.text[:1000]}")
            
            # Essayer de trouver des prix dans le HTML brut
            price_pattern = re.compile(r'\$[\d,]+\.?\d*')
            prices_found = price_pattern.findall(response.text[:5000])
            if prices_found:
                logger.info(f"💰 {len(prices_found)} prix trouvés dans le HTML: {prices_found[:5]}")
            
            return []
        
        for product_elem in product_elems[:max_results]:
            # Extraire le titre - Canada Computers utilise h2.product-title a
            title = None
            title_elem = product_elem.select_one('h2.product-title a, h3.product-title a, .product-title a')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            if not title or len(title) < 10:
                title = "Produit Canada Computers"
            
            # Extraire le prix - Canada Computers utilise span.price.sale-price (prix de vente)
            # ou data-price/data-final_price sur div.product-description
            price = None
            
            # Méthode 1: Chercher dans span.price.sale-price (prix de vente actuel)
            price_elem = product_elem.select_one('span.price.sale-price, span.sale-price')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', price_text)
                if price_match:
                    try:
                        price = float(price_match.group(1).replace(',', ''))
                    except ValueError:
                        pass
            
            # Méthode 2: Chercher dans data-price ou data-final_price (attributs HTML)
            if not price:
                product_desc = product_elem.select_one('div.product-description')
                if product_desc:
                    data_price = product_desc.get('data-price') or product_desc.get('data-final_price')
                    if data_price:
                        price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', data_price)
                        if price_match:
                            try:
                                price = float(price_match.group(1).replace(',', ''))
                            except ValueError:
                                pass
            
            # Méthode 3: Chercher dans span.regular-price si pas de sale-price
            if not price:
                price_elem = product_elem.select_one('span.regular-price')
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', price_text)
                    if price_match:
                        try:
                            price = float(price_match.group(1).replace(',', ''))
                        except ValueError:
                            pass
            
            # Méthode 4: Chercher dans tout le texte du produit
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
                logger.debug(f"⚠️ Produit sans prix valide: {title[:50]}")
                continue
            
            # Extraire l'URL - Canada Computers utilise h2.product-title a
            url = None
            url_elem = product_elem.select_one('h2.product-title a, h3.product-title a, .product-title a')
            if url_elem:
                url = url_elem.get('href')
            
            # Fallback: chercher dans a.thumbnail
            if not url:
                url_elem = product_elem.select_one('a.thumbnail, a.product-thumbnail')
                if url_elem:
                    url = url_elem.get('href')
            
            # Fallback: chercher tous les liens
            if not url:
                all_links = product_elem.select('a[href]')
                for link in all_links:
                    href = link.get('href')
                    if href and not href.startswith('javascript:') and \
                       'search' not in href.lower() and 'Search' not in href and \
                       ('/amd-' in href or '/armoury-' in href or '/gaming-' in href):
                        url = href
                        break
            
            if url and not url.startswith('http'):
                url = f"https://www.canadacomputers.com{url}"
            elif not url:
                url = search_url
            
            products_list.append({
                "title": title,
                "price": price,
                "url": url
            })
        
        if products_list:
            logger.info(f"✅ {len(products_list)} produit(s) Canada Computers trouvé(s) avec curl-cffi")
        
        return products_list
    
    async def search_products(self, search_query: str, max_results: int = 3) -> List[Dict]:
        """Recherche des produits sur Canada Computers et retourne plusieurs résultats."""
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
            
            # Fallback: Playwright (peut être bloqué)
            if not self.page or not self.browser:
                await self.init_browser()
            
            search_url = f"https://www.canadacomputers.com/en/search?s={search_query.replace(' ', '+')}&hot=1"
            
            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(3, 5))
            
            html = await self.page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # Chercher les produits
            product_elems = soup.select('div.product-item, div[class*="product-item"], div.product-tile')
            
            if not product_elems:
                return []
            
            products_list = []
            for product_elem in product_elems[:max_results]:
                # Extraire titre, prix, URL (similaire à curl-cffi)
                title_elem = product_elem.select_one('h2 a, h3 a, a[href*="/product/"]')
                title = title_elem.get_text(strip=True) if title_elem else "Produit Canada Computers"
                
                price_elem = product_elem.select_one('.price, [class*="price"]')
                price = None
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_matches = re.findall(r'\$?\s*([\d,]+\.?\d*)', price_text)
                    if price_matches:
                        try:
                            price = float(price_matches[0].replace(',', ''))
                        except ValueError:
                            pass
                
                if not price or price <= 0:
                    continue
                
                url_elem = product_elem.select_one('a[href*="/product/"]')
                url = url_elem.get('href') if url_elem else search_url
                if url and not url.startswith('http'):
                    url = f"https://www.canadacomputers.com{url}"
                
                products_list.append({
                    "title": title,
                    "price": price,
                    "url": url
                })
            
            return products_list
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Canada Computers: {e}")
            return []

