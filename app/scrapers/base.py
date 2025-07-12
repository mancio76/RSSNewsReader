import asyncio
import logging
from abc import ABC, abstractmethod
import datetime as dt
from typing import List, Dict, Optional, Any
import aiohttp
from dataclasses import dataclass

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@dataclass
class ScrapedArticle:
    """Struttura dati per articolo estratto"""
    title: str
    content: str
    url: str
    author: Optional[str] = None
    published_date: Optional[dt.datetime] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}

class BaseReader(ABC):
    """Classe base astratta per tutti i reader"""
    
    def __init__(self, source_config: Dict[str, Any]):
        self.source_config = source_config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Configurazione di base
        self.timeout = source_config.get('timeout', 30)
        self.rate_limit = source_config.get('rate_limit_delay', 2)
        self.max_retries = source_config.get('max_retries', 3)
        
        # Headers comuni
        self.headers = {
            'User-Agent': source_config.get('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
    async def __aenter__(self):
        """Context manager entry"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()
    
    async def fetch_url(self, url: str, retries: int = 0) -> Optional[str]:
        """Fetch URL con retry logic e rate limiting"""
        try:
            if retries > 0:
                await asyncio.sleep(self.rate_limit * retries)
            
            self.logger.info(f"Fetching URL: {url}")
            
            if not self.session:
                raise RuntimeError("Session is not initialized. Use 'async with BaseReader(...) as reader:' context manager.")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    self.logger.debug(f"Successfully fetched {len(content)} characters from {url}")
                    return content
                else:
                    self.logger.warning(f"HTTP {response.status} for {url}")
                    return None
                    
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout fetching {url}")
            if retries < self.max_retries:
                return await self.fetch_url(url, retries + 1)
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {str(e)}")
            if retries < self.max_retries:
                return await self.fetch_url(url, retries + 1)
            return None
    
    @abstractmethod
    async def fetch_articles(self) -> List[ScrapedArticle]:
        """Fetch articles from source - deve essere implementato dalle sottoclassi"""
        pass
    
    @abstractmethod
    async def validate_source(self) -> bool:
        """Validate if source is accessible and valid"""
        pass
    
    @abstractmethod
    def get_source_info(self) -> Dict[str, Any]:
        """Get source information"""
        pass
    
    def UTCNOW(self) -> dt.datetime:
        """Get current UTC time"""
        return dt.datetime.now(dt.timezone.utc)

    def LocalTimeZone(self) -> dt.tzinfo:
        """Get local timezone info"""
        tz = dt.datetime.now().astimezone().tzinfo
        return tz if tz is not None else dt.timezone.utc

    def LOCALNOW(self) -> dt.datetime:
        """Get current UTC time"""
        return dt.datetime.now(self.LocalTimeZone())

    def get_last_update(self) -> dt.datetime:
        """Get last update timestamp"""
        return dt.datetime.now(dt.timezone.utc)
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        return text.strip()
    
    def extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return url