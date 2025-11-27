"""
Telegram Bot pour surveiller les prix Amazon Canada avec Playwright (gratuit)
"""
import asyncio
import json
import logging
import re
import time
import random
from datetime import datetime
from typing import Dict, Optional, List

import asyncio
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Browser, Page, Playwright
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import (
    CHECK_INTERVAL_MINUTES,
    TELEGRAM_TOKEN,
    BIG_DISCOUNT_THRESHOLD,
    PRICE_ERROR_THRESHOLD,
    MIN_PRICE_FOR_ERROR,
    POPULAR_CATEGORIES,
    GLOBAL_SCAN_INTERVAL_MINUTES,
)
from price_analyzer import PriceAnalyzer
from database import db

# Configuration du logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# User agents pour rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]


# Fonctions de compatibilité pour la transition JSON -> SQLite
# TODO: Migrer complètement toutes les fonctions vers la DB
def load_data() -> Dict:
    """Charge les données depuis le fichier JSON (compatibilité)."""
    default_data = {
        "products": {},
        "users": {},
        "categories": {},
        "big_deals": {},
        "price_errors": {},
        "user_settings": {},
    }
    
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            for key, default_value in default_data.items():
                if key not in data:
                    data[key] = default_value
            return data
    except FileNotFoundError:
        return default_data
    except json.JSONDecodeError:
        logger.error("Erreur de lecture du fichier data.json, utilisation des valeurs par défaut")
        return default_data


def save_data(data: Dict) -> None:
    """Sauvegarde les données dans le fichier JSON (compatibilité)."""
    try:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {e}")


def extract_asin(url_or_asin: str) -> Optional[str]:
    """Extrait l'ASIN d'une URL Amazon ou retourne l'ASIN directement."""
    # Si c'est déjà un ASIN (10 caractères alphanumériques)
    if re.match(r"^[A-Z0-9]{10}$", url_or_asin.upper()):
        return url_or_asin.upper()

    # Extraire l'ASIN d'une URL Amazon
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/product/([A-Z0-9]{10})",
        r"/([A-Z0-9]{10})(?:[/?]|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_asin, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return None


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
            await self.page.goto(search_url, wait_until='networkidle', timeout=60000, referer='https://www.amazon.ca')
            
            # Vérifier si on a été bloqués
            await asyncio.sleep(random.uniform(3, 5))
            page_title = await self.page.title()
            if 'something went wrong' in page_title.lower() or 'error' in page_title.lower():
                logger.warning("⚠️ Amazon a détecté le bot, tentative de contournement...")
                # Attendre plus longtemps et réessayer
                await asyncio.sleep(random.uniform(5, 8))
                await self.page.reload(wait_until='networkidle', timeout=60000)
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
                    await self.page.goto(search_url, wait_until='networkidle', timeout=60000, referer='https://www.amazon.ca')
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


# Marques connues pour les composants PC (filtre qualité)
KNOWN_BRANDS = {
    # Cartes graphiques
    'nvidia', 'amd', 'asus', 'msi', 'gigabyte', 'evga', 'zotac', 'pny', 'sapphire', 'xfx', 'powercolor',
    # Processeurs
    'intel', 'amd', 'ryzen', 'core i', 'xeon',
    # RAM
    'corsair', 'g.skill', 'kingston', 'crucial', 'hyperx', 'team group', 'patriot', 'adata',
    # Stockage
    'samsung', 'western digital', 'seagate', 'crucial', 'intel', 'kingston', 'sandisk', 'adata', 'sabrent',
    # Cartes mères
    'asus', 'msi', 'gigabyte', 'asus rog', 'asus tuf', 'asus prime', 'msi mpg', 'msi mag', 'aorus',
    # Alimentations
    'corsair', 'evga', 'seasonic', 'be quiet', 'thermaltake', 'cooler master', 'fsp', 'super flower',
    # Refroidissement
    'noctua', 'be quiet', 'corsair', 'cooler master', 'arctic', 'thermalright', 'deepcool',
    # Boîtiers
    'corsair', 'fractal design', 'nzxt', 'cooler master', 'lian li', 'phanteks', 'be quiet', 'thermaltake',
    # Autres
    'logitech', 'razer', 'steelseries', 'hyperx', 'benq', 'asus', 'acer', 'dell', 'hp', 'lenovo',
}

# Instance globale du scraper
amazon_scraper = AmazonScraper()

# Instance globale de l'analyseur de prix
price_analyzer = PriceAnalyzer(
    big_discount_threshold=BIG_DISCOUNT_THRESHOLD,
    price_error_threshold=PRICE_ERROR_THRESHOLD,
    min_price_for_error=MIN_PRICE_FOR_ERROR,
)

