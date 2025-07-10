from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import asyncio
import re
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseReader, ScrapedArticle

class WebReader(BaseReader):
    """Reader per scraping diretto di pagine web"""
    
    def __init__(self, source_config: Dict[str, Any]):
        super().__init__(source_config)
        self.base_url = source_config.get('base_url', '')
        self.scraping_config = source_config.get('scraping_config', {})
        self.max_articles = source_config.get('max_articles', 20)
        
        # Selettori CSS/XPath
        self.article_list_selector = self.scraping_config.get('article_list_selector', 'article')
        self.title_selector = self.scraping_config.get('title_selector', 'h1, h2, h3')
        self.content_selector = self.scraping_config.get('content_selector', 'p')
        self.url_selector = self.scraping_config.get('url_selector', 'a')
        self.date_selector = self.scraping_config.get('date_selector', 'time')
        self.author_selector = self.scraping_config.get('author_selector', '.author')
        self.summary_selector = self.scraping_config.get('summary_selector', '.summary')
        
        # Configurazione avanzata
        self.follow_pagination = self.scraping_config.get('follow_pagination', False)
        self.pagination_selector = self.scraping_config.get('pagination_selector', '.pagination a')
        self.max_pages = self.scraping_config.get('max_pages', 3)
        
        self.logger.info(f"WebReader initialized for {self.base_url}")
    
    async def fetch_articles(self) -> List[ScrapedArticle]:
        """Fetch articles from web pages"""
        try:
            self.logger.info(f"Starting web scraping for {self.base_url}")
            
            articles = []
            pages_to_scrape = [self.base_url]
            
            # Add pagination if enabled
            if self.follow_pagination:
                pagination_urls = await self._get_pagination_urls()
                pages_to_scrape.extend(pagination_urls[:self.max_pages])
            
            # Scrape each page
            for page_url in pages_to_scrape:
                page_articles = await self._scrape_page(page_url)
                articles.extend(page_articles)
                
                # Rate limiting between pages
                if len(pages_to_scrape) > 1:
                    await asyncio.sleep(self.rate_limit)
                
                # Stop if we have enough articles
                if len(articles) >= self.max_articles:
                    break
            
            # Limit final results
            articles = articles[:self.max_articles]
            
            self.logger.info(f"Successfully scraped {len(articles)} articles from web")
            return articles
            
        except Exception as e:
            self.logger.error(f"Error in web scraping: {str(e)}")
            return []
    
    async def _scrape_page(self, url: str) -> List[ScrapedArticle]:
        """Scrape articles from a single page"""
        try:
            self.logger.info(f"Scraping page: {url}")
            
            html_content = await self.fetch_url(url)
            if not html_content:
                return []
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find article elements
            article_elements = soup.select(self.article_list_selector)
            
            if not article_elements:
                self.logger.warning(f"No articles found using selector: {self.article_list_selector}")
                return []
            
            articles = []
            for element in article_elements:
                article = await self._parse_article_element(element, url)
                if article:
                    articles.append(article)
            
            self.logger.info(f"Scraped {len(articles)} articles from {url}")
            return articles
            
        except Exception as e:
            self.logger.error(f"Error scraping page {url}: {str(e)}")
            return []
    
    async def _parse_article_element(self, element, base_url: str) -> Optional[ScrapedArticle]:
        """Parse single article element"""
        try:
            # Extract title
            title = self._extract_text_by_selector(element, self.title_selector)
            if not title:
                self.logger.debug("Skipping article: no title found")
                return None
            
            # Extract URL
            url = self._extract_url_by_selector(element, self.url_selector, base_url)
            if not url:
                self.logger.debug("Skipping article: no URL found")
                return None
            
            # Extract content (summary from listing page)
            content = self._extract_text_by_selector(element, self.content_selector)
            
            # Extract summary
            summary = self._extract_text_by_selector(element, self.summary_selector)
            
            # Extract author
            author = self._extract_text_by_selector(element, self.author_selector)
            
            # Extract date
            published_date = self._extract_date_by_selector(element, self.date_selector)
            
            # Extract tags (from classes or data attributes)
            tags = self._extract_tags_from_element(element)
            
            # Create metadata
            metadata = {
                'scraped_from': base_url,
                'element_classes': element.get('class', []),
                'element_id': element.get('id')
            }
            
            # Try to fetch full content if URL is different from base
            if url != base_url and content and len(content) < 200:
                full_content = await self._fetch_full_article_content(url)
                if full_content:
                    content = full_content
            
            article = ScrapedArticle(
                title=self.clean_text(title),
                content=self.clean_text(content),
                url=url,
                author=author,
                published_date=published_date,
                summary=self.clean_text(summary) if summary else None,
                tags=tags,
                metadata=metadata
            )
            
            self.logger.debug(f"Parsed web article: {title[:50]}...")
            return article
            
        except Exception as e:
            self.logger.error(f"Error parsing article element: {str(e)}")
            return None
    
    def _extract_text_by_selector(self, element, selector: str) -> Optional[str]:
        """Extract text using CSS selector"""
        try:
            found_element = element.select_one(selector)
            if found_element:
                return found_element.get_text(strip=True)
            return None
        except Exception as e:
            self.logger.debug(f"Error extracting text with selector {selector}: {str(e)}")
            return None
    
    def _extract_url_by_selector(self, element, selector: str, base_url: str) -> Optional[str]:
        """Extract URL using CSS selector"""
        try:
            found_element = element.select_one(selector)
            if found_element:
                href = found_element.get('href')
                if href:
                    # Make URL absolute
                    if href.startswith('http'):
                        return href
                    else:
                        return urljoin(base_url, href)
            return None
        except Exception as e:
            self.logger.debug(f"Error extracting URL with selector {selector}: {str(e)}")
            return None
    
    def _extract_date_by_selector(self, element, selector: str) -> Optional[datetime]:
        """Extract date using CSS selector"""
        try:
            found_element = element.select_one(selector)
            if found_element:
                # Try datetime attribute first
                date_str = found_element.get('datetime')
                if not date_str:
                    date_str = found_element.get_text(strip=True)
                
                if date_str:
                    return date_parser.parse(date_str)
            return None
        except Exception as e:
            self.logger.debug(f"Error extracting date with selector {selector}: {str(e)}")
            return None
    
    def _extract_tags_from_element(self, element) -> List[str]:
        """Extract tags from element classes and data attributes"""
        tags = []
        
        # From CSS classes
        classes = element.get('class', [])
        for cls in classes:
            if cls.startswith('tag-') or cls.startswith('category-'):
                tags.append(cls.replace('tag-', '').replace('category-', ''))
        
        # From data attributes
        for attr, value in element.attrs.items():
            if attr.startswith('data-tag') or attr.startswith('data-category'):
                if isinstance(value, str):
                    tags.append(value)
                elif isinstance(value, list):
                    tags.extend(value)
        
        return tags
    
    async def _fetch_full_article_content(self, url: str) -> Optional[str]:
        """Fetch full content from article URL"""
        try:
            html_content = await self.fetch_url(url)
            if not html_content:
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try to extract full content
            content_elements = soup.select(self.content_selector)
            if content_elements:
                content = ' '.join([elem.get_text() for elem in content_elements])
                return self.clean_text(content)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching full content for {url}: {str(e)}")
            return None
    
    async def _get_pagination_urls(self) -> List[str]:
        """Get pagination URLs"""
        try:
            html_content = await self.fetch_url(self.base_url)
            if not html_content:
                return []
            
            soup = BeautifulSoup(html_content, 'html.parser')
            pagination_links = soup.select(self.pagination_selector)
            
            urls = []
            for link in pagination_links:
                href = link.get('href')
                if href:
                    if href.startswith('http'):
                        urls.append(href)
                    else:
                        urls.append(urljoin(self.base_url, href))
            
            return list(set(urls))  # Remove duplicates
            
        except Exception as e:
            self.logger.error(f"Error getting pagination URLs: {str(e)}")
            return []
    
    async def validate_source(self) -> bool:
        """Validate web source"""
        try:
            html_content = await self.fetch_url(self.base_url)
            if not html_content:
                return False
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check if page has expected structure
            article_elements = soup.select(self.article_list_selector)
            
            if not article_elements:
                self.logger.warning(f"No articles found using selector: {self.article_list_selector}")
                return False
            
            self.logger.info(f"Web source validated successfully: {len(article_elements)} articles found")
            return True
            
        except Exception as e:
            self.logger.error(f"Web validation failed: {str(e)}")
            return False
    
    def get_source_info(self) -> Dict[str, Any]:
        """Get web source information"""
        return {
            'type': 'web',
            'base_url': self.base_url,
            'max_articles': self.max_articles,
            'scraping_config': self.scraping_config,
            'follow_pagination': self.follow_pagination,
            'last_update': self.get_last_update().isoformat()
        }