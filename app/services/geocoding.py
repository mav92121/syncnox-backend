import googlemaps
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.core.logging_config import logger
from app.schemas.bulk_upload import GeocodeResult


class GeocodingService:
    """Google Maps Geocoding API integration service"""
    
    def __init__(self):
        if settings.GOOGLE_MAPS_API_KEY:
            self.client = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
            logger.info("Google Maps geocoding client initialized")
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
    
    def batch_geocode(self, addresses: List[str]) -> List[GeocodeResult]:
        """
        Geocode multiple addresses
        
        Args:
            addresses: List of address strings
            
        Returns:
            List of GeocodeResult objects
        """
        results = []
        for idx, address in enumerate(addresses):
            logger.info(f"Geocoding address {idx + 1}/{len(addresses)}")
            result = self.geocode_address(address)
            results.append(result)
        
        return results
    
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
