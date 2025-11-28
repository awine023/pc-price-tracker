"""
Telegram Bot pour surveiller les prix Amazon Canada avec Playwright (gratuit)
"""
import asyncio
import logging
import signal
import sys
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import Application, CommandHandler

from config import (
    CHECK_INTERVAL_MINUTES,
    TELEGRAM_TOKEN,
    GLOBAL_SCAN_INTERVAL_MINUTES,
)
from price_analyzer import PriceAnalyzer
from database import db

# Imports modulaires
from scrapers import AmazonScraper, NeweggScraper, MemoryExpressScraper
from commands import (
    start_command,
    add_command,
    list_command,
    delete_command,
    compare_command,
    category_command,
    scannow_command,
    bigdeals_command,
    priceerrors_command,
    settings_command,
    stats_command,
    history_command,
    help_command,
    set_scrapers as set_command_scrapers,
    set_application as set_command_application,
)
from schedulers import (
    scan_amazon_globally,
    check_prices,
    check_price_comparisons,
    set_global_scrapers,
    set_price_checker_scrapers,
    set_comparison_scrapers,
)

# Configuration du logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialiser les scrapers
amazon_scraper = AmazonScraper()
newegg_scraper = NeweggScraper()
memoryexpress_scraper = MemoryExpressScraper()
price_analyzer = PriceAnalyzer(
    big_discount_threshold=30.0,
    price_error_threshold=50.0,
    min_price_for_error=100.0,
)

# Variable globale pour l'application (utilisée dans scannow_command)
global_application: Optional[Application] = None


def main() -> None:
    """Fonction principale du bot."""
    global global_application
    
    # Vérifier que le token est configuré
    if TELEGRAM_TOKEN == "VOTRE_TELEGRAM_BOT_TOKEN_ICI":
        logger.error("❌ Veuillez configurer TELEGRAM_TOKEN dans config.py")
        return

    # Configurer les scrapers dans les modules
    set_command_scrapers(amazon_scraper, newegg_scraper, memoryexpress_scraper, price_analyzer)
    set_global_scrapers(amazon_scraper, price_analyzer)
    set_price_checker_scrapers(amazon_scraper, price_analyzer)
    set_comparison_scrapers(amazon_scraper, newegg_scraper, memoryexpress_scraper)

    # Créer l'application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Stocker l'application globalement pour l'utiliser dans scannow_command
    global_application = application
    
    # Configurer l'application dans les commandes
    set_command_application(application)

    # Ajouter les handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("category", category_command))
    application.add_handler(CommandHandler("compare", compare_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("bigdeals", bigdeals_command))
    application.add_handler(CommandHandler("priceerrors", priceerrors_command))
    application.add_handler(CommandHandler("scannow", scannow_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("help", help_command))

    # Démarrer le scheduler pour vérifier les prix périodiquement
    scheduler = BackgroundScheduler()
    
    # Job 1: Vérifier les produits surveillés par l'utilisateur
    scheduler.add_job(
        check_prices,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        args=[application],
        id="check_prices",
        replace_existing=True,
    )
    logger.info(f"⏰ Vérification des produits surveillés programmée toutes les {CHECK_INTERVAL_MINUTES} minutes")
    
    # Job 2: Scanner Amazon globalement pour gros rabais et erreurs
    scheduler.add_job(
        scan_amazon_globally,
        "interval",
        minutes=GLOBAL_SCAN_INTERVAL_MINUTES,
        args=[application],
        id="scan_amazon_globally",
        replace_existing=True,
    )
    logger.info(f"🌍 Scan global d'Amazon.ca programmé toutes les {GLOBAL_SCAN_INTERVAL_MINUTES} minutes")
    
    # Job 3: Comparer les prix sur les 3 sites (Amazon, Newegg, Memory Express)
    scheduler.add_job(
        check_price_comparisons,
        "interval",
        minutes=60,  # Toutes les 60 minutes
        args=[application],
        id="check_price_comparisons",
        replace_existing=True,
    )
    logger.info(f"🛒 Comparaison de prix multi-sites programmée toutes les 60 minutes")
    
    scheduler.start()

    # Démarrer le bot
    logger.info("🤖 Bot démarré !")
    
    def cleanup():
        """Fonction de nettoyage propre."""
        logger.info("🧹 Nettoyage en cours...")
        
        # Arrêter le scheduler
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
            logger.info("✅ Scheduler arrêté")
        except Exception as e:
            logger.debug(f"Erreur arrêt scheduler: {e}")
        
        # Fermer les navigateurs de manière synchrone (plus sûr)
        try:
            # Créer une nouvelle boucle pour le nettoyage
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Fermer les navigateurs avec timeout
                async def close_browsers_async():
                    """Ferme tous les navigateurs."""
                    tasks = []
                    try:
                        if hasattr(amazon_scraper, 'browser') and amazon_scraper.browser:
                            tasks.append(amazon_scraper.close_browser())
                    except:
                        pass
                    try:
                        if hasattr(newegg_scraper, 'browser') and newegg_scraper.browser:
                            tasks.append(newegg_scraper.close_browser())
                    except:
                        pass
                    try:
                        if hasattr(memoryexpress_scraper, 'browser') and memoryexpress_scraper.browser:
                            tasks.append(memoryexpress_scraper.close_browser())
                    except:
                        pass
                    
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                
                # Exécuter avec timeout
                try:
                    loop.run_until_complete(asyncio.wait_for(close_browsers_async(), timeout=3.0))
                    logger.info("✅ Navigateurs fermés")
                except asyncio.TimeoutError:
                    logger.warning("⏱️ Timeout lors de la fermeture des navigateurs (non critique)")
                except Exception as e:
                    logger.debug(f"Erreur fermeture navigateurs: {e}")
                
                # Nettoyer la boucle proprement
                try:
                    # Annuler toutes les tâches en attente
                    pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                    if pending:
                        for task in pending:
                            task.cancel()
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except:
                    pass
                
            finally:
                # Fermer la boucle de manière sécurisée
                try:
                    if loop and not loop.is_closed():
                        # Attendre que toutes les tâches soient terminées
                        try:
                            loop.run_until_complete(asyncio.sleep(0.1))
                        except:
                            pass
                        loop.close()
                except Exception as e:
                    logger.debug(f"Erreur fermeture loop: {e}")
        except Exception as e:
            logger.debug(f"Erreur nettoyage navigateurs: {e}")
        
        logger.info("✅ Nettoyage terminé")
    
    try:
        # Sur Windows, utiliser stop_signals=None car l'event loop ne supporte pas add_signal_handler
        if sys.platform == "win32":
            application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)
        else:
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                stop_signals=(signal.SIGINT, signal.SIGTERM)
            )
    except KeyboardInterrupt:
        logger.info("🛑 Interruption clavier détectée...")
    except SystemExit:
        logger.info("🛑 Arrêt demandé...")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exécution: {e}")
    finally:
        cleanup()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Interruption clavier détectée")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

