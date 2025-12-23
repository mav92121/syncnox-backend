import googlemaps
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.core.logging_config import logger
from app.schemas.bulk_upload import GeocodeResult


class GeocodingService:
    """Google Maps Geocoding API integration service"""
    
    def __init__(self):
        if settings.GOOGLE_MAPS_API_KEY:
            # Initialize with higher rate limit for faster batch processing
            # Google allows up to 100 QPS with standard API key
            self.client = googlemaps.Client(
                key=settings.GOOGLE_MAPS_API_KEY,
                queries_per_second=100,  # Increased from default 60
                queries_per_minute=None  # Disable per-minute limit
            )
            logger.info("Google Maps geocoding client initialized with 100 QPS limit")
        else:
            self.client = None
            logger.warning("Google Maps API key not configured - geocoding disabled")
    
    def geocode_address(self, address: str) -> GeocodeResult:
        """
        Geocode a single address using Google Maps API
        
        Args:
            address: Address string to geocode
            
        Returns:
            GeocodeResult with lat/lng or error message
        """
        if not self.client:
            return GeocodeResult(
                address=address,
                error="Geocoding service not configured"
            )
        
        if not address or not address.strip():
            return GeocodeResult(
                address=address,
                error="Empty address provided"
            )
        
        try:
            result = self.client.geocode(address)
            
            if not result:
                return GeocodeResult(
                    address=address,
                    error="Invalid address - could not be geocoded",
                    quality_score=0.0
                )
            
            # Get the first result (best match)
            location_data = result[0]
            geometry = location_data.get('geometry', {})
            location = geometry.get('location', {})
            
            # Extract coordinates
            lat = location.get('lat')
            lng = location.get('lng')
            
            # If no coordinates returned, set error
            if lat is None or lng is None:
                return GeocodeResult(
                    address=address,
                    error="Invalid address - no coordinates found",
                    quality_score=0.0
                )
            
            # Validate coordinates are within valid ranges
            if not self.validate_location(lat, lng):
                return GeocodeResult(
                    address=address,
                    error=f"Invalid coordinates - lat={lat}, lng={lng} out of range",
                    quality_score=0.0
                )
            
            # Determine quality score based on location type
            location_type = geometry.get('location_type', '')
            quality_score = self._calculate_quality_score(location_type)
            
            # Don't set warnings - all valid geocoded addresses are acceptable
            return GeocodeResult(
                address=address,
                lat=lat,
                lng=lng,
                formatted_address=location_data.get('formatted_address'),
                quality_score=quality_score,
                warning=None
            )
            
        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Google Maps API error for address '{address}': {str(e)}")
            return GeocodeResult(
                address=address,
                error=f"API error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Geocoding error for address '{address}': {str(e)}")
            return GeocodeResult(
                address=address,
                error=f"Geocoding failed: {str(e)}"
            )
    
    def batch_geocode(self, addresses: List[str], max_workers: int = 10) -> List[GeocodeResult]:
        """
        Geocode multiple addresses concurrently for better performance
        
        Args:
            addresses: List of address strings
            max_workers: Maximum number of concurrent workers (default: 10)
            
        Returns:
            List of GeocodeResult objects in same order as input addresses
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if not addresses:
            return []
        
        logger.info(f"Starting batch geocoding for {len(addresses)} addresses with {max_workers} workers")
        
        # Use ThreadPoolExecutor for concurrent geocoding
        results_dict = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all geocoding tasks
            future_to_index = {
                executor.submit(self.geocode_address, address): idx 
                for idx, address in enumerate(addresses)
            }
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    result = future.result()
                    results_dict[idx] = result
                    completed += 1
                    
                    # Log progress every 10 addresses
                    if completed % 10 == 0 or completed == len(addresses):
                        logger.info(f"Geocoded {completed}/{len(addresses)} addresses")
                except Exception as e:
                    logger.error(f"Error geocoding address at index {idx}: {str(e)}")
                    results_dict[idx] = GeocodeResult(
                        address=addresses[idx],
                        error=f"Geocoding failed: {str(e)}"
                    )
        
        # Return results in original order
        return [results_dict[i] for i in range(len(addresses))]
    
    def _calculate_quality_score(self, location_type: str) -> float:
        """
        Calculate quality score based on Google's location type
        
        Args:
            location_type: Google Maps location type
            
        Returns:
            Quality score from 0.0 to 1.0
        """
        quality_map = {
            'ROOFTOP': 1.0,  # Most precise
            'RANGE_INTERPOLATED': 0.8,
            'GEOMETRIC_CENTER': 0.5,
            'APPROXIMATE': 0.3
        }
        return quality_map.get(location_type, 0.5)
    
    def validate_location(self, lat: float, lng: float) -> bool:
        """
        Validate that lat/lng are within valid ranges
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            True if valid, False otherwise
        """
        return -90 <= lat <= 90 and -180 <= lng <= 180


geocoding_service = GeocodingService()
