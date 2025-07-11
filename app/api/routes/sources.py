from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio

from ..dependencies import get_db
from ..models import SourceResponse, SourceListResponse, SourceCreate, SourceUpdate, ScrapeRequest, ScrapeResponse
from ...models import Source, Article
from ...scrapers import ScraperManager

router = APIRouter(prefix="/sources", tags=["sources"])

@router.get("/", response_model=SourceListResponse)
async def get_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    has_errors: Optional[bool] = Query(None),
    source_type: Optional[str] = Query(None, regex="^(rss|web)$"),
    db: Session = Depends(get_db)
):
    """Get sources with pagination and filtering"""
    
    query = db.query(Source)
    
    # Filtri
    if active_only:
        query = query.filter(Source.is_active == True)
    
    if has_errors is not None:
        if has_errors:
            query = query.filter(Source.error_count > 0)
        else:
            query = query.filter(Source.error_count == 0)
    
    if source_type:
        if source_type == "rss":
            query = query.filter(Source.rss_url.isnot(None))
        else:  # web
            query = query.filter(Source.rss_url.is_(None))
    
    # Ordinamento per nome
    query = query.order_by(Source.name)
    
    # Conta totale
    total = query.count()
    
    # Paginazione
    sources = query.offset(skip).limit(limit).all()
    
    # Aggiungi conteggio articoli per ogni source
    source_responses = []
    for source in sources:
        article_count = db.query(Article).filter(Article.source_id == source.id).count()
        
        source_response = SourceResponse(
            id=source.id,
            name=source.name,
            base_url=source.base_url,
            rss_url=source.rss_url,
            description=source.description,
            is_active=source.is_active,
            error_count=source.error_count,
            last_error=source.last_error,
            last_scraped=source.last_scraped,
            next_scrape=source.next_scrape,
            rate_limit_delay=source.rate_limit_delay,
            update_frequency=source.update_frequency,
            created_date=source.created_date,
            updated_date=source.updated_date,
            article_count=article_count
        )
        source_responses.append(source_response)
    
    return SourceListResponse(
        sources=source_responses,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: int, db: Session = Depends(get_db)):
    """Get single source by ID"""
    
    source = db.query(Source).filter(Source.id == source_id).first()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id {source_id} not found"
        )
    
    # Conta articoli
    article_count = db.query(Article).filter(Article.source_id == source.id).count()
    
    return SourceResponse(
        id=source.id,
        name=source.name,
        base_url=source.base_url,
        rss_url=source.rss_url,
        description=source.description,
        is_active=source.is_active,
        error_count=source.error_count,
        last_error=source.last_error,
        last_scraped=source.last_scraped,
        next_scrape=source.next_scrape,
        rate_limit_delay=source.rate_limit_delay,
        update_frequency=source.update_frequency,
        created_date=source.created_date,
        updated_date=source.updated_date,
        article_count=article_count
    )

@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(source_create: SourceCreate, db: Session = Depends(get_db)):
    """Create new source"""
    
    # Verifica nome duplicato
    existing = db.query(Source).filter(Source.name == source_create.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source with name '{source_create.name}' already exists"
        )
    
    # Crea source
    source = Source(
        name=source_create.name,
        base_url=str(source_create.base_url),
        rss_url=str(source_create.rss_url) if source_create.rss_url else None,
        description=source_create.description,
        is_active=source_create.is_active,
        rate_limit_delay=source_create.rate_limit_delay,
        update_frequency=source_create.update_frequency,
        scraping_config=source_create.scraping_config,
        created_date=datetime.now(datetime.timezone.utc),
        updated_date=datetime.now(datetime.timezone.utc)
    )
    
    try:
        db.add(source)
        db.commit()
        db.refresh(source)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating source: {str(e)}"
        )
    
    return await get_source(source.id, db)

@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    source_update: SourceUpdate,
    db: Session = Depends(get_db)
):
    """Update source"""
    
    source = db.query(Source).filter(Source.id == source_id).first()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id {source_id} not found"
        )
    
    # Verifica nome duplicato se viene cambiato
    if source_update.name and source_update.name != source.name:
        existing = db.query(Source).filter(Source.name == source_update.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source with name '{source_update.name}' already exists"
            )
    
    # Aggiorna campi
    update_data = source_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field in ['base_url', 'rss_url'] and value:
            value = str(value)
        setattr(source, field, value)
    
    source.updated_date = datetime.now(datetime.timezone.utc)
    
    try:
        db.commit()
        db.refresh(source)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating source: {str(e)}"
        )
    
    return await get_source(source_id, db)

@router.delete("/{source_id}")
async def delete_source(source_id: int, db: Session = Depends(get_db)):
    """Delete source and all associated articles"""
    
    source = db.query(Source).filter(Source.id == source_id).first()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id {source_id} not found"
        )
    
    article_count = db.query(Article).filter(Article.source_id == source_id).count()
    
    try:
        db.delete(source)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting source: {str(e)}"
        )
    
    return {
        "message": f"Source {source_id} deleted successfully",
        "articles_deleted": article_count
    }

