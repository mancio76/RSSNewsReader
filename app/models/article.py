from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import Base
import datetime as dt
import hashlib
from article_tag import ArticleTag

class Article(Base):
    __tablename__ = 'articles'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    summary = Column(Text)  # estratto automatico
    url = Column(String(1000), unique=True, nullable=False)
    
    # Metadati autore/fonte
    author = Column(String(200))
    source_id = Column(Integer, ForeignKey('sources.id'), nullable=False)
    
    # Date
    published_date = Column(DateTime)
    scraped_date = Column(DateTime, default=dt.datetime.now(dt.timezone.utc)) ## datetime.datetime.utcnow
    updated_date = Column(DateTime, default=dt.datetime.now(dt.timezone.utc), onupdate=dt.datetime.now(dt.timezone.utc))
    
    # Hashing per deduplicazione
    content_hash = Column(String(64), index=True)
    url_hash = Column(String(64), index=True)
    
    # Analisi contenuto
    word_count = Column(Integer)
    language = Column(String(10), default='it')
    sentiment_score = Column(Float)  # da -1 a 1
    
    # Stato
    is_duplicate = Column(Boolean, default=False)
    is_processed = Column(Boolean, default=False)

    # Attributi aggiuntivi
    sentiment_score = Column(Float, nullable=True)
    word_count = Column(Integer, nullable=True)
    language = Column(String(10), nullable=True)
    is_duplicate = Column(Boolean, default=False)
    
    # Relazioni
    source = relationship("Source", back_populates="articles")
    ##tags = relationship("Tag", secondary="article_tags", back_populates="articles")
    
     # ✅ CORRETTO - Relazione many-to-many tramite association object
    tags = relationship("Tag", secondary=ArticleTag.__table__, back_populates="articles")

    article_metadata = relationship("ArticleMetadata", back_populates="article", cascade="all, delete-orphan")
    versions = relationship("ArticleVersion", back_populates="article", cascade="all, delete-orphan")
    
    # Indici per performance
    __table_args__ = (
        Index('ix_articles_published_source', 'published_date', 'source_id'),
        Index('ix_articles_scraped_date', 'scraped_date'),
        # content_hash e url_hash hanno già index=True nella definizione della colonna
    )
    
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title[:50]}...', source_id={self.source_id})>"
    
    def generate_content_hash(self):
        """Genera hash del contenuto per deduplicazione"""
        if self.content is not None:
            content_clean = self.content.strip().lower()
            self.content_hash = hashlib.sha256(content_clean.encode()).hexdigest()
    
    def generate_url_hash(self):
        """Genera hash dell'URL canonico"""
        if self.url is not None:
            # Rimuovi parametri di tracking comuni
            url_clean = self.url.split('?')[0].split('#')[0]
            self.url_hash = hashlib.sha256(url_clean.encode()).hexdigest()
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'summary': self.summary,
            'url': self.url,
            'author': self.author,
            'source_id': self.source_id,
            'source_name': self.source.name if self.source else None,
            'published_date': self.published_date.isoformat() if self.published_date else None,  # type: ignore
            'scraped_date': self.scraped_date.isoformat() if self.scraped_date else None, # type: ignore
            'word_count': self.word_count,
            'language': self.language,
            'sentiment_score': self.sentiment_score,
            'tags': [tag.name for tag in self.tags] if self.tags else [],
            'metadata': [{'key': m.key, 'value': m.value} for m in self.article_metadata] if self.article_metadata else []
        }