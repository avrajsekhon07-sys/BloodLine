from math import asin, cos, radians, sin, sqrt


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Returns None if any coordinate is missing —
    we never invent locations."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(6371.0 * 2 * asin(sqrt(a)), 1)
