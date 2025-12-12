import reverse_geocoder as rg
import pycountry


def _country_name_from_code(code: str) -> str:
    """Return a human-readable country name from a 2-letter code."""
    if not code:
        return "UNKNOWN"
    try:
        country = pycountry.countries.get(alpha_2=code.upper())
        return country.name if country else code
    except Exception:
        return code


def get_location(lat: float, lng: float):
    try:
        r = rg.search((lat, lng))
        if r and len(r) > 0:
            code = r[0].get("cc", "UNKNOWN")
            city = r[0].get("name", "UNKNOWN")
            return _country_name_from_code(code), city
        return "UNKNOWN", "UNKNOWN"
    except Exception:
        return "ERROR", "ERROR"
