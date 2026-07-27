"""Best-effort geocoding for the student's stated area/city, used to compute
distance-based location fit against known campus coordinates. Students only
ever name a neighborhood ("Gulshan-e-Iqbal") or city, never coordinates, so
this turns that text into an approximate lat/long."""
from __future__ import annotations

import math
import re
from functools import lru_cache

import requests

# Common Karachi localities a student is likely to name. Covers the typical
# case with no network call; Nominatim (OpenStreetMap, free/no-key) is a
# fallback for anything not listed here.
KARACHI_AREA_COORDS: dict[str, tuple[float, float]] = {
    "clifton": (24.8138, 67.0299),
    "defence": (24.8100, 67.0700),
    "dha": (24.8100, 67.0700),
    "gulshan-e-iqbal": (24.9208, 67.0994),
    "gulshan e iqbal": (24.9208, 67.0994),
    "gulistan-e-johar": (24.9152, 67.1245),
    "gulistan e johar": (24.9152, 67.1245),
    "north nazimabad": (24.9370, 67.0428),
    "nazimabad": (24.9089, 67.0362),
    "federal b area": (24.9298, 67.0654),
    "fb area": (24.9298, 67.0654),
    "korangi": (24.8380, 67.1257),
    "malir": (24.8930, 67.2078),
    "malir cantt": (24.8981, 67.2299),
    "landhi": (24.8390, 67.1875),
    "shah faisal colony": (24.8611, 67.1848),
    "orangi town": (24.9686, 66.9948),
    "saddar": (24.8546, 67.0104),
    "surjani town": (25.0187, 67.0392),
    "gadap town": (25.0900, 67.2100),
    "pechs": (24.8735, 67.0670),
    "bahadurabad": (24.8735, 67.0603),
    "tariq road": (24.8697, 67.0596),
    "gulberg": (24.9271, 67.0654),
    "liaquatabad": (24.9037, 67.0308),
    "lyari": (24.8735, 66.9930),
    "kemari": (24.8438, 66.9890),
    "scheme 33": (24.9722, 67.1447),
    "gulshan-e-maymar": (24.9964, 67.1082),
    "north karachi": (24.9836, 67.0562),
}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _lookup_local(area_text: str) -> tuple[float, float] | None:
    """Exact match first; otherwise a token-set match (not raw substring) so
    a short key like "dha" can't accidentally match inside an unrelated word.
    When multiple gazetteer entries match, the most specific one (most
    tokens) wins, e.g. "malir cantt" over the plainer "malir"."""
    key = area_text.strip().lower()
    if key in KARACHI_AREA_COORDS:
        return KARACHI_AREA_COORDS[key]
    key_tokens = _tokenize(key)
    if not key_tokens:
        return None
    candidates = []
    for name, coords in KARACHI_AREA_COORDS.items():
        name_tokens = _tokenize(name)
        if name_tokens and (name_tokens <= key_tokens or key_tokens <= name_tokens):
            candidates.append((len(name_tokens), coords))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


@lru_cache(maxsize=256)
def geocode_area(area_text: str) -> tuple[float, float] | None:
    """Local gazetteer first, then a single Nominatim fallback call. Returns
    None (never raises) if nothing is found or the network call fails - a
    missing distance should degrade to 'unknown', not break the chat turn."""
    if not area_text or not area_text.strip():
        return None
    local = _lookup_local(area_text)
    if local:
        return local
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{area_text}, Pakistan", "format": "json", "limit": 1},
            headers={"User-Agent": "UniMate-university-recommender/1.0 (educational project)"},
            timeout=5,
        )
        response.raise_for_status()
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        return None
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
