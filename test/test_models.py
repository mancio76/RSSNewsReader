#!/usr/bin/env python3
"""
Test script per verificare i modelli del database
"""

import sys
import os

# Aggiungi il percorso root del progetto al PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.models import Base, Source, Article, Category, Tag, ArticleTag, ArticleMetadata, ArticleVersion
from app.models.base import create_db_engine, SessionLocal, create_tables
import datetime as dt

def test_models():
    """Test base dei modelli"""
    print("🔧 Creazione database e tabelle...")
    
    # Crea le tabelle
    create_tables()
    print("✅ Tabelle create con successo")
    
    # Crea sessione
    db = SessionLocal()
    
    try:
        # Test Source
        print("\n📰 Test Source...")
        source = Source(
            name="Test Source",
            base_url="https://example.com",
            rss_url="https://example.com/rss",
            description="Source di test",
            scraping_config={
                "title_selector": "h1",
                "content_selector": ".content",
                "date_selector": ".date"
            }
        )
        db.add(source)
        db.commit()
        print(f"✅ Source creata: {source}")
        
        # Test Category
        print("\n📂 Test Category...")
        category = Category(
            name="Tecnologia",
            description="Articoli su tecnologia",
            color="#007bff"
        )
        db.add(category)
        db.commit()
        print(f"✅ Category creata: {category}")
        
        # Test Tag
        print("\n🏷️ Test Tag...")
        tag = Tag(
            name="Python",
            normalized_name="python",
            category_id=category.id
        )
        db.add(tag)
        db.commit()
        print(f"✅ Tag creato: {tag}")
        
        # Test Article
        print("\n📄 Test Article...")
        article = Article(
            title="Test Article",
            content="Questo è un articolo di test per verificare il modello.",
            url="https://example.com/article-1",
            author="Test Author",
            source_id=source.id,
            published_date=dt.datetime.utcnow(),
            word_count=10,
            language="it"
        )
        
        # Genera hash
        article.generate_content_hash()
        article.generate_url_hash()
        
        db.add(article)
        db.commit()
        print(f"✅ Article creato: {article}")
        print(f"   Content hash: {article.content_hash}")
        print(f"   URL hash: {article.url_hash}")
        
        # Test ArticleTag (associazione)
        print("\n🔗 Test ArticleTag...")
        article_tag = ArticleTag(
            article_id=article.id,
            tag_id=tag.id,
            confidence=0.95,
            source="manual"
        )
        db.add(article_tag)
        db.commit()
        print(f"✅ ArticleTag creato: {article_tag}")
        
        # Test ArticleMetadata
        print("\n📊 Test ArticleMetadata...")
        article_metadata = ArticleMetadata(
            article_id=article.id,
            key="reading_time",
            value="2 minuti"
        )
        db.add(article_metadata)
        db.commit()
        print(f"✅ ArticleMetadata creato: {article_metadata}")
        
        # Test ArticleVersion
        print("\n📝 Test ArticleVersion...")
        version = ArticleVersion.create_from_article(article, "created")
        db.add(version)
        db.commit()
        print(f"✅ ArticleVersion creato: {version}")
        
        # Test relazioni
        print("\n🔗 Test relazioni...")
        db.refresh(article)
        print(f"   Article tags: {[tag.name for tag in article.tags]}")
        print(f"   Article metadata: {[(m.key, m.value) for m in article.article_metadata]}")
        print(f"   Article versions: {len(article.versions)}")
        print(f"   Source articles: {len(source.articles)}")
        
        # Test query
        print("\n🔍 Test query...")
        articles = db.query(Article).join(Source).filter(Source.name == "Test Source").all()
        print(f"   Articoli da 'Test Source': {len(articles)}")
        
        print("\n✅ Tutti i test completati con successo!")
        
    except Exception as e:
        print(f"❌ Errore durante i test: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    test_models()