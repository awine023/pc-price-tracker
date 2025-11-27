"""
Module d'analyse des prix pour détecter les gros rabais et erreurs de prix.
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class PriceAnalyzer:
    """Analyse les prix pour détecter les gros rabais et erreurs."""
    
    def __init__(
        self,
        big_discount_threshold: float = 30.0,  # Seuil pour gros rabais (%)
        price_error_threshold: float = 0.5,  # Seuil pour erreur de prix (ratio)
        min_price_for_error: float = 10.0,  # Prix minimum pour considérer une erreur
    ):
        """
        Args:
            big_discount_threshold: Pourcentage minimum pour considérer un "gros rabais"
            price_error_threshold: Ratio minimum (prix actuel / prix attendu) pour détecter une erreur
            min_price_for_error: Prix minimum en CAD pour considérer une erreur
        """
        self.big_discount_threshold = big_discount_threshold
        self.price_error_threshold = price_error_threshold
        self.min_price_for_error = min_price_for_error
    
    def analyze_price(
        self,
        current_price: float,
        original_price: Optional[float] = None,
        last_price: Optional[float] = None,
        expected_price_range: Optional[Tuple[float, float]] = None,
        product_title: str = "",
    ) -> Dict[str, any]:
        """
        Analyse un prix et détecte les anomalies.
        
        Returns:
            Dict avec:
            - 'is_big_discount': bool
            - 'is_price_error': bool
            - 'discount_percent': float (si applicable)
            - 'error_type': str (si erreur détectée)
            - 'confidence': float (0-1, confiance dans la détection)
        """
        result = {
            'is_big_discount': False,
            'is_price_error': False,
            'discount_percent': None,
            'error_type': None,
            'confidence': 0.0,
        }
        
        # 1. Détecter les gros rabais
        if original_price and original_price > current_price:
            discount_percent = ((original_price - current_price) / original_price) * 100
            result['discount_percent'] = discount_percent
            
            if discount_percent >= self.big_discount_threshold:
                result['is_big_discount'] = True
                result['confidence'] = min(discount_percent / 100, 1.0)
                logger.info(f"🔥 Gros rabais détecté: {discount_percent:.1f}% sur {product_title[:50]}")
        
        # 2. Détecter les erreurs de prix
        if current_price < self.min_price_for_error:
            # Prix trop bas pour être réaliste
            result['is_price_error'] = True
            result['error_type'] = 'price_too_low'
            result['confidence'] = 0.9
            logger.warning(f"⚠️ Prix suspect (trop bas): ${current_price:.2f} pour {product_title[:50]}")
        
        elif expected_price_range:
            min_expected, max_expected = expected_price_range
            if current_price < min_expected * self.price_error_threshold:
                # Prix beaucoup plus bas que prévu
                result['is_price_error'] = True
                result['error_type'] = 'price_below_expected'
                result['confidence'] = 0.8
                logger.warning(
                    f"⚠️ Prix suspect (sous la fourchette): ${current_price:.2f} "
                    f"(attendu: ${min_expected:.2f}-${max_expected:.2f}) pour {product_title[:50]}"
                )
        
        elif last_price and current_price < last_price * self.price_error_threshold:
            # Prix a chuté de manière suspecte
            drop_percent = ((last_price - current_price) / last_price) * 100
            if drop_percent > 50:  # Chute de plus de 50%
                result['is_price_error'] = True
                result['error_type'] = 'suspicious_drop'
                result['confidence'] = 0.7
                logger.warning(
                    f"⚠️ Chute suspecte: {drop_percent:.1f}% "
                    f"(${last_price:.2f} -> ${current_price:.2f}) pour {product_title[:50]}"
                )
        
        # 3. Détecter les prix anormalement élevés (erreur inverse)
        if expected_price_range:
            min_expected, max_expected = expected_price_range
            if current_price > max_expected * 2:
                result['is_price_error'] = True
                result['error_type'] = 'price_too_high'
                result['confidence'] = 0.6
                logger.warning(
                    f"⚠️ Prix suspect (trop élevé): ${current_price:.2f} "
                    f"(attendu: ${min_expected:.2f}-${max_expected:.2f}) pour {product_title[:50]}"
                )
        
        return result
    
    def get_expected_price_range(
        self,
        product_title: str,
        category: Optional[str] = None,
    ) -> Optional[Tuple[float, float]]:
        """
        Estime une fourchette de prix attendue basée sur le titre et la catégorie.
        
        Returns:
            Tuple (min_price, max_price) ou None si impossible à estimer
        """
        title_lower = product_title.lower()
        
        # Règles basiques basées sur les mots-clés
        price_ranges = {
            # Processeurs
            'ryzen 9': (400, 800),
            'ryzen 7': (250, 500),
            'core i9': (400, 800),
            'core i7': (250, 500),
            'core i5': (150, 350),
            
            # Cartes graphiques
            'rtx 4090': (1500, 2500),
            'rtx 4080': (1000, 1500),
            'rtx 4070': (600, 900),
            'rtx 4060': (300, 500),
            'rx 7900': (800, 1200),
            'rx 7800': (500, 800),
            'rx 7700': (400, 600),
            
            # RAM
            '32gb': (100, 300),
            '16gb': (50, 200),
            'ddr5': (80, 400),
            'ddr4': (50, 200),
            
            # Stockage
            '2tb': (100, 300),
            '1tb': (50, 200),
            'nvme': (60, 400),
            'ssd': (40, 300),
        }
        
        for keyword, (min_price, max_price) in price_ranges.items():
            if keyword in title_lower:
                return (min_price, max_price)
        
        return None

