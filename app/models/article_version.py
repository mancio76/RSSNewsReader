from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base
import datetime as dt

class ArticleVersion(Base):
    __tablename__ = 'article_versions'
    
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey('articles.id'), nullable=False)
    
    # Contenuto versione
    title = Column(String(500))
    content = Column(Text)
    summary = Column(Text)
    
    # Metadati versione
    version_number = Column(Integer, default=1)
    change_type = Column(String(20))  # 'created', 'title_change', 'content_update', 'summary_change'
    change_description = Column(Text)
    
    # Timestamp
    created_date = Column(DateTime, default=dt.datetime.now(dt.timezone.utc))
    
    # Relazioni
    article = relationship("Article", back_populates="versions")
    
    def __repr__(self):
        return f"<ArticleVersion(id={self.id}, article_id={self.article_id}, version={self.version_number}, change_type='{self.change_type}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'article_id': self.article_id,
            'title': self.title,
            'content': self.content,
            'summary': self.summary,
            'version_number': self.version_number,
            'change_type': self.change_type,
            'change_description': self.change_description,
            'created_date': self.created_date.isoformat() if self.created_date else None
        }
    
    @staticmethod
    def create_from_article(article, change_type='created'):
        """Crea una nuova versione da un articolo esistente"""
        return ArticleVersion(
            article_id=article.id,
            title=article.title,
            content=article.content,
            summary=article.summary,
            change_type=change_type,
            version_number=len(article.versions) + 1 if article.versions else 1
        )