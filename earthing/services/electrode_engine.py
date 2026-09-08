def select(soil,installation):
 large=installation in ("industrial","transformer","substation","generator"); rods=soil["factor"]+(3 if large else 1); return {"count":rods,"length_ft":7 if soil["factor"]>=4 else 6,"spacing_m":3,"arrangement":"Grid/Ring" if large else ("Two-rod linear" if rods==2 else "Triangular")}
