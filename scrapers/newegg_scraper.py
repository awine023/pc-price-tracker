"""Scraper pour Newegg Canada."""
import asyncio
import logging
import re
import random
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page, Playwright

from utils.constants import USER_AGENTS

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
    
    async def search_products(self, search_query: str, max_results: int = 3) -> List[Dict]:
        """Recherche des produits sur Newegg Canada et retourne plusieurs résultats."""
        try:
            if not self.page or not self.browser:
                await self.init_browser()
            
            search_url = f"https://www.newegg.ca/p/pl?d={search_query.replace(' ', '+')}"
            
            await self.page.goto(search_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(3, 5))
            
            # Essayer d'extraire avec JavaScript d'abord (plus fiable)
            try:
                js_results = await self.page.evaluate(f"""
                    () => {{
                        const maxResults = {max_results};
                        const results = [];
                        
                        // Chercher tous les produits dans les résultats de recherche
                        const products = document.querySelectorAll('.item-cell, .item-container, [class*="item-cell"], [class*="item-container"]');
                        
                        if (products.length === 0) {{
                            const altProducts = document.querySelectorAll('[class*="item"]');
                            if (altProducts.length > 0) {{
                                products = altProducts;
                            }}
                        }}
                        
                        for (let i = 0; i < Math.min(products.length, maxResults); i++) {{
                            const product = products[i];
                            
                            // Extraire le titre
                            let title = '';
                            const titleSelectors = [
                                'a.item-title', '.item-title', 
                                'img[alt]', 'a[title]', 
                                'a.item-img', '.item-info a'
                            ];
                            for (const selector of titleSelectors) {{
                                const titleElem = product.querySelector(selector);
                                if (titleElem) {{
                                    title = (
                                        titleElem.getAttribute('title') || 
                                        titleElem.getAttribute('alt') || 
                                        titleElem.textContent || 
                                        ''
                                    ).trim();
                                    if (title) break;
                                }}
                            }}
                            
                            // Extraire le prix
                            let price = null;
                            const priceSelectors = [
                                'li.price-current', '.price-current',
                                '.price', 'ul.price li',
                                '[class*="price-current"]', 
                                'strong.price-current', '.price-box'
                            ];
                            
                            for (const selector of priceSelectors) {{
                                const priceElem = product.querySelector(selector);
                                if (priceElem) {{
                                    const priceText = (priceElem.textContent || priceElem.innerText || '').trim();
                                    const matches = priceText.matchAll(/[\\d,]+\\\\.?\\d*/g);
                                    for (const match of matches) {{
                                        const testPrice = parseFloat(match[0].replace(/,/g, ''));
                                        if (testPrice > 1 && testPrice < 100000) {{
                                            price = testPrice;
                                            break;
                                        }}
                                    }}
                                    if (price) break;
                                }}
                            }}
                            
                            // Si pas trouvé, chercher dans tout le texte
                            if (!price || price <= 0) {{
                                const allText = product.textContent || '';
                                const priceMatches = allText.matchAll(/\\$?\\s*([\\d,]+\\\\.?\\d*)/g);
                                for (const match of priceMatches) {{
                                    const testPrice = parseFloat(match[1].replace(/,/g, ''));
                                    if (testPrice > 1 && testPrice < 100000) {{
                                        price = testPrice;
                                        break;
                                    }}
                                }}
                            }}
                            
                            // Extraire l'URL - IMPORTANT: chercher un lien direct vers le produit
                            let url = '';
                            const linkSelectors = [
                                'a.item-title', 
                                'a[href*="/p/"]', 
                                'a[href*="/Product"]',
                                'a.item-img',
                                'a[href]'
                            ];
                            for (const selector of linkSelectors) {{
                                const linkElem = product.querySelector(selector);
                                if (linkElem) {{
                                    url = linkElem.getAttribute('href') || '';
                                    // S'assurer que c'est un lien direct, pas une page de recherche
                                    if (url && !url.includes('p/pl') && !url.includes('Search')) {{
                                        break;
                                    }}
                                }}
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
                    for result in js_results:
                        url = result.get('url', '')
                        # S'assurer que l'URL est complète et directe
                        if url:
                            if not url.startswith('http'):
                                url = f"https://www.newegg.ca{url}"
                            # Vérifier que ce n'est pas une page de recherche
                            if 'p/pl' in url or 'Search' in url:
                                continue
                        else:
                            url = search_url  # Fallback si pas de lien direct
                        
                        products_list.append({
                            "title": result.get('title', 'Produit Newegg'),
                            "price": result['price'],
                            "url": url
                        })
                    
                    if products_list:
                        return products_list
            except Exception as e:
                logger.debug(f"Erreur extraction JS Newegg: {e}")
            
            # Fallback: BeautifulSoup - chercher plusieurs produits
            html = await self.page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # Chercher tous les produits
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
            
            products_list = []
            for product_elem in product_elems[:max_results]:
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
                    title = "Produit Newegg"
                
                # Extraire le prix avec plusieurs méthodes
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
                        # Newegg peut avoir "CAD $XXX.XX" ou "$XXX.XX" ou "XXX.XX"
                        # Chercher tous les nombres et prendre le premier valide
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
                    # Chercher tous les prix et prendre le premier valide
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
                
                # S'assurer que l'URL est un lien direct, pas une page de recherche
                if url and ('p/pl' in url or 'Search' in url):
                    # Essayer de trouver un meilleur lien
                    better_link = product_elem.select_one('a.item-title, a[href*="/p/"]')
                    if better_link and better_link.get('href'):
                        better_url = better_link.get('href')
                        if not better_url.startswith('http'):
                            better_url = f"https://www.newegg.ca{better_url}"
                        if 'p/pl' not in better_url and 'Search' not in better_url:
                            url = better_url
                
                if not url or 'p/pl' in url or 'Search' in url:
                    url = search_url  # Fallback
                
                products_list.append({
                    "title": title,
                    "price": price,
                    "url": url
                })
            
            return products_list
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Newegg: {e}")
            return []


