"""Analyseur utilisant des APIs IA gratuites."""
import logging
from typing import Dict, Optional
import os
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

# Provider: Groq (GRATUIT - Très rapide, Llama 3)
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("⚠️ groq non installé - pip install groq")

# Provider: Google Gemini (GRATUIT - Quotas généreux)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("⚠️ google-generativeai non installé - pip install google-generativeai")

# Provider: OpenAI GPT-3.5-turbo (GRATUIT avec limitations)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ openai non installé - pip install openai")


class FreeAIAnalyzer:
    """Analyseur utilisant des APIs IA gratuites."""
    
    def __init__(self, provider: str = "groq", api_key: Optional[str] = None):
        """
        Initialise l'analyseur avec un provider gratuit.
        
        Args:
            provider: "groq", "gemini", ou "openai"
            api_key: Clé API (optionnel, peut être dans .env)
        """
        self.provider = provider.lower()
        self.client = None
        self.api_key = api_key
        
        if self.provider == "groq":
            self._init_groq()
        elif self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "openai":
            self._init_openai()
        else:
            logger.warning(f"⚠️ Provider inconnu: {provider}, utilisation de Groq par défaut")
            self._init_groq()
    
    def _init_groq(self):
        """Initialise Groq (GRATUIT - Llama 3)."""
        if not GROQ_AVAILABLE:
            logger.error("❌ groq non disponible")
            return
        
        self.api_key = self.api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("⚠️ GROQ_API_KEY non configurée - Obtenez-la gratuitement sur https://console.groq.com")
            return
        
        try:
            self.client = Groq(api_key=self.api_key)
            logger.info("✅ Groq (Llama 3) initialisé - GRATUIT")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Groq: {e}")
    
    def _init_gemini(self):
        """Initialise Google Gemini (GRATUIT)."""
        if not GEMINI_AVAILABLE:
            logger.error("❌ google-generativeai non disponible")
            return
        
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("⚠️ GEMINI_API_KEY non configurée - Obtenez-la gratuitement sur https://makersuite.google.com/app/apikey")
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel('gemini-pro')
            logger.info("✅ Google Gemini initialisé - GRATUIT")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Gemini: {e}")
    
    def _init_openai(self):
        """Initialise OpenAI GPT-3.5-turbo (GRATUIT avec limitations)."""
        if not OPENAI_AVAILABLE:
            logger.error("❌ openai non disponible")
            return
        
        self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("⚠️ OPENAI_API_KEY non configurée")
            return
        
        try:
            self.client = OpenAI(api_key=self.api_key)
            logger.info("✅ OpenAI GPT-3.5-turbo initialisé")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation OpenAI: {e}")
    
    async def analyze_stock(
        self,
        ticker: str,
        stock_data: Dict,
        news: list,
        chart_analysis: Dict
    ) -> Optional[Dict]:
        """
        Analyse une action avec l'IA gratuite.
        
        Args:
            ticker: Symbole de l'action
            stock_data: Données techniques depuis Finviz
            news: Liste des nouvelles
            chart_analysis: Analyse du graphique
            
        Returns:
            Dict avec l'analyse et recommandation
        """
        if not self.client:
            logger.error(f"❌ {self.provider} non disponible")
            return None
        
        try:
            logger.info(f"🤖 Analyse {self.provider.upper()} pour {ticker}")
            
            # Construire le prompt
            prompt = self._build_analysis_prompt(ticker, stock_data, news, chart_analysis)
            
            # Appeler l'API selon le provider
            if self.provider == "groq":
                response_text = await self._call_groq(prompt)
            elif self.provider == "gemini":
                response_text = await self._call_gemini(prompt)
            elif self.provider == "openai":
                response_text = await self._call_openai(prompt)
            else:
                return None
            
            if not response_text:
                return None
            
            # Parser la réponse
            analysis = self._parse_ai_response(response_text, ticker)
            
            logger.info(f"✅ Analyse {self.provider.upper()} complétée pour {ticker}")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse {self.provider} pour {ticker}: {e}")
            raise Exception(f"{self.provider.upper()} Error: {str(e)}")
    
    async def _call_groq(self, prompt: str) -> Optional[str]:
        """Appelle l'API Groq avec fallback sur plusieurs modèles."""
        # Liste de modèles à essayer (du plus récent au plus ancien)
        models = [
            "llama-3.3-70b-versatile",  # Nouveau modèle 70B
            "llama-3.1-8b-instant",     # Modèle rapide 8B
            "mixtral-8x7b-32768",       # Mixtral (bon pour longues réponses)
            "llama-3.1-70b-versatile",  # Ancien modèle (peut ne plus fonctionner)
        ]
        
        loop = asyncio.get_event_loop()
        
        for model in models:
            try:
                logger.info(f"🔄 Tentative avec modèle Groq: {model}")
                chat_completion = await loop.run_in_executor(
                    None,
                    lambda m=model: self.client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        model=m,
                        temperature=0.7,
                        max_tokens=2000
                    )
                )
                logger.info(f"✅ Modèle Groq fonctionnel: {model}")
                return chat_completion.choices[0].message.content
            except Exception as e:
                logger.warning(f"⚠️ Modèle {model} non disponible: {e}")
                continue
        
        logger.error("❌ Aucun modèle Groq disponible")
        return None
    
    async def _call_gemini(self, prompt: str) -> Optional[str]:
        """Appelle l'API Gemini."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.generate_content(prompt)
            )
            return response.text
        except Exception as e:
            logger.error(f"Erreur Gemini API: {e}")
            return None
    
    async def _call_openai(self, prompt: str) -> Optional[str]:
        """Appelle l'API OpenAI."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2000,
                    temperature=0.7
                )
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Erreur OpenAI API: {e}")
            return None
    
    def _load_prompt_template(self) -> Optional[str]:
        """Charge le template de prompt depuis le fichier."""
        try:
            # Chercher le fichier prompt dans plusieurs emplacements possibles
            prompt_paths = [
                Path("prompts/investor_analysis_prompt.txt"),
                Path(__file__).parent.parent / "prompts" / "investor_analysis_prompt.txt",
                Path("investor_analysis_prompt.txt"),
            ]
            
            for prompt_path in prompt_paths:
                if prompt_path.exists():
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        template = f.read()
                    logger.info(f"✅ Template de prompt chargé depuis: {prompt_path}")
                    return template
            
            logger.warning("⚠️ Fichier prompt non trouvé, utilisation du prompt par défaut")
            return None
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors du chargement du prompt: {e}, utilisation du prompt par défaut")
            return None
    
    def _build_analysis_prompt(
        self,
        ticker: str,
        stock_data: Dict,
        news: list,
        chart_analysis: Dict
    ) -> str:
        """Construit le prompt pour l'IA en utilisant le template."""
        
        # Charger le template personnalisé
        template = self._load_prompt_template()
        
        # Formater les données
        tech_data = f"""
Données techniques ({ticker}):
- Prix actuel: ${stock_data.get('price', 'N/A')}
- P/E Ratio: {stock_data.get('pe_ratio', 'N/A')}
- Volume: {stock_data.get('volume', 'N/A')}
- Market Cap: {stock_data.get('market_cap', 'N/A')}
- RSI: {stock_data.get('rsi', 'N/A')}
- Beta: {stock_data.get('beta', 'N/A')}
- Change: {stock_data.get('change', 'N/A')}
- EPS: {stock_data.get('eps', 'N/A')}
- Dividend: {stock_data.get('dividend', 'N/A')}
- 52W Range: {stock_data.get('52w_range', 'N/A')}
"""
        
        news_text = "\nNouvelles récentes:\n"
        for i, article in enumerate(news[:5], 1):
            news_text += f"{i}. {article.get('title', 'N/A')} ({article.get('date', 'N/A')})\n"
        if not news:
            news_text = "\nAucune nouvelle récente disponible.\n"
        
        chart_text = f"""
Analyse graphique:
- Tendance: {chart_analysis.get('trend', 'N/A')}
- Prix actuel: ${chart_analysis.get('current_price', 'N/A')}
- Variation: {chart_analysis.get('price_change_percent', 'N/A')}%
- Support: ${chart_analysis.get('support_level', 'N/A')}
- Résistance: ${chart_analysis.get('resistance_level', 'N/A')}
- RSI: {chart_analysis.get('rsi', 'N/A')}
- SMA 20: ${chart_analysis.get('moving_averages', {}).get('sma_20', 'N/A')}
- SMA 50: ${chart_analysis.get('moving_averages', {}).get('sma_50', 'N/A')}
- High 52W: ${chart_analysis.get('high_52w', 'N/A')}
- Low 52W: ${chart_analysis.get('low_52w', 'N/A')}
"""
        
        # Si template personnalisé existe, l'utiliser
        if template:
            prompt = template.format(
                stock_data=tech_data,
                nouvelles=news_text,
                analyse_graphique=chart_text
            )
        else:
            # Fallback sur prompt par défaut
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
    
    def _parse_ai_response(self, response: str, ticker: str) -> Dict:
        """Parse la réponse de l'IA."""
        try:
            analysis = {
                "ticker": ticker,
                "raw_response": response,
                "recommendation": "HOLD",
                "confidence": 5,
                "reasoning": "",
                "positives": [],
                "negatives": [],
                "risks": []
            }
            
            response_upper = response.upper()
            if "ACHETER" in response_upper or "BUY" in response_upper:
                analysis["recommendation"] = "ACHETER"
            elif "VENDRE" in response_upper or "SELL" in response_upper:
                analysis["recommendation"] = "VENDRE"
            else:
                analysis["recommendation"] = "HOLD"
            
            import re
            confidence_match = re.search(r'confiance[:\s]+(\d+)', response, re.I)
            if confidence_match:
                analysis["confidence"] = int(confidence_match.group(1))
            
            analysis["reasoning"] = response
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Erreur parsing réponse IA: {e}")
            return {
                "ticker": ticker,
                "recommendation": "HOLD",
                "raw_response": response
            }

