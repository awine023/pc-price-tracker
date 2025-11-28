"""Scrapers pour différents sites e-commerce."""
from .amazon_scraper import AmazonScraper
from .newegg_scraper import NeweggScraper
from .memoryexpress_scraper import MemoryExpressScraper
from .canadacomputers_scraper import CanadaComputersScraper
from .bestbuy_scraper import BestBuyScraper

__all__ = ['AmazonScraper', 'NeweggScraper', 'MemoryExpressScraper', 'CanadaComputersScraper', 'BestBuyScraper']

