import os
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from typing import Optional, List

import datetime as dt

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
            id=tag.id, # type: ignore
            name=tag.name, # type: ignore
            category_id=tag.category_id, # type: ignore
            category_name=tag.category.name if tag.category else None,
            frequency=tag.frequency, # type: ignore
            tag_type=tag.tag_type # type: ignore
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
        id=tag.id, # type: ignore
        name=tag.name, # type: ignore
        category_id=tag.category_id, # type: ignore
        category_name=tag.category.name if tag.category else None,
        frequency=tag.frequency, # type: ignore
        tag_type=tag.tag_type # type: ignore
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
    
    return await get_tag(tag.id, db) # type: ignore

@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: int,
    tag_update: TagCreate,  # Riusa il modello di creazione per semplicità
    db: Session = Depends(get_db)
):
    """Update tag"""
    
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with id {tag_id} not found"
        )
    
    # Verifica nome duplicato se viene cambiato
    if tag_update.name.lower() != tag.normalized_name:
        existing = db.query(Tag).filter(Tag.normalized_name == tag_update.name.lower()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tag with name '{tag_update.name}' already exists"
            )
    
    # Verifica categoria se specificata
    if tag_update.category_id:
        category = db.query(Category).filter(Category.id == tag_update.category_id).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with id {tag_update.category_id} not found"
            )
    
    # Aggiorna campi
    tag.name = tag_update.name # type: ignore
    tag.normalized_name = tag_update.name.lower() # type: ignore
    tag.category_id = tag_update.category_id # type: ignore
    
    try:
        db.commit()
        db.refresh(tag)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating tag: {str(e)}"
        )
    
    return await get_tag(tag_id, db)

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

