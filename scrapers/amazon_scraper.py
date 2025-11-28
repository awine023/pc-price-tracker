"""Scraper Amazon.ca utilisant Playwright."""
import asyncio
import json
import logging
import re
import random
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page, Playwright

from utils.constants import USER_AGENTS, KNOWN_BRANDS

logger = logging.getLogger(__name__)


class AmazonScraper:
    """Scraper Amazon.ca utilisant Playwright (gratuit)."""
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def init_browser(self):
        """Initialise le navigateur Playwright avec anti-détection avancée."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--start-maximized',
                ]
            )
            
            # Headers réalistes pour Amazon.ca
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-CA,en-US;q=0.9,en;q=0.8,fr-CA;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
            
            context = await self.browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                locale='en-CA',
                timezone_id='America/Toronto',
                extra_http_headers=headers,
                java_script_enabled=True,
                has_touch=False,
                is_mobile=False,
            )
            
            # Scripts anti-détection avancés
            await context.add_init_script("""
                // Supprimer webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Chrome runtime
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-CA', 'en-US', 'en']
                });
                
                // Platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                // Hardware concurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                
                // Device memory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                
                // Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Masquer automation
                delete Object.getPrototypeOf(navigator).webdriver;
            """)
            
            self.page = await context.new_page()
            
            # Aller d'abord sur la page d'accueil Amazon.ca pour établir une session
            logger.info("Establishing session with Amazon.ca...")
            await self.page.goto('https://www.amazon.ca', wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))
            
            logger.info("Browser initialized with advanced stealth")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def close_browser(self):
        """Ferme le navigateur."""
        try:
            if self.page:
                try:
                    await self.page.close()
                except Exception as e:
                    logger.debug(f"Erreur lors de la fermeture de la page: {e}")
                finally:
                    self.page = None
        except Exception as e:
            logger.debug(f"Erreur lors de la fermeture de la page: {e}")
        
        try:
            if self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.debug(f"Erreur lors de la fermeture du navigateur: {e}")
                finally:
                    self.browser = None
        except Exception as e:
            logger.debug(f"Erreur lors de la fermeture du navigateur: {e}")
        
        try:
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    logger.debug(f"Erreur lors de l'arrêt de Playwright: {e}")
                finally:
                    self.playwright = None
        except Exception as e:
            logger.debug(f"Erreur lors de l'arrêt de Playwright: {e}")
    
    async def get_camelcamelcamel_lowest_price(self, asin: str) -> Optional[Dict]:
        """Récupère le prix historique le plus bas depuis CamelCamelCamel."""
        camel_url = f"https://ca.camelcamelcamel.com/product/{asin}"
        
        try:
            # Vérifier et réinitialiser le navigateur si nécessaire
            if not self.page or not self.browser:
                await self.init_browser()
            
            logger.debug(f"Scraping CamelCamelCamel pour {asin}")
            
            # Naviguer vers CamelCamelCamel
            await self.page.goto(camel_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))
            
            # Obtenir le HTML
            html = await self.page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # Chercher le prix le plus bas dans le tableau de CamelCamelCamel
            # CamelCamelCamel affiche généralement "Prix le plus bas" dans un tableau
            lowest_price = None
            lowest_date = None
            
            # Méthode 1: Chercher dans les tableaux avec "Prix le plus bas" ou "Lowest Price"
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    cell_text = ' '.join([cell.get_text(strip=True) for cell in cells]).lower()
                    
                    # Chercher "prix le plus bas" ou "lowest price"
                    if 'prix le plus bas' in cell_text or 'lowest price' in cell_text:
                        # Le prix devrait être dans la même ligne
                        for cell in cells:
                            cell_text_price = cell.get_text(strip=True)
                            # Chercher un prix (format: $XXX.XX)
                            price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', cell_text_price)
                            if price_match:
                                try:
                                    test_price = float(price_match.group(1).replace(',', ''))
                                    if 1 < test_price < 100000:
                                        lowest_price = test_price
                                        
                                        # Chercher la date dans la même ligne ou la ligne suivante
                                        date_match = re.search(r'(\w+\s+\d{1,2},\s+\d{4})', ' '.join([c.get_text() for c in cells]))
                                        if date_match:
                                            lowest_date = date_match.group(1)
                                        break
                                except ValueError:
                                    continue
                        if lowest_price:
                            break
                if lowest_price:
                    break
            
            # Méthode 2: Chercher dans les divs/spans avec des classes spécifiques
            if not lowest_price:
                # CamelCamelCamel utilise souvent des classes comme "lowest-price" ou "best-price"
                price_elements = soup.find_all(['div', 'span'], 
                    class_=re.compile(r'lowest|best.*price|historical', re.I))
                for elem in price_elements:
                    text = elem.get_text(strip=True)
                    # Chercher un prix
                    price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', text)
                    if price_match:
                        try:
                            test_price = float(price_match.group(1).replace(',', ''))
                            if 1 < test_price < 100000:
                                lowest_price = test_price
                                
                                # Chercher la date dans le parent ou les siblings
                                parent = elem.parent
                                if parent:
                                    parent_text = parent.get_text()
                                    date_match = re.search(r'(\w+\s+\d{1,2},\s+\d{4})', parent_text)
                                    if date_match:
                                        lowest_date = date_match.group(1)
                                break
                        except ValueError:
                            continue
            
            # Méthode 3: Chercher dans le texte de la page
            if not lowest_price:
                page_text = soup.get_text()
                # Pattern pour "Prix le plus bas: $XXX.XX (Date)"
                patterns = [
                    r'prix\s+le\s+plus\s+bas[:\s]+\$?\s*([\d,]+\.?\d*)\s*\(?(\w+\s+\d{1,2},\s+\d{4})?\)?',
                    r'lowest\s+price[:\s]+\$?\s*([\d,]+\.?\d*)\s*\(?(\w+\s+\d{1,2},\s+\d{4})?\)?',
                ]
                for pattern in patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        try:
                            test_price = float(match.group(1).replace(',', ''))
                            if 1 < test_price < 100000:
                                lowest_price = test_price
                                if len(match.groups()) > 1 and match.group(2):
                                    lowest_date = match.group(2)
                                break
                        except (ValueError, IndexError):
                            continue
            
            if lowest_price:
                logger.info(f"✅ Prix historique CamelCamelCamel trouvé: ${lowest_price:.2f} ({lowest_date or 'date inconnue'})")
                return {
                    'price': lowest_price,
                    'date': lowest_date
                }
            else:
                logger.debug(f"Prix historique CamelCamelCamel non trouvé pour {asin}")
                return None
                
        except Exception as e:
            logger.debug(f"Erreur lors du scraping CamelCamelCamel pour {asin}: {e}")
            return None
    
    async def get_product_info(self, asin: str) -> Optional[Dict]:
        """Récupère les informations d'un produit Amazon.ca via Playwright."""
        url = f"https://www.amazon.ca/dp/{asin}"
        
        try:
            # Vérifier et réinitialiser le navigateur si nécessaire
            if not self.page or not self.browser:
                logger.info("Navigateur non initialisé, initialisation...")
                await self.init_browser()
            
            # Vérifier que la page est toujours valide
            try:
                # Test simple pour vérifier que la page fonctionne
                _ = self.page.url
            except Exception:
                logger.warning("Page invalide, réinitialisation du navigateur...")
                await self.close_browser()
                await asyncio.sleep(1)
                await self.init_browser()
            
            # Naviguer vers la page
            logger.info(f"Navigating to: {url}")
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # Attendre le chargement
            await asyncio.sleep(random.uniform(3, 5))
            
            # Simuler un comportement humain
            await self.page.evaluate("window.scrollTo(0, 500)")
            await asyncio.sleep(random.uniform(1, 2))
            
            # Obtenir le HTML
            html = await self.page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # Extraire le titre
            title = None
            title_elem = soup.find('span', {'id': 'productTitle'})
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                # Fallback
                title_elem = soup.find('h1', {'class': re.compile(r'product', re.I)})
                if title_elem:
                    title = title_elem.get_text(strip=True)
            
            if not title:
                title = "Produit Amazon"
            
            # Extraire le prix
            price = None
            
            # Méthode 1: Prix principal (span.a-price-whole)
            price_elem = soup.find('span', {'class': 'a-price-whole'})
            if price_elem:
                price_text = price_elem.get_text(strip=True).replace(',', '')
                try:
                    price = float(price_text)
                except ValueError:
                    pass
            
            # Méthode 2: Prix dans span.a-offscreen
            if not price:
                price_elem = soup.find('span', {'class': 'a-offscreen'})
                if price_elem:
                    price_text = price_elem.get_text(strip=True).replace('$', '').replace(',', '').replace('CAD', '').strip()
                    try:
                        price = float(price_text)
                    except ValueError:
                        pass
            
            # Méthode 3: Chercher dans le texte de la page
            if not price:
                page_text = soup.get_text()
                price_patterns = [
                    r'\$\s*([\d,]+\.?\d*)\s*CAD',
                    r'CAD\s*\$?\s*([\d,]+\.?\d*)',
                    r'\$\s*([\d,]+\.?\d*)',
                ]
                for pattern in price_patterns:
                    matches = re.findall(pattern, page_text)
                    if matches:
                        try:
                            test_price = float(matches[0].replace(',', ''))
                            if 10 < test_price < 100000:  # Validation raisonnable
                                price = test_price
                                break
                        except ValueError:
                            continue
            
            # Vérifier le stock
            in_stock = True
            availability_elem = soup.find('div', {'id': 'availability'})
            if availability_elem:
                availability_text = availability_elem.get_text(strip=True).lower()
                out_of_stock_indicators = [
                    'currently unavailable', 'out of stock',
                    'temporarily out of stock', 'available from these sellers'
                ]
                for indicator in out_of_stock_indicators:
                    if indicator in availability_text:
                        in_stock = False
                        break
            
            # Extraire le prix original (pour calculer le rabais)
            original_price = None
            list_price_elem = soup.find('span', {'class': 'a-price a-text-price'})
            if list_price_elem:
                original_text = list_price_elem.get_text(strip=True)
                original_match = re.search(r'[\d,]+\.?\d*', original_text.replace(',', ''))
                if original_match:
                    try:
                        original_price = float(original_match.group())
                    except ValueError:
                        pass
            
            # Extraire le prix historique le plus bas depuis CamelCamelCamel (plus fiable)
            amazon_lowest_price = None
            amazon_lowest_date = None
            
            # PRIORITÉ 1: Utiliser CamelCamelCamel pour obtenir le prix historique
            try:
                camel_data = await self.get_camelcamelcamel_lowest_price(asin)
                if camel_data:
                    amazon_lowest_price = camel_data.get('price')
                    amazon_lowest_date = camel_data.get('date')
                    logger.info(f"✅ Prix historique obtenu depuis CamelCamelCamel: ${amazon_lowest_price:.2f}")
            except Exception as e:
                logger.debug(f"Erreur lors de la récupération depuis CamelCamelCamel: {e}")
            
            # PRIORITÉ 2: Si CamelCamelCamel n'a pas fonctionné, essayer Amazon directement
            if not amazon_lowest_price:
                # Méthode 1: Chercher dans les données JavaScript de la page (via Playwright)
                try:
                    # Exécuter du JavaScript pour extraire les données de prix depuis les objets globaux
                    js_result = await self.page.evaluate("""
                        () => {
                            // Méthode 1: Chercher dans window.ue_backflow_data
                            if (window.ue_backflow_data) {
                                const data = window.ue_backflow_data;
                                if (data.priceHistory && Array.isArray(data.priceHistory) && data.priceHistory.length > 0) {
                                    const prices = data.priceHistory.map(p => parseFloat(p.price || 0)).filter(p => p > 0);
                                    if (prices.length > 0) {
                                        const lowest = Math.min(...prices);
                                        const lowestEntry = data.priceHistory.find(p => parseFloat(p.price) === lowest);
                                        return {
                                            price: lowest,
                                            date: lowestEntry?.date || lowestEntry?.timestamp || null
                                        };
                                    }
                                }
                            }
                            
                            // Méthode 2: Chercher dans window.ue_sn
                            if (window.ue_sn) {
                                const sn = window.ue_sn;
                                if (sn.priceHistory && Array.isArray(sn.priceHistory)) {
                                    const prices = sn.priceHistory.map(p => parseFloat(p.price || 0)).filter(p => p > 0);
                                    if (prices.length > 0) {
                                        const lowest = Math.min(...prices);
                                        const lowestEntry = sn.priceHistory.find(p => parseFloat(p.price) === lowest);
                                        return {
                                            price: lowest,
                                            date: lowestEntry?.date || lowestEntry?.timestamp || null
                                        };
                                    }
                                }
                            }
                            
                            // Méthode 3: Chercher dans les scripts pour des patterns JSON
                            const scripts = document.querySelectorAll('script');
                            for (let script of scripts) {
                                const text = script.textContent || script.innerHTML || '';
                                
                                // Chercher "lowestPrice" ou "priceHistory"
                                const lowestMatch = text.match(/"lowestPrice"\\s*:\\s*([\\d.]+)/);
                                if (lowestMatch) {
                                    return {price: parseFloat(lowestMatch[1]), date: null};
                                }
                                
                                // Chercher dans priceHistory array
                                const historyMatch = text.match(/"priceHistory"\\s*:\\s*\\[([^\\]]+)\\]/);
                                if (historyMatch) {
                                    try {
                                        const historyStr = '[' + historyMatch[1] + ']';
                                        const history = JSON.parse(historyStr);
                                        if (Array.isArray(history) && history.length > 0) {
                                            const prices = history.map(p => parseFloat(p.price || p.value || 0)).filter(p => p > 0);
                                            if (prices.length > 0) {
                                                const lowest = Math.min(...prices);
                                                const lowestEntry = history.find(p => parseFloat(p.price || p.value) === lowest);
                                                return {
                                                    price: lowest,
                                                    date: lowestEntry?.date || lowestEntry?.timestamp || null
                                                };
                                            }
                                        }
                                    } catch (e) {
                                        // Ignorer les erreurs de parsing
                                    }
                                }
                            }
                            
                            return null;
                        }
                    """)
                    if js_result and js_result.get('price'):
                        amazon_lowest_price = float(js_result['price'])
                        amazon_lowest_date = js_result.get('date')
                        logger.debug(f"Prix historique Amazon trouvé via JS: ${amazon_lowest_price}")
                except Exception as e:
                    logger.debug(f"Erreur lors de l'extraction JS du prix historique: {e}")
                
                # Méthode 2: Chercher dans les scripts JSON-LD et autres scripts JSON
                if not amazon_lowest_price:
                    scripts = soup.find_all('script')
                    for script in scripts:
                        script_content = script.string
                        if not script_content:
                            continue
                        
                        # Chercher des patterns JSON avec prix historique
                        try:
                            # Chercher des objets JSON avec "lowestPrice", "priceHistory", etc.
                            json_patterns = [
                                r'"lowestPrice"\s*:\s*([\d.]+)',
                                r'"bestPrice"\s*:\s*([\d.]+)',
                                r'"historicalLowPrice"\s*:\s*([\d.]+)',
                                r'"allTimeLow"\s*:\s*([\d.]+)',
                                r'"minPrice"\s*:\s*([\d.]+)',
                            ]
                            for pattern in json_patterns:
                                matches = re.findall(pattern, script_content, re.IGNORECASE)
                                if matches:
                                    try:
                                        test_price = float(matches[0])
                                        if 1 < test_price < 100000:
                                            amazon_lowest_price = test_price
                                            # Chercher aussi la date associée
                                            date_match = re.search(r'"date"\s*:\s*"([^"]+)"', script_content)
                                            if date_match:
                                                amazon_lowest_date = date_match.group(1)
                                            logger.debug(f"Prix historique Amazon trouvé via pattern JSON: ${amazon_lowest_price}")
                                            break
                                    except ValueError:
                                        continue
                            
                            if amazon_lowest_price:
                                break
                            
                            # Essayer de parser le JSON directement pour priceHistory
                            if 'priceHistory' in script_content:
                                try:
                                    # Chercher un array priceHistory
                                    history_match = re.search(r'"priceHistory"\s*:\s*\[([^\]]+)\]', script_content, re.DOTALL)
                                    if history_match:
                                        # Extraire les prix de l'array
                                        prices_match = re.findall(r'"price"\s*:\s*([\d.]+)', history_match.group(1))
                                        if prices_match:
                                            prices = [float(p) for p in prices_match if 1 < float(p) < 100000]
                                            if prices:
                                                amazon_lowest_price = min(prices)
                                                logger.debug(f"Prix historique Amazon trouvé via priceHistory array: ${amazon_lowest_price}")
                                except (json.JSONDecodeError, ValueError, KeyError) as e:
                                    logger.debug(f"Erreur parsing priceHistory: {e}")
                        except Exception as e:
                            logger.debug(f"Erreur lors de l'analyse du script: {e}")
                            continue
                
                # Méthode 3: Chercher dans le HTML brut (fallback)
                if not amazon_lowest_price:
                    page_text = html
                    # Chercher des patterns comme "lowestPrice", "priceHistory", "bestPrice"
                    patterns = [
                        r'"lowestPrice"\s*:\s*([\d.]+)',
                        r'"bestPrice"\s*:\s*([\d.]+)',
                        r'"historicalLowPrice"\s*:\s*([\d.]+)',
                        r'"allTimeLow"\s*:\s*([\d.]+)',
                        r'"minPrice"\s*:\s*([\d.]+)',
                    ]
                    for pattern in patterns:
                        matches = re.findall(pattern, page_text, re.IGNORECASE)
                        if matches:
                            try:
                                test_price = float(matches[0])
                                if 1 < test_price < 100000:  # Validation raisonnable
                                    amazon_lowest_price = test_price
                                    logger.debug(f"Prix historique Amazon trouvé via HTML brut: ${amazon_lowest_price}")
                                    break
                            except ValueError:
                                continue
                
                # Méthode 4: Chercher dans les éléments HTML spécifiques (sections d'historique de prix)
                if not amazon_lowest_price:
                    # Chercher dans les divs/spans qui pourraient contenir l'historique
                    price_history_elements = soup.find_all(['div', 'span'], 
                        string=re.compile(r'lowest|historique|all.*time.*low', re.I))
                    for elem in price_history_elements:
                        parent = elem.parent
                        if parent:
                            # Chercher un prix dans le texte du parent
                            parent_text = parent.get_text()
                            price_match = re.search(r'\$?\s*([\d,]+\.?\d*)', parent_text)
                            if price_match:
                                try:
                                    test_price = float(price_match.group(1).replace(',', ''))
                                    if 1 < test_price < 100000 and test_price < price:  # Doit être inférieur au prix actuel
                                        amazon_lowest_price = test_price
                                        logger.debug(f"Prix historique Amazon trouvé via éléments HTML: ${amazon_lowest_price}")
                                        break
                                except ValueError:
                                    continue
                        if amazon_lowest_price:
                            break
            
            # Log si on n'a pas trouvé le prix historique
            if not amazon_lowest_price:
                logger.debug(f"Prix historique Amazon non trouvé pour {asin}")
            
            if not price:
                logger.warning(f"Could not find price for {asin}")
                return None
            
            return {
                "asin": asin,
                "title": title,
                "current_price": price,
                "lowest_price": amazon_lowest_price or price,  # Utiliser le prix historique Amazon si disponible
                "amazon_lowest_price": amazon_lowest_price,  # Prix historique Amazon
                "amazon_lowest_date": amazon_lowest_date,  # Date du prix historique
                "in_stock": in_stock,
                "original_price": original_price,
                "url": url,
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du scraping: {e}")
            return None
    
    async def get_category_products(self, search_query: str, max_products: int = 20) -> List[Dict]:
        """Récupère tous les produits d'une catégorie/recherche Amazon.ca avec leurs rabais."""
        # Construire l'URL de recherche
        search_url = f"https://www.amazon.ca/s?k={search_query.replace(' ', '+')}"
        
        try:
            # Vérifier et réinitialiser le navigateur si nécessaire
            if not self.page or not self.browser:
                logger.info("Navigateur non initialisé, initialisation...")
                await self.init_browser()
            
            # Vérifier que la page est toujours valide
            try:
                # Test simple pour vérifier que la page fonctionne
                _ = self.page.url
            except Exception:
                logger.warning("Page invalide, réinitialisation du navigateur...")
                await self.close_browser()
                await asyncio.sleep(1)
                await self.init_browser()
            
            logger.info(f"Scraping category: {search_query}")
            
            # Naviguer vers la page de recherche avec referer
            # Utiliser 'domcontentloaded' d'abord (plus rapide), puis fallback sur 'load' si nécessaire
            try:
                await self.page.goto(search_url, wait_until='domcontentloaded', timeout=45000, referer='https://www.amazon.ca')
                logger.debug("Page chargée avec domcontentloaded")
            except Exception as e:
                logger.warning(f"Timeout avec domcontentloaded, tentative avec 'load': {e}")
                try:
                    await self.page.goto(search_url, wait_until='load', timeout=30000, referer='https://www.amazon.ca')
                    logger.debug("Page chargée avec load")
                except Exception as e2:
                    logger.error(f"Impossible de charger la page Amazon: {e2}")
                    return []
            
            # Vérifier si on a été bloqués
            await asyncio.sleep(random.uniform(3, 5))
            page_title = await self.page.title()
            if 'something went wrong' in page_title.lower() or 'error' in page_title.lower():
                logger.warning("⚠️ Amazon a détecté le bot, tentative de contournement...")
                # Attendre plus longtemps et réessayer
                await asyncio.sleep(random.uniform(5, 8))
                try:
                    await self.page.reload(wait_until='domcontentloaded', timeout=30000)
                except:
                    await self.page.reload(wait_until='load', timeout=20000)
                await asyncio.sleep(random.uniform(3, 5))
            
            # Simuler un comportement humain
            await self.page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            await asyncio.sleep(random.uniform(1, 2))
            
            # Scroller progressivement pour charger plus de produits
            for i in range(3):
                scroll_pos = 500 * (i + 1)
                await self.page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                await asyncio.sleep(random.uniform(1.5, 2.5))
                # Petit mouvement de souris
                await self.page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                await asyncio.sleep(random.uniform(0.5, 1))
            
            # Vérifier à nouveau si on a été bloqués
            page_title = await self.page.title()
            current_url = self.page.url
            
            if 'something went wrong' in page_title.lower() or 'error' in page_title.lower():
                logger.error(f"❌ Amazon bloque le scraping - Titre: {page_title}")
                logger.error(f"   URL: {current_url}")
                # Essayer de fermer et recréer le navigateur
                try:
                    await self.close_browser()
                    await asyncio.sleep(2)
                    await self.init_browser()
                    # Réessayer une fois
                    try:
                        await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000, referer='https://www.amazon.ca')
                    except:
                        await self.page.goto(search_url, wait_until='load', timeout=20000, referer='https://www.amazon.ca')
                    await asyncio.sleep(random.uniform(5, 7))
                    page_title = await self.page.title()
                    if 'something went wrong' in page_title.lower():
                        logger.error("❌ Amazon bloque toujours après réessai")
                        return []
                except Exception as e:
                    logger.error(f"Erreur lors de la réinitialisation: {e}")
                    return []
            
            # Obtenir le HTML
            html = await self.page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            products = []
            
            # Méthode 1: Chercher avec data-component-type (méthode principale)
            product_containers = soup.find_all('div', {'data-component-type': 's-search-result'})
            
            # Méthode 2: Si pas de résultats, chercher avec data-asin directement
            if not product_containers:
                logger.debug("Méthode 1 échouée, essai méthode 2 (data-asin)")
                # Chercher tous les divs qui contiennent un data-asin et qui semblent être des produits
                all_divs = soup.find_all('div')
                for div in all_divs:
                    if div.get('data-asin') and div.get('data-asin') != '':
                        # Vérifier si c'est un conteneur de produit (contient un titre)
                        if div.find('h2') or div.find('span', {'class': re.compile(r'title|text', re.I)}):
                            product_containers.append(div)
            
            # Méthode 3: Chercher avec class s-result-item
            if not product_containers:
                logger.debug("Méthode 2 échouée, essai méthode 3 (s-result-item)")
                product_containers = soup.find_all('div', {'class': re.compile(r's-result-item', re.I)})
            
            logger.info(f"Trouvé {len(product_containers)} conteneurs de produits")
            
            for container in product_containers[:max_products]:
                try:
                    # Extraire l'ASIN
                    asin = container.get('data-asin')
                    if not asin:
                        continue
                    
                    # Extraire le titre (plusieurs méthodes)
                    title = None
                    title_elem = container.find('h2', {'class': re.compile(r's-title', re.I)})
                    if not title_elem:
                        title_elem = container.find('h2')
                    if not title_elem:
                        title_elem = container.find('span', {'class': re.compile(r'text-normal', re.I)})
                    if not title_elem:
                        # Chercher n'importe quel span avec du texte
                        title_elem = container.find('span', {'class': re.compile(r'text', re.I)})
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                    
                    if not title or len(title) < 5:
                        # Dernière tentative: chercher dans tous les spans
                        all_spans = container.find_all('span')
                        for span in all_spans:
                            text = span.get_text(strip=True)
                            if len(text) > 20 and len(text) < 200:
                                title = text
                                break
                    
                    if not title:
                        title = "Produit sans titre"
                    
                    # Extraire le prix actuel
                    current_price = None
                    price_elem = container.find('span', {'class': 'a-price-whole'})
                    if price_elem:
                        price_text = price_elem.get_text(strip=True).replace(',', '')
                        try:
                            current_price = float(price_text)
                        except ValueError:
                            pass
                    
                    # Si pas de prix, chercher dans a-offscreen
                    if not current_price:
                        price_elem = container.find('span', {'class': 'a-offscreen'})
                        if price_elem:
                            price_text = price_elem.get_text(strip=True).replace('$', '').replace(',', '').strip()
                            try:
                                current_price = float(price_text)
                            except ValueError:
                                pass
                    
                    # Extraire le prix original (rabais) - AMÉLIORÉ
                    original_price = None
                    
                    # Méthode 1: Prix barré (a-price a-text-price)
                    list_price_elem = container.find('span', {'class': 'a-price a-text-price'})
                    if list_price_elem:
                        original_text = list_price_elem.get_text(strip=True)
                        original_match = re.search(r'[\d,]+\.?\d*', original_text.replace(',', ''))
                        if original_match:
                            try:
                                original_price = float(original_match.group())
                            except ValueError:
                                pass
                    
                    # Méthode 2: Chercher dans les spans avec "was" ou "list price"
                    if not original_price:
                        all_spans = container.find_all('span')
                        for span in all_spans:
                            span_text = span.get_text(strip=True).lower()
                            # Chercher des patterns comme "was $XXX" ou "list price $XXX"
                            if 'was' in span_text or 'list price' in span_text or 'reg' in span_text:
                                price_match = re.search(r'\$?([\d,]+\.?\d*)', span.get_text())
                                if price_match:
                                    try:
                                        test_price = float(price_match.group(1).replace(',', ''))
                                        if test_price > current_price and test_price < current_price * 2:
                                            original_price = test_price
                                            break
                                    except ValueError:
                                        continue
                    
                    # Méthode 3: Chercher dans savings/badge de rabais
                    if not original_price:
                        savings_elem = container.find('span', {'class': re.compile(r'savings|badge|discount', re.I)})
                        if savings_elem:
                            savings_text = savings_elem.get_text()
                            # Chercher un prix barré dans le texte
                            price_match = re.search(r'\$([\d,]+\.?\d*)', savings_text)
                            if price_match:
                                try:
                                    test_price = float(price_match.group(1).replace(',', ''))
                                    if test_price > current_price:
                                        original_price = test_price
                                except ValueError:
                                    pass
                    
                    # Méthode 4: Chercher dans aria-label ou data attributes
                    if not original_price:
                        # Chercher dans les attributs data
                        price_attrs = container.find_all(attrs={'data-a-price': True})
                        for elem in price_attrs:
                            try:
                                data_price = float(elem.get('data-a-price', '').replace(',', ''))
                                if data_price > current_price:
                                    original_price = data_price
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # Méthode 5: Chercher un pourcentage de rabais et calculer le prix original
                    if not original_price and current_price:
                        # Chercher des badges comme "Save 30%" ou "-30%"
                        discount_badge = container.find(string=re.compile(r'(?:save|save up to|-\s*)(\d+)%', re.I))
                        if not discount_badge:
                            discount_badge = container.find('span', string=re.compile(r'(?:save|-\s*)(\d+)%', re.I))
                        if discount_badge:
                            discount_text = discount_badge if isinstance(discount_badge, str) else discount_badge.get_text()
                            discount_match = re.search(r'(\d+)%', discount_text)
                            if discount_match:
                                discount_pct = float(discount_match.group(1))
                                # Calculer le prix original: current = original * (1 - discount/100)
                                # Donc: original = current / (1 - discount/100)
                                if discount_pct > 0 and discount_pct < 100:
                                    calculated_original = current_price / (1 - discount_pct / 100)
                                    if calculated_original > current_price:
                                        original_price = calculated_original
                    
                    # Extraire la note (rating)
                    rating = None
                    rating_elem = container.find('span', {'class': re.compile(r'a-icon-alt', re.I)})
                    if rating_elem:
                        rating_text = rating_elem.get_text(strip=True)
                        # Format: "4.5 out of 5 stars" ou "4,5 sur 5 étoiles"
                        rating_match = re.search(r'([\d,]+\.?\d*)\s*(?:out of|sur)', rating_text, re.I)
                        if rating_match:
                            try:
                                rating = float(rating_match.group(1).replace(',', '.'))
                            except ValueError:
                                pass
                    
                    # Si pas trouvé, chercher dans aria-label
                    if not rating:
                        rating_elem = container.find('span', {'aria-label': re.compile(r'(\d+\.?\d*)\s*(?:out of|sur)', re.I)})
                        if rating_elem:
                            aria_label = rating_elem.get('aria-label', '')
                            rating_match = re.search(r'([\d,]+\.?\d*)\s*(?:out of|sur)', aria_label, re.I)
                            if rating_match:
                                try:
                                    rating = float(rating_match.group(1).replace(',', '.'))
                                except ValueError:
                                    pass
                    
                    # Vérifier si en stock
                    in_stock = True
                    stock_elem = container.find('span', {'class': re.compile(r'unavailable|out.*stock', re.I)})
                    if stock_elem:
                        in_stock = False
                    
                    # Vérifier si c'est une marque connue
                    is_known_brand = False
                    title_lower = title.lower()
                    for brand in KNOWN_BRANDS:
                        if brand.lower() in title_lower:
                            is_known_brand = True
                            break
                    
                    # FILTRE SPÉCIAL: Pour les processeurs Ryzen, ne garder que Ryzen 7 et Ryzen 9 (pas Ryzen 5)
                    if 'ryzen' in title_lower:
                        # Vérifier si c'est un Ryzen 5 (à exclure)
                        if re.search(r'ryzen\s*5', title_lower, re.I):
                            continue  # Rejeter les Ryzen 5
                        # Vérifier si c'est un Ryzen 7 ou 9 (à garder)
                        if not (re.search(r'ryzen\s*[79]', title_lower, re.I) or 
                                re.search(r'ryzen\s*7\d{3}', title_lower, re.I) or 
                                re.search(r'ryzen\s*9\d{3}', title_lower, re.I)):
                            # Si c'est un Ryzen mais pas 7 ou 9, vérifier s'il y a un numéro de modèle
                            # Exemples: Ryzen 7 7800X3D, Ryzen 9 7950X
                            ryzen_model_match = re.search(r'ryzen\s*(\d)', title_lower, re.I)
                            if ryzen_model_match:
                                ryzen_number = int(ryzen_model_match.group(1))
                                if ryzen_number != 7 and ryzen_number != 9:
                                    continue  # Rejeter si ce n'est pas un 7 ou 9
                            else:
                                # Si on ne peut pas déterminer, on garde (pour éviter de rejeter des modèles valides)
                                pass
                    
                    # Calculer le pourcentage de rabais
                    discount_percent = None
                    if original_price and current_price and original_price > current_price:
                        discount_percent = ((original_price - current_price) / original_price) * 100
                    
                    # FILTRES: Ne garder que les produits qui répondent aux critères
                    # 1. Prix valide
                    # 2. Note >= 4.0 étoiles (ou pas de note)
                    # 3. Marque connue
                    if current_price and 10 < current_price < 100000:
                        # Vérifier la note (doit être >= 4.0 ou None)
                        if rating is not None and rating < 4.0:
                            continue  # Rejeter les produits avec moins de 4 étoiles
                        
                        # Vérifier la marque
                        if not is_known_brand:
                            continue  # Rejeter les produits de marques inconnues
                        
                        products.append({
                            "asin": asin,
                            "title": title,
                            "current_price": current_price,
                            "original_price": original_price,
                            "discount_percent": round(discount_percent, 1) if discount_percent else None,
                            "rating": rating,
                            "in_stock": in_stock,
                            "url": f"https://www.amazon.ca/dp/{asin}",
                        })
                
                except Exception as e:
                    logger.debug(f"Erreur lors de l'extraction d'un produit: {e}")
                    continue
            
            logger.info(f"Trouvé {len(products)} produits (4+ étoiles, marques connues) dans la catégorie '{search_query}'")
            return products
            
        except Exception as e:
            logger.error(f"Erreur lors du scraping de catégorie: {e}")
            # Réinitialiser le navigateur en cas d'erreur
            try:
                await self.close_browser()
            except:
                pass
            return []

