"""Scraper pour Memory Express Canada."""
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

class MemoryExpressScraper:
    """Scraper pour Memory Express Canada."""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def init_browser(self):
        """Initialise le navigateur Playwright avec techniques anti-détection avancées pour contourner Cloudflare."""
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
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )
            context = await self.browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                locale='en-CA',
                timezone_id='America/Toronto',
                permissions=[],
                extra_http_headers={
                    'Accept-Language': 'en-CA,en;q=0.9,fr;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                }
            )
            
            # Scripts anti-détection avancés pour contourner Cloudflare
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                window.navigator.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-CA', 'en', 'fr-CA', 'fr'],
                });
                
                // Masquer les propriétés de Playwright
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });
            """)
            
            self.page = await context.new_page()
            
            # Masquer les propriétés de Playwright sur la page
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });
            """)
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du navigateur Memory Express: {e}")
    
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
        """Recherche avec curl-cffi (meilleur pour contourner Cloudflare) - méthode synchrone."""
        # Memory Express utilise le format: /Search/Products?Search=query
        search_url = f"https://www.memoryexpress.com/Search/Products?Search={search_query.replace(' ', '+')}"
        
        logger.info(f"🔍 Recherche Memory Express avec curl-cffi: {search_query}")
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
                        "https://www.memoryexpress.com/",
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
                    import time
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
                        'Referer': 'https://www.memoryexpress.com/',
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
                    logger.debug(f"Memory Express retourné {response.status_code} avec {impersonate}")
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
            logger.warning(f"Memory Express retourné {response.status_code if response else 'None'} après toutes les tentatives")
            return []
        
        # Vérifier si Cloudflare bloque
        if 'Just a moment' in response.text or 'Verify you are human' in response.text:
            logger.warning("⚠️ Cloudflare détecté même avec curl-cffi")
            return []
        
        # Sauvegarder le HTML pour analyse
        try:
            import os
            debug_dir = "debug_html"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            # Nettoyer le nom de fichier
            safe_query = "".join(c for c in search_query if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_query = safe_query.replace(' ', '_')
            html_file = os.path.join(debug_dir, f"memoryexpress_{safe_query}.html")
            
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
        
        # Vérifier si c'est toujours Cloudflare
        if 'Just a moment' in response.text or 'Verify you are human' in response.text:
            logger.warning("⚠️ Cloudflare détecté dans le HTML curl-cffi")
            return []
        
        # Vérifier si c'est une page de résultats valide
        if 'no results' in response.text.lower() or 'aucun résultat' in response.text.lower():
            logger.info("ℹ️ Page de résultats vide (aucun produit trouvé)")
            return []
        
        # Chercher les produits avec plusieurs stratégies
        products_list = []
        product_elems = []
        
        # Sélecteurs pour Memory Express - structure réelle trouvée dans le HTML
        selectors = [
            'div.c-shca-icon-item',  # Structure principale des produits
            'div[class*="c-shca-icon-item"]',
            'div.c-product-tile',
            'div[class*="product-tile"]',
            'div[class*="ProductTile"]',
            'div.product-tile',
            'div.product-item',
            'div[class*="product"]',
            'article.product',
            'article[class*="product"]',
            '.product-card',
            '.search-result-item',
            'div[data-product]',
            'li[class*="product"]',
            'div[class*="Product"]',
            'div[class*="item"]',
            'div[class*="result"]'
        ]
        
        for selector in selectors:
            product_elems = soup.select(selector)
            if product_elems:
                logger.info(f"✅ Trouvé {len(product_elems)} produits avec {selector}")
                break
        
        # Si aucun produit trouvé, essayer de chercher dans tout le HTML
        if not product_elems:
            # Chercher tous les liens qui pourraient être des produits
            all_links = soup.select('a[href*="/Products/"], a[href*="/Product/"]')
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
            # Dernière tentative: chercher par texte
            logger.warning("Aucun produit trouvé avec curl-cffi - sélecteurs CSS")
            logger.info(f"🔍 Extrait du HTML (premiers 1000 caractères): {response.text[:1000]}")
            
            # Essayer de trouver des prix dans le HTML brut
            price_pattern = re.compile(r'\$[\d,]+\.?\d*')
            prices_found = price_pattern.findall(response.text[:5000])
            if prices_found:
                logger.info(f"💰 {len(prices_found)} prix trouvés dans le HTML: {prices_found[:5]}")
            
            # Chercher des liens produits
            product_links = soup.select('a[href*="/Products/"], a[href*="/Product/"]')
            if product_links:
                logger.info(f"🔗 {len(product_links)} liens produits trouvés")
            
            return []
        
        for product_elem in product_elems[:max_results]:
            # Extraire le titre - Memory Express utilise c-shca-icon-item__body-name
            title = None
            title_selectors = [
                '.c-shca-icon-item__body-name a',  # Structure réelle Memory Express
                '.c-shca-icon-item__body-name',
                'a[href*="/Products/"]',
                'a[title]', 
                'h2', 'h3', 
                '.product-name', '.product-title', 
                '[class*="title"]', 
                'a'
            ]
            for selector in title_selectors:
                title_elem = product_elem.select_one(selector)
                if title_elem:
                    # Pour les liens, prendre le texte du lien
                    if title_elem.name == 'a':
                        title = title_elem.get_text(strip=True)
                    else:
                        title = title_elem.get('title') or title_elem.get_text(strip=True)
                    # Nettoyer le titre (enlever les images, etc.)
                    if title:
                        # Enlever les références de marque comme "AMD" si c'est juste une image
                        title = re.sub(r'^\s*[A-Z]+\s+', '', title).strip()
                        if len(title) > 10:  # Titre valide doit être assez long
                            break
            
            if not title or len(title) < 10:
                title = "Produit Memory Express"
            
            # Extraire le prix - Memory Express utilise c-shca-icon-item__summary-prices
            price = None
            price_selectors = [
                '.c-shca-icon-item__summary-list span',  # Prix de vente (priorité)
                '.c-shca-icon-item__summary-regular span',  # Prix régulier
                '.c-shca-icon-item__summary-prices',
                '.price', '.product-price', '.price-current',
                '.price-regular', 'strong.price', 'span.price', 
                '[class*="price"]', '.c-price', '.price-box'
            ]
            
            for selector in price_selectors:
                price_elem = product_elem.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Chercher le prix dans le texte
                    price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', price_text)
                    if price_match:
                        try:
                            test_price = float(price_match.group(1).replace(',', ''))
                            if 1 < test_price < 100000:
                                price = test_price
                                break
                        except ValueError:
                            continue
            
            # Si pas de prix trouvé, chercher dans tout le conteneur de prix
            if not price:
                price_container = product_elem.select_one('.c-shca-icon-item__summary-prices')
                if price_container:
                    price_text = price_container.get_text()
                    price_matches = re.findall(r'\$?\s*([\d,]+\.?\d*)', price_text)
                    for match in price_matches:
                        try:
                            test_price = float(match.replace(',', ''))
                            if 1 < test_price < 100000:
                                price = test_price
                                break
                        except ValueError:
                            continue
            
            # Dernière tentative : chercher dans tout le texte du produit
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
            
            # Extraire l'URL - Memory Express utilise des liens /Products/MX...
            url = None
            url_selectors = [
                '.c-shca-icon-item__body-name a[href*="/Products/"]',  # Structure réelle
                'a[href*="/Products/"]',
                'a[href*="/Product/"]',
                'a.product-link',
                'h2 a', 'h3 a',
                'a[title]',
                'a[href]'
            ]
            
            for selector in url_selectors:
                url_elems = product_elem.select(selector)
                for url_elem in url_elems:
                    href = url_elem.get('href')
                    if href and not href.startswith('javascript:') and '/Products/' in href:
                        if ('/Products/' in href or '/Product/' in href) and \
                           'Search' not in href and 'search' not in href:
                            url = href
                            break
                if url:
                    break
            
            if not url:
                all_links = product_elem.select('a[href]')
                for link in all_links:
                    href = link.get('href')
                    if href and not href.startswith('javascript:') and \
                       'Search' not in href and 'search' not in href:
                        url = href
                        break
            
            if url and not url.startswith('http'):
                url = f"https://www.memoryexpress.com{url}"
            elif not url:
                url = search_url
            
            products_list.append({
                "title": title,
                "price": price,
                "url": url
            })
        
        if products_list:
            logger.info(f"✅ {len(products_list)} produit(s) Memory Express trouvé(s) avec curl-cffi")
        
        return products_list
    
    async def search_products(self, search_query: str, max_results: int = 3) -> List[Dict]:
        """Recherche des produits sur Memory Express et retourne plusieurs résultats."""
        try:
            # Essayer d'abord avec curl-cffi (meilleur pour Cloudflare)
            if CURL_CFFI_AVAILABLE:
                try:
                    # curl-cffi est synchrone, donc on l'exécute dans un thread
                    import concurrent.futures
                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        result = await loop.run_in_executor(
                            executor, 
                            self._search_with_curl_cffi, 
                            search_query, 
                            max_results
                        )
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"curl-cffi échoué, fallback sur Playwright: {e}")
            
            # Fallback sur Playwright
            if not self.page or not self.browser:
                await self.init_browser()
            
            # Memory Express utilise des paramètres de requête pour la recherche
            search_url = f"https://www.memoryexpress.com/Search/Products?Search={search_query.replace(' ', '+')}"
            logger.info(f"🔍 Recherche Memory Express: {search_query}")
            logger.info(f"🔗 URL: {search_url}")
            
            # Utiliser 'domcontentloaded' pour être plus rapide
            try:
                await self.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
                logger.debug("Page Memory Express chargée avec domcontentloaded")
            except Exception as e:
                logger.warning(f"Timeout domcontentloaded, tentative avec 'load': {e}")
                try:
                    await self.page.goto(search_url, wait_until='load', timeout=30000)
                    logger.debug("Page Memory Express chargée avec load")
                except Exception as e2:
                    logger.error(f"Impossible de charger Memory Express: {e2}")
                    return []
            
            # Attendre que le JavaScript charge les produits
            await asyncio.sleep(random.uniform(4, 6))
            
            # Scroller pour déclencher le chargement lazy
            await self.page.evaluate("window.scrollTo(0, 500)")
            await asyncio.sleep(2)
            
            # Attendre que les produits soient chargés (plusieurs sélecteurs possibles)
            try:
                await self.page.wait_for_selector('.c-product-tile, .product-tile, .product-item, [class*="product"], .product-card, article, [data-product], .search-result', timeout=20000)
            except:
                logger.debug("Sélecteurs de produits Memory Express non trouvés, continuation...")
                await asyncio.sleep(3)
            
            # Vérifier si la page a chargé correctement
            page_title = await self.page.title()
            page_url = self.page.url
            logger.info(f"📄 Titre de la page Memory Express: {page_title}")
            logger.info(f"🔗 URL actuelle: {page_url}")
            
            # Vérifier le contenu de la page
            page_content = await self.page.content()
            logger.debug(f"📊 Taille du HTML: {len(page_content)} caractères")
            
            # Vérifier s'il y a Cloudflare
            is_cloudflare = False
            if 'Just a moment' in page_title or 'just a moment' in page_title.lower():
                is_cloudflare = True
                logger.warning("⚠️ Memory Express est protégé par Cloudflare - attente de la vérification...")
            
            # Vérifier s'il y a des résultats avec plusieurs méthodes
            page_info = await self.page.evaluate("""
                () => {
                    const bodyText = document.body ? document.body.innerText.substring(0, 500) : 'No body';
                    const titleText = document.title || '';
                    const info = {
                        bodyText: bodyText,
                        titleText: titleText,
                        productCount1: document.querySelectorAll('.c-product-tile, .product-tile, .product-item').length,
                        productCount2: document.querySelectorAll('[class*="product"]').length,
                        productCount3: document.querySelectorAll('[class*="Product"]').length,
                        productCount4: document.querySelectorAll('article, [data-product], .product-card').length,
                        hasNoResults: bodyText.includes('No results') || bodyText.includes('no results'),
                        hasError: bodyText.includes('error') || bodyText.includes('Error'),
                        isCloudflare: bodyText.includes('Verifying you are human') || 
                                     bodyText.includes('Verify you are human') ||
                                     bodyText.includes('Checking your browser') || 
                                     bodyText.includes('Just a moment') ||
                                     bodyText.includes('Cloudflare') ||
                                     titleText.includes('Just a moment') ||
                                     document.querySelector('#challenge-form') !== null ||
                                     document.querySelector('.cf-browser-verification') !== null
                    };
                    return info;
                }
            """)
            
            logger.info(f"📊 Info page Memory Express: {page_info}")
            
            # Si Cloudflare est détecté, attendre plus longtemps
            if page_info.get('isCloudflare') or is_cloudflare:
                logger.warning("🛡️ Cloudflare détecté - attente de 15-20 secondes...")
                # Attendre que Cloudflare se résolve
                for attempt in range(3):
                    await asyncio.sleep(5)
                    # Vérifier si Cloudflare est toujours présent
                    current_title = await self.page.title()
                    current_info = await self.page.evaluate("""
                        () => {
                            const bodyText = document.body ? document.body.innerText.substring(0, 200) : '';
                            return {
                                isCloudflare: bodyText.includes('Verifying') || 
                                            bodyText.includes('Verify you are human') ||
                                            bodyText.includes('Checking your browser') ||
                                            document.title.includes('Just a moment')
                            };
                        }
                    """)
                    
                    if not current_info.get('isCloudflare') and 'Just a moment' not in current_title:
                        logger.info("✅ Cloudflare résolu, continuation...")
                        break
                    logger.debug(f"⏳ Tentative {attempt + 1}/3 - Cloudflare toujours présent...")
                
                # Vérifier une dernière fois
                final_title = await self.page.title()
                if 'Just a moment' in final_title or page_info.get('isCloudflare'):
                    logger.error("❌ Cloudflare bloque toujours après 3 tentatives - Memory Express non disponible")
                    logger.warning("💡 Suggestion: Memory Express utilise Cloudflare qui bloque les scrapers automatiques")
                    return []
            
            if page_info.get('hasNoResults') or page_info.get('hasError'):
                logger.warning("Page Memory Express indique 'No results' ou erreur")
            
            total_products = sum([
                page_info.get('productCount1', 0),
                page_info.get('productCount2', 0),
                page_info.get('productCount3', 0),
                page_info.get('productCount4', 0)
            ])
            
            if total_products == 0:
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
            
            # Essayer d'extraire avec JavaScript
            try:
                js_results = await self.page.evaluate(f"""
                    () => {{
                        const maxResults = {max_results};
                        const results = [];
                        const products = document.querySelectorAll('.c-shca-icon-item, .c-product-tile, .product-tile, [class*="product"]');
                        
                        if (!products || products.length === 0) return [];
                        
                        for (let i = 0; i < Math.min(products.length, maxResults); i++) {{
                            const product = products[i];
                            let title = '';
                            let price = null;
                            let url = '';
                            
                            // Titre
                            const titleElem = product.querySelector('.c-shca-icon-item__body-name a, a[title], h2 a, h3 a');
                            if (titleElem) {{
                                title = (titleElem.getAttribute('title') || titleElem.textContent || '').trim();
                            }}
                            
                            // Prix
                            const priceElem = product.querySelector('.c-shca-icon-item__summary-list span, .c-shca-icon-item__summary-regular span, .price, [class*="price"]');
                            if (priceElem) {{
                                const match = priceElem.textContent.match(/\\$?\\s*([\\d,]+\\\\.?\\d*)/);
                                if (match) {{
                                    price = parseFloat(match[1].replace(/,/g, ''));
                                }}
                            }}
                            
                            // URL
                            const linkElem = product.querySelector('.c-shca-icon-item__body-name a[href*="/Products/"], a[href*="/Products/"]');
                            if (linkElem) {{
                                url = linkElem.getAttribute('href') || '';
                            }}
                            
                            if (title && price && price > 0) {{
                                results.push({{ title, price, url }});
                            }}
                        }}
                        return results;
                    }}
                """)
                
                if js_results and len(js_results) > 0:
                    products_list = []
                    for idx, result in enumerate(js_results):
                        title = result.get('title', '').strip()
                        price = result.get('price')
                        url = result.get('url', '').strip()
                        
                        # Valider les données
                        if not title or len(title) < 3:
                            continue
                        
                        if not price or price <= 0:
                            continue
                        
                        if url:
                            if not url.startswith('http'):
                                url = f"https://www.memoryexpress.com{url}"
                            if 'Search' in url or 'search' in url:
                                continue
                        else:
                            url = search_url
                        
                        products_list.append({
                            "title": title,
                            "price": float(price),
                            "url": url
                        })
                    
                    if products_list:
                        logger.info(f"✅ {len(products_list)} produit(s) Memory Express trouvé(s)")
                        return products_list
            except Exception as e:
                logger.error(f"❌ Erreur extraction JS Memory Express: {e}")
                import traceback
                logger.debug(traceback.format_exc())
            
            # Fallback: BeautifulSoup
            html = await self.page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            product_elems = []
            selectors = [
                'div.c-product-tile',
                'div.product-tile',
                'div.product-item',
                'div[class*="product"]',
                'article.product',
                '.product-card',
                '.search-result-item'
            ]
            
            for selector in selectors:
                product_elems = soup.select(selector)
                if product_elems:
                    logger.debug(f"Trouvé {len(product_elems)} produits Memory Express avec le sélecteur: {selector}")
                    break
            
            if not product_elems:
                logger.warning("Aucun produit trouvé avec BeautifulSoup sur Memory Express")
                return []
            
            products_list = []
            for product_elem in product_elems[:max_results]:
                # Extraire le titre
                title = None
                title_selectors = ['a[title]', 'h2', 'h3', '.product-name', '.product-title', '[class*="title"]', 'a']
                for selector in title_selectors:
                    title_elem = product_elem.select_one(selector)
                    if title_elem:
                        title = title_elem.get('title') or title_elem.get_text(strip=True)
                        if title:
                            break
                
                if not title:
                    title = "Produit Memory Express"
                
                # Extraire le prix
                price = None
                price_selectors = [
                    '.price', '.product-price', '.price-current',
                    '.price-regular', 'strong.price', 'span.price', 
                    '[class*="price"]', '.c-price', '.price-box'
                ]
                
                for selector in price_selectors:
                    price_elem = product_elem.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', price_text)
                        if price_match:
                            try:
                                test_price = float(price_match.group(1).replace(',', ''))
                                if 1 < test_price < 100000:
                                    price = test_price
                                    break
                            except ValueError:
                                continue
                
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
                url_selectors = [
                    'a[href*="/Products/"]',
                    'a[href*="/Product/"]',
                    'a.product-link',
                    'h2 a', 'h3 a',
                    'a[title]',
                    'a[href]'
                ]
                
                for selector in url_selectors:
                    url_elems = product_elem.select(selector)
                    for url_elem in url_elems:
                        href = url_elem.get('href')
                        if href and not href.startswith('javascript:') and '/Products/' in href:
                            if 'Search' not in href and 'search' not in href:
                                url = href
                                break
                    if url:
                        break
                
                if url:
                    if not url.startswith('http'):
                        url = f"https://www.memoryexpress.com{url}"
                else:
                    url = search_url
                
                products_list.append({
                    "title": title,
                    "price": price,
                    "url": url
                })
            
            return products_list
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Memory Express: {e}")
            return []