@router.get("/export/csv")
async def export_tags_csv(
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    min_frequency: int = Query(1, ge=1),
    db: Session = Depends(get_db)
):
    """Export tags as CSV data"""
    
    try:
        # Query tags con filtri
        query = db.query(Tag).options(joinedload(Tag.category))
        
        if search:
            query = query.filter(Tag.name.ilike(f"%{search}%"))
        
        if category_id:
            query = query.filter(Tag.category_id == category_id)
        
        if min_frequency > 1:
            query = query.filter(Tag.frequency >= min_frequency)
        
        tags = query.order_by(desc(Tag.frequency)).all()
        
        # Prepara dati per export
        export_data = []
        for tag in tags:
            export_data.append({
                "id": tag.id,
                "name": tag.name,
                "frequency": tag.frequency,
                "tag_type": tag.tag_type,
                "category_name": tag.category.name if tag.category else "",
                "category_color": tag.category.color if tag.category else "",
                "normalized_name": tag.normalized_name
            })
        
        return {
            "data": export_data,
            "total_records": len(export_data),
            "export_date": dt.datetime.now(dt.timezone.utc).isoformat(),
            "filters_applied": {
                "search": search,
                "category_id": category_id,
                "min_frequency": min_frequency
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting tags: {str(e)}"
        )

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

@router.get("/wordcloud/image")
async def tags_wordcloud(
    max_tags: int = Query(100, ge=10, le=500),
    min_frequency: int = Query(2, ge=1),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Genera immagine wordcloud per i tag"""
    ##import numpy as np
    ##from PIL import Image
    from wordcloud import WordCloud, STOPWORDS
    ##import matplotlib.pyplot as plt
    import matplotlib.figure as Figure
    import base64
    from io import BytesIO
    ##from nltk.corpus import stopwords

    try:
        # Recupera i tag
        tags = db.query(Tag).filter(Tag.frequency >= min_frequency).order_by(desc(Tag.frequency)).all()

        # Create stopword list:
        sw = set(STOPWORDS)
        ##sw.update(stopwords.words("italian"))  # Aggiungi stopwords italiane


        # Prepara dati per wordcloud
        frequent_tags = [(tag.normalized_name + ' ') * tag.frequency for tag in tags]
        wordcloud_data = " ".join(frequent_tags) # type: ignore
        wc = WordCloud(stopwords=sw, max_words=50, background_color="white").generate(wordcloud_data)

        # Save the image in the img folder:
        image_file = "wordcloud.png"
        image_path = f"./app/img/{image_file}"

        if not os.path.exists('./app/img'):
            os.makedirs('./app/img')
        if os.path.exists(image_path):
            os.remove(image_path)

        ##wc.to_file(image_path)
        # with plt.ioff():
        #     ##plt.figure()
        #     plt.imshow(wc, interpolation='bilinear')
        #     plt.axis("off")
        #     plt.savefig(image_path, format='png', bbox_inches='tight', pad_inches=0)
        #     plt.close()
        
        # Genera immagine senza visualizzazione (no pyplot)
        fig = Figure.Figure(figsize=(8, 6))
        ax = fig.subplots()
        ax.axis("off")
        ax.imshow(wc, interpolation='bilinear')
        buf = BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        
        data = base64.b64encode(buf.getbuffer()).decode('ascii')
        image_element = f'<img src="data:image/png;base64,{data}" alt="Tags Word Cloud" style="width: 100%; height: 100%;">'

        return {
            "max_tags": max_tags,
            "min_frequency": min_frequency,
            "category_id": category_id,
            "wordcloud_image": image_path,
            "wordcloud_file": image_file,
            "image_element": image_element,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating wordcloud: {str(e)}"
        )

@router.get("/stats/detailed")
async def get_detailed_tag_stats(db: Session = Depends(get_db)):
    """Get detailed tag statistics"""
    
    # Statistiche generali
    total_tags_count = db.query(Tag).count()
    auto_tags = db.query(Tag).filter(Tag.tag_type == 'auto').count()
    manual_tags = db.query(Tag).filter(Tag.tag_type == 'manual').count()
    
    # Tags per categoria
    tags_by_category = db.query(
        Category.name,
        func.count(Tag.id).label('tag_count')
    ).outerjoin(Tag).group_by(Category.name).all()
    
    # Tags senza categoria
    uncategorized_tags = db.query(Tag).filter(Tag.category_id.is_(None)).count()
    
    # Distribuzione frequenze
    frequency_distribution = db.query(
        func.case([
            (Tag.frequency == 1, 'Single use'),
            (Tag.frequency.between(2, 5), '2-5 uses'),
            (Tag.frequency.between(6, 10), '6-10 uses'),
            (Tag.frequency.between(11, 25), '11-25 uses'),
            (Tag.frequency > 25, '25+ uses')
        ]).label('frequency_range'),
        func.count(Tag.id).label('count')
    ).group_by('frequency_range').all()
    
    # Top tags
    top_tags_list = db.query(Tag.name, Tag.frequency)\
        .order_by(desc(Tag.frequency))\
        .limit(10).all()
    
    # Tags recenti (creati di recente - simulato con frequency bassa)
    recent_tags = db.query(Tag.name, Tag.frequency)\
        .filter(Tag.frequency <= 3)\
        .order_by(Tag.id.desc())\
        .limit(10).all()
    
    return {
        "general_stats": {
            "total_tags_count": total_tags_count,
            "auto_tags": auto_tags,
            "manual_tags": manual_tags,
            "uncategorized_tags": uncategorized_tags
        },
        "category_distribution": [
            {"category": name or "Senza categoria", "count": count} 
            for name, count in tags_by_category
        ],
        "frequency_distribution": [
            {"range": freq_range, "count": count}
            for freq_range, count in frequency_distribution
        ],
        "top_tags": [
            {"name": name, "frequency": freq}
            for name, freq in top_tags_list
        ],
        "recent_tags": [
            {"name": name, "frequency": freq}
            for name, freq in recent_tags
        ]
    }

@router.get("/{tag_id}/articles")
async def get_tag_articles(
    tag_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get articles for a specific tag"""
    
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with id {tag_id} not found"
        )
    
    # Query articoli con questo tag
    articles_query = db.query(Article)\
        .join(ArticleTag)\
        .filter(ArticleTag.tag_id == tag_id)\
        .options(joinedload(Article.source))\
        .order_by(desc(Article.scraped_date))
    
    total_articles = articles_query.count()
    articles = articles_query.offset(skip).limit(limit).all()
    
    # Converti in response format
    from ..models import ArticleResponse
    article_responses = []
    for article in articles:
        # Carica tutti i tags dell'articolo
        article_tags = db.query(Tag).join(ArticleTag).filter(ArticleTag.article_id == article.id).all()
        tag_names = [t.name for t in article_tags]
        
        article_response = ArticleResponse(
            id=article.id, # type: ignore
            title=article.title, # type: ignore
            content=article.content, # type: ignore
            summary=article.summary, # type: ignore
            url=article.url, # type: ignore
            author=article.author, # type: ignore
            source_id=article.source_id, # type: ignore
            source_name=article.source.name if article.source else None,
            published_date=article.published_date, # type: ignore
            scraped_date=article.scraped_date, # type: ignore
            word_count=article.word_count, # type: ignore
            language=article.language, # type: ignore
            sentiment_score=article.sentiment_score, # type: ignore
            tags=tag_names, # type: ignore
            is_duplicate=article.is_duplicate # type: ignore
        )
        article_responses.append(article_response)
    
    return {
        "tag": {
            "id": tag.id,
            "name": tag.name,
            "frequency": tag.frequency,
            "tag_type": tag.tag_type,
            "category_name": tag.category.name if tag.category else None
        },
        "articles": article_responses,
        "total_articles": total_articles,
        "skip": skip,
        "limit": limit,
        "has_next": (skip + limit) < total_articles,
        "has_prev": skip > 0
    }

@router.post("/bulk-delete")
async def bulk_delete_tags(
    tag_ids: List[int],
    db: Session = Depends(get_db)
):
    """Delete multiple tags"""
    
    if not tag_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tag IDs provided"
        )
    
    try:
        # Conta associazioni che verranno rimosse
        total_associations = db.query(ArticleTag).filter(ArticleTag.tag_id.in_(tag_ids)).count()
        
        # Elimina tags
        deleted_count = db.query(Tag).filter(Tag.id.in_(tag_ids)).delete(synchronize_session=False)
        
        db.commit()
        
        return {
            "message": f"Successfully deleted {deleted_count} tags",
            "deleted_tags": deleted_count,
            "associations_removed": total_associations
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting tags: {str(e)}"
        )

