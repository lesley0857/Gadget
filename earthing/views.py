from django.shortcuts import render
from catalog.models import ProductListing
from .models import FieldEarthingDesign
from .services.engine import design
def calculator(request):
 values=request.POST.dict() if request.method=="POST" else {}; result=design(values) if values else None
 if result:
  result["products"]=ProductListing.objects.filter(is_active=True,name__iregex=r"earth|copper|bentonite|clamp|chamber|charcoal")[:20]
  if request.user.is_authenticated: FieldEarthingDesign.objects.create(user=request.user,project_name=values.get("project_name","Earthing Design"),installation_type=values.get("installation_type","residential"),inputs=values,result=result)
 return render(request,"earthing/calculator.html",{"values":values,"result":result})
