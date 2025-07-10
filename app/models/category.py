from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))
    
    # Gerarchia categorie (self-referential)
    parent_id = Column(Integer, ForeignKey('categories.id'))
    
    # UI
    color = Column(String(7), default='#007bff')  # hex color
    icon = Column(String(50))  # nome icona
    
    # Relazioni
    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent")
    tags = relationship("Tag", back_populates="category")
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', parent_id={self.parent_id})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parent_id': self.parent_id,
            'color': self.color,
            'icon': self.icon,
            'children': [child.to_dict() for child in self.children] if self.children else []
        }
    
    def get_full_path(self):
        """Ritorna il percorso completo della categoria"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name