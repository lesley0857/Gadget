def select(installation,current,distance,rods):
 large=installation in ("industrial","transformer","substation","generator"); size=35 if large else (16 if current else 10); return {"size_mm2":size,"type":"Bare copper","length_m":round((float(distance or 10)+(rods-1)*3)*1.1,1)}
