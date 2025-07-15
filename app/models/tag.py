from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base
from .article_tag import ArticleTag
import datetime as dt

class Tag(Base):
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    normalized_name = Column(String(100), index=True)  # per ricerche case-insensitive
    
    # Categoria di appartenenza
    category_id = Column(Integer, ForeignKey('categories.id'))
    
    # Statistiche
    frequency = Column(Integer, default=1, nullable=False)  # numero di articoli con questo tag
    
    # Tipo di tag
    tag_type = Column(String(20), default='manual')  # manual, auto, nlp
    created_date = Column(DateTime, default=dt.datetime.now(dt.timezone.utc))

    # Relazioni
    category = relationship("Category", back_populates="tags")
    
    ## articles = relationship("Article", secondary="article_tags", back_populates="tags")
    # ✅ CORRETTO - Relazione many-to-many tramite association object
    articles = relationship("Article", ArticleTag.__tablename__, back_populates="tags")
    
    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}', frequency={self.frequency})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'frequency': self.frequency,
            'tag_type': self.tag_type,
            'created_date': self.created_date.isoformat() if self.created_date else None # type: ignore
        }
    
    def increment_frequency(self):
        """Incrementa la frequenza del tag"""
        self.frequency += 1
    
    def decrement_frequency(self):
        """Decrementa la frequenza del tag"""
        if self.frequency > 0: # type: ignore
            self.frequency -= 1