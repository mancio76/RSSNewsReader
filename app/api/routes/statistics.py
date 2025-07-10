from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from collections import Counter

from ..dependencies import get_db
from ..models import SystemStats, SourceStats, ArticleStats
from ...models import Source, Article, Tag, ArticleTag

router = APIRouter(prefix="/statistics", tags=["statistics"])

@router.get("/dashboard", response_model=SystemStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get comprehensive dashboard statistics"""
    
    # Source statistics
    total_sources = db.query(Source).count()
    active_sources = db.query(Source).filter(Source.is_active == True).count()
    error_sources = db.query(Source).filter(Source.error_count > 0).count()
    rss_sources = db.query(Source).filter(Source.rss_url.isnot(None)).count()
    web_sources = total_sources - rss_sources
    
    source_stats = SourceStats(
        total_sources=total_sources,
        active_sources=active_sources,
        error_sources=error_sources,
        rss_sources=rss_sources,
        web_sources=web_sources
    )
    
    # Article statistics
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
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
    
    article_stats = ArticleStats(
        total_articles=total_articles,
        articles_today=articles_today,
        articles_week=articles_week,
        articles_month=articles_month,
        avg_words_per_article=round(avg_words, 1),
        most_active_source=most_active[0] if most_active else None
    )
    
    # Top tags
    top_tags = db.query(Tag).order_by(desc(Tag.frequency)).limit(10).all()
    
    from ..models import TagResponse
    top_tag_responses = [
        TagResponse(
            id=tag.id,
            name=tag.name,
            category_id=tag.category_id,
            category_name=tag.category.name if tag.category else None,
            frequency=tag.frequency,
            tag_type=tag.tag_type
        )
        for tag in top_tags
    ]
    
    # Recent errors
    error_sources_list = db.query(Source.last_error).filter(
        Source.last_error.isnot(None),
        Source.error_count > 0
    ).limit(5).all()
    
    recent_errors = [error[0] for error in error_sources_list if error[0]]
    
    # Last scrape
    last_scrape = db.query(func.max(Source.last_scraped)).scalar()
    
    return SystemStats(
        source_stats=source_stats,
        article_stats=article_stats,
        top_tags=top_tag_responses,
        recent_errors=recent_errors,
        last_scrape=last_scrape
    )

@router.get("/articles/timeline")
async def get_articles_timeline(
    days: int = Query(30, ge=1, le=365),
    source_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Get articles timeline for the last N days"""
    
    end_date = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    start_date = end_date - timedelta(days=days)
    
    query = db.query(
        func.date(Article.scraped_date).label('date'),
        func.count(Article.id).label('count')
    ).filter(
        Article.scraped_date >= start_date,
        Article.scraped_date <= end_date
    )
    
    if source_id:
        query = query.filter(Article.source_id == source_id)
    
    results = query.group_by(func.date(Article.scraped_date))\
        .order_by(func.date(Article.scraped_date))\
        .all()
    
    # Fill missing days with 0
    timeline = {}
    current_date = start_date.date()
    
    while current_date <= end_date.date():
        timeline[current_date.isoformat()] = 0
        current_date += timedelta(days=1)
    
    # Fill actual data
    for date, count in results:
        timeline[date.isoformat()] = count
    
    return {
        "timeline": [
            {"date": date, "articles": count}
            for date, count in timeline.items()
        ],
        "total_articles": sum(timeline.values()),
        "period_days": days
    }

@router.get("/sources/performance")
async def get_sources_performance(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get sources performance metrics"""
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Articles per source in period
    articles_per_source = db.query(
        Source.name,
        Source.id,
        func.count(Article.id).label('articles_count'),
        func.avg(Article.word_count).label('avg_words'),
        func.max(Article.scraped_date).label('last_article')
    ).outerjoin(Article, and_(
        Source.id == Article.source_id,
        Article.scraped_date >= start_date
    )).group_by(Source.id, Source.name).all()
    
    performance_data = []
    for source_name, source_id, articles_count, avg_words, last_article in articles_per_source:
        # Get source details
        source = db.query(Source).filter(Source.id == source_id).first()
        
        performance_data.append({
            "source_id": source_id,
            "source_name": source_name,
            "articles_count": articles_count or 0,
            "avg_words": round(avg_words or 0, 1),
            "last_article": last_article.isoformat() if last_article else None,
            "is_active": source.is_active,
            "error_count": source.error_count,
            "last_scraped": source.last_scraped.isoformat() if source.last_scraped else None,
            "source_type": "RSS" if source.rss_url else "WEB"
        })
    
    # Sort by articles count
    performance_data.sort(key=lambda x: x["articles_count"], reverse=True)
    
    return {
        "sources": performance_data,
        "period_days": days,
        "total_sources": len(performance_data),
        "active_sources": len([s for s in performance_data if s["is_active"]])
    }

@router.get("/tags/trends")
async def get_tag_trends(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db)
):
    """Get trending tags over time"""
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get tag usage in the period
    tag_usage = db.query(
        Tag.name,
        Tag.id,
        func.count(ArticleTag.article_id).label('usage_count'),
        func.max(Article.scraped_date).label('last_used')
    ).join(ArticleTag, Tag.id == ArticleTag.tag_id)\
     .join(Article, ArticleTag.article_id == Article.id)\
     .filter(Article.scraped_date >= start_date)\
     .group_by(Tag.id, Tag.name)\
     .order_by(desc('usage_count'))\
     .limit(limit).all()
    
    trends = []
    for tag_name, tag_id, usage_count, last_used in tag_usage:
        # Get total frequency for comparison
        tag = db.query(Tag).filter(Tag.id == tag_id).first()
        
        trends.append({
            "tag_id": tag_id,
            "tag_name": tag_name,
            "usage_count": usage_count,
            "total_frequency": tag.frequency,
            "last_used": last_used.isoformat() if last_used else None,
            "trend_percentage": round((usage_count / tag.frequency * 100), 1) if tag.frequency > 0 else 0
        })
    
    return {
        "trending_tags": trends,
        "period_days": days,
        "analysis_date": end_date.isoformat()
    }

@router.get("/content/analysis")
async def get_content_analysis(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get content analysis statistics"""
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Articles in period
    articles = db.query(Article).filter(
        Article.scraped_date >= start_date,
        Article.scraped_date <= end_date
    ).all()
    
    if not articles:
        return {
            "total_articles": 0,
            "language_distribution": {},
            "word_count_stats": {},
            "sentiment_analysis": {},
            "duplicate_analysis": {}
        }
    
    # Language distribution
    languages = Counter([a.language for a in articles if a.language])
    
    # Word count statistics
    word_counts = [a.word_count for a in articles if a.word_count and a.word_count > 0]
    if word_counts:
        word_stats = {
            "min": min(word_counts),
            "max": max(word_counts),
            "avg": round(sum(word_counts) / len(word_counts), 1),
            "median": sorted(word_counts)[len(word_counts) // 2]
        }
    else:
        word_stats = {"min": 0, "max": 0, "avg": 0, "median": 0}
    
    # Sentiment analysis
    sentiments = [a.sentiment_score for a in articles if a.sentiment_score is not None]
    if sentiments:
        positive = len([s for s in sentiments if s > 0.1])
        negative = len([s for s in sentiments if s < -0.1])
        neutral = len(sentiments) - positive - negative
        
        sentiment_stats = {
            "total_analyzed": len(sentiments),
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "avg_sentiment": round(sum(sentiments) / len(sentiments), 3)
        }
    else:
        sentiment_stats = {
            "total_analyzed": 0,
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "avg_sentiment": 0
        }
    
    # Duplicate analysis
    duplicates = len([a for a in articles if a.is_duplicate])
    
    return {
        "total_articles": len(articles),
        "period_days": days,
        "language_distribution": dict(languages),
        "word_count_stats": word_stats,
        "sentiment_analysis": sentiment_stats,
        "duplicate_analysis": {
            "total_duplicates": duplicates,
            "duplicate_percentage": round((duplicates / len(articles) * 100), 1) if articles else 0,
            "unique_articles": len(articles) - duplicates
        }
    }

@router.get("/authors/top")
async def get_top_authors(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db)
):
    """Get top authors by article count"""
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    authors = db.query(
        Article.author,
        func.count(Article.id).label('article_count'),
        func.avg(Article.word_count).label('avg_words'),
        func.max(Article.scraped_date).label('last_article')
    ).filter(
        Article.author.isnot(None),
        Article.author != '',
        Article.scraped_date >= start_date
    ).group_by(Article.author)\
     .order_by(desc('article_count'))\
     .limit(limit).all()
    
    return {
        "top_authors": [
            {
                "author": author,
                "article_count": article_count,
                "avg_words": round(avg_words or 0, 1),
                "last_article": last_article.isoformat() if last_article else None
            }
            for author, article_count, avg_words, last_article in authors
        ],
        "period_days": days,
        "total_authors": len(authors)
    }

@router.get("/export/csv")
async def export_statistics_csv(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Export statistics as CSV data"""
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get articles with related data
    articles = db.query(Article).join(Source).filter(
        Article.scraped_date >= start_date
    ).all()
    
    csv_data = []
    for article in articles:
        # Get tags
        tags = db.query(Tag).join(ArticleTag).filter(ArticleTag.article_id == article.id).all()
        tag_names = "; ".join([tag.name for tag in tags])
        
        csv_data.append({
            "article_id": article.id,
            "title": article.title,
            "author": article.author or "",
            "source_name": article.source.name,
            "published_date": article.published_date.isoformat() if article.published_date else "",
            "scraped_date": article.scraped_date.isoformat(),
            "word_count": article.word_count or 0,
            "language": article.language or "",
            "sentiment_score": article.sentiment_score or 0,
            "is_duplicate": article.is_duplicate,
            "tags": tag_names,
            "url": article.url
        })
    
    return {
        "data": csv_data,
        "total_records": len(csv_data),
        "period": f"{start_date.date()} to {end_date.date()}",
        "export_date": datetime.utcnow().isoformat()
    }

@router.get("/health")
async def get_system_health(db: Session = Depends(get_db)):
    """Get system health metrics"""
    
    # Database health
    try:
        total_articles = db.query(Article).count()
        total_sources = db.query(Source).count()
        db_healthy = True
    except Exception:
        total_articles = 0
        total_sources = 0
        db_healthy = False
    
    # Recent activity
    now = datetime.utcnow()
    last_hour = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)
    
    recent_articles = db.query(Article).filter(Article.scraped_date >= last_hour).count()
    articles_24h = db.query(Article).filter(Article.scraped_date >= last_24h).count()
    
    # Error analysis
    error_sources = db.query(Source).filter(Source.error_count > 0).count()
    total_errors = db.query(func.sum(Source.error_count)).scalar() or 0
    
    # Calculate health score
    health_score = 100
    if not db_healthy:
        health_score -= 50
    if error_sources > 0:
        health_score -= min(30, (error_sources / total_sources * 30)) if total_sources > 0 else 0
    if recent_articles == 0 and articles_24h == 0:
        health_score -= 20
    
    return {
        "health_score": max(0, round(health_score, 1)),
        "database_healthy": db_healthy,
        "total_articles": total_articles,
        "total_sources": total_sources,
        "recent_activity": {
            "articles_last_hour": recent_articles,
            "articles_last_24h": articles_24h
        },
        "error_summary": {
            "sources_with_errors": error_sources,
            "total_error_count": total_errors
        },
        "check_time": now.isoformat()
    }

@router.get("/wordcloud")
async def get_wordcloud_data(
    days: int = Query(30, ge=1, le=365),
    max_words: int = Query(100, ge=10, le=500),
    min_frequency: int = Query(2, ge=1),
    db: Session = Depends(get_db)
):
    """Get wordcloud data based on recent tag usage"""
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get tags used in the period
    tag_data = db.query(
        Tag.name,
        func.count(ArticleTag.article_id).label('recent_usage')
    ).join(ArticleTag, Tag.id == ArticleTag.tag_id)\
     .join(Article, ArticleTag.article_id == Article.id)\
     .filter(Article.scraped_date >= start_date)\
     .group_by(Tag.id, Tag.name)\
     .having(func.count(ArticleTag.article_id) >= min_frequency)\
     .order_by(desc('recent_usage'))\
     .limit(max_words).all()
    
    wordcloud_data = [
        {"text": name, "value": usage}
        for name, usage in tag_data
    ]
    
    return {
        "words": wordcloud_data,
        "total_words": len(wordcloud_data),
        "period_days": days,
        "min_frequency": min_frequency
    }

@router.get("/sources/errors")
async def get_source_errors(
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get sources with recent errors"""
    
    error_sources = db.query(Source).filter(
        Source.error_count > 0,
        Source.last_error.isnot(None)
    ).order_by(desc(Source.error_count)).all()
    
    errors_data = []
    for source in error_sources:
        errors_data.append({
            "source_id": source.id,
            "source_name": source.name,
            "error_count": source.error_count,
            "last_error": source.last_error,
            "last_scraped": source.last_scraped.isoformat() if source.last_scraped else None,
            "is_active": source.is_active,
            "source_type": "RSS" if source.rss_url else "WEB"
        })
    
    return {
        "error_sources": errors_data,
        "total_error_sources": len(errors_data),
        "check_date": datetime.utcnow().isoformat()
    }