from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, and_
from typing import Optional
from datetime import datetime, timedelta
import json

from ..api.dependencies import get_db
from ..models import Source, Article, Tag, ArticleTag

router = APIRouter(prefix="/web", tags=["frontend"])
templates = Jinja2Templates(directory="app/frontend/templates")

# Aggiungi filtro JSON per Jinja2 con gestione datetime
def to_json(value):
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    return json.dumps(value, default=json_serializer)

templates.env.filters['tojsonfilter'] = to_json

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard principale"""
    
    # Statistiche generali
    total_articles = db.query(Article).count()
    total_sources = db.query(Source).count()
    active_sources = db.query(Source).filter(Source.is_active == True).count()
    
    # Articoli recenti (ultimi 7 giorni)
    week_ago = datetime.now(datetime.timezone.utc) - timedelta(days=7)
    recent_articles = db.query(Article).filter(Article.scraped_date >= week_ago).count()
    
    # Top sources per numero articoli
    top_sources = db.query(
        Source.name,
        func.count(Article.id).label('count')
    ).join(Article).group_by(Source.name).order_by(desc('count')).limit(5).all()
    
    # Articoli più recenti - prepara dati serializzabili
    latest_articles_query = db.query(Article).options(joinedload(Article.source))\
        .order_by(desc(Article.scraped_date)).limit(10).all()
    
    latest_articles = []
    for article in latest_articles_query:
        article_dict = {
            'id': article.id,
            'title': article.title,
            'summary': article.summary,
            'author': article.author,
            'word_count': article.word_count,
            'scraped_date': article.scraped_date.strftime('%d/%m/%Y %H:%M') if article.scraped_date else None,
            'source': {
                'name': article.source.name if article.source else None
            }
        }
        latest_articles.append(article_dict)
    
    # Top tags
    top_tags = db.query(Tag).order_by(desc(Tag.frequency)).limit(10).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_articles": total_articles,
        "total_sources": total_sources,
        "active_sources": active_sources,
        "recent_articles": recent_articles,
        "top_sources": top_sources,
        "latest_articles": latest_articles,
        "top_tags": top_tags,
        "page_title": "Dashboard"
    })

@router.get("/articles", response_class=HTMLResponse)
async def articles_list(
    request: Request,
    page: int = Query(1, ge=1),
    source_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Lista articoli con paginazione"""
    
    limit = 20
    skip = (page - 1) * limit
    
    # Query base
    query = db.query(Article).options(joinedload(Article.source))
    
    # Filtri
    if source_id:
        query = query.filter(Article.source_id == source_id)
    
    if search:
        query = query.filter(
            Article.title.ilike(f"%{search}%") |
            Article.content.ilike(f"%{search}%")
        )
    
    # Ordinamento
    query = query.order_by(desc(Article.scraped_date))
    
    # Conteggio totale
    total = query.count()
    total_pages = (total + limit - 1) // limit
    
    # Paginazione
    articles_query = query.offset(skip).limit(limit).all()
    
    # Converti in formato serializzabile
    articles = []
    for article in articles_query:
        article_dict = {
            'id': article.id,
            'title': article.title,
            'content': article.content,
            'summary': article.summary,
            'url': article.url,
            'author': article.author,
            'word_count': article.word_count,
            'language': article.language,
            'sentiment_score': article.sentiment_score,
            'is_duplicate': article.is_duplicate,
            'scraped_date': article.scraped_date.strftime('%d/%m/%Y %H:%M') if article.scraped_date else None,
            'published_date': article.published_date.strftime('%d/%m/%Y') if article.published_date else None,
            'source': {
                'name': article.source.name if article.source else None
            }
        }
        articles.append(article_dict)
    
    # Sources per filtro
    sources = db.query(Source).filter(Source.is_active == True).order_by(Source.name).all()
    
    return templates.TemplateResponse("articles.html", {
        "request": request,
        "articles": articles,
        "sources": sources,
        "current_page": page,
        "total_pages": total_pages,
        "total_articles": total,
        "selected_source": source_id,
        "search_query": search,
        "page_title": "Articoli"
    })

@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: int, db: Session = Depends(get_db)):
    """Dettaglio articolo"""
    
    article = db.query(Article).options(joinedload(Article.source))\
        .filter(Article.id == article_id).first()
    
    if not article:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": "Articolo non trovato",
            "page_title": "Errore"
        })
    
    # Tags dell'articolo
    tags = db.query(Tag).join(ArticleTag).filter(ArticleTag.article_id == article_id).all()
    
    # Articoli correlati (stessa source)
    related_articles = db.query(Article).filter(
        Article.source_id == article.source_id,
        Article.id != article_id
    ).order_by(desc(Article.scraped_date)).limit(5).all()
    
    return templates.TemplateResponse("article_detail.html", {
        "request": request,
        "article": article,
        "tags": tags,
        "related_articles": related_articles,
        "page_title": article.title
    })

