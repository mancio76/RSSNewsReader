#!/usr/bin/env python3
"""
Test script per verificare i scrapers
"""

import sys
import os
import asyncio
from datetime import datetime

# Aggiungi il percorso root del progetto al PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.models import Base, Source
from app.models.base import SessionLocal, create_tables
from app.scrapers import RSSReader, WebReader, ScraperManager

async def test_rss_reader():
    """Test RSSReader con feed di esempio"""
    print("\n📰 Test RSSReader...")
    
    # Configurazione test RSS
    rss_config = {
        'base_url': 'https://feeds.bbci.co.uk/news/rss.xml',
        'rss_url': 'https://feeds.bbci.co.uk/news/rss.xml',
        'max_articles': 5,
        'rate_limit_delay': 1
    }
    
    try:
        async with RSSReader(rss_config) as reader:
            # Test validazione
            print("   Validating RSS source...")
            is_valid = await reader.validate_source()
            print(f"   ✅ RSS validation: {'PASS' if is_valid else 'FAIL'}")
            
            if is_valid:
                # Test fetch articles
                print("   Fetching RSS articles...")
                articles = await reader.fetch_articles()
                print(f"   ✅ Fetched {len(articles)} articles")
                
                # Mostra dettagli primi articoli
                for i, article in enumerate(articles[:2]):
                    print(f"   📄 Article {i+1}:")
                    print(f"      Title: {article.title[:80]}...")
                    print(f"      URL: {article.url}")
                    print(f"      Author: {article.author}")
                    print(f"      Published: {article.published_date}")
                    print(f"      Content length: {len(article.content) if article.content else 0}")
                    print(f"      Tags: {article.tags}")
                    
                # Test source info
                info = reader.get_source_info()
                print(f"   📊 Source info: {info}")
                
    except Exception as e:
        print(f"   ❌ RSS test failed: {str(e)}")

async def test_web_reader():
    """Test WebReader con sito di esempio"""
    print("\n🌐 Test WebReader...")
    
    # Configurazione test web scraping
    web_config = {
        'base_url': 'https://example.com',  # Sito semplice per test
        'scraping_config': {
            'article_list_selector': 'p',  # Semplice per example.com
            'title_selector': 'h1',
            'content_selector': 'p',
            'url_selector': 'a'
        },
        'max_articles': 3,
        'rate_limit_delay': 1
    }
    
    try:
        async with WebReader(web_config) as reader:
            # Test validazione
            print("   Validating web source...")
            is_valid = await reader.validate_source()
            print(f"   ✅ Web validation: {'PASS' if is_valid else 'FAIL'}")
            
            if is_valid:
                # Test fetch articles
                print("   Fetching web articles...")
                articles = await reader.fetch_articles()
                print(f"   ✅ Found {len(articles)} articles")
                
                # Mostra dettagli
                for i, article in enumerate(articles):
                    print(f"   📄 Article {i+1}:")
                    print(f"      Title: {article.title[:50]}...")
                    print(f"      URL: {article.url}")
                    print(f"      Content: {article.content[:100]}...")
                    
                # Test source info
                info = reader.get_source_info()
                print(f"   📊 Source info: {info}")
                
    except Exception as e:
        print(f"   ❌ Web test failed: {str(e)}")

async def test_scraper_manager():
    """Test ScraperManager con database"""
    print("\n🔧 Test ScraperManager...")
    
    try:
        # Crea database e tabelle se necessario
        create_tables()
        
        # Crea sessione database
        db = SessionLocal()
        
        try:
            # Crea o aggiorna source di test
            test_source = db.query(Source).filter_by(name="BBC RSS").first()
            if not test_source:
                test_source = Source(
                    name="Test RSS Source",
                    base_url="https://feeds.bbci.co.uk/news/rss.xml",
                    rss_url="https://feeds.bbci.co.uk/news/rss.xml",
                    description="BBC News RSS feed for testing",
                    is_active=True,
                    rate_limit_delay=2,
                    update_frequency=3600
                )
                db.add(test_source)
                db.commit()
            
            # Crea ScraperManager
            manager = ScraperManager(db)
            
            print("   Testing ScraperManager...")
            
            # Test creazione reader
            reader = manager.create_reader(test_source)
            print(f"   ✅ Reader created: {type(reader).__name__}")
            
            # Test scrape singola source
            print("   Scraping test source...")
            articles = await manager.scrape_source(test_source)
            print(f"   ✅ Scraped and saved {len(articles)} articles to database")
            
            # Test statistiche
            stats = manager.get_source_statistics()
            print(f"   📊 Statistics: {stats}")
            
            # Test validazione sources
            print("   Validating all sources...")
            validation_results = await manager.validate_all_sources()
            print(f"   ✅ Validation results: {validation_results}")
            
            # Mostra alcuni articoli dal database
            saved_articles = db.query(Source).filter_by(name="Test RSS Source").first().articles
            print(f"   📚 Total articles in DB for this source: {len(saved_articles)}")
            
            for i, article in enumerate(saved_articles[:2]):
                print(f"   📄 DB Article {i+1}:")
                print(f"      ID: {article.id}")
                print(f"      Title: {article.title[:50]}...")
                print(f"      URL: {article.url}")
                print(f"      Scraped: {article.scraped_date}")
                print(f"      Published: {article.published_date}")
                print(f"      Tags: {len(article.tags)}")
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"   ❌ ScraperManager test failed: {str(e)}")

async def test_concurrent_scraping():
    """Test scraping concorrente"""
    print("\n⚡ Test Concurrent Scraping...")
    
    try:
        create_tables()
        db = SessionLocal()
        
        try:
            # Crea multiple sources di test
            test_sources = [
                {
                    'name': 'BBC News RSS',
                    'rss_url': 'https://feeds.bbci.co.uk/news/rss.xml',
                    'base_url': 'https://www.bbc.com/news'
                },
                {
                    'name': 'Ansa RSS',
                    'rss_url': 'https://www.ansa.it/sito/ansait_rss.xml',
                    'base_url': 'https://www.ansa.it'
                }
            ]
            
            # Aggiungi sources se non esistono
            for source_data in test_sources:
                existing = db.query(Source).filter_by(name=source_data['name']).first()
                if not existing:
                    source = Source(
                        name=source_data['name'],
                        base_url=source_data['base_url'],
                        rss_url=source_data['rss_url'],
                        description=f"Test source: {source_data['name']}",
                        is_active=True,
                        rate_limit_delay=1,
                        update_frequency=3600
                    )
                    db.add(source)
            
            db.commit()
            
            # Test scraping concorrente
            manager = ScraperManager(db)
            
            print("   Starting concurrent scraping...")
            start_time = datetime.now()
            
            results = await manager.scrape_all_active_sources()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            total_articles = sum(len(articles) for articles in results.values())
            
            print(f"   ✅ Concurrent scraping completed in {duration:.2f} seconds")
            print(f"   📊 Results: {len(results)} sources, {total_articles} total articles")
            
            for source_name, articles in results.items():
                print(f"      {source_name}: {len(articles)} articles")
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"   ❌ Concurrent scraping test failed: {str(e)}")

async def main():
    """Esegui tutti i test"""
    print("🚀 Starting Scrapers Test Suite")
    print("=" * 50)
    
    # Test individuali
    await test_rss_reader()
    await test_web_reader()
    await test_scraper_manager()
    await test_concurrent_scraping()
    
    print("\n" + "=" * 50)
    print("✅ All scraper tests completed!")

if __name__ == "__main__":
    # Esegui i test
    asyncio.run(main())