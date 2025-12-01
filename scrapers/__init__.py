"""Scrapers pour différents sites e-commerce et financiers."""
from .amazon_scraper import AmazonScraper
from .newegg_scraper import NeweggScraper
from .memoryexpress_scraper import MemoryExpressScraper
from .canadacomputers_scraper import CanadaComputersScraper
from .bestbuy_scraper import BestBuyScraper
from .finviz_scraper import FinvizScraper
from .news_scraper import NewsScraper
from .chart_analyzer import ChartAnalyzer

__all__ = [
    'AmazonScraper', 
    'NeweggScraper', 
    'MemoryExpressScraper', 
    'CanadaComputersScraper', 
    'BestBuyScraper',
    'FinvizScraper',
    'NewsScraper',
    'ChartAnalyzer'
]

