from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os

Base = declarative_base()

def get_db_path():
    """Ritorna path database nella cartella data relativa al programma"""
    # Ottieni il percorso della directory principale del progetto
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))  # Risale di 2 livelli (da app/models/ a root)
    data_dir = os.path.join(project_root, 'data')
    
    # Crea la cartella data se non esiste
    os.makedirs(data_dir, exist_ok=True)
    
    return os.path.join(data_dir, 'database.db')

def create_db_engine():
    """Crea engine SQLite compatibile cross-platform"""
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    engine = create_engine(
        f'sqlite:///{db_path}',
        echo=False,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False}
    )
    return engine

# Crea engine globale
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency per ottenere sessione database"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Crea tutte le tabelle nel database"""
    Base.metadata.create_all(bind=engine)