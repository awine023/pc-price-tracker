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
            
            # Log de la réponse brute pour debug (premiers 1000 caractères)
            logger.info(f"📝 Réponse brute Groq pour {ticker} (premiers 1000 chars):\n{response_text[:1000]}")
            
            # Calculer le score de base automatiquement basé sur les données réelles
            base_score = self._calculate_base_score(stock_data, news, chart_analysis)
            logger.info(f"📊 Score de base calculé pour {ticker}: {base_score}/10 (basé sur données techniques + nouvelles + graphique)")
            
            # Parser la réponse
            analysis = self._parse_ai_response(response_text, ticker, base_score)
            
            # Si aucune situation n'est trouvée, créer des situations par défaut basées sur les données du graphique
            if not analysis.get("situations") and chart_analysis:
                logger.warning(f"⚠️ Aucune situation trouvée dans la réponse Groq pour {ticker}, création de situations par défaut")
                analysis["situations"] = self._create_default_situations(ticker, stock_data, chart_analysis)
            
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
    
    def _calculate_base_score(
        self,
        stock_data: Dict,
        news: list,
        chart_analysis: Dict
    ) -> int:
        """Calcule un score de base basé sur les données réelles."""
        score = 5  # Score de base
        
        # Facteur 1: Qualité des données techniques (0-2 points)
        tech_data_count = sum([
            1 if stock_data.get('price') else 0,
            1 if stock_data.get('pe_ratio') else 0,
            1 if stock_data.get('volume') else 0,
            1 if stock_data.get('rsi') else 0,
            1 if stock_data.get('beta') else 0,
        ])
        if tech_data_count >= 4:
            score += 2
        elif tech_data_count >= 2:
            score += 1
        
        # Facteur 2: Nouvelles disponibles (0-2 points)
        news_count = len(news)
        if news_count >= 3:
            score += 2
        elif news_count >= 1:
            score += 1
        
        # Facteur 3: Clarté de la tendance graphique (0-2 points)
        trend = chart_analysis.get('trend', '')
        if trend in ['Haussière', 'Baissière']:
            score += 2
        elif trend == 'Neutre':
            score += 1
        
        # Facteur 4: RSI disponible (0-1 point)
        if chart_analysis.get('rsi'):
            score += 1
        
        # Limiter entre 1 et 10
        return max(1, min(10, score))
    
    def _create_default_situations(
        self,
        ticker: str,
        stock_data: Dict,
        chart_analysis: Dict
    ) -> list:
        """Crée des situations par défaut basées sur les données du graphique."""
        situations = []
        
        current_price = chart_analysis.get('current_price') or stock_data.get('price')
        support = chart_analysis.get('support_level')
        resistance = chart_analysis.get('resistance_level')
        
        if not current_price:
            return situations
        
        # Situation 1: Achat conservateur (basé sur support)
        if support and support < current_price:
            entry1 = support * 0.98  # 2% sous le support
            exit1 = resistance if resistance else current_price * 1.15
            stop1 = support * 0.95
            gain1 = ((exit1 - entry1) / entry1 * 100) if exit1 > entry1 else 0
            
            situations.append({
                "numero": 1,
                "prix_entree": round(entry1, 2),
                "prix_sortie": round(exit1, 2),
                "stop_loss": round(stop1, 2),
                "score": 8,
                "raison": f"Achat au niveau de support technique ({support:.2f})",
                "horizon": "Moyen terme",
                "potentiel_gain": round(gain1, 1),
                "risque": "Modéré"
            })
        
        # Situation 2: Achat actuel (prix actuel)
        exit2 = resistance if resistance else current_price * 1.10
        stop2 = current_price * 0.92
        gain2 = ((exit2 - current_price) / current_price * 100) if exit2 > current_price else 0
        
        situations.append({
            "numero": 2,
            "prix_entree": round(current_price, 2),
            "prix_sortie": round(exit2, 2),
            "stop_loss": round(stop2, 2),
            "score": 7,
            "raison": f"Achat au prix actuel avec objectif sur résistance",
            "horizon": "Court terme",
            "potentiel_gain": round(gain2, 1),
            "risque": "Modéré"
        })
        
        # Situation 3: Achat agressif (sous le prix actuel)
        entry3 = current_price * 0.95
        exit3 = resistance if resistance else current_price * 1.20
        stop3 = current_price * 0.90
        gain3 = ((exit3 - entry3) / entry3 * 100) if exit3 > entry3 else 0
        
        situations.append({
            "numero": 3,
            "prix_entree": round(entry3, 2),
            "prix_sortie": round(exit3, 2),
            "stop_loss": round(stop3, 2),
            "score": 6,
            "raison": f"Achat en baisse avec objectif optimiste",
            "horizon": "Moyen terme",
            "potentiel_gain": round(gain3, 1),
            "risque": "Élevé"
        })
        
        logger.info(f"✅ {len(situations)} situations par défaut créées pour {ticker}")
        return situations
    
    def _build_analysis_prompt(
        self,
        ticker: str,
        stock_data: Dict,
        news: list,
        chart_analysis: Dict
    ) -> str:
        """Construit le prompt simplifié pour l'IA."""
        
        # Calculer le score de base automatiquement
        base_score = self._calculate_base_score(stock_data, news, chart_analysis)
        
        # Formater les données de manière concise
        tech_data = f"""Données techniques:
Prix: ${stock_data.get('price', 'N/A')} | P/E: {stock_data.get('pe_ratio', 'N/A')} | Volume: {stock_data.get('volume', 'N/A')}
RSI: {stock_data.get('rsi', 'N/A')} | Beta: {stock_data.get('beta', 'N/A')} | Change: {stock_data.get('change', 'N/A')}
"""
        
        news_text = f"Nouvelles: {len(news)} article(s)\n"
        for i, article in enumerate(news[:3], 1):
            title = article.get('title', 'N/A')[:60]
            news_text += f"{i}. {title}\n"
        
        trend = chart_analysis.get('trend', 'N/A')
        chart_text = f"""Graphique:
Tendance: {trend} | Variation: {chart_analysis.get('price_change_percent', 'N/A')}%
Support: ${chart_analysis.get('support_level', 'N/A')} | Résistance: ${chart_analysis.get('resistance_level', 'N/A')}
RSI: {chart_analysis.get('rsi', 'N/A')}
"""
        
        # Prompt simplifié et direct avec sources réelles
        prompt = f"""Analyse {ticker} comme un investisseur expert.

**IMPORTANT - SOURCES RÉELLES OBLIGATOIRES:**
- Utilise UNIQUEMENT les données fournies ci-dessous (Finviz, Yahoo Finance, analyse technique)
- Ne invente JAMAIS de données ou de faits
- Base-toi sur les valeurs RÉELLES des indicateurs techniques
- Utilise les nouvelles RÉELLES fournies pour évaluer le sentiment
- Les prix d'entrée/sortie DOIVENT être basés sur les supports/résistances RÉELS du graphique

DONNÉES RÉELLES (sources: Finviz, Yahoo Finance, analyse technique):
{tech_data}
{news_text}
{chart_text}

Donne une réponse CONCISE basée UNIQUEMENT sur ces données réelles:
1. RECOMMANDATION: ACHETER / VENDRE / HOLD (basée sur les données réelles)
2. CONFIANCE: {base_score}/10 (ajuste selon qualité réelle des données disponibles)
3. RAISON (2-3 phrases): Synthèse des données techniques RÉELLES + graphique RÉEL + nouvelles RÉELLES
4. PRIX ENTRÉE: $XX.XX (basé sur support RÉEL du graphique)
5. PRIX SORTIE: $XX.XX (basé sur résistance RÉELLE du graphique)
6. STOP LOSS: $XX.XX (protection basée sur les niveaux RÉELS)

**LES 3 MEILLEURES SITUATIONS D'INVESTISSEMENT:**
Pour chaque situation, fournis:
- PRIX ENTRÉE: $XX.XX (basé sur support/résistance RÉEL)
- PRIX SORTIE: $XX.XX (objectif basé sur résistance RÉELLE)
- STOP LOSS: $XX.XX
- SCORE: X/10 (10 = meilleure opportunité)
- RAISON: Pourquoi cette situation est intéressante (basée sur données réelles)
- HORIZON: Court/Moyen/Long terme
- POTENTIEL DE GAIN: X% (calculé: (sortie - entrée) / entrée * 100)
- RISQUE: Faible/Modéré/Élevé

SITUATION 1 (MEILLEURE - Score 9-10):
SITUATION 2 (Score 7-8):
SITUATION 3 (Score 5-7):

Sois concis, factuel, et utilise UNIQUEMENT les données réelles fournies."""
        
        return prompt
    
    def _parse_ai_response(self, response: str, ticker: str, base_score: int = 5) -> Dict:
        """Parse la réponse de l'IA."""
        try:
            import re
            
            analysis = {
                "ticker": ticker,
                "raw_response": response,
                "recommendation": "HOLD",
                "confidence": base_score,  # Utiliser le score calculé par défaut
                "reasoning": "",
                "situations": [],  # Les 3 meilleures situations
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
            
            # Extraire le score de confiance (plusieurs patterns possibles)
            confidence_patterns = [
                r'confiance[:\s]+(\d+)/10',
                r'confiance[:\s]+(\d+)',
                r'CONFIANCE[:\s]+(\d+)',
                r'score\s+de\s+confiance[:\s]+(\d+)',
                r'confidence[:\s]+(\d+)',
                r'confiance[:\s]+(\d+)\s+sur\s+10',
            ]
            confidence_found = False
            for pattern in confidence_patterns:
                confidence_match = re.search(pattern, response, re.I)
                if confidence_match:
                    conf_value = int(confidence_match.group(1))
                    if 1 <= conf_value <= 10:
                        analysis["confidence"] = conf_value
                        logger.info(f"✅ Score de confiance extrait pour {ticker}: {conf_value}/10")
                        confidence_found = True
                        break
            
            if not confidence_found:
                logger.warning(f"⚠️ Score de confiance non trouvé dans la réponse pour {ticker}, utilisation de la valeur par défaut: 5/10")
            
            # Extraire les 3 meilleures situations
            # Chercher les sections "SITUATION 1", "SITUATION 2", "SITUATION 3"
            situations_found = []
            logger.info(f"🔍 Recherche des 3 situations dans la réponse pour {ticker}...")
            
            for i in range(1, 4):
                # Patterns plus flexibles pour trouver les situations
                next_i = i + 1
                situation_patterns = [
                    rf'SITUATION\s+{i}[^\n]*\n(.*?)(?=SITUATION\s+{next_i}|$)',
                    rf'SITUATION\s+{i}[^\n]*\n(.*?)(?=SITUATION\s+{next_i}|POINTS|RISQUES|$)',
                    rf'\*\*SITUATION\s+{i}\*\*[^\n]*\n(.*?)(?=SITUATION\s+{next_i}|POINTS|RISQUES|$)',
                    rf'{i}\.[^\n]*SITUATION[^\n]*\n(.*?)(?={next_i}\.|POINTS|RISQUES|$)',
                    rf'SITUATION\s+{i}.*?PRIX\s+ENTRÉE[^\n]*\n(.*?)(?=SITUATION\s+{next_i}|$)',
                    rf'SITUATION\s+{i}.*?ENTRÉE[^\n]*\n(.*?)(?=SITUATION\s+{next_i}|$)',
                ]
                
                situation_found_for_i = False
                for pattern in situation_patterns:
                    try:
                        situation_match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
                        if situation_match:
                            situation_text = situation_match.group(1)
                            logger.debug(f"📝 Texte situation {i} extrait: {situation_text[:100]}...")
                            situation = self._parse_situation(situation_text, i)
                            if situation:
                                situations_found.append(situation)
                                logger.info(f"✅ Situation {i} trouvée et parsée pour {ticker}")
                                situation_found_for_i = True
                                break
                    except re.error as e:
                        logger.warning(f"⚠️ Erreur regex pattern pour situation {i} de {ticker}: {e}")
                        continue
                
                if not situation_found_for_i:
                    logger.warning(f"⚠️ Situation {i} non trouvée dans la réponse pour {ticker}")
            
            logger.info(f"📊 Total situations trouvées pour {ticker}: {len(situations_found)}/3")
            
            # Stocker les situations (sans doublons)
            analysis["situations"] = situations_found
            
            # Retirer les situations du raisonnement pour éviter la duplication
            reasoning_clean = response
            if situations_found:
                # Retirer la section des situations du raisonnement
                try:
                    reasoning_clean = re.sub(
                        r'STRATÉGIE DE PRIX.*?SITUATION\s+3.*?(?=\d\.\s+\*\*POINTS|$)',
                        '',
                        reasoning_clean,
                        flags=re.IGNORECASE | re.DOTALL
                    )
                    # Retirer aussi les sections individuelles
                    for j in range(1, 4):
                        next_j = j + 1
                        pattern = f'SITUATION\\s+{j}.*?(?=SITUATION\\s+{next_j}|\\d\\.\\s+\\*\\*POINTS|$)'
                        reasoning_clean = re.sub(
                            pattern,
                            '',
                            reasoning_clean,
                            flags=re.IGNORECASE | re.DOTALL
                        )
                except re.error as e:
                    logger.warning(f"⚠️ Erreur regex lors du nettoyage du raisonnement pour {ticker}: {e}")
                    # Si erreur regex, garder le raisonnement original
            
            analysis["reasoning"] = reasoning_clean.strip()
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Erreur parsing réponse IA: {e}")
            return {
                "ticker": ticker,
                "recommendation": "HOLD",
                "raw_response": response
            }
    
    def _parse_situation(self, situation_text: str, num: int) -> Optional[Dict]:
        """Parse une situation d'investissement."""
        try:
            import re
            
            situation = {
                "numero": num,
                "prix_entree": None,
                "prix_sortie": None,
                "stop_loss": None,
                "score": None,
                "raison": "",
                "horizon": "",
                "potentiel_gain": None,
                "risque": ""
            }
            
            logger.debug(f"🔍 Parsing situation {num}, texte: {situation_text[:200]}")
            
            # Extraire prix d'entrée (plusieurs patterns)
            entree_patterns = [
                r'prix\s+d[''"]?entrée[:\s]+\$?([\d.]+)',
                r'entrée[:\s]+\$?([\d.]+)',
                r'prix\s+d[''"]?entree[:\s]+\$?([\d.]+)',
                r'acheter\s+à[:\s]+\$?([\d.]+)',
            ]
            for pattern in entree_patterns:
                entree_match = re.search(pattern, situation_text, re.I)
                if entree_match:
                    try:
                        situation["prix_entree"] = float(entree_match.group(1))
                        break
                    except:
                        continue
            
            # Extraire prix de sortie (plusieurs patterns)
            sortie_patterns = [
                r'prix\s+de\s+sortie[:\s]+\$?([\d.]+)',
                r'sortie[:\s]+\$?([\d.]+)',
                r'vendre\s+à[:\s]+\$?([\d.]+)',
                r'objectif[:\s]+\$?([\d.]+)',
                r'cible[:\s]+\$?([\d.]+)',
            ]
            for pattern in sortie_patterns:
                sortie_match = re.search(pattern, situation_text, re.I)
                if sortie_match:
                    try:
                        situation["prix_sortie"] = float(sortie_match.group(1))
                        break
                    except:
                        continue
            
            # Extraire stop loss (plusieurs patterns)
            stop_patterns = [
                r'stop\s+loss[:\s]+\$?([\d.]+)',
                r'stop[:\s]+\$?([\d.]+)',
                r'limite\s+de\s+perte[:\s]+\$?([\d.]+)',
            ]
            for pattern in stop_patterns:
                stop_match = re.search(pattern, situation_text, re.I)
                if stop_match:
                    try:
                        situation["stop_loss"] = float(stop_match.group(1))
                        break
                    except:
                        continue
            
            # Extraire score (plusieurs patterns possibles)
            score_patterns = [
                r'score[:\s]+(\d+)/10',
                r'score[:\s]+(\d+)',
                r'score\s+de\s+la\s+situation[:\s]+(\d+)',
                r'situation.*?score[:\s]+(\d+)',
                r'\(score[:\s]+(\d+)\)',
            ]
            score_found = False
            for pattern in score_patterns:
                score_match = re.search(pattern, situation_text, re.I)
                if score_match:
                    score_value = int(score_match.group(1))
                    if 1 <= score_value <= 10:
                        situation["score"] = score_value
                        logger.info(f"✅ Score situation {num} extrait pour {ticker}: {score_value}/10")
                        score_found = True
                        break
            
            if not score_found:
                logger.warning(f"⚠️ Score situation {num} non trouvé pour {ticker}")
            
            # Extraire potentiel de gain (plusieurs patterns)
            gain_patterns = [
                r'potentiel\s+de\s+gain[:\s]+([\d.]+)%',
                r'gain[:\s]+([\d.]+)%',
                r'potentiel[:\s]+([\d.]+)%',
                r'\+([\d.]+)%',
                r'([\d.]+)%\s+de\s+gain',
            ]
            for pattern in gain_patterns:
                gain_match = re.search(pattern, situation_text, re.I)
                if gain_match:
                    try:
                        situation["potentiel_gain"] = float(gain_match.group(1))
                        break
                    except:
                        continue
            
            # Extraire risque
            risque_match = re.search(r'risque[:\s]+(faible|modéré|élevé|faible|modere|eleve)', situation_text, re.I)
            if risque_match:
                situation["risque"] = risque_match.group(1).capitalize()
            
            # Extraire raison (texte après "Raison :")
            raison_match = re.search(r'raison[:\s]+(.*?)(?=horizon|potentiel|risque|$)', situation_text, re.I | re.DOTALL)
            if raison_match:
                situation["raison"] = raison_match.group(1).strip()[:200]  # Limiter à 200 caractères
            
            # Extraire horizon
            horizon_match = re.search(r'horizon[:\s]+(court|moyen|long)\s+terme', situation_text, re.I)
            if horizon_match:
                situation["horizon"] = horizon_match.group(1).capitalize() + " terme"
            
            return situation if situation["prix_entree"] or situation["prix_sortie"] else None
            
        except Exception as e:
            logger.debug(f"Erreur parsing situation {num}: {e}")
            return None

