"""Constantes et configurations partagées."""
import logging

logger = logging.getLogger(__name__)

# User agents pour rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

# Essayer d'importer curl-cffi pour un meilleur contournement de Cloudflare
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    curl_requests = None

if CURL_CFFI_AVAILABLE:
    logger.info("✅ curl-cffi disponible - meilleur contournement Cloudflare activé")
else:
    logger.warning("⚠️ curl-cffi non disponible - installation: pip install curl-cffi")

# Marques connues pour les composants PC (filtre qualité)
KNOWN_BRANDS = {
    # Cartes graphiques
    'nvidia', 'amd', 'asus', 'msi', 'gigabyte', 'evga', 'zotac', 'pny', 'sapphire', 'xfx', 'powercolor',
    # Processeurs
    'intel', 'amd', 'ryzen', 'core i', 'xeon',
    # RAM
    'corsair', 'g.skill', 'kingston', 'crucial', 'hyperx', 'team group', 'patriot', 'adata',
    # Stockage
    'samsung', 'western digital', 'seagate', 'crucial', 'intel', 'kingston', 'sandisk', 'adata', 'sabrent',
    # Cartes mères
    'asus', 'msi', 'gigabyte', 'asus rog', 'asus tuf', 'asus prime', 'msi mpg', 'msi mag', 'aorus',
    # Alimentations
    'corsair', 'evga', 'seasonic', 'be quiet', 'thermaltake', 'cooler master', 'fsp', 'super flower',
    # Refroidissement
    'noctua', 'be quiet', 'corsair', 'cooler master', 'arctic', 'thermalright', 'deepcool',
    # Boîtiers
    'corsair', 'fractal design', 'nzxt', 'cooler master', 'lian li', 'phanteks', 'be quiet', 'thermaltake',
    # Autres
    'logitech', 'razer', 'steelseries', 'hyperx', 'benq', 'asus', 'acer', 'dell', 'hp', 'lenovo',
}

