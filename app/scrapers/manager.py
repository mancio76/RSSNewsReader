import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from .base import BaseReader, ScrapedArticle
from .rss_reader import RSSReader
from .web_reader import WebReader
from app.models import Source, Article, Tag, ArticleTag, ArticleMetadata

class ScraperManager:
    """Manager per orchestrare tutti gli scrapers"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.logger = logging.getLogger(self.__class__.__name__)
        self.active_scrapers = {}
        
    def create_reader(self, source: Source) -> Optional[BaseReader]:
        """Factory method per creare il reader appropriato"""
        try:
            config = {
                'base_url': source.base_url,
                'rss_url': source.rss_url,
                'scraping_config': source.scraping_config or {},
                'rate_limit_delay': source.rate_limit_delay,
                'timeout': 30,
                'max_retries': 3,
                'max_articles': 50
            }
            
            # Scegli il reader basato sulla configurazione
            if source.rss_url:
                self.logger.info(f"Creating RSSReader for source {source.name}")
                return RSSReader(config)
            elif source.scraping_config:
                self.logger.info(f"Creating WebReader for source {source.name}")
                return WebReader(config)
            else:
                self.logger.error(f"No valid configuration for source {source.name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating reader for source {source.name}: {str(e)}")
            return None
    
    async def scrape_source(self, source: Source) -> List[Article]:
        """Scrape singola source e salva articoli nel database"""
        try:
            self.logger.info(f"Starting scrape for source: {source.name}")
            
            # Crea reader
            reader = self.create_reader(source)
            if not reader:
                self.logger.error(f"Failed to create reader for source {source.name}")
                return []
            
            articles = []
            async with reader:
                # Valida source
                if not await reader.validate_source():
                    self.logger.error(f"Source validation failed: {source.name}")
                    source.error_count += 1
                    source.last_error = "Source validation failed"
                    self.db.commit()
                    return []
                
                # Fetch articles
                scraped_articles = await reader.fetch_articles()
                
                if not scraped_articles:
                    self.logger.warning(f"No articles found for source: {source.name}")
                    return []
                
                # Salva articoli nel database
                for scraped_article in scraped_articles:
                    article = await self._save_article(scraped_article, source)
                    if article:
                        articles.append(article)
                
                # Aggiorna source metadata
                source.last_scraped = datetime.utcnow()
                source.next_scrape = datetime.utcnow() + timedelta(seconds=source.update_frequency)
                source.error_count = 0
                source.last_error = None
                self.db.commit()
                
                self.logger.info(f"Successfully scraped {len(articles)} articles from {source.name}")
                return articles
                
        except Exception as e:
            self.logger.error(f"Error scraping source {source.name}: {str(e)}")
            source.error_count += 1
            source.last_error = str(e)
            self.db.commit()
            return []
    
    async def _save_article(self, scraped_article: ScrapedArticle, source: Source) -> Optional[Article]:
        """Salva articolo nel database con deduplicazione"""
        try:
            # Controlla se l'articolo esiste già (by URL)
            existing_article = self.db.query(Article).filter_by(url=scraped_article.url).first()
            if existing_article:
                self.logger.debug(f"Article already exists: {scraped_article.url}")
                return existing_article
            
            # Crea nuovo articolo
            article = Article(
                title=scraped_article.title,
                content=scraped_article.content,
                summary=scraped_article.summary,
                url=scraped_article.url,
                author=scraped_article.author,
                source_id=source.id,
                published_date=scraped_article.published_date,
                scraped_date=datetime.utcnow(),
                word_count=len(scraped_article.content.split()) if scraped_article.content else 0,
                language='it'  # Default, potrebbe essere rilevato automaticamente
            )
            
            # Genera hash per deduplicazione
            article.generate_content_hash()
            article.generate_url_hash()
            
            # Controlla duplicati per content hash
            if article.content_hash:
                duplicate = self.db.query(Article).filter_by(content_hash=article.content_hash).first()
                if duplicate:
                    self.logger.debug(f"Duplicate content found for: {scraped_article.title}")
                    article.is_duplicate = True
            
            self.db.add(article)
            self.db.flush()  # Per ottenere l'ID senza commit
            
            # Salva tags
            await self._save_article_tags(article, scraped_article.tags)
            
            # Salva metadata
            await self._save_article_metadata(article, scraped_article.metadata)
            
            self.db.commit()
            
            self.logger.debug(f"Saved article: {article.title[:50]}...")
            return article
            
        except Exception as e:
            self.logger.error(f"Error saving article {scraped_article.title}: {str(e)}")
            self.db.rollback()
            return None
    
    async def _save_article_tags(self, article: Article, tags: List[str]):
        """Salva tags dell'articolo"""
        try:
            for tag_name in tags:
                if not tag_name:
                    continue
                
                tag_name_clean = tag_name.strip().lower()
                
                # Trova o crea tag
                tag = self.db.query(Tag).filter_by(normalized_name=tag_name_clean).first()
                if not tag:
                    tag = Tag(
                        name=tag_name,
                        normalized_name=tag_name_clean,
                        tag_type='auto'
                    )
                    self.db.add(tag)
                    self.db.flush()
                
                # Crea associazione article-tag
                article_tag = ArticleTag(
                    article_id=article.id,
                    tag_id=tag.id,
                    confidence=0.8,
                    source='scraper'
                )
                self.db.add(article_tag)
                
                # Incrementa frequenza tag
                tag.increment_frequency()
                
        except Exception as e:
            self.logger.error(f"Error saving tags for article {article.id}: {str(e)}")
    
    async def _save_article_metadata(self, article: Article, metadata: Dict[str, Any]):
        """Salva metadata dell'articolo"""
        try:
            for key, value in metadata.items():
                if value is not None:
                    article_metadata = ArticleMetadata(
                        article_id=article.id,
                        key=key,
                        value=str(value)
                    )
                    self.db.add(article_metadata)
                    
        except Exception as e:
            self.logger.error(f"Error saving metadata for article {article.id}: {str(e)}")
    
    async def scrape_all_active_sources(self) -> Dict[str, List[Article]]:
        """Scrape tutte le sources attive"""
        try:
            # Ottieni sources attive
            active_sources = self.db.query(Source).filter_by(is_active=True).all()
            
            if not active_sources:
                self.logger.warning("No active sources found")
                return {}
            
            self.logger.info(f"Starting scrape for {len(active_sources)} active sources")
            
            results = {}
            
            # Scrape sources in parallelo (con limite di concorrenza)
            semaphore = asyncio.Semaphore(3)  # Max 3 concurrent scrapes
            
            async def scrape_with_semaphore(source):
                async with semaphore:
                    return source.name, await self.scrape_source(source)
            
            tasks = [scrape_with_semaphore(source) for source in active_sources]
            completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Processa risultati
            total_articles = 0
            for result in completed_tasks:
                if isinstance(result, Exception):
                    self.logger.error(f"Scraping task failed: {str(result)}")
                    continue
                
                source_name, articles = result
                results[source_name] = articles
                total_articles += len(articles)
            
            self.logger.info(f"Scraping completed. Total articles: {total_articles}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error in scrape_all_active_sources: {str(e)}")
            return {}
    
    async def scrape_sources_by_schedule(self) -> Dict[str, List[Article]]:
        """Scrape solo le sources che necessitano aggiornamento secondo schedule"""
        try:
            now = datetime.utcnow()
            
            # Sources che devono essere aggiornate
            sources_to_update = self.db.query(Source).filter(
                Source.is_active == True,
                (Source.next_scrape.is_(None)) | (Source.next_scrape <= now)
            ).all()
            
            if not sources_to_update:
                self.logger.info("No sources need updating")
                return {}
            
            self.logger.info(f"Found {len(sources_to_update)} sources to update")
            
            results = {}
            for source in sources_to_update:
                articles = await self.scrape_source(source)
                results[source.name] = articles
                
                # Pausa tra sources per evitare overload
                await asyncio.sleep(1)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in scrape_sources_by_schedule: {str(e)}")
            return {}
    
    async def validate_all_sources(self) -> Dict[str, bool]:
        """Valida tutte le sources"""
        try:
            all_sources = self.db.query(Source).all()
            results = {}
            
            for source in all_sources:
                reader = self.create_reader(source)
                if reader:
                    async with reader:
                        is_valid = await reader.validate_source()
                        results[source.name] = is_valid
                        
                        if not is_valid:
                            source.error_count += 1
                            source.last_error = "Validation failed"
                        else:
                            source.error_count = 0
                            source.last_error = None
                else:
                    results[source.name] = False
                    source.error_count += 1
                    source.last_error = "Could not create reader"
            
            self.db.commit()
            return results
            
        except Exception as e:
            self.logger.error(f"Error validating sources: {str(e)}")
            return {}
    
    def get_source_statistics(self) -> Dict[str, Any]:
        """Ottieni statistiche sulle sources"""
        try:
            total_sources = self.db.query(Source).count()
            active_sources = self.db.query(Source).filter_by(is_active=True).count()
            error_sources = self.db.query(Source).filter(Source.error_count > 0).count()
            
            recent_articles = self.db.query(Article).filter(
                Article.scraped_date >= datetime.utcnow() - timedelta(days=1)
            ).count()
            
            return {
                'total_sources': total_sources,
                'active_sources': active_sources,
                'error_sources': error_sources,
                'recent_articles_24h': recent_articles,
                'last_update': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {str(e)}")
            return {}