@router.post("/{source_id}/scrape", response_model=ScrapeResponse)
async def scrape_source(
    source_id: int,
    background_tasks: BackgroundTasks,
    force_update: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Scrape single source"""
    
    source = db.query(Source).filter(Source.id == source_id).first()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id {source_id} not found"
        )
    
    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source {source.name} is not active"
        )
    
    # Controlla se necessita aggiornamento
    if not force_update and source.next_scrape and source.next_scrape > datetime.now(datetime.timezone.utc):
        time_left = (source.next_scrape - datetime.now(datetime.timezone.utc)).total_seconds()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Source not ready for scraping. Try again in {int(time_left)} seconds"
        )
    
    try:
        manager = ScraperManager(db)
        start_time = datetime.now(datetime.timezone.utc)
        
        articles = await manager.scrape_source(source)
        
        end_time = datetime.now(datetime.timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        from ..models import ScrapeResult
        result = ScrapeResult(
            source_id=source.id,
            source_name=source.name,
            articles_scraped=len(articles),
            success=True,
            error_message=None,
            duration_seconds=duration
        )
        
        return ScrapeResponse(
            results=[result],
            total_articles=len(articles),
            total_duration=duration,
            success_count=1,
            error_count=0
        )
        
    except Exception as e:
        error_msg = str(e)
        
        from ..models import ScrapeResult
        result = ScrapeResult(
            source_id=source.id,
            source_name=source.name,
            articles_scraped=0,
            success=False,
            error_message=error_msg,
            duration_seconds=0
        )
        
        return ScrapeResponse(
            results=[result],
            total_articles=0,
            total_duration=0,
            success_count=0,
            error_count=1
        )

@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_sources(
    scrape_request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Scrape multiple sources or all active sources"""
    
    # Determina sources da fare scraping
    if scrape_request.source_ids:
        sources = db.query(Source).filter(
            Source.id.in_(scrape_request.source_ids),
            Source.is_active == True
        ).all()
    else:
        # Scrape tutte le sources attive
        if scrape_request.force_update:
            sources = db.query(Source).filter(Source.is_active == True).all()
        else:
            # Solo quelle che necessitano aggiornamento
            now = datetime.now(datetime.timezone.utc)
            sources = db.query(Source).filter(
                Source.is_active == True,
                (Source.next_scrape.is_(None)) | (Source.next_scrape <= now)
            ).all()
    
    if not sources:
        return ScrapeResponse(
            results=[],
            total_articles=0,
            total_duration=0,
            success_count=0,
            error_count=0
        )
    
    try:
        manager = ScraperManager(db)
        start_time = datetime.now(datetime.timezone.utc)
        
        # Scrape in parallelo
        results = []
        total_articles = 0
        success_count = 0
        error_count = 0
        
        for source in sources:
            try:
                source_start = datetime.now(datetime.timezone.utc)
                articles = await manager.scrape_source(source)
                source_end = datetime.now(datetime.timezone.utc)
                source_duration = (source_end - source_start).total_seconds()
                
                from ..models import ScrapeResult
                result = ScrapeResult(
                    source_id=source.id,
                    source_name=source.name,
                    articles_scraped=len(articles),
                    success=True,
                    error_message=None,
                    duration_seconds=source_duration
                )
                results.append(result)
                total_articles += len(articles)
                success_count += 1
                
            except Exception as e:
                from ..models import ScrapeResult
                result = ScrapeResult(
                    source_id=source.id,
                    source_name=source.name,
                    articles_scraped=0,
                    success=False,
                    error_message=str(e),
                    duration_seconds=0
                )
                results.append(result)
                error_count += 1
        
        end_time = datetime.now(datetime.timezone.utc)
        total_duration = (end_time - start_time).total_seconds()
        
        return ScrapeResponse(
            results=results,
            total_articles=total_articles,
            total_duration=total_duration,
            success_count=success_count,
            error_count=error_count
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during scraping: {str(e)}"
        )

@router.post("/{source_id}/validate")
async def validate_source(source_id: int, db: Session = Depends(get_db)):
    """Validate source configuration"""
    
    source = db.query(Source).filter(Source.id == source_id).first()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id {source_id} not found"
        )
    
    try:
        manager = ScraperManager(db)
        reader = manager.create_reader(source)
        
        if not reader:
            return {
                "source_id": source_id,
                "source_name": source.name,
                "valid": False,
                "error": "Could not create reader for source"
            }
        
        async with reader:
            is_valid = await reader.validate_source()
            
            return {
                "source_id": source_id,
                "source_name": source.name,
                "valid": is_valid,
                "source_info": reader.get_source_info() if is_valid else None
            }
            
    except Exception as e:
        return {
            "source_id": source_id,
            "source_name": source.name,
            "valid": False,
            "error": str(e)
        }

@router.get("/stats/summary")
async def get_source_stats(db: Session = Depends(get_db)):
    """Get source statistics"""
    
    total_sources = db.query(Source).count()
    active_sources = db.query(Source).filter(Source.is_active == True).count()
    error_sources = db.query(Source).filter(Source.error_count > 0).count()
    rss_sources = db.query(Source).filter(Source.rss_url.isnot(None)).count()
    web_sources = total_sources - rss_sources
    
    # Sources con più articoli
    top_sources = db.query(Source.name, func.count(Article.id).label('count'))\
        .join(Article, Source.id == Article.source_id)\
        .group_by(Source.name)\
        .order_by(desc('count'))\
        .limit(5)\
        .all()
    
    # Sources con errori recenti
    error_sources_list = db.query(Source).filter(
        Source.error_count > 0,
        Source.last_error.isnot(None)
    ).limit(5).all()
    
    return {
        "total_sources": total_sources,
        "active_sources": active_sources,
        "error_sources": error_sources,
        "rss_sources": rss_sources,
        "web_sources": web_sources,
        "top_sources": [{"name": name, "article_count": count} for name, count in top_sources],
        "recent_errors": [{"name": s.name, "error": s.last_error} for s in error_sources_list]
    }