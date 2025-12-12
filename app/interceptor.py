import re
import csv
import os
from datetime import datetime
from mitmproxy import http
from app.util import get_location

CSV_FILE = "captures.csv"
notify_fn = None

COORD_PATTERNS = [
    # Object format: {lat: X, lng: Y} or {"lat": X, "lng": Y}
    r'\{\s*["\']lat["\']\s*:\s*([+-]?\d+\.?\d*)\s*,\s*["\']lng["\']\s*:\s*([+-]?\d+\.?\d*)\s*\}',
    # Object format: {lng: X, lat: Y} or {"lng": X, "lat": Y}
    r'\{\s*["\']lng["\']\s*:\s*([+-]?\d+\.?\d*)\s*,\s*["\']lat["\']\s*:\s*([+-]?\d+\.?\d*)\s*\}',
    # Simple array: [X, Y] where X and Y are valid coordinates
    r'\[([+-]?(?:90(?:\.0+)?|[1-8]?\d(?:\.\d+)?|0(?:\.\d+)?)),\s*([+-]?(?:180(?:\.0+)?|1[0-7]\d(?:\.\d+)?|[1-9]?\d(?:\.\d+)?|0(?:\.\d+)?))\]',
    # 4-element array with nulls/values: [..., lat, lng] - matches pattern like [null,null,34.66,135.43]
    r'\[[^\]]*?,\s*[^\]]*?,\s*([+-]?\d+\.\d+),\s*([+-]?\d+\.\d+)\]',
    # coords = [X, Y] format
    r'coords\s*=\s*\[\s*([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)\s*\]',
    # Generic two-number pattern in array (fallback, matches any two floats)
    r'\[([+-]?\d+\.\d+),\s*([+-]?\d+\.\d+)\]'
]


class Interceptor:
    def response(self, flow: http.HTTPFlow):
        # Only intercept GeoPhotoService.GetMetadata requests to reduce false positives/overhead
        req = flow.request
        host = (req.host or "").lower()
        path = (req.path or "").lower()
        if host != "maps.googleapis.com":
            return
        if "/maps/api/js/geophotoservice.getmetadata" not in path:
            return

        # Only process responses with content
        if not flow.response or not flow.response.content:
            return
        # Light content-type check
        ctype = (flow.response.headers.get("content-type") or "").lower()
        if "javascript" not in ctype and "json" not in ctype:
            return

        # Try to get text content (limit size to avoid heavy processing)
        try:
            body = flow.response.get_text()
        except Exception:
            return
        if not body or len(body) == 0:
            return
        if len(body) > 500_000:  # skip very large payloads
            return

        lat, lng = None, None
        for idx, p in enumerate(COORD_PATTERNS):
            m = re.search(p, body)
            if m:
                a, b = m.groups()
                try:
                    a, b = float(a), float(b)
                    
                    # Determine order based on pattern
                    if idx == 1:
                        # Pattern 1 is lng, lat format
                        candidate_lng, candidate_lat = a, b
                    else:
                        # Patterns 0, 2, 3, 4, 5 are lat, lng format
                        candidate_lat, candidate_lng = a, b
                    
                    # Strict validation: lat must be in [-90, 90], lng in [-180, 180]
                    # Also exclude obvious non-coordinates (small integers like 8.0, 9.0)
                    lat_is_small_int = abs(candidate_lat) < 10 and candidate_lat == int(candidate_lat)
                    lng_is_small_int = abs(candidate_lng) < 10 and candidate_lng == int(candidate_lng)
                    
                    if (-90 <= candidate_lat <= 90 and 
                        -180 <= candidate_lng <= 180 and
                        # Exclude small integers that are likely not coordinates
                        not (lat_is_small_int and lng_is_small_int)):
                        lat, lng = candidate_lat, candidate_lng
                        break
                except (ValueError, OverflowError):
                    continue

        if lat is None or lng is None:
            return
        
        # Additional validation: coordinates should have reasonable precision
        # (exclude very round numbers that might be false positives)
        if abs(lat) < 1 and abs(lng) < 1:
            # Very small coordinates, be more strict
            if lat == int(lat) and lng == int(lng):
                return  # Likely false positive

        country, city = get_location(lat, lng)
        url = flow.request.pretty_url
        ts = datetime.now().isoformat()

        # Save CSV in project root (parent of app directory)
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), CSV_FILE)
        new = not os.path.exists(path)

        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "url", "lat", "lng", "country", "city"])
            w.writerow([ts, url, lat, lng, country, city])

        if notify_fn:
            notify_fn(lat, lng, country, city)

        print(f"MATCH|{url}|{lat}|{lng}|{country}|{city}", flush=True)


addons = [Interceptor()]
