"""Fonctions utilitaires."""
import asyncio
import json
import re
import logging
from typing import Dict, Optional
from telegram.ext import Application

logger = logging.getLogger(__name__)


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


def send_message_sync(app: Application, chat_id: int, text: str, loop: asyncio.AbstractEventLoop) -> None:
    """Envoie un message Telegram de manière synchrone."""
    try:
        if loop.is_closed():
            logger.warning(f"Boucle fermée, création d'une nouvelle boucle pour envoyer le message à {chat_id}")
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(
                    app.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode="Markdown"
                    )
                )
            finally:
                new_loop.close()
        else:
            loop.run_until_complete(
                app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown"
                )
            )
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du message à {chat_id}: {e}")


def extract_asin(url_or_asin: str) -> Optional[str]:
    """Extrait l'ASIN d'une URL Amazon ou retourne l'ASIN directement."""
    if re.match(r"^[A-Z0-9]{10}$", url_or_asin.upper()):
        return url_or_asin.upper()

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

