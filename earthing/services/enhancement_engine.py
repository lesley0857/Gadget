def estimate(rods,ground):
 dry=ground=="dry"; wet=ground=="waterlogged"; b=rods*(30 if dry else 15 if wet else 25); return {"bentonite_kg":b,"charcoal_kg":round(b*.4,1),"water":"Not required" if wet else "Recommended" if dry else "Optional"}
