from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Form
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, date as date_type
import math

from app.database import get_db
from app.core.tenant_context import get_tenant_id
from app.core.logging_config import logger
from app.schemas.bulk_upload import (
    BulkUploadResponse,
    BulkGeocodeRequest,
    BulkGeocodeResponse,
    BulkImportRequest,
    BulkImportResponse,
    GeocodedRow,
    ColumnMetadata
)
from app.schemas.job import JobCreate, Location
from app.services.bulk_upload import bulk_upload_service
from app.services.geocoding import geocoding_service
from app.services.user_mapping import user_mapping_service
from app.services.job import job_service


router = APIRouter()


@router.post("/upload", response_model=BulkUploadResponse)
async def upload_bulk_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Step 1: Upload and parse CSV/Excel file, detect columns
    
    Returns column metadata with intelligent mapping suggestions
    and user's saved default mapping if available.
    """
    try:
        logger.info(f"Processing bulk upload for tenant={tenant_id}, file={file.filename}")
        
        # Parse the file
        df = await bulk_upload_service.parse_file(file)
        
        # Get user's saved default mapping if exists
        saved_mapping_obj = user_mapping_service.get_default_mapping(
            db=db,
            tenant_id=tenant_id,
            entity_type="job"
        )
        saved_mapping = saved_mapping_obj.mapping_config if saved_mapping_obj else None
        
        # Detect columns with intelligent mapping
        columns = bulk_upload_service.detect_columns(
            df=df,
            entity_type="job",
            saved_mapping=saved_mapping
        )
        
        # Extract sample data for preview
        sample_data = bulk_upload_service.extract_sample_data(df, sample_size=5)
        
        return BulkUploadResponse(
            columns=columns,
            sample_data=sample_data,
            total_rows=len(df),
            success=True
        )
        
    except ValueError as e:
        logger.error(f"File parsing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in bulk upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )


@router.post("/geocode", response_model=BulkGeocodeResponse)
async def geocode_bulk_data(
    file: UploadFile = File(...),
    column_mapping: str = Form(...),  # Sent as JSON string
    default_scheduled_date: str = Form(None),  # Optional default date
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Step 2: Geocode addresses from mapped data
    
    Applies column mapping to raw data, geocodes addresses,
    and detects duplicates.
    """
    try:
        import json
        
        # Parse column_mapping from JSON string
        mapping_dict = json.loads(column_mapping)
        
        logger.info(f"Geocoding bulk data for tenant={tenant_id}")
        
        # Re-parse the file (user may have edited mappings)
        df = await bulk_upload_service.parse_file(file)
        
        # Apply column mapping to get structured data
        mapped_data = bulk_upload_service.map_data_to_schema(
            df=df,
            column_mapping=mapping_dict,
            default_scheduled_date=default_scheduled_date
        )
        
        # Check if address column is mapped
        if "address_formatted" not in mapping_dict or not mapping_dict["address_formatted"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="There has to be at least one column defining location (address)"
            )
        
        # Geocode all addresses
        addresses = [row.get("address_formatted", "") for row in mapped_data]
        geocode_results = geocoding_service.batch_geocode(addresses)
        
        # Build geocoded rows
        geocoded_rows: List[GeocodedRow] = []
        for idx, (data_row, geocode_result) in enumerate(zip(mapped_data, geocode_results, strict=True)):
            geocoded_rows.append(GeocodedRow(
                original_data=data_row,
                geocode_result=geocode_result,
                is_duplicate=False
            ))
        
        # Detect duplicates
        geocoded_rows = _detect_duplicates(geocoded_rows)
        
        # Count errors, warnings, duplicates
        errors_count = sum(1 for row in geocoded_rows if row.geocode_result.error)
        warnings_count = sum(1 for row in geocoded_rows if row.geocode_result.warning)
        duplicates_count = sum(1 for row in geocoded_rows if row.is_duplicate)
        
        logger.info(f"Geocoding complete: {len(geocoded_rows)} rows, "
                   f"{errors_count} errors, {warnings_count} warnings, {duplicates_count} duplicates")
        
        return BulkGeocodeResponse(
            data=geocoded_rows,
            errors_count=errors_count,
            warnings_count=warnings_count,
            duplicates_count=duplicates_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Geocoding failed: {str(e)}"
        )


@router.post("/import", response_model=BulkImportResponse)
def import_bulk_jobs(
    request: BulkImportRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Step 3: Import validated jobs into database
    
    Also saves user's column mapping as default if requested.
    """
    try:
        logger.info(f"Importing {len(request.jobs)} jobs for tenant={tenant_id}")
        
        # Bulk create jobs
        result = job_service.bulk_create_jobs(
            db=db,
            jobs_data=request.jobs,
            tenant_id=tenant_id
        )
        
        # Save user's mapping if requested
        if request.save_mapping and request.mapping_config:
            user_mapping_service.save_mapping(
                db=db,
                tenant_id=tenant_id,
                entity_type="job",
                mapping_config=request.mapping_config
            )
            logger.info(f"Saved default mapping for tenant={tenant_id}")
        
        return BulkImportResponse(
            created=result['created'],
            failed=result['failed'],
            errors=result.get('errors', [])
        )
        
    except Exception as e:
        logger.error(f"Import error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


def _detect_duplicates(rows: List[GeocodedRow]) -> List[GeocodedRow]:
    """
    Detect duplicate addresses in geocoded rows
    
    Duplicates are detected by:
    - Exact address match (case-insensitive)
    - Similar lat/lng coordinates (within 10 meters)
    """
    seen_addresses = {}
    seen_locations = {}
    
    for row in rows:
        geocode = row.geocode_result
        
        # Skip rows with geocoding errors
        if geocode.error or not geocode.lat or not geocode.lng:
            continue
        
        # Check for exact address duplicates
        address_key = geocode.address.lower().strip()
        if address_key in seen_addresses:
            row.is_duplicate = True
            continue
        
        # Check for nearby location duplicates (within ~10 meters)
        location_key = (round(geocode.lat, 4), round(geocode.lng, 4))  # ~11m precision
        if location_key in seen_locations:
            # Calculate exact distance
            prev_row = seen_locations[location_key]
            distance = _calculate_distance(
                geocode.lat, geocode.lng,
                prev_row.geocode_result.lat, prev_row.geocode_result.lng
            )
            if distance < 10:  # Less than 10 meters
                row.is_duplicate = True
                continue
        
        # Mark as seen
        seen_addresses[address_key] = row
        seen_locations[location_key] = row
    
    return rows


def _calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two coordinates in meters using Haversine formula
    """
    R = 6371000  # Earth radius in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c
