"""
Script de migration des données JSON vers SQLite.
À exécuter une seule fois pour migrer les données existantes.
"""
import json
import logging
from datetime import datetime
from database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "data.json"


def migrate_json_to_db():
    """Migre les données de data.json vers la base de données SQLite."""
    try:
        # Charger les données JSON
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        logger.info("🔄 Début de la migration JSON -> SQLite...")
        
        # Migrer les utilisateurs
        users = data.get("users", {})
        for user_id, user_data in users.items():
            username = user_data.get("username", "Inconnu")
            db.add_user(user_id, username)
            logger.info(f"✅ Utilisateur migré: {user_id} ({username})")
        
        # Migrer les produits
        products = data.get("products", {})
        for asin, product_data in products.items():
            db.add_product(
                asin=asin,
                title=product_data.get("title", "Produit inconnu"),
                url=product_data.get("url", f"https://www.amazon.ca/dp/{asin}"),
                added_by=product_data.get("added_by", ""),
                current_price=product_data.get("last_price")
            )
            
            # Migrer l'historique si disponible
            if product_data.get("last_price"):
                db.update_product_price(
                    asin=asin,
                    price=product_data.get("last_price"),
                    original_price=product_data.get("original_price"),
                    discount_percent=None,
                    in_stock=True
                )
            
            logger.info(f"✅ Produit migré: {asin}")
        
        # Migrer les catégories
        categories = data.get("categories", {})
        for category_id, category_data in categories.items():
            db.add_category(
                category_id=category_id,
                name=category_data.get("name", category_id),
                search_query=category_data.get("search_query", category_id),
                added_by=category_data.get("added_by", "")
            )
            
            # Migrer les produits de la catégorie
            category_products = category_data.get("products", {})
            products_list = []
            for asin, product_info in category_products.items():
                # Gérer les valeurs None pour discount_percent
                discount_percent = product_info.get("discount_percent")
                if discount_percent is None:
                    discount_percent = 0
                
                products_list.append({
                    "asin": asin,
                    "title": product_info.get("title", "Produit inconnu"),
                    "current_price": product_info.get("current_price"),
                    "original_price": product_info.get("original_price"),
                    "discount_percent": discount_percent,
                })
            
            if products_list:
                db.update_category_products(category_id, products_list)
            
            logger.info(f"✅ Catégorie migrée: {category_id}")
        
        # Migrer les gros rabais
        big_deals = data.get("big_deals", {})
        for asin, deal in big_deals.items():
            db.add_big_deal(
                asin=asin,
                title=deal.get("title", "Produit inconnu"),
                original_price=deal.get("original_price", 0),
                current_price=deal.get("current_price", 0),
                discount_percent=deal.get("discount_percent", 0),
                url=deal.get("url", f"https://www.amazon.ca/dp/{asin}"),
                category=deal.get("category")
            )
            logger.info(f"✅ Gros rabais migré: {asin}")
        
        # Migrer les erreurs de prix
        price_errors = data.get("price_errors", {})
        for asin, error in price_errors.items():
            db.add_price_error(
                asin=asin,
                title=error.get("title", "Produit inconnu"),
                price=error.get("price", 0),
                error_type=error.get("error_type", "unknown"),
                confidence=error.get("confidence", 0.5),
                url=error.get("url", f"https://www.amazon.ca/dp/{asin}"),
                category=error.get("category")
            )
            logger.info(f"✅ Erreur de prix migrée: {asin}")
        
        # Migrer les paramètres utilisateur
        user_settings = data.get("user_settings", {})
        for user_id, settings in user_settings.items():
            db.update_user_settings(
                user_id=user_id,
                big_discount_threshold=settings.get("big_discount_threshold"),
                price_error_threshold=settings.get("price_error_threshold")
            )
            logger.info(f"✅ Paramètres utilisateur migrés: {user_id}")
        
        logger.info("✅ Migration terminée avec succès!")
        logger.info("💡 Vous pouvez maintenant utiliser la base de données SQLite.")
        logger.info("💡 Le fichier data.json peut être sauvegardé comme backup.")
        
    except FileNotFoundError:
        logger.warning(f"⚠️ Fichier {DATA_FILE} non trouvé. Aucune migration nécessaire.")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la migration: {e}", exc_info=True)


if __name__ == "__main__":
    migrate_json_to_db()

