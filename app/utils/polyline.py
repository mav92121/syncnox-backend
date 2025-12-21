"""
Polyline encoding utility.
Implements the Encoded Polyline Algorithm Format.
ref: https://developers.google.com/maps/documentation/utilities/polylinealgorithm
"""
from typing import List, Tuple

def encode_polyline(points: List[Tuple[float, float]]) -> str:
    """
    Encode a list of (lat, lon) tuples into a polyline string.
    
    Args:
        points: List of (latitude, longitude) tuples.
        
    Returns:
        Encoded polyline string.
    """
    result = []
    prev_lat = 0
    prev_lon = 0
    
    for lat, lon in points:
        lat_e5 = int(round(lat * 1e5))
        lon_e5 = int(round(lon * 1e5))
        
        d_lat = lat_e5 - prev_lat
        d_lon = lon_e5 - prev_lon
        
        prev_lat = lat_e5
        prev_lon = lon_e5
        
        result.append(_encode_value(d_lat))
        result.append(_encode_value(d_lon))
        
    return "".join(result)

def _encode_value(value: int) -> str:
    """Encode a single value."""
    value = value << 1
    if value < 0:
        value = ~value
        
    result = []
    while value >= 0x20:
        result.append(chr((0x20 | (value & 0x1f)) + 63))
        value >>= 5
    result.append(chr(value + 63))
    
    return "".join(result)
