# solar/services/recommendation_engine.py

def build_recommendations(*systems):

    recommendations = []

    for system in systems:

        if not isinstance(system, dict):
            continue

        if system.get("success"):
            continue

        recommendations.append({

            "message":
                system.get(
                    "message",
                    "Product not found"
                ),

            "required":
                system.get(
                    "required"
                ),

            "closest":
                system.get(
                    "closest"
                ),
        })

    return recommendations