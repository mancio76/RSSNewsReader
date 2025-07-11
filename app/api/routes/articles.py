from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, and_, or_, func
from typing import Optional, List
import datetime as dt

from ..dependencies import get_db, validate_pagination
from ..models import ArticleResponse, ArticleListResponse, ArticleUpdate, SearchFilter
from ...models import Article, Source, Tag, ArticleTag

router = APIRouter(prefix="/articles", tags=["articles"])

@router.get("/", response_model=ArticleListResponse)
async def get_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    source_id: Optional[int] = Query(None),
    author: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    date_from: Optional[dt.datetime] = Query(None),
    date_to: Optional[dt.datetime] = Query(None),
    exclude_duplicates: bool = Query(True),
    search: Optional[str] = Query(None),
    sort_by: str = Query("scraped_date", regex="^(scraped_date|published_date|title|word_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Get articles with pagination and filtering"""
    
    # Base query con join per source
    query = db.query(Article).options(joinedload(Article.source))
    
    # Filtri
    if source_id:
        query = query.filter(Article.source_id == source_id)
    
    if author:
        query = query.filter(Article.author.ilike(f"%{author}%"))
    
    if language:
        query = query.filter(Article.language == language)
    
    if date_from:
        query = query.filter(Article.published_date >= date_from)
    
    if date_to:
        query = query.filter(Article.published_date <= date_to)
    
    if exclude_duplicates:
        query = query.filter(Article.is_duplicate == False)
    
    if search:
        search_filter = or_(
            Article.title.ilike(f"%{search}%"),
            Article.content.ilike(f"%{search}%"),
            Article.summary.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Ordinamento
    sort_column = getattr(Article, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    # Conta totale
    total = query.count()
    
    # Paginazione
    articles = query.offset(skip).limit(limit).all()
    
    # Converti in response model
    article_responses = []
    for article in articles:
        # Carica tags
        tags = db.query(Tag).join(ArticleTag).filter(ArticleTag.article_id == article.id).all()
        tag_names = [tag.name for tag in tags]
        
        article_response = ArticleResponse(
            id=article.id,
            title=article.title,
            content=article.content,
            summary=article.summary,
            url=article.url,
            author=article.author,
            source_id=article.source_id,
            source_name=article.source.name if article.source else None,
            published_date=article.published_date,
            scraped_date=article.scraped_date,
            word_count=article.word_count,
            language=article.language,
            sentiment_score=article.sentiment_score,
            tags=tag_names,
            is_duplicate=article.is_duplicate
        )
        article_responses.append(article_response)
    
    return ArticleListResponse(
        articles=article_responses,
        total=total,
        skip=skip,
        limit=limit,
        has_next=(skip + limit) < total,
        has_prev=skip > 0
    )

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: Session = Depends(get_db)):
    """Get single article by ID"""
    
    article = db.query(Article).options(joinedload(Article.source)).filter(Article.id == article_id).first()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article with id {article_id} not found"
        )
    
    # Carica tags
    tags = db.query(Tag).join(ArticleTag).filter(ArticleTag.article_id == article.id).all()
    tag_names = [tag.name for tag in tags]
    
    return ArticleResponse(
        id=article.id,
        title=article.title,
        content=article.content,
        summary=article.summary,
        url=article.url,
        author=article.author,
        source_id=article.source_id,
        source_name=article.source.name if article.source else None,
        published_date=article.published_date,
        scraped_date=article.scraped_date,
        word_count=article.word_count,
        language=article.language,
        sentiment_score=article.sentiment_score,
        tags=tag_names,
        is_duplicate=article.is_duplicate
    )

@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: int,
    article_update: ArticleUpdate,
    db: Session = Depends(get_db)
):
    """Update article"""
    
    article = db.query(Article).filter(Article.id == article_id).first()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article with id {article_id} not found"
        )
    
    # Aggiorna campi
    update_data = article_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(article, field, value)
    
    # Rigenera hash se contenuto cambiato
    if 'content' in update_data:
        article.generate_content_hash()
        article.word_count = len(article.content.split()) if article.content else 0
    
    article.updated_date = dt.datetime.now(dt.timezone.utc)
    
    try:
        db.commit()
        db.refresh(article)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating article: {str(e)}"
        )
    
    return await get_article(article_id, db)

@router.delete("/{article_id}")
async def delete_article(article_id: int, db: Session = Depends(get_db)):
    """Delete article"""
    
    article = db.query(Article).filter(Article.id == article_id).first()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article with id {article_id} not found"
        )
    
    try:
        db.delete(article)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting article: {str(e)}"
        )
    
    return {"message": f"Article {article_id} deleted successfully"}

