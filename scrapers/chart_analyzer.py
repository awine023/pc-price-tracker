"""Analyseur de graphiques d'actions."""
import logging
from typing import Dict, Optional
import yfinance as yf
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ChartAnalyzer:
    """Analyse les graphiques d'actions."""
    
    def __init__(self):
        pass
    
    async def analyze_chart(self, ticker: str, period: str = "1mo") -> Optional[Dict]:
        """
        Analyse le graphique d'une action.
        
        Args:
            ticker: Symbole de l'action
            period: Période ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y")
            
        Returns:
            Dict avec l'analyse du graphique
        """
        try:
            ticker = ticker.upper().strip()
            logger.info(f"📈 Analyse graphique pour {ticker} (période: {period})")
            
            # Utiliser yfinance pour récupérer les données
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist.empty:
                logger.warning(f"⚠️ Aucune donnée historique pour {ticker}")
                return None
            
            # Calculer les indicateurs techniques
            analysis = {
                "ticker": ticker,
                "current_price": float(hist['Close'].iloc[-1]),
                "price_change": float(hist['Close'].iloc[-1] - hist['Close'].iloc[0]),
                "price_change_percent": float((hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100),
                "high_52w": float(hist['High'].max()),
                "low_52w": float(hist['Low'].min()),
                "volume_avg": float(hist['Volume'].mean()),
                "trend": self._calculate_trend(hist),
                "support_level": self._calculate_support(hist),
                "resistance_level": self._calculate_resistance(hist),
                "rsi": self._calculate_rsi(hist),
                "moving_averages": self._calculate_moving_averages(hist),
            }
            
            logger.info(f"✅ Analyse graphique complétée pour {ticker}")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse graphique pour {ticker}: {e}")
            return None
    
    def _calculate_trend(self, hist) -> str:
        """Calcule la tendance (haussière, baissière, neutre)."""
        try:
            # Comparer les prix récents vs anciens
            recent_avg = hist['Close'].tail(5).mean()
            older_avg = hist['Close'].head(5).mean()
            
            if recent_avg > older_avg * 1.02:
                return "Haussière"
            elif recent_avg < older_avg * 0.98:
                return "Baissière"
            else:
                return "Neutre"
        except:
            return "Inconnue"
    
    def _calculate_support(self, hist) -> Optional[float]:
        """Calcule le niveau de support."""
        try:
            # Support = prix minimum récent
            return float(hist['Low'].tail(20).min())
        except:
            return None
    
    def _calculate_resistance(self, hist) -> Optional[float]:
        """Calcule le niveau de résistance."""
        try:
            # Résistance = prix maximum récent
            return float(hist['High'].tail(20).max())
        except:
            return None
    
    def _calculate_rsi(self, hist, period: int = 14) -> Optional[float]:
        """Calcule le RSI (Relative Strength Index)."""
        try:
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1]) if not rsi.empty else None
        except:
            return None
    
    def _calculate_moving_averages(self, hist) -> Dict:
        """Calcule les moyennes mobiles."""
        try:
            return {
                "sma_20": float(hist['Close'].tail(20).mean()),
                "sma_50": float(hist['Close'].tail(50).mean()) if len(hist) >= 50 else None,
                "sma_200": float(hist['Close'].tail(200).mean()) if len(hist) >= 200 else None,
            }
        except:
            return {}

