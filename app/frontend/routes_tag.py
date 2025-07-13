# Aggiungi questi endpoint al file app/api/routes/tags.py

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
    tag.name = tag_update.name
    tag.normalized_name = tag_update.name.lower()
    tag.category_id = tag_update.category_id
    
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
    category.name = category_update.name
    category.description = category_update.description
    category.parent_id = category_update.parent_id
    category.color = category_update.color
    category.icon = category_update.icon
    
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
        id=category.id,
        name=category.name,
        description=category.description,
        parent_id=category.parent_id,
        color=category.color,
        icon=category.icon,
        children=[]
    )

@router.get("/stats/detailed")
async def get_detailed_tag_stats(db: Session = Depends(get_db)):
    """Get detailed tag statistics"""
    
    # Statistiche generali
    total_tags = db.query(Tag).count()
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
            "total_tags": total_tags,
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
            id=article.id,
            title=article.title,
            content=article.content,
            summary=article.summary,
            url=article.url,
            author=article.author,
            source_id=article.source_id,
            source_name=article.source.name if article.source else None,
            published_date=article.published_date,
            scraped_date=article.scraped_date,
            word_count=article.word_count,
            language=article.language,
            sentiment_score=article.sentiment_score,
            tags=tag_names,
            is_duplicate=article.is_duplicate
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
                association.tag_id = target_tag_id
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