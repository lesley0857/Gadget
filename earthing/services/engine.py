from .soil_engine import assess
from .electrode_engine import select as electrodes
from .conductor_engine import select as conductor
from .enhancement_engine import estimate
from .warning_engine import warnings
def design(v):
 soil=assess(v.get("soil_type","unknown"),v.get("ground_condition","normal")); el=electrodes(soil,v.get("installation_type","residential")); co=conductor(v.get("installation_type"),v.get("rated_current"),v.get("equipment_distance"),el["count"]); en=estimate(el["count"],soil["ground"]); return {"method":"Practical Field-Based Earthing Estimate","soil_assumption":soil,"electrode":el,"conductor":co,"enhancement":en,"earth_mat":v.get("installation_type") in ("industrial","transformer","substation","generator"),"warnings":warnings(v.get("soil_type","unknown"),soil["ground"]),"disclaimer":"Engineering estimates based on visual soil classification and practical installation assumptions. Final earth resistance and performance must be verified on site using an approved earth resistance tester where required."}
