from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, and_
from typing import Optional, List
from datetime import datetime, timedelta
import os

from ..models import Source, Article, Tag, ArticleTag, Category
from ..api.dependencies import get_db

# Setup templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard principale"""
    
    # Statistiche generali
    total_articles = db.query(Article).count()
    total_sources = db.query(Source).count()
    active_sources = db.query(Source).filter(Source.is_active == True).count()
    
    # Articoli recenti (ultimi 10)
    recent_articles = db.query(Article)\
        .options(joinedload(Article.source))\
        .order_by(desc(Article.scraped_date))\
        .limit(10).all()
    
    # Sources con più articoli
    top_sources = db.query(Source.name, func.count(Article.id).label('count'))\
        .join(Article)\
        .group_by(Source.name)\
        .order_by(desc('count'))\
        .limit(5).all()
    
    # Top tags
    top_tags = db.query(Tag.name, Tag.frequency)\
        .order_by(desc(Tag.frequency))\
        .limit(10).all()
    
    # Articoli ultimi 7 giorni
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_count = db.query(Article).filter(Article.scraped_date >= week_ago).count()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_articles": total_articles,
        "total_sources": total_sources,
        "active_sources": active_sources,
        "recent_articles": recent_articles,
        "top_sources": top_sources,
        "top_tags": top_tags,
        "recent_count": recent_count,
        "page_title": "Dashboard"
    })

