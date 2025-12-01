"""Scraper pour les nouvelles financières."""
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from datetime import datetime

from utils.constants import curl_requests, CURL_CFFI_AVAILABLE

logger = logging.getLogger(__name__)


class NewsScraper:
    """Scraper pour récupérer les nouvelles financières."""
    
    def __init__(self):
        self.finviz_base = "https://finviz.com"
        self.yahoo_base = "https://finance.yahoo.com"
        self.session = None
    
    def _get_session(self):
        """Obtenir ou créer une session curl-cffi."""
        if not CURL_CFFI_AVAILABLE:
            logger.warning("⚠️ curl-cffi non disponible pour News")
            return None
        
        if self.session is None:
            try:
                self.session = curl_requests.Session()
            except Exception as e:
                logger.error(f"Erreur lors de la création de la session: {e}")
                return None
        
        return self.session
    
    async def get_stock_news(self, ticker: str, source: str = "finviz", limit: int = 10) -> List[Dict]:
        """
        Récupère les nouvelles pour une action.
        
        Args:
            ticker: Symbole de l'action
            source: Source des nouvelles ("finviz" ou "yahoo")
            limit: Nombre maximum de nouvelles à retourner
            
        Returns:
            Liste de dicts avec les nouvelles
        """
        if source == "finviz":
            return await self._get_finviz_news(ticker, limit)
        elif source == "yahoo":
            return await self._get_yahoo_news(ticker, limit)
        else:
            logger.warning(f"⚠️ Source inconnue: {source}")
            return []
    
    async def _get_finviz_news(self, ticker: str, limit: int) -> List[Dict]:
        """Récupère les nouvelles depuis Finviz."""
        try:
            ticker = ticker.upper().strip()
            url = f"{self.finviz_base}/quote.ashx?t={ticker}"
            
            logger.info(f"📰 Récupération nouvelles Finviz pour {ticker}")
            
            session = self._get_session()
            if not session:
                return []
            
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: session.get(url, impersonate="chrome120", timeout=30)
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ Status {response.status_code} pour nouvelles {ticker}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news = self._parse_finviz_news(soup, ticker, limit)
            
            logger.info(f"✅ {len(news)} nouvelles trouvées pour {ticker}")
            return news
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du scraping nouvelles Finviz: {e}")
            return []
    
    def _parse_finviz_news(self, soup: BeautifulSoup, ticker: str, limit: int) -> List[Dict]:
        """Parse les nouvelles depuis Finviz."""
        news = []
        try:
            # Trouver la table des nouvelles
            news_table = soup.find('table', id='news-table')
            if not news_table:
                logger.warning("⚠️ Table de nouvelles non trouvée")
                return news
            
            rows = news_table.find_all('tr')[:limit]
            for row in rows:
                try:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        date_cell = cells[0].get_text(strip=True)
                        title_cell = cells[1]
                        
                        title = title_cell.get_text(strip=True)
                        link = title_cell.find('a')
                        url = link.get('href', '') if link else ''
                        
                        # Parser la date
                        date = self._parse_finviz_date(date_cell)
                        
                        news.append({
                            "title": title,
                            "url": url,
                            "date": date,
                            "source": "Finviz",
                            "ticker": ticker
                        })
                except Exception as e:
                    logger.debug(f"Erreur parsing nouvelle: {e}")
                    continue
            
            return news
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du parsing nouvelles: {e}")
            return []
    
    async def _get_yahoo_news(self, ticker: str, limit: int) -> List[Dict]:
        """Récupère les nouvelles depuis Yahoo Finance."""
        try:
            ticker = ticker.upper().strip()
            url = f"{self.yahoo_base}/quote/{ticker}/news"
            
            logger.info(f"📰 Récupération nouvelles Yahoo pour {ticker}")
            
            session = self._get_session()
            if not session:
                return []
            
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: session.get(url, impersonate="chrome120", timeout=30)
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ Status {response.status_code} pour nouvelles Yahoo {ticker}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news = self._parse_yahoo_news(soup, ticker, limit)
            
            logger.info(f"✅ {len(news)} nouvelles trouvées pour {ticker}")
            return news
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du scraping nouvelles Yahoo: {e}")
            return []
    
    def _parse_yahoo_news(self, soup: BeautifulSoup, ticker: str, limit: int) -> List[Dict]:
        """Parse les nouvelles depuis Yahoo Finance."""
        news = []
        try:
            # Yahoo Finance structure (peut varier)
            news_items = soup.find_all('li', class_='js-stream-content')[:limit]
            
            for item in news_items:
                try:
                    title_elem = item.find('h3')
                    link_elem = item.find('a')
                    date_elem = item.find('span', class_='C(#959595)')
                    
                    title = title_elem.get_text(strip=True) if title_elem else "Sans titre"
                    url = link_elem.get('href', '') if link_elem else ''
                    date_text = date_elem.get_text(strip=True) if date_elem else ""
                    
                    news.append({
                        "title": title,
                        "url": url if url.startswith('http') else f"{self.yahoo_base}{url}",
                        "date": date_text,
                        "source": "Yahoo Finance",
                        "ticker": ticker
                    })
                except Exception as e:
                    logger.debug(f"Erreur parsing nouvelle Yahoo: {e}")
                    continue
            
            return news
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du parsing nouvelles Yahoo: {e}")
            return []
    
    def _parse_finviz_date(self, date_str: str) -> str:
        """Parse une date depuis Finviz."""
        try:
            # Format Finviz: "Nov-30-25 05:05PM"
            # On garde tel quel pour l'instant
            return date_str
        except:
            return ""

