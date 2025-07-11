from pydantic import BaseModel, HttpUrl, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Response Models
class ArticleResponse(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    url: str
    author: Optional[str] = None
    source_id: int
    source_name: Optional[str] = None
    published_date: Optional[datetime] = None
    scraped_date: datetime
    word_count: Optional[int] = None
    language: Optional[str] = None
    sentiment_score: Optional[float] = None
    tags: List[str] = []
    is_duplicate: bool = False
    
    class Config:
        from_attributes = True

class ArticleListResponse(BaseModel):
    articles: List[ArticleResponse]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_prev: bool

class SourceResponse(BaseModel):
    id: int
    name: str
    base_url: str
    rss_url: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    error_count: int
    last_error: Optional[str] = None
    last_scraped: Optional[datetime] = None
    next_scrape: Optional[datetime] = None
    rate_limit_delay: int
    update_frequency: int
    created_date: datetime
    updated_date: datetime
    article_count: Optional[int] = None
    
    class Config:
        from_attributes = True

class SourceListResponse(BaseModel):
    sources: List[SourceResponse]
    total: int
    skip: int
    limit: int

class TagResponse(BaseModel):
    id: int
    name: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    frequency: int
    tag_type: str
    
    class Config:
        from_attributes = True

class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    color: str
    icon: Optional[str] = None
    children: List['CategoryResponse'] = []
    
    class Config:
        from_attributes = True

# Request Models
class SourceCreate(BaseModel):
    name: str
    base_url: HttpUrl
    rss_url: Optional[HttpUrl] = None
    description: Optional[str] = None
    is_active: bool = True
    rate_limit_delay: int = 2
    update_frequency: int = 3600
    scraping_config: Optional[Dict[str, Any]] = None
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('Name must be at least 3 characters long')
        return v.strip()
    
    @validator('rate_limit_delay')
    def validate_rate_limit(cls, v):
        if v < 0 or v > 300:
            raise ValueError('Rate limit delay must be between 0 and 300 seconds')
        return v
    
    @validator('update_frequency')
    def validate_update_frequency(cls, v):
        if v < 300 or v > 86400:
            raise ValueError('Update frequency must be between 300 and 86400 seconds')
        return v

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[HttpUrl] = None
    rss_url: Optional[HttpUrl] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    rate_limit_delay: Optional[int] = None
    update_frequency: Optional[int] = None
    scraping_config: Optional[Dict[str, Any]] = None
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None and (not v or len(v.strip()) < 3):
            raise ValueError('Name must be at least 3 characters long')
        return v.strip() if v else v

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    language: Optional[str] = None
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None and (not v or len(v.strip()) < 5):
            raise ValueError('Title must be at least 5 characters long')
        return v.strip() if v else v

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    color: str = "#007bff"
    icon: Optional[str] = None
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        return v.strip()

class TagCreate(BaseModel):
    name: str
    category_id: Optional[int] = None
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        return v.strip()

# Statistics Models
class SourceStats(BaseModel):
    total_sources: int
    active_sources: int
    error_sources: int
    rss_sources: int
    web_sources: int

class ArticleStats(BaseModel):
    total_articles: int
    articles_today: int
    articles_week: int
    articles_month: int
    avg_words_per_article: float
    most_active_source: Optional[str] = None

class SystemStats(BaseModel):
    source_stats: SourceStats
    article_stats: ArticleStats
    top_tags: List[TagResponse]
    recent_errors: List[str]
    last_scrape: Optional[datetime] = None

# Search Models
class SearchFilter(BaseModel):
    query: Optional[str] = None
    source_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    language: Optional[str] = None
    min_word_count: Optional[int] = None
    max_word_count: Optional[int] = None
    sentiment_min: Optional[float] = None
    sentiment_max: Optional[float] = None
    exclude_duplicates: bool = True

# Scraping Models
class ScrapeRequest(BaseModel):
    source_ids: Optional[List[int]] = None
    force_update: bool = False

class ScrapeResult(BaseModel):
    source_id: int
    source_name: str
    articles_scraped: int
    success: bool
    error_message: Optional[str] = None
    duration_seconds: float

class ScrapeResponse(BaseModel):
    results: List[ScrapeResult]
    total_articles: int
    total_duration: float
    success_count: int
    error_count: int

# Error Models
class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = datetime.now(datetime.timezone.utc).isoformat()

# Allow forward references
CategoryResponse.model_rebuild()