import pandas as pd
import io
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
from difflib import SequenceMatcher
from app.schemas.bulk_upload import ColumnMetadata
from app.core.logging_config import logger


class BulkUploadService:
    """Service for parsing and processing bulk upload files"""
    
    # Define all available Job model fields
    # Maps field identifier to user-friendly description
    JOB_FIELDS = {
        "address_formatted": "Delivery Address *",
        "first_name": "Customer First Name",
        "last_name": "Customer Last Name",
        "email": "Customer Email",
        "phone_number": "Phone Number",
        "business_name": "Business/Company Name",
        "time_window_start": "Time Window Start",
        "time_window_end": "Time Window End",
        "service_duration": "Service Duration (minutes)",
        "additional_notes": "Additional Notes",
        "customer_preferences": "Customer Preferences",
        "priority_level": "Priority Level",
        "job_type": "Job Type",
        "scheduled_date": "Scheduled Date",
    }
    
    # Column patterns for intelligent auto-mapping
    # Maps Job field to possible Excel column names
    AUTO_MAPPING_PATTERNS = {
        "address_formatted": ["address", "location", "street", "full address", "delivery address", "main address"],
        "first_name": ["first name", "firstname", "fname", "customer first name", "name"],
        "last_name": ["last name", "lastname", "lname", "surname", "customer last name"],
        "email": ["email", "e-mail", "mail", "email address", "customer email"],
        "phone_number": ["phone", "telephone", "mobile", "contact", "phone number", "cell", "ph"],
        "business_name": ["business", "company", "business name", "company name", "organization"],
        "time_window_start": ["time window start", "start time", "time start", "earliest", "from", "start", "time from"],
        "time_window_end": ["time window end", "end time", "time end", "latest", "to", "until", "time to"],
        "service_duration": ["duration", "service time", "service duration"],
        "additional_notes": ["notes", "comments", "remarks", "additional notes", "instructions"],
        "customer_preferences": ["preferences", "customer preferences", "special instructions"],
        "priority_level": ["priority", "priority level", "urgency"],
        "job_type": ["type", "job type", "service type", "order type"],
        "scheduled_date": ["date", "scheduled date", "delivery date", "service date"],
    }
    
    async def parse_file(self, file: UploadFile) -> pd.DataFrame:
        """
        Parse uploaded CSV or Excel file into pandas DataFrame
        
        Args:
            file: Uploaded file (CSV or Excel)
            
        Returns:
            DataFrame with parsed data
        """
        content = await file.read()
        
        # Determine file type based on extension
        filename = (file.filename or "").lower()
        if not filename:
            raise ValueError("No filename provided")
        
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(content))
            elif filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(content))
            else:
                raise ValueError(f"Unsupported file format: {filename}")
            
            logger.info(f"Parsed file '{file.filename}': {len(df)} rows, {len(df.columns)} columns")
            return df
            
        except Exception as e:
            logger.error(f"Error parsing file '{file.filename}': {str(e)}")
            raise ValueError(f"Failed to parse file: {str(e)}")
    
    def detect_columns(
        self, 
        df: pd.DataFrame, 
        entity_type: str = "job",
        saved_mapping: Optional[Dict[str, str]] = None
    ) -> List[ColumnMetadata]:
        """
        Return ALL Job fields with auto-detected Excel column mappings
        
        Args:
            df: DataFrame with uploaded data
            entity_type: Type of entity (e.g., "job")
            saved_mapping: User's saved mapping if available {job_field: excel_column}
            
        Returns:
            List of ColumnMetadata - one for each Job field
        """
        columns_metadata = []
        excel_columns = list(df.columns)
        used_excel_columns = set()  # Track already-mapped Excel columns
        
        # PASS 1: Apply saved mappings first
        saved_mappings_applied = {}
        if saved_mapping:
            for job_field, excel_col in saved_mapping.items():
                if excel_col and excel_col in excel_columns:
                    saved_mappings_applied[job_field] = excel_col
                    used_excel_columns.add(excel_col)
                    logger.info(f"Applied saved mapping: '{job_field}' -> Excel:'{excel_col}'")
        
        # PASS 2: Auto-detect for remaining fields
        # Build all potential matches first
        potential_matches = []  # List of (job_field, excel_col, score)
        
        for job_field in self.JOB_FIELDS.keys():
            if job_field in saved_mappings_applied:
                continue  # Skip already mapped fields
                
            if job_field not in self.AUTO_MAPPING_PATTERNS:
                continue
                
            patterns = self.AUTO_MAPPING_PATTERNS[job_field]
            
            for excel_col in excel_columns:
                if excel_col in used_excel_columns:
                    continue  # Skip already-used columns
                    
                excel_col_lower = excel_col.lower().strip()
                best_pattern_score = 0.0
                
                for pattern in patterns:
                    # Calculate similarity score
                    score = SequenceMatcher(None, excel_col_lower, pattern.lower()).ratio()
                    
                    # Boost score if pattern is contained in Excel column
                    if pattern.lower() in excel_col_lower or excel_col_lower in pattern.lower():
                        score = max(score, 0.85)
                    
                    best_pattern_score = max(best_pattern_score, score)
                
                if best_pattern_score >= 0.7:
                    potential_matches.append((job_field, excel_col, best_pattern_score))
        
        # Sort by score (highest first) and greedily assign
        potential_matches.sort(key=lambda x: x[2], reverse=True)
        auto_detected_mappings = {}
        
        for job_field, excel_col, score in potential_matches:
            if job_field not in auto_detected_mappings and excel_col not in used_excel_columns:
                auto_detected_mappings[job_field] = excel_col
                used_excel_columns.add(excel_col)
                logger.info(f"Auto-detected: Job field '{job_field}' -> Excel column '{excel_col}' (score: {score:.2f})")
        
        # PASS 3: Build final metadata for ALL job fields
        for idx, (job_field, description) in enumerate(self.JOB_FIELDS.items()):
            mapped_excel_column = None
            sample_value = ""
            
            # Check saved mapping first, then auto-detected
            if job_field in saved_mappings_applied:
                mapped_excel_column = saved_mappings_applied[job_field]
            elif job_field in auto_detected_mappings:
                mapped_excel_column = auto_detected_mappings[job_field]
            
            # Get sample value from mapped column
            if mapped_excel_column and mapped_excel_column in df.columns:
                for val in df[mapped_excel_column]:
                    if pd.notna(val) and str(val).strip():
                        sample_value = str(val)[:50]
                        break
            
            columns_metadata.append(ColumnMetadata(
                description=description,  # Job field description
                identifier=job_field,  # Job field identifier
                index=idx,
                mapping=mapped_excel_column,  # Mapped Excel column (or None)
                sample_value=sample_value
            ))
        
        return columns_metadata
    
    
    def extract_sample_data(self, df: pd.DataFrame, sample_size: int = 5) -> List[Dict[str, Any]]:
        """
        Extract sample rows for preview
        
        Args:
            df: DataFrame
            sample_size: Number of sample rows
            
        Returns:
            List of row dictionaries
        """
        sample_df = df.head(sample_size)
        return sample_df.to_dict('records')
    
    def map_data_to_schema(
        self,
        df: pd.DataFrame,
        column_mapping: Dict[str, str],
        default_scheduled_date: str = None
    ) -> List[Dict[str, Any]]:
        """
        Map raw data to internal schema using column mapping
        
        Args:
            df: DataFrame with raw data
            column_mapping: {job_field: excel_column_name}
            default_scheduled_date: Optional default date to apply if Excel doesn't have one
            
        Returns:
            List of mapped row dictionaries
        """
        mapped_data = []
        
        for idx, row in df.iterrows():
            mapped_row = {}
            for job_field, excel_column in column_mapping.items():
                if excel_column and excel_column in df.columns:
                    value = row[excel_column]
                    # Only include non-null values
                    if pd.notna(value):
                        # Handle date fields specially
                        if job_field == 'scheduled_date':
                            # Convert to datetime if it's not already
                            if isinstance(value, str):
                                # Parse string date
                                try:
                                    dt = pd.to_datetime(value)
                                    formatted_date = dt.strftime('%Y-%m-%d')
                                    logger.info(f"Parsed string date '{value}' to '{formatted_date}'")
                                    mapped_row[job_field] = formatted_date
                                except Exception as e:
                                    logger.warning(f"Could not parse date: {value}, error: {e}")
                                    mapped_row[job_field] = str(value).strip()
                            else:
                                # Handle pandas Timestamp or datetime
                                formatted_date = pd.to_datetime(value).strftime('%Y-%m-%d')
                                logger.info(f"Converted timestamp/datetime {value} to '{formatted_date}'")
                                mapped_row[job_field] = formatted_date
                        else:
                            # Convert to string to handle Excel number formatting
                            # (e.g., phone numbers stored as integers)
                            mapped_row[job_field] = str(value).strip()
            
            # Apply default scheduled date if not present in Excel and default is provided
            # Excel date takes priority over default date
            if 'scheduled_date' not in mapped_row and default_scheduled_date:
                mapped_row['scheduled_date'] = default_scheduled_date
                logger.info(f"Applied default scheduled_date: {default_scheduled_date}")
            
            mapped_data.append(mapped_row)
        
        return mapped_data
    
    def validate_row_data(self, row_data: Dict[str, Any]) -> List[str]:
        """
        Validate row data against JobCreate field types.
        Returns list of user-friendly validation error messages.
        
        Validates:
        - service_duration: Must be a valid integer (minutes)
        - time_window_start/end: Must be valid time format (HH:MM)
        - scheduled_date: Must be a valid date format
        - email: Must be a valid email format
        - priority_level: Must be one of the valid enum values
        - job_type: Must be one of the valid enum values
        """
        import re
        from email_validator import validate_email, EmailNotValidError
        
        errors = []
        
        # Validate service_duration (must be integer representing minutes)
        if 'service_duration' in row_data and row_data['service_duration']:
            value = row_data['service_duration']
            try:
                int_value = int(value)
                if int_value <= 0:
                    errors.append("Service Duration must be a positive number")
            except (ValueError, TypeError):
                errors.append(f"Service Duration must be a valid number in minutes, got '{value}'")
        
        # Get time window values
        time_start = row_data.get('time_window_start')
        time_end = row_data.get('time_window_end')
        time_pattern = r'^([01]?[0-9]|2[0-3]):([0-5][0-9])(:[0-5][0-9])?$'
        
        time_start_valid = False
        time_end_valid = False
        
        # Validate time_window_start (HH:MM or HH:MM:SS format)
        if time_start:
            value = str(time_start).strip()
            if not re.match(time_pattern, value):
                errors.append(f"Time Window Start must be in HH:MM format, got '{value}'")
            else:
                time_start_valid = True
        
        # Validate time_window_end (HH:MM or HH:MM:SS format)
        if time_end:
            value = str(time_end).strip()
            if not re.match(time_pattern, value):
                errors.append(f"Time Window End must be in HH:MM format, got '{value}'")
            else:
                time_end_valid = True
        
        # Cross-validation: If start exists, end must also exist
        if time_start and not time_end:
            errors.append("Time Window End is required when Time Window Start is provided")
        
        # Cross-validation: Start must be before End
        if time_start_valid and time_end_valid:
            start_str = str(time_start).strip()
            end_str = str(time_end).strip()
            # Normalize to HH:MM for comparison
            start_parts = start_str.split(':')
            end_parts = end_str.split(':')
            start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
            end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
            if start_minutes >= end_minutes:
                errors.append(f"Time Window Start ({start_str}) must be before Time Window End ({end_str})")
        
        # Validate scheduled_date (YYYY-MM-DD format)
        if 'scheduled_date' in row_data and row_data['scheduled_date']:
            value = str(row_data['scheduled_date']).strip()
            date_pattern = r'^\d{4}-\d{2}-\d{2}$'
            if not re.match(date_pattern, value):
                errors.append(f"Scheduled Date must be in YYYY-MM-DD format, got '{value}'")
        
        # Validate email format
        if 'email' in row_data and row_data['email']:
            value = str(row_data['email']).strip()
            try:
                validate_email(value, check_deliverability=False)
            except EmailNotValidError:
                errors.append(f"Email '{value}' is not a valid email address")
        
        # Validate priority_level enum values
        valid_priority_levels = ['low', 'medium', 'high', 'urgent']
        if 'priority_level' in row_data and row_data['priority_level']:
            value = str(row_data['priority_level']).strip().lower()
            if value not in valid_priority_levels:
                errors.append(f"Priority Level must be Low, Medium, High, or Urgent, got '{value}'")
        
        # Validate job_type enum values  
        valid_job_types = ['delivery', 'pickup', 'service', 'installation', 'inspection']
        if 'job_type' in row_data and row_data['job_type']:
            value = str(row_data['job_type']).strip().lower()
            if value not in valid_job_types:
                errors.append(f"Job Type must be Delivery, Pickup, Service, Installation, or Inspection, got '{value}'")
        
        return errors


bulk_upload_service = BulkUploadService()