# Variable globale pour stocker l'instance Application
global_application: Optional[Application] = None


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

    # Obtenir les produits et catégories de l'utilisateur depuis la DB
    user_products = db.get_user_products(user_id)
    user_categories = db.get_user_categories(user_id)
    
    # Obtenir les big deals et erreurs de prix
    big_deals = db.get_big_deals(limit=20)  # Limiter à 20 pour éviter les messages trop longs
    price_errors = db.get_price_errors(limit=20)

    if not user_products and not user_categories and not big_deals and not price_errors:
        await update.message.reply_text(
            "📭 Vous n'avez aucun produit ou catégorie surveillé.\n"
            "Utilisez /add pour ajouter un produit ou /category pour surveiller une catégorie."
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
/delete B08N5WRWNW
/settings bigdiscount 40

**Surveillance de catégories :**
Le bot surveille tous les produits en rabais dans la catégorie et vous alerte pour chaque nouveau rabais trouvé !

**Filtres automatiques :**
⭐ Note: 4+ étoiles uniquement
🏷️ Marques connues uniquement (NVIDIA, AMD, ASUS, MSI, Corsair, Samsung, etc.)
🔧 Processeurs: Ryzen 7 et 9 uniquement (pas de Ryzen 5)

**Détection intelligente :**
🔥 Gros rabais: Alerte automatique pour rabais >{BIG_DISCOUNT_THRESHOLD}%
⚠️ Erreurs de prix: Détection des prix anormalement bas/élevés

Le bot vérifie automatiquement les prix toutes les {CHECK_INTERVAL_MINUTES} minutes.

**Note:** Ce bot utilise Playwright (gratuit) pour scraper Amazon.ca directement.
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


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
                
                loop.run_until_complete(
                    app.bot.send_message(
                        chat_id=notify_chat_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                )
                logger.info(f"✅ Notification envoyée à {notify_chat_id} après le scan")
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi de la notification: {e}")
    
    finally:
        loop.close()


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
                            try:
                                loop.run_until_complete(
                                    app.bot.send_message(
                                        chat_id=int(user_id),
                                        text=error_message,
                                        parse_mode="Markdown",
                                    )
                                )
                                logger.info(f"⚠️ Alerte erreur de prix envoyée à {user_id} pour {asin}")
                            except Exception as e:
                                logger.error(f"Erreur lors de l'envoi de l'alerte erreur: {e}")

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
                            try:
                                loop.run_until_complete(
                                    app.bot.send_message(
                                        chat_id=int(user_id),
                                        text=big_deal_message,
                                        parse_mode="Markdown",
                                    )
                                )
                                logger.info(f"🔥 Alerte gros rabais envoyée à {user_id} pour {asin}")
                            except Exception as e:
                                logger.error(f"Erreur lors de l'envoi de l'alerte gros rabais: {e}")

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
                            try:
                                loop.run_until_complete(
                                    app.bot.send_message(
                                        chat_id=int(user_id),
                                        text=alert_message,
                                        parse_mode="Markdown",
                                    )
                                )
                                logger.info(f"Alerte envoyée à l'utilisateur {user_id} pour {asin}")
                            except Exception as e:
                                logger.error(f"Erreur lors de l'envoi de l'alerte: {e}")

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
                                try:
                                    loop.run_until_complete(
                                        app.bot.send_message(
                                            chat_id=int(user_id),
                                            text=alert_message,
                                            parse_mode="Markdown",
                                        )
                                    )
                                    logger.info(f"Alerte catégorie envoyée à {user_id} pour {product['asin']}")
                                except Exception as e:
                                    logger.error(f"Erreur lors de l'envoi de l'alerte catégorie: {e}")
                
                save_data(data)
                time.sleep(3)  # Pause entre les catégories
                
            except Exception as e:
                logger.error(f"Erreur lors de la vérification de la catégorie {category_id}: {e}")
    
    finally:
        loop.close()


def main() -> None:
    """Fonction principale du bot."""
    global global_application
    
    # Vérifier que le token est configuré
    if TELEGRAM_TOKEN == "VOTRE_TELEGRAM_BOT_TOKEN_ICI":
        logger.error("❌ Veuillez configurer TELEGRAM_TOKEN dans config.py")
        return

    # Créer l'application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Stocker l'application globalement pour l'utiliser dans scannow_command
    global_application = application

    # Ajouter les handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("category", category_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("bigdeals", bigdeals_command))
    application.add_handler(CommandHandler("priceerrors", priceerrors_command))
    application.add_handler(CommandHandler("scannow", scannow_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("help", help_command))

    # Démarrer le scheduler pour vérifier les prix périodiquement
    scheduler = BackgroundScheduler()
    
    # Job 1: Vérifier les produits surveillés par l'utilisateur
    scheduler.add_job(
        check_prices,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        args=[application],
        id="check_prices",
        replace_existing=True,
    )
    logger.info(f"⏰ Vérification des produits surveillés programmée toutes les {CHECK_INTERVAL_MINUTES} minutes")
    
    # Job 2: Scanner Amazon globalement pour gros rabais et erreurs
    scheduler.add_job(
        scan_amazon_globally,
        "interval",
        minutes=GLOBAL_SCAN_INTERVAL_MINUTES,
        args=[application],
        id="scan_amazon_globally",
        replace_existing=True,
    )
    logger.info(f"🌍 Scan global d'Amazon.ca programmé toutes les {GLOBAL_SCAN_INTERVAL_MINUTES} minutes")
    
    scheduler.start()

    # Démarrer le bot
    logger.info("🤖 Bot démarré !")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()