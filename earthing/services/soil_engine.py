ASSUMPTIONS={"loamy":{"conductivity":"moderate","factor":2},"clay":{"conductivity":"good","factor":2},"dry_sandy":{"conductivity":"poor","factor":4},"sandy":{"conductivity":"limited","factor":3},"rocky":{"conductivity":"uncertain","factor":4},"laterite":{"conductivity":"limited","factor":3},"unknown":{"conductivity":"unknown","factor":3}}
def assess(soil,ground):
 a=ASSUMPTIONS.get(soil,ASSUMPTIONS["unknown"]).copy(); a["ground"]=ground; a["factor"]=max(1,a["factor"]-1) if ground in ("wet","waterlogged") else a["factor"]; return a