@router.post("/{tag_id}/merge")
async def merge_tags(

    tag_id: int,
    target_tag_id: int,
    db: Session = Depends(get_db)
):
    """Merge tag into another tag"""
    
    source_tag = db.query(Tag).filter(Tag.id == tag_id).first()
    target_tag = db.query(Tag).filter(Tag.id == target_tag_id).first()
    
    if not source_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source tag with id {tag_id} not found"
        )
    
    if not target_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target tag with id {target_tag_id} not found"
        )
    
    if tag_id == target_tag_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot merge tag with itself"
        )
    
    try:
        # Sposta tutte le associazioni dal source tag al target tag
        associations = db.query(ArticleTag).filter(ArticleTag.tag_id == tag_id).all()
        
        moved_associations = 0
        for association in associations:
            # Controlla se l'articolo ha già il target tag
            existing = db.query(ArticleTag).filter(
                ArticleTag.article_id == association.article_id,
                ArticleTag.tag_id == target_tag_id
            ).first()
            
            if not existing:
                # Sposta l'associazione
                association.tag_id = target_tag_id # type: ignore
                moved_associations += 1
            else:
                # Elimina l'associazione duplicata
                db.delete(association)
        
        # Aggiorna frequenza del target tag
        target_tag.frequency += moved_associations
        
        # Elimina il source tag
        db.delete(source_tag)
        
        db.commit()
        
        return {
            "message": f"Successfully merged '{source_tag.name}' into '{target_tag.name}'",
            "source_tag": source_tag.name,
            "target_tag": target_tag.name,
            "moved_associations": moved_associations,
            "new_target_frequency": target_tag.frequency
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error merging tags: {str(e)}"
        )
        
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
            id=category.id, # type: ignore
            name=category.name, # type: ignore
            description=category.description, # type: ignore
            parent_id=category.parent_id, # type: ignore
            color=category.color, # type: ignore
            icon=category.icon, # type: ignore
            children=[]
        )
    
    # Costruisci gerarchia
    for category in categories:
        if category.parent_id is not None:
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
        id=category.id, # type: ignore
        name=category.name, # type: ignore
        description=category.description, # type: ignore
        parent_id=category.parent_id, # type: ignore
        color=category.color, # type: ignore
        icon=category.icon, # type: ignore
        children=[]
    )

@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_update: CategoryCreate,
    db: Session = Depends(get_db)
):
    """Update category"""
    
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found"
        )
    
    # Verifica nome duplicato se viene cambiato
    if category_update.name != category.name:
        existing = db.query(Category).filter(Category.name == category_update.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with name '{category_update.name}' already exists"
            )
    
    # Verifica parent se specificato
    if category_update.parent_id:
        parent = db.query(Category).filter(Category.id == category_update.parent_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parent category with id {category_update.parent_id} not found"
            )
    
    # Aggiorna campi
    category.name = category_update.name # type: ignore
    category.description = category_update.description # type: ignore
    category.parent_id = category_update.parent_id # type: ignore
    category.color = category_update.color # type: ignore
    category.icon = category_update.icon # type: ignore
    
    try:
        db.commit()
        db.refresh(category)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating category: {str(e)}"
        )
    
    return CategoryResponse(
        id=category.id, # type: ignore
        name=category.name, # type: ignore
        description=category.description, # type: ignore
        parent_id=category.parent_id, # type: ignore
        color=category.color, # type: ignore
        icon=category.icon, # type: ignore
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