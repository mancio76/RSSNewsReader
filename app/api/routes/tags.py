from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from typing import Optional, List

from ..dependencies import get_db
from ..models import TagResponse, CategoryResponse, TagCreate, CategoryCreate
from ...models import Tag, Category, ArticleTag, Article

router = APIRouter(prefix="/tags", tags=["tags"])

@router.get("/", response_model=List[TagResponse])
async def get_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category_id: Optional[int] = Query(None),
    min_frequency: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    sort_by: str = Query("frequency", regex="^(name|frequency)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Get tags with filtering and sorting"""
    
    query = db.query(Tag).options(joinedload(Tag.category))
    
    # Filtri
    if category_id:
        query = query.filter(Tag.category_id == category_id)
    
    if min_frequency > 1:
        query = query.filter(Tag.frequency >= min_frequency)
    
    if search:
        query = query.filter(Tag.name.ilike(f"%{search}%"))
    
    # Ordinamento
    sort_column = getattr(Tag, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Paginazione
    tags = query.offset(skip).limit(limit).all()
    
    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            category_id=tag.category_id,
            category_name=tag.category.name if tag.category else None,
            frequency=tag.frequency,
            tag_type=tag.tag_type
        )
        for tag in tags
    ]

@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(tag_id: int, db: Session = Depends(get_db)):
    """Get single tag by ID"""
    
    tag = db.query(Tag).options(joinedload(Tag.category)).filter(Tag.id == tag_id).first()
    
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with id {tag_id} not found"
        )
    
    return TagResponse(
        id=tag.id,
        name=tag.name,
        category_id=tag.category_id,
        category_name=tag.category.name if tag.category else None,
        frequency=tag.frequency,
        tag_type=tag.tag_type
    )

@router.post("/", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(tag_create: TagCreate, db: Session = Depends(get_db)):
    """Create new tag"""
    
    # Verifica nome duplicato
    existing = db.query(Tag).filter(Tag.normalized_name == tag_create.name.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag with name '{tag_create.name}' already exists"
        )
    
    # Verifica categoria se specificata
    if tag_create.category_id:
        category = db.query(Category).filter(Category.id == tag_create.category_id).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with id {tag_create.category_id} not found"
            )
    
    tag = Tag(
        name=tag_create.name,
        normalized_name=tag_create.name.lower(),
        category_id=tag_create.category_id,
        frequency=0,
        tag_type='manual'
    )
    
    try:
        db.add(tag)
        db.commit()
        db.refresh(tag)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating tag: {str(e)}"
        )
    
    return await get_tag(tag.id, db)

@router.delete("/{tag_id}")
async def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Delete tag and all associations"""
    
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with id {tag_id} not found"
        )
    
    # Conta associazioni
    associations_count = db.query(ArticleTag).filter(ArticleTag.tag_id == tag_id).count()
    
    try:
        db.delete(tag)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting tag: {str(e)}"
        )
    
    return {
        "message": f"Tag {tag_id} deleted successfully",
        "associations_removed": associations_count
    }

@router.get("/stats/top")
async def get_top_tags(
    limit: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Get top tags by frequency"""
    
    query = db.query(Tag).options(joinedload(Tag.category))
    
    if category_id:
        query = query.filter(Tag.category_id == category_id)
    
    tags = query.order_by(desc(Tag.frequency)).limit(limit).all()
    
    return [
        {
            "id": tag.id,
            "name": tag.name,
            "frequency": tag.frequency,
            "category_name": tag.category.name if tag.category else None
        }
        for tag in tags
    ]

@router.get("/wordcloud/data")
async def get_wordcloud_data(
    max_tags: int = Query(100, ge=10, le=500),
    min_frequency: int = Query(2, ge=1),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Get data for wordcloud visualization"""
    
    query = db.query(Tag.name, Tag.frequency)
    
    if category_id:
        query = query.filter(Tag.category_id == category_id)
    
    tags = query.filter(Tag.frequency >= min_frequency)\
        .order_by(desc(Tag.frequency))\
        .limit(max_tags)\
        .all()
    
    return [
        {"text": name, "value": frequency}
        for name, frequency in tags
    ]

# Categories endpoints

@router.get("/categories/", response_model=List[CategoryResponse])
async def get_categories(db: Session = Depends(get_db)):
    """Get all categories with hierarchy"""
    
    categories = db.query(Category).order_by(Category.name).all()
    
    # Organizza in gerarchia
    category_dict = {}
    root_categories = []
    
    for category in categories:
        category_dict[category.id] = CategoryResponse(
            id=category.id,
            name=category.name,
            description=category.description,
            parent_id=category.parent_id,
            color=category.color,
            icon=category.icon,
            children=[]
        )
    
    # Costruisci gerarchia
    for category in categories:
        if category.parent_id:
            parent = category_dict.get(category.parent_id)
            if parent:
                parent.children.append(category_dict[category.id])
        else:
            root_categories.append(category_dict[category.id])
    
    return root_categories

@router.post("/categories/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(category_create: CategoryCreate, db: Session = Depends(get_db)):
    """Create new category"""
    
    # Verifica nome duplicato
    existing = db.query(Category).filter(Category.name == category_create.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category with name '{category_create.name}' already exists"
        )
    
    # Verifica parent se specificato
    if category_create.parent_id:
        parent = db.query(Category).filter(Category.id == category_create.parent_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parent category with id {category_create.parent_id} not found"
            )
    
    category = Category(
        name=category_create.name,
        description=category_create.description,
        parent_id=category_create.parent_id,
        color=category_create.color,
        icon=category_create.icon
    )
    
    try:
        db.add(category)
        db.commit()
        db.refresh(category)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating category: {str(e)}"
        )
    
    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        parent_id=category.parent_id,
        color=category.color,
        icon=category.icon,
        children=[]
    )

@router.delete("/categories/{category_id}")
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Delete category"""
    
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found"
        )
    
    # Controlla se ha figli
    children = db.query(Category).filter(Category.parent_id == category_id).count()
    if children > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category with child categories"
        )
    
    # Conta tags associate
    tags_count = db.query(Tag).filter(Tag.category_id == category_id).count()
    
    try:
        # Rimuovi associazione dai tags
        db.query(Tag).filter(Tag.category_id == category_id).update({Tag.category_id: None})
        
        # Elimina categoria
        db.delete(category)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting category: {str(e)}"
        )
    
    return {
        "message": f"Category {category_id} deleted successfully",
        "tags_unlinked": tags_count
    }