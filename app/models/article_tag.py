from sqlalchemy import Column, Integer, ForeignKey, Float, String, DateTime, Table
from sqlalchemy.orm import relationship
from .base import Base
import datetime as dt

# Tabella di associazione molti-a-molti con metadati aggiuntivi
class ArticleTag(Base):
    __tablename__ = 'article_tags'
    
    article_id = Column(Integer, ForeignKey('articles.id'), primary_key=True)
    tag_id = Column(Integer, ForeignKey('tags.id'), primary_key=True)
    
    # Metadati associazione
    confidence = Column(Float, default=1.0)  # confidenza se estratto automaticamente
    source = Column(String(20), default='manual')  # manual, nlp, auto
    created_date = Column(DateTime, default=dt.datetime.now(dt.timezone.utc))
    
    # Relazioni
    ## article = relationship("Article")
    ## tag = relationship("Tag")
    
    # ✅ OPPURE se vuoi mantenere le relazioni dirette, cambia i nomi:
    article_ref = relationship("Article", foreign_keys=[article_id])
    tag_ref = relationship("Tag", foreign_keys=[tag_id])
    
    def __repr__(self):
        return f"<ArticleTag(article_id={self.article_id}, tag_id={self.tag_id}, confidence={self.confidence})>"
    
    def to_dict(self):
        return {
            'article_id': self.article_id,
            'tag_id': self.tag_id,
            'confidence': self.confidence,
            'source': self.source,
            'created_date': self.created_date.isoformat() if self.created_date else None # type: ignore
        }