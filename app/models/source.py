from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text
from sqlalchemy.orm import relationship
from .base import Base
import datetime

class Source(Base):
    __tablename__ = 'sources'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    base_url = Column(String(255), nullable=False)
    rss_url = Column(String(255))
    description = Column(Text)
    
    # Configurazione scraping (JSON)
    scraping_config = Column(JSON)
    
    # Impostazioni aggiornamento
    update_frequency = Column(Integer, default=3600)  # secondi
    last_scraped = Column(DateTime)
    next_scrape = Column(DateTime)
    
    # Rate limiting
    rate_limit_delay = Column(Integer, default=2)  # secondi
    
    # Stato
    is_active = Column(Boolean, default=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    
    # Timestamp
    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relazioni
    articles = relationship("Article", back_populates="source", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Source(id={self.id}, name='{self.name}', url='{self.base_url}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'base_url': self.base_url,
            'rss_url': self.rss_url,
            'description': self.description,
            'is_active': self.is_active,
            'last_scraped': self.last_scraped.isoformat() if self.last_scraped else None,
            'error_count': self.error_count,
            'update_frequency': self.update_frequency
        }