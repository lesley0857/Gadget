# logistics/nigeria_cities.py
# Pure-Python lookup table for Nigerian cities and state centroids.
# Used for vendor address geocoding and customer location resolution at checkout.
# No external API required.

NIGERIA_CITIES = {
    # FCT / Abuja
    "abuja": (9.0579, 7.4951),
    "gwagwalada": (8.9440, 7.0789),
    "kuje": (8.8776, 7.2272),
    "bwari": (9.2057, 7.3811),

    # Lagos
    "lagos": (6.4541, 3.3947),
    "ikeja": (6.5958, 3.3414),
    "lekki": (6.4281, 3.5852),
    "ajah": (6.4673, 3.5875),
    "victoria island": (6.4281, 3.4219),
    "surulere": (6.5059, 3.3540),
    "yaba": (6.5164, 3.3754),
    "apapa": (6.4480, 3.3600),
    "badagry": (6.4161, 2.8876),
    "ikorodu": (6.6194, 3.5091),
    "alimosho": (6.6086, 3.2669),
    "mushin": (6.5270, 3.3557),
    "oshodi": (6.5567, 3.3352),
    "isale eko": (6.4545, 3.3885),
    "agege": (6.6219, 3.3218),
    "epe": (6.5862, 3.9812),
    "kosofe": (6.5697, 3.3907),

    # Kano
    "kano": (12.0022, 8.5920),
    "wudil": (11.7897, 8.8442),
    "gwarzo": (12.0292, 7.9672),

    # Rivers
    "port harcourt": (4.8156, 7.0498),
    "obio": (4.8153, 6.9952),
    "bonny": (4.4418, 7.1504),

    # Anambra
    "awka": (6.2104, 7.0723),
    "onitsha": (6.1429, 6.7867),
    "nnewi": (6.0158, 6.9255),

    # Enugu
    "enugu": (6.4584, 7.5464),
    "nsukka": (6.8571, 7.3958),
    "agbani": (6.3230, 7.5028),

    # Delta
    "asaba": (6.1998, 6.7354),
    "warri": (5.5167, 5.7500),
    "ughelli": (5.5000, 5.9833),
    "sapele": (5.9000, 5.6833),

    # Ogun
    "abeokuta": (7.1557, 3.3451),
    "sagamu": (6.8377, 3.6366),
    "ijebu ode": (6.8183, 3.9200),

    # Oyo
    "ibadan": (7.3776, 3.9470),
    "ogbomosho": (8.1333, 4.2500),
    "oyo": (7.8522, 3.9333),

    # Ondo
    "akure": (7.2527, 5.1937),
    "ondo": (7.1000, 4.8333),
    "okitipupa": (6.5000, 4.7833),

    # Osun
    "osogbo": (7.7710, 4.5624),
    "ile-ife": (7.4667, 4.5667),
    "ilesa": (7.6167, 4.7333),

    # Ekiti
    "ado-ekiti": (7.6233, 5.2213),
    "ikere": (7.5015, 5.2341),

    # Kwara
    "ilorin": (8.4966, 4.5426),
    "offa": (8.1500, 4.7167),

    # Kogi
    "lokoja": (7.7967, 6.7333),
    "okene": (7.5500, 6.2333),

    # Niger
    "minna": (9.6139, 6.5569),
    "bida": (9.0833, 6.0167),
    "kontagora": (10.4000, 5.4667),

    # Sokoto
    "sokoto": (13.0059, 5.2476),
    "wurno": (13.2833, 5.4167),

    # Kebbi
    "birnin kebbi": (12.4544, 4.2006),
    "argungu": (12.7500, 4.5167),

    # Zamfara
    "gusau": (12.1704, 6.6642),

    # Kaduna
    "kaduna": (10.5105, 7.4165),
    "zaria": (11.0667, 7.7000),

    # Katsina
    "katsina": (12.9899, 7.6006),
    "daura": (13.0422, 8.3258),

    # Jigawa
    "dutse": (11.7597, 9.3447),
    "hadejia": (12.4500, 10.0333),

    # Yobe
    "damaturu": (11.7470, 11.9610),
    "potiskum": (11.7103, 11.0700),

    # Borno
    "maiduguri": (11.8311, 13.1512),
    "biu": (10.6100, 12.2000),

    # Adamawa
    "yola": (9.2035, 12.4954),
    "mubi": (10.2658, 13.2717),

    # Taraba
    "jalingo": (8.9100, 11.3736),

    # Gombe
    "gombe": (10.2789, 11.1670),

    # Bauchi
    "bauchi": (10.3133, 9.8436),
    "azare": (11.6789, 10.1881),

    # Plateau
    "jos": (9.8965, 8.8583),
    "shendam": (8.8833, 9.5333),

    # Nasarawa
    "lafia": (8.4933, 8.5236),
    "keffi": (8.8475, 7.8736),

    # Benue
    "makurdi": (7.7316, 8.5338),
    "gboko": (7.3203, 8.9972),

    # Cross River
    "calabar": (4.9517, 8.3220),
    "ikom": (5.9667, 8.7167),

    # Akwa Ibom
    "uyo": (5.0377, 7.9128),
    "eket": (4.6501, 7.9255),

    # Bayelsa
    "yenagoa": (4.9247, 6.2642),

    # Edo
    "benin city": (6.3350, 5.6037),
    "auchi": (7.0667, 6.2667),

    # Abia
    "umuahia": (5.5243, 7.4892),
    "aba": (5.1066, 7.3667),

    # Imo
    "owerri": (5.4836, 7.0333),
    "orlu": (5.7897, 7.0351),

    # Ebonyi
    "abakaliki": (6.3249, 8.1137),
    "afikpo": (5.8867, 7.9334),
}