@router.get("/articles", response_class=HTMLResponse)
async def articles_page(
    request: Request,
    page: int = Query(1, ge=1),
    source_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Pagina articoli con filtri"""
    
    page_size = 20
    offset = (page - 1) * page_size
    
    # Query base
    query = db.query(Article).options(joinedload(Article.source))
    
    # Filtri
    if source_id:
        query = query.filter(Article.source_id == source_id)
    
    if search:
        search_filter = Article.title.ilike(f"%{search}%") | Article.content.ilike(f"%{search}%")
        query = query.filter(search_filter)
    
    # Ordinamento e paginazione
    query = query.order_by(desc(Article.scraped_date))
    total_count = query.count()
    articles = query.offset(offset).limit(page_size).all()
    
    # Info paginazione
    total_pages = (total_count + page_size - 1) // page_size
    has_prev = page > 1
    has_next = page < total_pages
    
    # Sources per filtro
    sources = db.query(Source).filter(Source.is_active == True).order_by(Source.name).all()
    
    return templates.TemplateResponse("articles.html", {
        "request": request,
        "articles": articles,
        "sources": sources,
        "page": page,
        "total_pages": total_pages,
        "has_prev": has_prev,
        "has_next": has_next,
        "total_count": total_count,
        "current_source_id": source_id,
        "search": search or "",
        "page_title": "Articles"
    })

@router.get("/articles/{article_id}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: int, db: Session = Depends(get_db)):
    """Dettaglio singolo articolo"""
    
    article = db.query(Article)\
        .options(joinedload(Article.source))\
        .filter(Article.id == article_id)\
        .first()
    
    if not article:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Article {article_id} not found",
            "page_title": "Error"
        })
    
    # Tags dell'articolo
    tags = db.query(Tag).join(ArticleTag).filter(ArticleTag.article_id == article_id).all()
    
    # Articoli correlati dalla stessa source
    related_articles = db.query(Article)\
        .filter(Article.source_id == article.source_id, Article.id != article_id)\
        .order_by(desc(Article.scraped_date))\
        .limit(5).all()
    
    return templates.TemplateResponse("article_detail.html", {
        "request": request,
        "article": article,
        "tags": tags,
        "related_articles": related_articles,
        "page_title": article.title
    })

@router.get("/sources", response_class=HTMLResponse)
async def sources_page(request: Request, db: Session = Depends(get_db)):
    """Pagina gestione sources"""
    
    sources = db.query(Source).order_by(Source.name).all()
    
    # Aggiungi conteggio articoli per ogni source
    source_stats = []
    for source in sources:
        article_count = db.query(Article).filter(Article.source_id == source.id).count()
        recent_count = db.query(Article).filter(
            Article.source_id == source.id,
            Article.scraped_date >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        source_stats.append({
            'source': source,
            'article_count': article_count,
            'recent_count': recent_count
        })
    
    return templates.TemplateResponse("sources.html", {
        "request": request,
        "source_stats": source_stats,
        "page_title": "Sources"
    })

@router.get("/sources/{source_id}", response_class=HTMLResponse)
async def source_detail(request: Request, source_id: int, db: Session = Depends(get_db)):
    """Dettaglio singola source"""
    
    source = db.query(Source).filter(Source.id == source_id).first()
    
    if not source:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Source {source_id} not found",
            "page_title": "Error"
        })
    
    # Articoli della source
    articles = db.query(Article)\
        .filter(Article.source_id == source_id)\
        .order_by(desc(Article.scraped_date))\
        .limit(20).all()
    
    # Statistiche
    total_articles = db.query(Article).filter(Article.source_id == source_id).count()
    recent_articles = db.query(Article).filter(
        Article.source_id == source_id,
        Article.scraped_date >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    return templates.TemplateResponse("source_detail.html", {
        "request": request,
        "source": source,
        "articles": articles,
        "total_articles": total_articles,
        "recent_articles": recent_articles,
        "page_title": f"Source: {source.name}"
    })

@router.get("/tags", response_class=HTMLResponse)
async def tags_page(request: Request, db: Session = Depends(get_db)):
    """Pagina tags e wordcloud"""
    
    # Top tags
    tags = db.query(Tag).order_by(desc(Tag.frequency)).limit(50).all()
    
    # Tags per wordcloud (JSON)
    wordcloud_data = [{"text": tag.name, "size": tag.frequency} for tag in tags[:30]]
    
    # Categorie
    categories = db.query(Category).order_by(Category.name).all()
    
    return templates.TemplateResponse("tags.html", {
        "request": request,
        "tags": tags,
        "wordcloud_data": wordcloud_data,
        "categories": categories,
        "page_title": "Tags"
    })

@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, db: Session = Depends(get_db)):
    """Pagina analytics e statistiche"""
    
    # Dati per grafici
    # Articoli per giorno (ultimi 30 giorni)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    daily_stats = db.query(
        func.date(Article.scraped_date).label('date'),
        func.count(Article.id).label('count')
    ).filter(
        Article.scraped_date >= start_date
    ).group_by(func.date(Article.scraped_date))\
     .order_by(func.date(Article.scraped_date)).all()
    
    # Sources performance
    source_performance = db.query(
        Source.name,
        func.count(Article.id).label('count'),
        func.max(Article.scraped_date).label('last_article')
    ).join(Article)\
     .filter(Article.scraped_date >= start_date)\
     .group_by(Source.name)\
     .order_by(desc('count')).all()
    
    # Tag trends
    tag_trends = db.query(
        Tag.name,
        func.count(ArticleTag.article_id).label('usage')
    ).join(ArticleTag)\
     .join(Article)\
     .filter(Article.scraped_date >= start_date)\
     .group_by(Tag.name)\
     .order_by(desc('usage'))\
     .limit(15).all()
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "daily_stats": daily_stats,
        "source_performance": source_performance,
        "tag_trends": tag_trends,
        "page_title": "Analytics"
    })

@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Pagina ricerca avanzata"""
    
    articles = []
    total_count = 0
    
    if q and len(q) >= 3:
        # Ricerca in titolo e contenuto
        search_query = db.query(Article)\
            .options(joinedload(Article.source))\
            .filter(
                Article.title.ilike(f"%{q}%") | 
                Article.content.ilike(f"%{q}%") |
                Article.summary.ilike(f"%{q}%")
            )\
            .order_by(desc(Article.scraped_date))
        
        total_count = search_query.count()
        articles = search_query.limit(50).all()
    
    return templates.TemplateResponse("search.html", {
        "request": request,
        "query": q or "",
        "articles": articles,
        "total_count": total_count,
        "page_title": "Search"
    })