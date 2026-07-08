# solar/services/serializer_engine.py

from decimal import Decimal


def make_json_safe(data):

    if isinstance(data, dict):

        return {
            k: make_json_safe(v)
            for k, v in data.items()
        }

    if isinstance(data, list):

        return [
            make_json_safe(i)
            for i in data
        ]

    if isinstance(data, Decimal):

        return float(data)

    if hasattr(data, "_meta"):

        return str(data)

    return data