def warnings(soil,ground):
 w=[]
 if soil in ("dry_sandy","rocky","unknown"): w.append("Difficult or uncertain ground: consider deeper/additional electrodes and mandatory post-installation testing.")
 if ground=="waterlogged": w.append("Waterlogged ground can increase corrosion risk; select suitable electrode material and do not add water unnecessarily.")
 return w