# State centroids — fallback when vendor's city is not found but state is known
STATE_CENTROIDS = {
    "Abia": (5.4527, 7.5248),
    "Adamawa": (9.3265, 12.3984),
    "Akwa Ibom": (5.0077, 7.8497),
    "Anambra": (6.2209, 6.9370),
    "Bauchi": (10.7764, 9.9999),
    "Bayelsa": (4.7719, 6.0699),
    "Benue": (7.3369, 8.7400),
    "Borno": (11.8846, 13.1520),
    "Cross River": (5.8702, 8.5988),
    "Delta": (5.7040, 5.9339),
    "Ebonyi": (6.2649, 8.0137),
    "Edo": (6.5438, 5.8987),
    "Ekiti": (7.7190, 5.3110),
    "Enugu": (6.5338, 7.4356),
    "FCT": (9.0579, 7.4951),
    "Abuja": (9.0579, 7.4951),
    "Gombe": (10.3636, 11.1889),
    "Imo": (5.5720, 7.0588),
    "Jigawa": (12.2281, 9.5616),
    "Kaduna": (10.3764, 7.7095),
    "Kano": (12.0022, 8.5920),
    "Katsina": (12.3799, 7.6309),
    "Kebbi": (11.4942, 4.2333),
    "Kogi": (7.8000, 6.7400),
    "Kwara": (8.9669, 4.5874),
    "Lagos": (6.4541, 3.3947),
    "Nasarawa": (8.4966, 8.2086),
    "Niger": (9.9309, 5.5983),
    "Ogun": (7.1602, 3.3492),
    "Ondo": (7.2508, 5.0000),
    "Osun": (7.5629, 4.5200),
    "Oyo": (8.1574, 3.6149),
    "Plateau": (9.2182, 9.5179),
    "Rivers": (5.0000, 6.8000),
    "Sokoto": (13.0059, 5.2476),
    "Taraba": (7.9993, 10.7741),
    "Yobe": (12.2939, 11.4390),
    "Zamfara": (12.1704, 6.6642),
}


def lookup_city(city_name: str):
    """
    Resolve a Nigerian city name to (lat, lon).
    Returns None if not found.
    Case-insensitive, strips whitespace.
    """
    if not city_name:
        return None
    key = city_name.strip().lower()
    return NIGERIA_CITIES.get(key)


def lookup_state_centroid(state_name: str):
    """
    Return state centroid (lat, lon) for a Nigerian state name.
    Tries exact match then case-insensitive.
    Returns None if not found.
    """
    if not state_name:
        return None
    coords = STATE_CENTROIDS.get(state_name)
    if coords:
        return coords
    key = state_name.strip().title()
    return STATE_CENTROIDS.get(key)


def suggest_cities(partial: str, limit: int = 8):
    """
    Return up to `limit` city names that start with `partial` (case-insensitive).
    Used by the AJAX city-lookup API.
    """
    if not partial or len(partial) < 2:
        return []
    term = partial.strip().lower()
    results = []
    for name, coords in NIGERIA_CITIES.items():
        if name.startswith(term):
            results.append({
                "city": name.title(),
                "lat": coords[0],
                "lon": coords[1],
            })
        if len(results) >= limit:
            break
    return results
