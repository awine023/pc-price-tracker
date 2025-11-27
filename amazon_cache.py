"""
Module de cache et gestion des erreurs Amazon avec backoff exponentiel.
Améliore la résilience face aux blocages Amazon.
"""
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


class AmazonCache:
    """Cache simple pour les résultats de scraping Amazon."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes par défaut
        """
        Args:
            ttl_seconds: Temps de vie du cache en secondes
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Récupère une valeur du cache si elle n'est pas expirée."""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() - entry['timestamp'] > self.ttl_seconds:
            # Expiré, supprimer
            del self.cache[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Ajoute une valeur au cache."""
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
    
    def clear(self) -> None:
        """Vide le cache."""
        self.cache.clear()
    
    def clear_expired(self) -> None:
        """Supprime les entrées expirées."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time - entry['timestamp'] > self.ttl_seconds
        ]
        for key in expired_keys:
            del self.cache[key]


class BackoffManager:
    """Gestionnaire de backoff exponentiel pour les requêtes Amazon."""
    
    def __init__(self, initial_delay: float = 1.0, max_delay: float = 300.0, multiplier: float = 2.0):
        """
        Args:
            initial_delay: Délai initial en secondes
            max_delay: Délai maximum en secondes
            multiplier: Multiplicateur pour le backoff exponentiel
        """
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.blocked_until: Dict[str, float] = {}  # URL -> timestamp jusqu'à quand bloquer
    
    def is_blocked(self, url: str) -> bool:
        """Vérifie si une URL est actuellement bloquée."""
        if url not in self.blocked_until:
            return False
        
        if time.time() < self.blocked_until[url]:
            return True
        
        # Blocage expiré
        del self.blocked_until[url]
        return False
    
    def block(self, url: str, attempt: int = 1) -> float:
        """
        Bloque une URL pour un certain temps basé sur le nombre de tentatives.
        
        Args:
            url: URL à bloquer
            attempt: Numéro de tentative (1 = première tentative)
        
        Returns:
            Temps d'attente en secondes
        """
        delay = min(
            self.initial_delay * (self.multiplier ** (attempt - 1)),
            self.max_delay
        )
        
        self.blocked_until[url] = time.time() + delay
        logger.warning(f"🚫 URL bloquée pour {delay:.1f}s: {url[:50]}...")
        return delay
    
    def unblock(self, url: str) -> None:
        """Débloque une URL immédiatement."""
        if url in self.blocked_until:
            del self.blocked_until[url]
    
    def get_wait_time(self, url: str) -> float:
        """Retourne le temps d'attente restant pour une URL."""
        if url not in self.blocked_until:
            return 0.0
        
        wait_time = self.blocked_until[url] - time.time()
        return max(0.0, wait_time)


# Instances globales
amazon_cache = AmazonCache(ttl_seconds=300)  # Cache de 5 minutes
backoff_manager = BackoffManager(initial_delay=5.0, max_delay=300.0, multiplier=2.0)


def with_retry(max_attempts: int = 3, backoff: bool = True):
    """
    Décorateur pour réessayer une fonction avec backoff exponentiel.
    
    Args:
        max_attempts: Nombre maximum de tentatives
        backoff: Activer le backoff exponentiel
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    # Vérifier si c'est un blocage Amazon
                    is_blocked = any(keyword in error_msg for keyword in [
                        'blocked', 'captcha', 'something went wrong', 
                        'access denied', 'forbidden', 'rate limit'
                    ])
                    
                    if is_blocked and backoff:
                        # Calculer le délai avec backoff
                        delay = backoff_manager.initial_delay * (backoff_manager.multiplier ** (attempt - 1))
                        delay = min(delay, backoff_manager.max_delay)
                        
                        logger.warning(
                            f"⚠️ Blocage Amazon détecté (tentative {attempt}/{max_attempts}). "
                            f"Attente de {delay:.1f}s avant réessai..."
                        )
                        
                        if attempt < max_attempts:
                            await asyncio.sleep(delay)
                            continue
                    
                    # Si ce n'est pas un blocage ou dernière tentative
                    if attempt < max_attempts:
                        delay = 2.0 * attempt  # Délai simple
                        logger.warning(f"⚠️ Erreur (tentative {attempt}/{max_attempts}). Réessai dans {delay:.1f}s...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"❌ Échec après {max_attempts} tentatives: {e}")
                        raise last_exception
            
            raise last_exception
        
        return wrapper
    return decorator


# Import asyncio pour le décorateur
import asyncio