@router.post("/search", response_model=ArticleListResponse)
async def search_articles(
    search_filter: SearchFilter,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: str = Query("scraped_date", regex="^(scraped_date|published_date|title|word_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Advanced search for articles"""
    
    query = db.query(Article).options(joinedload(Article.source))
    
    # Text search
    if search_filter.query:
        text_search = or_(
            Article.title.ilike(f"%{search_filter.query}%"),
            Article.content.ilike(f"%{search_filter.query}%"),
            Article.summary.ilike(f"%{search_filter.query}%")
        )
        query = query.filter(text_search)
    
    # Source filter
    if search_filter.source_ids:
        query = query.filter(Article.source_id.in_(search_filter.source_ids))
    
    # Author filter
    if search_filter.author:
        query = query.filter(Article.author.ilike(f"%{search_filter.author}%"))
    
    # Date filters
    if search_filter.date_from:
        query = query.filter(Article.published_date >= search_filter.date_from)
    
    if search_filter.date_to:
        query = query.filter(Article.published_date <= search_filter.date_to)
    
    # Language filter
    if search_filter.language:
        query = query.filter(Article.language == search_filter.language)
    
    # Word count filters
    if search_filter.min_word_count:
        query = query.filter(Article.word_count >= search_filter.min_word_count)
    
    if search_filter.max_word_count:
        query = query.filter(Article.word_count <= search_filter.max_word_count)
    
    # Sentiment filters
    if search_filter.sentiment_min is not None:
        query = query.filter(Article.sentiment_score >= search_filter.sentiment_min)
    
    if search_filter.sentiment_max is not None:
        query = query.filter(Article.sentiment_score <= search_filter.sentiment_max)
    
    # Tags filter
    if search_filter.tags:
        tag_articles = db.query(ArticleTag.article_id).join(Tag).filter(
            Tag.name.in_(search_filter.tags)
        ).subquery()
        query = query.filter(Article.id.in_(tag_articles))
    
    # Exclude duplicates
    if search_filter.exclude_duplicates:
        query = query.filter(Article.is_duplicate == False)
    
    # Sorting
    sort_column = getattr(Article, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    # Count and paginate
    total = query.count()
    articles = query.offset(skip).limit(limit).all()
    
    # Convert to response
    article_responses = []
    for article in articles:
        tags = db.query(Tag).join(ArticleTag).filter(ArticleTag.article_id == article.id).all()
        tag_names = [tag.name for tag in tags]
        
        article_response = ArticleResponse(
            id=article.id,
            title=article.title,
            content=article.content,
            summary=article.summary,
            url=article.url,
            author=article.author,
            source_id=article.source_id,
            source_name=article.source.name if article.source else None,
            published_date=article.published_date,
            scraped_date=article.scraped_date,
            word_count=article.word_count,
            language=article.language,
            sentiment_score=article.sentiment_score,
            tags=tag_names,
            is_duplicate=article.is_duplicate
        )
        article_responses.append(article_response)
    
    return ArticleListResponse(
        articles=article_responses,
        total=total,
        skip=skip,
        limit=limit,
        has_next=(skip + limit) < total,
        has_prev=skip > 0
    )

@router.get("/stats/summary")
async def get_article_stats(db: Session = Depends(get_db)):
    """Get article statistics"""
    
    now = dt.datetime.now(dt.timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - dt.timedelta(days=7)
    month_ago = today - dt.timedelta(days=30)
    
    total_articles = db.query(Article).count()
    articles_today = db.query(Article).filter(Article.scraped_date >= today).count()
    articles_week = db.query(Article).filter(Article.scraped_date >= week_ago).count()
    articles_month = db.query(Article).filter(Article.scraped_date >= month_ago).count()
    
    # Average word count
    avg_words = db.query(func.avg(Article.word_count)).filter(Article.word_count.isnot(None)).scalar() or 0
    
    # Most active source
    most_active = db.query(Source.name, func.count(Article.id).label('count'))\
        .join(Article)\
        .group_by(Source.name)\
        .order_by(desc('count'))\
        .first()
    
    return {
        "total_articles": total_articles,
        "articles_today": articles_today,
        "articles_week": articles_week,
        "articles_month": articles_month,
        "avg_words_per_article": round(avg_words, 1),
        "most_active_source": most_active[0] if most_active else None
    }