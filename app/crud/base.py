from typing import Generic, TypeVar, Type, Optional, List, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from fastapi import HTTPException, status
from app.database import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Generic CRUD class with tenant isolation via explicit tenant_id.
    
    This class provides type-safe CRUD operations that filter by tenant_id.
    Tenant ID is always passed explicitly from the router layer.
    
    Type Parameters:
        ModelType: SQLAlchemy model class
        CreateSchemaType: Pydantic schema for creating records
        UpdateSchemaType: Pydantic schema for updating records
    """
    
    def __init__(self, model: Type[ModelType]):
        """
        Initialize CRUD object with model class.
        
        Args:
            model: SQLAlchemy model class
        """
        self.model = model
    
    def get(self, db: Session, id: int, tenant_id: int) -> Optional[ModelType]:
        """
        Retrieve a single record by ID with tenant filtering.
        
        Args:
            db: Database session
            id: Record ID
            tenant_id: Tenant ID for isolation
            
        Returns:
            Model instance or None if not found or doesn't belong to tenant
        """
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.tenant_id == tenant_id
        )
        result = db.execute(stmt)
        return result.scalar_one_or_none()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        tenant_id: int
    ) -> List[ModelType]:
        """
        Retrieve multiple records with pagination and tenant filtering.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Tenant ID for isolation
            
        Returns:
            List of model instances belonging to tenant
        """
        stmt = select(self.model).where(
            self.model.tenant_id == tenant_id
        ).offset(skip).limit(limit)
        result = db.execute(stmt)
        return list(result.scalars().all())
    
    def create(
        self,
        db: Session,
        *,
        obj_in: CreateSchemaType,
        tenant_id: int
    ) -> ModelType:
        """
        Create a new record with tenant association.
        
        Args:
            db: Database session
            obj_in: Pydantic schema with creation data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Created model instance
        """
        obj_data = obj_in.model_dump()
        db_obj = self.model(tenant_id=tenant_id, **obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | Dict[str, Any]
    ) -> ModelType:
        """
        Update an existing record.
        
        Note: This method assumes the db_obj was already retrieved using
        get() or similar method, which ensures tenant isolation.
        
        Args:
            db: Database session
            db_obj: Existing model instance to update
            obj_in: Pydantic schema or dict with update data
            
        Returns:
            Updated model instance
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, id: int, tenant_id: int) -> Optional[ModelType]:
        """
        Delete a record by ID with tenant filtering.
        
        Args:
            db: Database session
            id: Record ID to delete
            tenant_id: Tenant ID for isolation
            
        Returns:
            Deleted model instance or None if not found
        """
        obj = self.get(db=db, id=id, tenant_id=tenant_id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
