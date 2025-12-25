from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.schemas.job import JobCreate


class ColumnMetadata(BaseModel):
    """Metadata for a detected column in uploaded file"""
    description: str  # User-friendly description
    identifier: str  # Internal field name (e.g., "first_name")
    index: int  # Column index in the file
    mapping: Optional[str] = None  # Suggested/saved mapping
    sample_value: str  # Sample value from the data


class BulkUploadResponse(BaseModel):
    """Response from initial file upload"""
    columns: List[ColumnMetadata]
    sample_data: List[Dict[str, Any]]  # Sample rows for preview
    total_rows: int
    success: bool


class BulkGeocodeRequest(BaseModel):
    """Request to geocode mapped data"""
    column_mapping: Dict[str, str]  # {identifier: excel_column_name}
    data: List[Dict[str, Any]]  # Raw data rows
    scheduled_date: Optional[str] = None  # Optional: for all jobs


class GeocodeResult(BaseModel):
    """Result of geocoding an address"""
    address: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    formatted_address: Optional[str] = None
    quality_score: Optional[float] = None  # 0-1, confidence in geocoding
    error: Optional[str] = None
    warning: Optional[str] = None


class GeocodedRow(BaseModel):
    """A row with geocoding applied"""
    original_data: Dict[str, Any]
    geocode_result: GeocodeResult
    is_duplicate: bool = False
    validation_errors: List[str] = []  # Field-level validation errors


class BulkGeocodeResponse(BaseModel):
    """Response from geocoding operation"""
    data: List[GeocodedRow]
    errors_count: int
    warnings_count: int
    duplicates_count: int
    validation_errors_count: int  # Count of rows with validation errors


class BulkImportRequest(BaseModel):
    """Request to import jobs"""
    jobs: List[JobCreate]
    save_mapping: bool = False
    mapping_config: Optional[Dict[str, str]] = None  # {identifier: excel_column}


class BulkImportResponse(BaseModel):
    """Response from bulk import"""
    created: int
    failed: int
    errors: List[Dict[str, str]] = []  # [{row_index, error_message}]


class UserMappingCreate(BaseModel):
    """Request to save user's default mapping"""
    entity_type: str
    mapping_config: Dict[str, str]


class UserMappingResponse(BaseModel):
    """Response with user's saved mapping"""
    id: int
    tenant_id: int
    entity_type: str
    mapping_config: Dict[str, str]
    
    class Config:
        from_attributes = True