@router.get("/sources", response_class=HTMLResponse)
async def sources_list(request: Request, db: Session = Depends(get_db)):
    """Lista sources"""
    
    sources_query = db.query(Source).order_by(Source.name).all()
    
    # Prepara dati completamente serializzabili
    sources_data = []
    for source in sources_query:
        article_count = db.query(Article).filter(Article.source_id == source.id).count()
        recent_articles = db.query(Article).filter(
            Article.source_id == source.id,
            Article.scraped_date >= datetime.now(datetime.timezone.utc) - timedelta(days=7)
        ).count()
        
        # Crea un dict completamente serializzabile (NO oggetti datetime)
        source_dict = {
            'id': source.id,
            'name': source.name,
            'base_url': source.base_url,
            'rss_url': source.rss_url,
            'description': source.description,
            'is_active': source.is_active,
            'error_count': source.error_count or 0,
            'last_error': source.last_error,
            'rate_limit_delay': source.rate_limit_delay,
            'update_frequency': source.update_frequency,
            'scraping_config': source.scraping_config,
            'article_count': article_count,
            'recent_articles': recent_articles,
            # Converti datetime in stringhe
            'last_scraped': source.last_scraped.strftime('%d/%m/%Y %H:%M') if source.last_scraped else None,
            'last_scraped_iso': source.last_scraped.isoformat() if source.last_scraped else None,
            'next_scrape': source.next_scrape.isoformat() if source.next_scrape else None,
            'created_date': source.created_date.isoformat() if source.created_date else None,
            'updated_date': source.updated_date.isoformat() if source.updated_date else None
        }
        sources_data.append(source_dict)
    
    return templates.TemplateResponse("sources.html", {
        "request": request,
        "sources": sources_data,
        "page_title": "Sources"
    })

@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, db: Session = Depends(get_db)):
    """Pagina analytics"""
    
    # Timeline ultimi 30 giorni
    end_date = datetime.now(datetime.timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    timeline_data = db.query(
        func.date(Article.scraped_date).label('date'),
        func.count(Article.id).label('count')
    ).filter(
        Article.scraped_date >= start_date
    ).group_by(func.date(Article.scraped_date)).order_by('date').all()
    
    # Converti in formato per Chart.js
    timeline = []
    current_date = start_date.date()
    timeline_dict = {date: count for date, count in timeline_data}
    
    while current_date <= end_date.date():
        timeline.append({
            'date': current_date.isoformat(),
            'articles': timeline_dict.get(current_date, 0)
        })
        current_date += timedelta(days=1)
    
    # Sources performance
    sources_performance = db.query(
        Source.name,
        func.count(Article.id).label('articles_count')
    ).join(Article).filter(
        Article.scraped_date >= start_date
    ).group_by(Source.name).order_by(desc('articles_count')).limit(10).all()
    
    # Converti in formato serializzabile
    sources_performance_data = [
        {'source_name': name, 'articles_count': count} 
        for name, count in sources_performance
    ]
    
    # Top tags per wordcloud
    top_tags = db.query(Tag.name, Tag.frequency)\
        .filter(Tag.frequency >= 2)\
        .order_by(desc(Tag.frequency))\
        .limit(50).all()
    
    # Converti in formato serializzabile
    top_tags_data = [[name, freq] for name, freq in top_tags]
    
    # Linguaggi
    languages = db.query(
        Article.language,
        func.count(Article.id).label('count')
    ).filter(
        Article.language.isnot(None),
        Article.scraped_date >= start_date
    ).group_by(Article.language).order_by(desc('count')).all()
    
    # Converti in formato serializzabile
    languages_data = [[lang, count] for lang, count in languages]
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "timeline": timeline,
        "sources_performance": sources_performance_data,
        "top_tags": top_tags_data,
        "languages": languages_data,
        "page_title": "Analytics"
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request, db: Session = Depends(get_db)):
    """Pagina impostazioni"""
    
    sources = db.query(Source).order_by(Source.name).all()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "sources": sources,
        "page_title": "Impostazioni"
    })

@router.post("/sources/toggle/{source_id}")
async def toggle_source(source_id: int, db: Session = Depends(get_db)):
    """Attiva/disattiva source"""
    
    source = db.query(Source).filter(Source.id == source_id).first()
    if source:
        source.is_active = not source.is_active
        source.updated_date = datetime.now(datetime.timezone.utc)
        db.commit()
    
    return {"success": True, "is_active": source.is_active if source else False}

@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Pagina di ricerca"""
    
    results = []
    total_results = 0
    
    if q and len(q.strip()) >= 3:
        query = db.query(Article).options(joinedload(Article.source))
        
        search_filter = Article.title.ilike(f"%{q}%") | Article.content.ilike(f"%{q}%")
        results_query = query.filter(search_filter).order_by(desc(Article.scraped_date))
        
        total_results = results_query.count()
        results = results_query.limit(50).all()
    
    return templates.TemplateResponse("search.html", {
        "request": request,
        "query": q,
        "results": results,
        "total_results": total_results,
        "page_title": f"Ricerca: {q}" if q else "Ricerca"
    })