from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Generator
import logging

from ..models.base import SessionLocal

logger = logging.getLogger(__name__)

def get_db() -> Generator[Session, None, None]:
    """Dependency per ottenere sessione database"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    finally:
        db.close()

def validate_pagination(skip: int = 0, limit: int = 100) -> tuple[int, int]:
    """Valida parametri di paginazione"""
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skip parameter must be >= 0"
        )
    
    if limit <= 0 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit parameter must be between 1 and 1000"
        )
    
    return skip, limit