"""Scraper pour Finviz - Données d'actions."""
import logging
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

from utils.constants import curl_requests, CURL_CFFI_AVAILABLE

logger = logging.getLogger(__name__)


class FinvizScraper:
    """Scraper pour récupérer les données d'actions depuis Finviz."""
    
    def __init__(self):
        self.base_url = "https://finviz.com"
        self.session = None
        
    def _get_session(self):
        """Obtenir ou créer une session curl-cffi."""
        if not CURL_CFFI_AVAILABLE:
            logger.warning("⚠️ curl-cffi non disponible pour Finviz")
            return None
        
        if self.session is None:
            try:
                self.session = curl_requests.Session()
            except Exception as e:
                logger.error(f"Erreur lors de la création de la session: {e}")
                return None
        
        return self.session
    
    async def get_stock_data(self, ticker: str) -> Optional[Dict]:
        """
        Récupère les données d'une action depuis Finviz.
        
        Args:
            ticker: Symbole de l'action (ex: AAPL, TSLA)
            
        Returns:
            Dict avec les données de l'action ou None
        """
        try:
            ticker = ticker.upper().strip()
            url = f"{self.base_url}/quote.ashx?t={ticker}"
            
            logger.info(f"🔍 Récupération données Finviz pour {ticker}")
            
            session = self._get_session()
            if not session:
                logger.error("❌ Session curl-cffi non disponible")
                return None
            
            # Utiliser curl-cffi pour contourner les protections (synchrone, donc on utilise asyncio)
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: session.get(url, impersonate="chrome120", timeout=30)
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ Status {response.status_code} pour {ticker}")
                return None
            
            # Parser le HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire les données depuis la table de quote
            stock_data = self._parse_quote_page(soup, ticker)
            
            if stock_data:
                logger.info(f"✅ Données récupérées pour {ticker}")
            else:
                logger.warning(f"⚠️ Aucune donnée trouvée pour {ticker}")
            
            return stock_data
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du scraping Finviz pour {ticker}: {e}")
            return None
    
    def _parse_quote_page(self, soup: BeautifulSoup, ticker: str) -> Optional[Dict]:
        """Parse la page de quote Finviz."""
        try:
            # Trouver la table principale avec les données
            quote_table = soup.find('table', class_='snapshot-table2')
            if not quote_table:
                logger.warning("⚠️ Table de quote non trouvée")
                return None
            
            data = {"ticker": ticker}
            
            # Extraire toutes les paires clé-valeur
            rows = quote_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    for i in range(0, len(cells) - 1, 2):
                        key = cells[i].get_text(strip=True)
                        value = cells[i + 1].get_text(strip=True)
                        
                        # Mapper les clés importantes
                        if key == "Price":
                            data["price"] = self._parse_price(value)
                        elif key == "Volume":
                            data["volume"] = self._parse_volume(value)
                        elif key == "Market Cap":
                            data["market_cap"] = value
                        elif key == "P/E":
                            data["pe_ratio"] = self._parse_number(value)
                        elif key == "EPS (ttm)":
                            data["eps"] = self._parse_number(value)
                        elif key == "Dividend":
                            data["dividend"] = value
                        elif key == "52W Range":
                            data["52w_range"] = value
                        elif key == "Beta":
                            data["beta"] = self._parse_number(value)
                        elif key == "RSI (14)":
                            data["rsi"] = self._parse_number(value)
                        elif key == "Price":
                            data["current_price"] = self._parse_price(value)
                        elif key == "Change":
                            data["change"] = value
                        elif key == "Target Price":
                            data["target_price"] = self._parse_price(value)
            
            return data if len(data) > 1 else None
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du parsing: {e}")
            return None
    
    def _parse_price(self, value: str) -> Optional[float]:
        """Parse un prix depuis une string."""
        try:
            # Enlever les symboles $, espaces, etc.
            cleaned = re.sub(r'[^\d.-]', '', value)
            return float(cleaned) if cleaned else None
        except:
            return None
    
    def _parse_volume(self, value: str) -> Optional[int]:
        """Parse un volume depuis une string."""
        try:
            # Gérer les formats comme "1.2M", "500K", etc.
            value = value.upper().replace(',', '')
            multiplier = 1
            if 'M' in value:
                multiplier = 1_000_000
                value = value.replace('M', '')
            elif 'K' in value:
                multiplier = 1_000
                value = value.replace('K', '')
            elif 'B' in value:
                multiplier = 1_000_000_000
                value = value.replace('B', '')
            
            cleaned = re.sub(r'[^\d.-]', '', value)
            return int(float(cleaned) * multiplier) if cleaned else None
        except:
            return None
    
    def _parse_number(self, value: str) -> Optional[float]:
        """Parse un nombre depuis une string."""
        try:
            cleaned = re.sub(r'[^\d.-]', '', value)
            return float(cleaned) if cleaned else None
        except:
            return None
    
    async def screen_stocks(self, filters: Dict) -> List[Dict]:
        """
        Utilise le screener Finviz avec des filtres.
        
        Args:
            filters: Dict avec les filtres (ex: {"price": "5-50", "volume": ">1M"})
            
        Returns:
            Liste de dicts avec les actions correspondantes
        """
        try:
            # Construire l'URL du screener
            url = f"{self.base_url}/screener.ashx"
            params = {"v": "111"}  # Vue par défaut
            
            # Ajouter les filtres
            for key, value in filters.items():
                params[key] = value
            
            logger.info(f"🔍 Screener Finviz avec filtres: {filters}")
            
            session = self._get_session()
            if not session:
                return []
            
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: session.get(url, params=params, impersonate="chrome120", timeout=30)
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ Status {response.status_code} pour screener")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            stocks = self._parse_screener_results(soup)
            
            logger.info(f"✅ {len(stocks)} actions trouvées avec le screener")
            return stocks
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du screener: {e}")
            return []
    
    def _parse_screener_results(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse les résultats du screener."""
        stocks = []
        try:
            # Trouver la table des résultats
            table = soup.find('table', class_='screener_table')
            if not table:
                return stocks
            
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    ticker = cells[0].get_text(strip=True)
                    price = self._parse_price(cells[1].get_text(strip=True))
                    
                    stocks.append({
                        "ticker": ticker,
                        "price": price,
                        # Ajouter plus de données si nécessaire
                    })
            
            return stocks
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du parsing screener: {e}")
            return []

