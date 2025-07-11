import feedparser
import datetime as dt
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import asyncio
import re
from dateutil import parser as date_parser

from .base import BaseReader, ScrapedArticle

class RSSReader(BaseReader):
    """Reader per feed RSS/Atom"""
    
    def __init__(self, source_config: Dict[str, Any]):
        super().__init__(source_config)
        self.rss_url = source_config.get('rss_url') or source_config.get('base_url')
        self.base_url = source_config.get('base_url', '')
        self.max_articles = source_config.get('max_articles', 50)
        
        # Configurazione parsing
        self.extract_full_content = source_config.get('extract_full_content', False)
        self.content_selectors = source_config.get('scraping_config', {}) if self.extract_full_content else {}
        
        self.logger.info(f"RSSReader initialized for {self.rss_url}")
    
    async def fetch_articles(self) -> List[ScrapedArticle]:
        """Fetch articles from RSS feed"""
        try:
            self.logger.info(f"Fetching RSS feed: {self.rss_url}")
            
            # Fetch RSS content
            rss_content = await self.fetch_url(self.rss_url)
            if not rss_content:
                self.logger.error(f"Failed to fetch RSS feed: {self.rss_url}")
                return []
            
            # Parse RSS
            feed = feedparser.parse(rss_content)
            
            if feed.bozo:
                self.logger.warning(f"RSS feed has parsing errors: {feed.bozo_exception}")
            
            self.logger.info(f"Found {len(feed.entries)} entries in RSS feed")
            
            articles = []
            for entry in feed.entries[:self.max_articles]:
                article = await self._parse_rss_entry(entry)
                if article:
                    articles.append(article)
                    
                # Rate limiting
                if len(articles) > 1:
                    await asyncio.sleep(0.1)
            
            self.logger.info(f"Successfully parsed {len(articles)} articles from RSS")
            return articles
            
        except Exception as e:
            self.logger.error(f"Error fetching RSS articles: {str(e)}")
            return []
    
    async def _parse_rss_entry(self, entry) -> Optional[ScrapedArticle]:
        """Parse single RSS entry"""
        try:
            # Extract basic info
            title = self.clean_text(entry.get('title', ''))
            url = entry.get('link', '')
            
            if not title or not url:
                self.logger.warning(f"Skipping entry with missing title or URL")
                return None
            
            # Make URL absolute
            if not url.startswith('http'):
                url = urljoin(self.base_url, url)
            
            # Extract content
            content = self._extract_content_from_entry(entry)
            summary = self._extract_summary_from_entry(entry)
            
            # Extract author
            author = self._extract_author_from_entry(entry)
            
            # Extract published date
            published_date = self._extract_date_from_entry(entry)
            
            # Extract tags
            tags = self._extract_tags_from_entry(entry)
            
            # Extract metadata
            metadata = self._extract_metadata_from_entry(entry)
            
            # If full content extraction is enabled, fetch full article
            if self.extract_full_content and content and len(content) < 500:
                full_content = await self._fetch_full_content(url)
                if full_content:
                    content = full_content
            
            article = ScrapedArticle(
                title=title,
                content=content,
                url=url,
                author=author,
                published_date=published_date,
                summary=summary,
                tags=tags,
                metadata=metadata
            )
            
            self.logger.debug(f"Parsed article: {title[:50]}...")
            return article
            
        except Exception as e:
            self.logger.error(f"Error parsing RSS entry: {str(e)}")
            return None
    
    def _extract_content_from_entry(self, entry) -> str:
        """Extract content from RSS entry"""
        # Try different content fields
        content_fields = ['content', 'summary', 'description']
        
        for field in content_fields:
            if hasattr(entry, field):
                field_value = getattr(entry, field)
                
                # Handle different content formats
                if isinstance(field_value, list) and len(field_value) > 0:
                    content = field_value[0].get('value', '')
                elif isinstance(field_value, str):
                    content = field_value
                elif hasattr(field_value, 'value'):
                    content = field_value.value
                else:
                    continue
                
                if content:
                    return self._clean_html_content(content)
        
        return ""
    
    def _extract_summary_from_entry(self, entry) -> str:
        """Extract summary from RSS entry"""
        summary = entry.get('summary', '')
        if summary:
            return self._clean_html_content(summary)
        return ""
    
    def _extract_author_from_entry(self, entry) -> Optional[str]:
        """Extract author from RSS entry"""
        # Try different author fields
        author_fields = ['author', 'author_detail', 'dc_creator']
        
        for field in author_fields:
            if hasattr(entry, field):
                author = getattr(entry, field)
                if isinstance(author, dict):
                    return author.get('name', '')
                elif isinstance(author, str):
                    return author
        
        return None
    
    def _extract_date_from_entry(self, entry) -> Optional[dt.datetime]:
        """Extract published date from RSS entry"""
        date_fields = ['published', 'updated', 'created']
        
        for field in date_fields:
            if hasattr(entry, field):
                date_str = getattr(entry, field)
                if date_str:
                    try:
                        # Try feedparser's parsed date first
                        parsed_field = f"{field}_parsed"
                        if hasattr(entry, parsed_field):
                            parsed_date = getattr(entry, parsed_field)
                            if parsed_date:
                                return dt.datetime(*parsed_date[:6])
                        
                        # Fallback to dateutil parser
                        return date_parser.parse(date_str)
                    except:
                        continue
        
        return None
    
    def _extract_tags_from_entry(self, entry) -> List[str]:
        """Extract tags from RSS entry"""
        tags = []
        
        # Try tags field
        if hasattr(entry, 'tags'):
            for tag in entry.tags:
                if isinstance(tag, dict):
                    tag_name = tag.get('term', '')
                else:
                    tag_name = str(tag)
                
                if tag_name:
                    tags.append(tag_name)
        
        # Try category field
        if hasattr(entry, 'category'):
            tags.append(entry.category)
        
        return tags
    
    def _extract_metadata_from_entry(self, entry) -> Dict[str, Any]:
        """Extract metadata from RSS entry"""
        metadata = {}
        
        # Add RSS-specific metadata
        if hasattr(entry, 'id'):
            metadata['rss_id'] = entry.id
        
        if hasattr(entry, 'comments'):
            metadata['comments_url'] = entry.comments
        
        if hasattr(entry, 'enclosures'):
            metadata['enclosures'] = [enc.href for enc in entry.enclosures]
        
        return metadata
    
    def _clean_html_content(self, content: str) -> str:
        """Clean HTML content"""
        if not content:
            return ""
        
        # Remove HTML tags
        import re
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Clean text
        return self.clean_text(content)
    
    async def _fetch_full_content(self, url: str) -> Optional[str]:
        """Fetch full content from article URL"""
        try:
            if not self.content_selectors:
                return None
            
            html_content = await self.fetch_url(url)
            if not html_content:
                return None
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try to extract content using selectors
            content_selector = self.content_selectors.get('content_selector')
            if content_selector:
                content_elements = soup.select(content_selector)
                if content_elements:
                    content = ' '.join([elem.get_text() for elem in content_elements])
                    return self.clean_text(content)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching full content for {url}: {str(e)}")
            return None
    
    async def validate_source(self) -> bool:
        """Validate RSS source"""
        try:
            rss_content = await self.fetch_url(self.rss_url)
            if not rss_content:
                return False
            
            feed = feedparser.parse(rss_content)
            
            # Check if it's a valid feed
            if not hasattr(feed, 'entries'):
                return False
            
            # Check if it has at least one entry
            if len(feed.entries) == 0:
                self.logger.warning(f"RSS feed is valid but empty: {self.rss_url}")
                return True
            
            self.logger.info(f"RSS source validated successfully: {len(feed.entries)} entries")
            return True
            
        except Exception as e:
            self.logger.error(f"RSS validation failed: {str(e)}")
            return False
    
    def get_source_info(self) -> Dict[str, Any]:
        """Get RSS source information"""
        return {
            'type': 'rss',
            'url': self.rss_url,
            'base_url': self.base_url,
            'max_articles': self.max_articles,
            'extract_full_content': self.extract_full_content,
            'last_update': self.get_last_update().isoformat()
        }