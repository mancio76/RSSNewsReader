from .base import BaseReader
from .rss_reader import RSSReader
from .web_reader import WebReader
from .manager import ScraperManager

__all__ = [
    'BaseReader',
    'RSSReader', 
    'WebReader',
    'ScraperManager'
]