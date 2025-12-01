"""Orchestrateur d'analyse d'actions."""
import logging
from typing import Dict, Optional
import asyncio

from scrapers.finviz_scraper import FinvizScraper
from scrapers.news_scraper import NewsScraper
from scrapers.chart_analyzer import ChartAnalyzer
from analyzers.free_ai_analyzer import FreeAIAnalyzer

logger = logging.getLogger(__name__)


class StockAnalyzer:
    """Orchestre l'analyse complète d'une action."""
    
    def __init__(self, ai_provider: str = "groq"):
        """
        Initialise l'analyseur d'actions.
        
        Args:
            ai_provider: Provider IA ("groq", "gemini", "openai")
        """
        self.finviz_scraper = FinvizScraper()
        self.news_scraper = NewsScraper()
        self.chart_analyzer = ChartAnalyzer()
        
        # Utiliser un provider IA gratuit (Groq recommandé)
        self.ai_analyzer = FreeAIAnalyzer(provider=ai_provider)
        
        logger.info(f"✅ StockAnalyzer initialisé avec provider: {ai_provider}")
    
    async def analyze_stock(self, ticker: str) -> Optional[Dict]:
        """
        Analyse complète d'une action.
        
        Args:
            ticker: Symbole de l'action (ex: AAPL, TSLA)
            
        Returns:
            Dict avec toutes les analyses combinées
        """
        try:
            ticker = ticker.upper().strip()
            logger.info(f"📊 Début analyse complète pour {ticker}")
            
            # 1. Récupérer les données techniques (Finviz)
            stock_data = await self.finviz_scraper.get_stock_data(ticker)
            if not stock_data:
                logger.warning(f"⚠️ Aucune donnée Finviz pour {ticker}")
                stock_data = {}
            
            # 2. Récupérer les nouvelles
            news_finviz = await self.news_scraper.get_stock_news(ticker, source="finviz", limit=5)
            news_yahoo = await self.news_scraper.get_stock_news(ticker, source="yahoo", limit=5)
            all_news = news_finviz + news_yahoo
            
            # 3. Analyser le graphique
            chart_analysis = await self.chart_analyzer.analyze_chart(ticker, period="3mo")
            if not chart_analysis:
                logger.warning(f"⚠️ Aucune analyse graphique pour {ticker}")
                chart_analysis = {}
            
            # 4. Analyse IA (Groq, Gemini, ou OpenAI)
            ai_analysis = None
            ai_error = None
            if self.ai_analyzer.client:
                try:
                    ai_analysis = await self.ai_analyzer.analyze_stock(
                        ticker,
                        stock_data,
                        all_news,
                        chart_analysis
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Erreur IA: {e}")
                    ai_error = str(e)
                    # Continuer sans IA
            else:
                logger.warning("⚠️ IA non disponible - analyse sans IA")
            
            # 5. Combiner toutes les analyses
            complete_analysis = {
                "ticker": ticker,
                "stock_data": stock_data,
                "news": all_news,
                "chart_analysis": chart_analysis,
                "ai_analysis": ai_analysis,
                "ai_error": ai_error,
                "summary": self._generate_summary(ticker, stock_data, chart_analysis, ai_analysis)
            }
            
            logger.info(f"✅ Analyse complète terminée pour {ticker}")
            return complete_analysis
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse complète pour {ticker}: {e}")
            return None
    
    def _generate_summary(
        self,
        ticker: str,
        stock_data: Dict,
        chart_analysis: Dict,
        ai_analysis: Optional[Dict]
    ) -> Dict:
        """Génère un résumé de l'analyse."""
        summary = {
            "ticker": ticker,
            "current_price": stock_data.get("price") or chart_analysis.get("current_price"),
            "recommendation": "HOLD",
            "confidence": 5,
            "key_points": []
        }
        
        # Utiliser la recommandation de l'IA si disponible
        if ai_analysis:
            summary["recommendation"] = ai_analysis.get("recommendation", "HOLD")
            summary["confidence"] = ai_analysis.get("confidence", 5)
            summary["key_points"].append(ai_analysis.get("reasoning", ""))
        
        # Ajouter des points basés sur les données techniques
        if chart_analysis.get("trend") == "Haussière":
            summary["key_points"].append("Tendance haussière détectée")
        elif chart_analysis.get("trend") == "Baissière":
            summary["key_points"].append("Tendance baissière détectée")
        
        rsi = chart_analysis.get("rsi")
        if rsi:
            if rsi > 70:
                summary["key_points"].append("RSI élevé (>70) - possible survente")
            elif rsi < 30:
                summary["key_points"].append("RSI bas (<30) - possible survente")
        
        return summary

