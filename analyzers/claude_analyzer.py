"""Intégration Claude AI pour l'analyse d'actions."""
import logging
from typing import Dict, Optional
import os

logger = logging.getLogger(__name__)

# Essayer d'importer anthropic (API Claude)
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("⚠️ anthropic non installé - pip install anthropic")


class ClaudeAnalyzer:
    """Analyseur utilisant Claude AI pour évaluer les actions."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise l'analyseur Claude.
        
        Args:
            api_key: Clé API Anthropic (ou depuis variable d'environnement)
        """
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
        
        if not ANTHROPIC_AVAILABLE:
            logger.error("❌ anthropic non disponible - installation requise")
            self.client = None
        elif not self.api_key:
            logger.warning("⚠️ CLAUDE_API_KEY non configurée")
            self.client = None
        else:
            try:
                self.client = Anthropic(api_key=self.api_key)
                logger.info("✅ Claude AI initialisé")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'initialisation Claude: {e}")
                self.client = None
    
    async def analyze_stock(
        self,
        ticker: str,
        stock_data: Dict,
        news: list,
        chart_analysis: Dict
    ) -> Optional[Dict]:
        """
        Analyse une action avec Claude AI.
        
        Args:
            ticker: Symbole de l'action
            stock_data: Données techniques depuis Finviz
            news: Liste des nouvelles
            chart_analysis: Analyse du graphique
            
        Returns:
            Dict avec l'analyse et recommandation de Claude
        """
        if not self.client:
            logger.error("❌ Claude AI non disponible")
            return None
        
        try:
            logger.info(f"🤖 Analyse Claude AI pour {ticker}")
            
            # Construire le prompt pour Claude
            prompt = self._build_analysis_prompt(ticker, stock_data, news, chart_analysis)
            
            # Appeler Claude API (synchrone, donc on utilise asyncio)
            import asyncio
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",  # Modèle récent
                    max_tokens=2000,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
            )
            
            # Extraire la réponse
            response_text = message.content[0].text if message.content else ""
            
            # Parser la réponse pour extraire la recommandation
            analysis = self._parse_claude_response(response_text, ticker)
            
            logger.info(f"✅ Analyse Claude complétée pour {ticker}")
            return analysis
            
        except Exception as e:
            error_msg = str(e)
            # Extraire le message d'erreur détaillé si disponible
            if hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data and 'message' in error_data['error']:
                        error_msg = error_data['error']['message']
                except:
                    pass
            
            logger.error(f"❌ Erreur lors de l'analyse Claude pour {ticker}: {error_msg}")
            # Lever l'exception pour que stock_analyzer puisse la gérer
            raise Exception(f"Claude AI Error: {error_msg}")
    
    def _build_analysis_prompt(
        self,
        ticker: str,
        stock_data: Dict,
        news: list,
        chart_analysis: Dict
    ) -> str:
        """Construit le prompt pour Claude AI."""
        
        # Format des données techniques
        tech_data = f"""
Données techniques ({ticker}):
- Prix actuel: ${stock_data.get('price', 'N/A')}
- P/E Ratio: {stock_data.get('pe_ratio', 'N/A')}
- Volume: {stock_data.get('volume', 'N/A')}
- Market Cap: {stock_data.get('market_cap', 'N/A')}
- RSI: {stock_data.get('rsi', 'N/A')}
- Beta: {stock_data.get('beta', 'N/A')}
- Change: {stock_data.get('change', 'N/A')}
"""
        
        # Format des nouvelles
        news_text = "\nNouvelles récentes:\n"
        for i, article in enumerate(news[:5], 1):
            news_text += f"{i}. {article.get('title', 'N/A')} ({article.get('date', 'N/A')})\n"
        
        # Format de l'analyse graphique
        chart_text = f"""
Analyse graphique:
- Tendance: {chart_analysis.get('trend', 'N/A')}
- Prix actuel: ${chart_analysis.get('current_price', 'N/A')}
- Variation: {chart_analysis.get('price_change_percent', 'N/A')}%
- Support: ${chart_analysis.get('support_level', 'N/A')}
- Résistance: ${chart_analysis.get('resistance_level', 'N/A')}
- RSI: {chart_analysis.get('rsi', 'N/A')}
- SMA 20: ${chart_analysis.get('moving_averages', {}).get('sma_20', 'N/A')}
"""
        
        prompt = f"""Tu es un analyste financier expert. Analyse cette action et donne une recommandation.

{tech_data}

{news_text}

{chart_text}

Analyse cette action et fournis:
1. **Recommandation**: ACHETER, VENDRE, ou HOLD
2. **Score de confiance**: 1-10 (10 = très confiant)
3. **Raisonnement**: Explication détaillée de ta recommandation (3-5 phrases)
4. **Points positifs**: 2-3 points forts
5. **Points négatifs**: 2-3 points faibles
6. **Risques**: Principaux risques à surveiller

Format ta réponse de manière claire et structurée."""
        
        return prompt
    
    def _parse_claude_response(self, response: str, ticker: str) -> Dict:
        """Parse la réponse de Claude pour extraire les informations."""
        try:
            analysis = {
                "ticker": ticker,
                "raw_response": response,
                "recommendation": "HOLD",  # Par défaut
                "confidence": 5,
                "reasoning": "",
                "positives": [],
                "negatives": [],
                "risks": []
            }
            
            # Extraire la recommandation
            response_upper = response.upper()
            if "ACHETER" in response_upper or "BUY" in response_upper:
                analysis["recommendation"] = "ACHETER"
            elif "VENDRE" in response_upper or "SELL" in response_upper:
                analysis["recommendation"] = "VENDRE"
            else:
                analysis["recommendation"] = "HOLD"
            
            # Extraire le score de confiance
            import re
            confidence_match = re.search(r'confiance[:\s]+(\d+)', response, re.I)
            if confidence_match:
                analysis["confidence"] = int(confidence_match.group(1))
            
            # Le reste est dans le texte brut
            analysis["reasoning"] = response
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du parsing réponse Claude: {e}")
            return {
                "ticker": ticker,
                "recommendation": "HOLD",
                "raw_response": response
            }

