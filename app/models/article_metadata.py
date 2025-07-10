from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class ArticleMetadata(Base):
    __tablename__ = 'article_metadata'
    
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey('articles.id'), nullable=False)
    key = Column(String(50), nullable=False)
    value = Column(Text)
    
    # Relazioni
    article = relationship("Article", back_populates="article_metadata")
    
    # Indice composito per performance
    __table_args__ = (
        {'extend_existing': True},
    )
    
    def __repr__(self):
        return f"<ArticleMetadata(article_id={self.article_id}, key='{self.key}', value='{self.value[:50]}...')>"
    
    def to_dict(self):
        return {
            'article_id': self.article_id,
            'key': self.key,
            'value': self.value
        }

# Metadati comuni che potrebbero essere utili:
# - "image_url": URL immagine principale
# - "video_url": URL video embedded
# - "reading_time": tempo di lettura stimato
# - "social_shares": numero condivisioni social
# - "comments_count": numero commenti
# - "upvotes": upvotes se da Reddit/HackerNews
# - "category_auto": categoria auto-rilevata
# - "keywords": parole chiave estratte
# - "entities": entità nominate (persone, luoghi, etc.)
# - "topics": topic modeling results