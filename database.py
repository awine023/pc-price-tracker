"""
Module de gestion de la base de données SQLite pour le bot Telegram Amazon.
Remplace le système JSON par une vraie base de données.
"""
import sqlite3
import logging
import json
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_FILE = "bot_database.db"


class Database:
    """Gestionnaire de base de données SQLite."""
    
    def __init__(self, db_file: str = DB_FILE):
        """Initialise la connexion à la base de données."""
        self.db_file = db_file
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Obtient une connexion à la base de données."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
        return conn
    
    def init_database(self):
        """Initialise les tables de la base de données."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table des utilisateurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table des produits surveillés
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                asin TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                added_by TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_check TIMESTAMP,
                last_price REAL,
                lowest_price REAL,
                amazon_lowest_price REAL,
                amazon_lowest_date TEXT,
                FOREIGN KEY (added_by) REFERENCES users(user_id)
            )
        """)
        
        # Table de l'historique des prix
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT NOT NULL,
                price REAL NOT NULL,
                original_price REAL,
                discount_percent REAL,
                in_stock BOOLEAN,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asin) REFERENCES products(asin)
            )
        """)
        
        # Table des catégories surveillées
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                category_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                search_query TEXT NOT NULL,
                added_by TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_check TIMESTAMP,
                product_count INTEGER DEFAULT 0,
                discounted_count INTEGER DEFAULT 0,
                FOREIGN KEY (added_by) REFERENCES users(user_id)
            )
        """)
        
        # Table des produits dans les catégories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_products (
                category_id TEXT,
                asin TEXT,
                title TEXT,
                current_price REAL,
                original_price REAL,
                discount_percent REAL,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (category_id, asin),
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
        """)
        
        # Table des gros rabais détectés
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS big_deals (
                asin TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                original_price REAL NOT NULL,
                current_price REAL NOT NULL,
                discount_percent REAL NOT NULL,
                category TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                url TEXT NOT NULL
            )
        """)
        
        # Table des erreurs de prix détectées
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_errors (
                asin TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                error_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                category TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                url TEXT NOT NULL
            )
        """)
        
        # Table des paramètres utilisateur
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                big_discount_threshold REAL,
                price_error_threshold REAL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Table des comparaisons de prix multi-sites
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                search_query TEXT NOT NULL,
                amazon_price REAL,
                amazon_url TEXT,
                canadacomputers_price REAL,
                canadacomputers_url TEXT,
                newegg_price REAL,
                newegg_url TEXT,
                memoryexpress_price REAL,
                memoryexpress_url TEXT,
                best_price REAL,
                best_site TEXT,
                last_check TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Index pour améliorer les performances
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_asin ON price_history(asin)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(recorded_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_added_by ON products(added_by)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category_products_category ON category_products(category_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_comparisons_user ON price_comparisons(user_id)")
        
        conn.commit()
        conn.close()
        logger.info("✅ Base de données initialisée")
    
    # ========================================================================
    # MÉTHODES POUR LES UTILISATEURS
    # ========================================================================
    
    def add_user(self, user_id: str, username: str = None):
        """Ajoute ou met à jour un utilisateur."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        conn.commit()
        conn.close()
    
    # ========================================================================
    # MÉTHODES POUR LES PRODUITS
    # ========================================================================
    
    def add_product(self, asin: str, title: str, url: str, added_by: str, current_price: float = None,
                   amazon_lowest_price: float = None, amazon_lowest_date: str = None):
        """Ajoute ou met à jour un produit."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Si le produit existe déjà, préserver amazon_lowest_price et amazon_lowest_date
        existing = self.get_product(asin)
        if existing:
            if amazon_lowest_price is None:
                amazon_lowest_price = existing.get('amazon_lowest_price')
            if amazon_lowest_date is None:
                amazon_lowest_date = existing.get('amazon_lowest_date')
        
        cursor.execute("""
            INSERT OR REPLACE INTO products 
            (asin, title, url, added_by, last_check, last_price, lowest_price, amazon_lowest_price, amazon_lowest_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (asin, title, url, added_by, datetime.now(), current_price, current_price, amazon_lowest_price, amazon_lowest_date))
        conn.commit()
        conn.close()
    
    def update_product_amazon_lowest(self, asin: str, amazon_lowest_price: float, amazon_lowest_date: str = None):
        """Met à jour le prix historique Amazon d'un produit."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE products 
            SET amazon_lowest_price = ?, amazon_lowest_date = ?
            WHERE asin = ?
        """, (amazon_lowest_price, amazon_lowest_date, asin))
        conn.commit()
        conn.close()
    
    def get_product(self, asin: str) -> Optional[Dict]:
        """Récupère un produit."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE asin = ?", (asin,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_user_products(self, user_id: str) -> List[Dict]:
        """Récupère tous les produits d'un utilisateur."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE added_by = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def delete_product(self, asin: str, user_id: str) -> bool:
        """Supprime un produit (seulement si ajouté par l'utilisateur)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE asin = ? AND added_by = ?", (asin, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def update_product_price(self, asin: str, price: float, original_price: float = None, 
                            discount_percent: float = None, in_stock: bool = True):
        """Met à jour le prix d'un produit et ajoute à l'historique."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Mettre à jour le produit
        product = self.get_product(asin)
        if product:
            lowest_price = min(product.get('lowest_price', price) or price, price)
            cursor.execute("""
                UPDATE products 
                SET last_price = ?, lowest_price = ?, last_check = ?
                WHERE asin = ?
            """, (price, lowest_price, datetime.now(), asin))
        
        # Ajouter à l'historique
        cursor.execute("""
            INSERT INTO price_history 
            (asin, price, original_price, discount_percent, in_stock)
            VALUES (?, ?, ?, ?, ?)
        """, (asin, price, original_price, discount_percent, in_stock))
        
        conn.commit()
        conn.close()
    
    def get_price_history(self, asin: str, days: int = 30) -> List[Dict]:
        """Récupère l'historique des prix pour un produit."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM price_history 
            WHERE asin = ? AND recorded_at >= datetime('now', '-' || ? || ' days')
            ORDER BY recorded_at DESC
        """, (asin, days))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ========================================================================
    # MÉTHODES POUR LES CATÉGORIES
    # ========================================================================
    
    def add_category(self, category_id: str, name: str, search_query: str, added_by: str):
        """Ajoute ou met à jour une catégorie."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO categories 
            (category_id, name, search_query, added_by, last_check)
            VALUES (?, ?, ?, ?, ?)
        """, (category_id, name, search_query, added_by, datetime.now()))
        conn.commit()
        conn.close()
    
    # ========================================================================
    # MÉTHODES POUR LES GROS RABAIS
    # ========================================================================
    
    def add_big_deal(self, asin: str, title: str, original_price: float, current_price: float,
                     discount_percent: float, url: str, category: str = None):
        """Ajoute ou met à jour un gros rabais."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO big_deals
            (asin, title, original_price, current_price, discount_percent, category, url, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (asin, title, original_price, current_price, discount_percent, category, url, datetime.now()))
        conn.commit()
        conn.close()
    
    def get_big_deals(self, limit: int = None, days: int = 7) -> List[Dict]:
        """Récupère les gros rabais récents."""
        conn = self.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT * FROM big_deals 
            WHERE detected_at >= datetime('now', '-' || ? || ' days')
            ORDER BY discount_percent DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (days,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_all_big_deals(self) -> List[Dict]:
        """Récupère tous les gros rabais."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM big_deals ORDER BY discount_percent DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ========================================================================
    # MÉTHODES POUR LES ERREURS DE PRIX
    # ========================================================================
    
    def add_price_error(self, asin: str, title: str, price: float, error_type: str,
                       confidence: float, url: str, category: str = None):
        """Ajoute ou met à jour une erreur de prix."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO price_errors
            (asin, title, price, error_type, confidence, category, url, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (asin, title, price, error_type, confidence, category, url, datetime.now()))
        conn.commit()
        conn.close()
    
    def get_price_errors(self, limit: int = None, days: int = 2) -> List[Dict]:
        """Récupère les erreurs de prix récentes."""
        conn = self.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT * FROM price_errors 
            WHERE detected_at >= datetime('now', '-' || ? || ' days')
            ORDER BY confidence DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (days,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ========================================================================
    # MÉTHODES POUR LES PARAMÈTRES UTILISATEUR
    # ========================================================================
    
    def get_user_settings(self, user_id: str) -> Dict:
        """Récupère les paramètres d'un utilisateur."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {}
    
    def update_user_settings(self, user_id: str, **kwargs):
        """Met à jour les paramètres d'un utilisateur."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Vérifier si l'utilisateur existe dans la table
        existing = self.get_user_settings(user_id)
        if existing:
            # Mettre à jour
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            cursor.execute(f"UPDATE user_settings SET {set_clause} WHERE user_id = ?", values)
        else:
            # Insérer
            columns = ["user_id"] + list(kwargs.keys())
            placeholders = ", ".join(["?"] * len(columns))
            values = [user_id] + list(kwargs.values())
            cursor.execute(f"INSERT INTO user_settings ({', '.join(columns)}) VALUES ({placeholders})", values)
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # MÉTHODES DE STATISTIQUES
    # ========================================================================
    
    def get_stats(self) -> Dict:
        """Récupère les statistiques globales du bot."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Nombre d'utilisateurs
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = cursor.fetchone()[0]
        
        # Nombre de produits surveillés
        cursor.execute("SELECT COUNT(*) FROM products")
        stats['total_products'] = cursor.fetchone()[0]
        
        # Nombre de catégories surveillées
        cursor.execute("SELECT COUNT(*) FROM categories")
        stats['total_categories'] = cursor.fetchone()[0]
        
        # Nombre de gros rabais détectés (7 derniers jours)
        cursor.execute("""
            SELECT COUNT(*) FROM big_deals 
            WHERE detected_at >= datetime('now', '-7 days')
        """)
        stats['big_deals_7d'] = cursor.fetchone()[0]
        
        # Nombre d'erreurs de prix détectées (7 derniers jours)
        cursor.execute("""
            SELECT COUNT(*) FROM price_errors 
            WHERE detected_at >= datetime('now', '-7 days')
        """)
        stats['price_errors_7d'] = cursor.fetchone()[0]
        
        # Nombre total d'entrées dans l'historique
        cursor.execute("SELECT COUNT(*) FROM price_history")
        stats['total_price_records'] = cursor.fetchone()[0]
        
        # Prix moyen des produits surveillés
        cursor.execute("SELECT AVG(last_price) FROM products WHERE last_price IS NOT NULL")
        result = cursor.fetchone()[0]
        stats['avg_price'] = round(result, 2) if result else 0
        
        conn.close()
        return stats
    
    # ========================================================================
    # MÉTHODES POUR LES COMPARAISONS DE PRIX MULTI-SITES
    # ========================================================================
    
    def add_price_comparison(self, user_id: str, product_name: str, search_query: str) -> int:
        """Ajoute un produit à comparer sur plusieurs sites."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO price_comparisons (user_id, product_name, search_query)
            VALUES (?, ?, ?)
        """, (user_id, product_name, search_query))
        comparison_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return comparison_id
    
    def get_all_comparisons(self) -> List[Dict]:
        """Récupère toutes les comparaisons actives."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM price_comparisons 
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_user_comparisons(self, user_id: str) -> List[Dict]:
        """Récupère toutes les comparaisons d'un utilisateur."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM price_comparisons 
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_comparison_by_id(self, comparison_id: int) -> Optional[Dict]:
        """Récupère une comparaison par son ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM price_comparisons 
            WHERE id = ?
        """, (comparison_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def update_price_comparison(self, comparison_id: int, amazon_price: float = None, amazon_url: str = None,
                                canadacomputers_price: float = None, canadacomputers_url: str = None,
                                newegg_price: float = None, newegg_url: str = None,
                                memoryexpress_price: float = None, memoryexpress_url: str = None):
        """Met à jour les prix d'une comparaison."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Ajouter les colonnes si elles n'existent pas (migration)
        try:
            cursor.execute("ALTER TABLE price_comparisons ADD COLUMN memoryexpress_price REAL")
        except sqlite3.OperationalError:
            pass  # Colonne existe déjà
        try:
            cursor.execute("ALTER TABLE price_comparisons ADD COLUMN memoryexpress_url TEXT")
        except sqlite3.OperationalError:
            pass  # Colonne existe déjà
        
        # Déterminer le meilleur prix
        prices = []
        if amazon_price:
            prices.append(('amazon', amazon_price))
        if canadacomputers_price:
            prices.append(('canadacomputers', canadacomputers_price))
        if newegg_price:
            prices.append(('newegg', newegg_price))
        if memoryexpress_price:
            prices.append(('memoryexpress', memoryexpress_price))
        
        best_price = None
        best_site = None
        if prices:
            best_site, best_price = min(prices, key=lambda x: x[1])
        
        cursor.execute("""
            UPDATE price_comparisons 
            SET amazon_price = COALESCE(?, amazon_price),
                amazon_url = COALESCE(?, amazon_url),
                canadacomputers_price = COALESCE(?, canadacomputers_price),
                canadacomputers_url = COALESCE(?, canadacomputers_url),
                newegg_price = COALESCE(?, newegg_price),
                newegg_url = COALESCE(?, newegg_url),
                memoryexpress_price = COALESCE(?, memoryexpress_price),
                memoryexpress_url = COALESCE(?, memoryexpress_url),
                best_price = ?,
                best_site = ?,
                last_check = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (amazon_price, amazon_url, canadacomputers_price, canadacomputers_url,
              newegg_price, newegg_url, memoryexpress_price, memoryexpress_url,
              best_price, best_site, comparison_id))
        conn.commit()
        conn.close()


# Instance globale de la base de données
db = Database()

